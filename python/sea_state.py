"""Deterministic sea-state wave field -- schema v1 rev 1.3 (heave).

WHY THIS EXISTS
    The NaviSense plant is 3-DOF on a flat plane (KI-008). WP-7 added a heel/trim
    *attitude* proxy (rev 1.2). This module adds the vertical half: a small,
    deterministic HEAVE (vertical bob) sampled from a parameterised sea-state wave
    field at the ship's horizontal position and sim time. It is shipped in
    state.v1 as ``heaveM`` and applied by the pawn as a Z offset, so the hull
    rises and falls on the swell (gate D2, "6-DOF water ride"). It also seeds gate
    D3, "sea states", because the sea-state index is the same knob D3 needs.

    It is a VISUAL PROXY, not hydrodynamic truth: the plant dynamics are untouched,
    so the IMO manoeuvring KPIs (turning circle, zig-zag) are unchanged. True
    radiation/diffraction sea-keeping is out of scope.

DETERMINISM (replayability)
    Surface elevation is a fixed sum of sinusoids whose phases and directions are
    seeded ONCE at construction (never at sample time). Given (east, north, t) the
    field always returns the same value, so a logged run replays identically and
    plays nicely with WP-4's deterministic sim clock. No RNG is touched per sample.

SEA STATES (WMO sea-state code / Douglas scale, simplified to representative midpoints)
    Indexed 0..9 by significant wave height Hs (m) and a peak period Tp (s). SS0 is
    glassy: Hs = 0 => elevation identically 0 => byte-for-byte identical to rev 1.2
    (backward compatible). Higher states raise Hs and lengthen Tp. Heave is clamped
    (HEAVE_CLAMP_M) so the visual can never fling the hull off the deck even in SS9.

SIGN CONVENTION (wire frame; mirrored in NaviSenseCoords::WireHeaveToUE on the UE side)
    heave_m : + = UP (a wave crest lifts the hull; a trough drops it).
    Horizontal sample coords are (east, north) metres, matching the wire pose
    (x = East, z = North). To invert the bob, flip the sign in
    NaviSenseCoords::WireHeaveToUE -- never here, never per-call (invariant #1).

DELIBERATELY LEFT OUT (the natural F1 part-3)
    Wave SLOPE -> wave-induced roll/pitch coupling, and sampling the *rendered* UE
    water surface. ``slope_rad`` is provided for that future use but is NOT yet on
    the wire.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple

G = 9.80665  # gravitational acceleration, m/s^2 (deep-water dispersion)

# Per-sea-state (significant wave height Hs [m], peak period Tp [s]).
# Representative midpoints of the WMO sea-state code / Douglas sea scale.
SEA_STATES = {
    0: (0.0,   0.0),    # calm (glassy)      -- no heave
    1: (0.05,  2.5),    # calm (rippled)
    2: (0.3,   3.5),    # smooth (wavelets)
    3: (0.875, 4.5),    # slight
    4: (1.875, 6.5),    # moderate
    5: (3.25,  8.5),    # rough
    6: (5.0,  10.5),    # very rough
    7: (7.5,  12.5),    # high
    8: (11.5, 15.0),    # very high
    9: (16.0, 18.0),    # phenomenal
}

HEAVE_CLAMP_M  = 4.0     # hard limit on |heave| so the hull never detaches visually
N_COMPONENTS   = 7       # sinusoidal components summed to approximate the spectrum
DIR_SPREAD_DEG = 25.0    # +/- directional spread of components about the mean heading
# Period factors spread the components around Tp so the bob is not a pure sinusoid.
_PERIOD_FACTORS = [0.65, 0.8, 0.9, 1.0, 1.15, 1.35, 1.6]


def _clamp(x: float, lim: float) -> float:
    return lim if x > lim else (-lim if x < -lim else x)


def _pierson_moskowitz(omega: float, omega_p: float) -> float:
    """Unnormalised Pierson-Moskowitz spectral shape S(omega) (relative energy).

    S(w) proportional to w**-5 * exp(-1.25 * (w_p/w)**4). Only the *relative*
    weights across the discrete components are used, so the leading constant and
    units are irrelevant.
    """
    if omega <= 0.0:
        return 0.0
    return (omega ** -5.0) * math.exp(-1.25 * (omega_p / omega) ** 4.0)


@dataclass
class WaveField:
    """Deterministic directional wave field; sample with :meth:`elevation`.

    sea_state    integer 0..9 (clamped); selects (Hs, Tp). SS0 => no heave.
    heading_deg  mean direction the waves TRAVEL TOWARD, compass (0=N, 90=E).
    seed         seeds the per-component phases + directional spread (replayable).
    """
    sea_state: int = 0
    heading_deg: float = 0.0
    seed: int = 1337

    # Derived per-component arrays (built in __post_init__; never mutated after).
    hs: float = field(init=False, default=0.0)
    tp: float = field(init=False, default=0.0)
    _amp: List[float] = field(init=False, default_factory=list)
    _kx: List[float] = field(init=False, default_factory=list)
    _ky: List[float] = field(init=False, default_factory=list)
    _omega: List[float] = field(init=False, default_factory=list)
    _phase: List[float] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        ss = max(0, min(9, int(self.sea_state)))
        self.hs, self.tp = SEA_STATES[ss]
        if self.hs <= 0.0 or self.tp <= 0.0:
            return  # SS0: empty component set => elevation() == 0 everywhere

        rng = random.Random(self.seed)
        omega_p = 2.0 * math.pi / self.tp
        omegas = [2.0 * math.pi / (self.tp * pf) for pf in _PERIOD_FACTORS[:N_COMPONENTS]]
        raw = [_pierson_moskowitz(w, omega_p) for w in omegas]
        wsum = sum(raw) or 1.0
        m0 = (self.hs / 4.0) ** 2          # target variance: Hs = 4*sqrt(m0)
        for w, rw in zip(omegas, raw):
            e_i = m0 * (rw / wsum)          # energy share of this component
            a_i = math.sqrt(2.0 * e_i)     # var(a*cos) = a^2/2 = e_i
            k = w * w / G                  # deep-water dispersion: w^2 = g k
            theta = math.radians(self.heading_deg
                                  + rng.uniform(-DIR_SPREAD_DEG, DIR_SPREAD_DEG))
            self._amp.append(a_i)
            self._omega.append(w)
            self._kx.append(k * math.sin(theta))   # east component (compass frame)
            self._ky.append(k * math.cos(theta))   # north component
            self._phase.append(rng.uniform(0.0, 2.0 * math.pi))

    # --- queries --------------------------------------------------------------
    def elevation(self, east: float, north: float, t: float) -> float:
        """Surface elevation (m, +up) at horizontal (east, north) and time t."""
        s = 0.0
        for a, kx, ky, w, ph in zip(self._amp, self._kx, self._ky, self._omega, self._phase):
            s += a * math.cos(kx * east + ky * north - w * t + ph)
        return _clamp(s, HEAVE_CLAMP_M)

    def slope_rad(self, east: float, north: float, t: float) -> Tuple[float, float]:
        """(d_eta/d_east, d_eta/d_north) small-angle slopes [rad] -- reserved for a
        future wave-induced roll/pitch coupling (F1 part 3). NOT on the wire yet."""
        de = dn = 0.0
        for a, kx, ky, w, ph in zip(self._amp, self._kx, self._ky, self._omega, self._phase):
            phase = kx * east + ky * north - w * t + ph
            de += -a * kx * math.sin(phase)
            dn += -a * ky * math.sin(phase)
        return de, dn

    def significant_height(self) -> float:
        """Analytic Hs = 4*sqrt(m0), m0 = sum(a_i^2 / 2). == target Hs by construction."""
        m0 = sum(0.5 * a * a for a in self._amp)
        return 4.0 * math.sqrt(m0)

    @property
    def active(self) -> bool:
        return bool(self._amp)


def make_wave_field(sea_state: int = 0, heading_deg: float = 0.0, seed: int = 1337) -> WaveField:
    """Factory mirroring the listener's other make_* helpers."""
    return WaveField(sea_state=sea_state, heading_deg=heading_deg, seed=seed)


# ===========================================================================
# Runtime sea-state SCHEDULE -- schema v1 rev 1.5 (time-varying sea state)
# ===========================================================================
# WHY THIS EXISTS
#     Demo gate D3 wants >=3 sea states *switched at runtime* within a single run
#     and recorded in the log. A fixed WaveField cannot change Hs/Tp mid-run, and
#     hard-swapping fields would JUMP the surface elevation (visible vertical
#     jitter -- exactly what the G_UE8 "smooth" eye-check forbids).
#     ScheduledSeaState instead CROSS-FADES a small set of deterministic
#     WaveFields (one per distinct sea-state value in the schedule) with a
#     piecewise-linear weight, so elevation/slope stay CONTINUOUS in time and are
#     EXACT at every set-point. It DUCK-TYPES WaveField (.elevation / .slope_rad /
#     .active), so it drops into the listener interchangeably -- no DTO/wire change
#     (it still rides heaveM/rollDeg/pitchDeg), no recompile. It adds
#     .sea_state_at(t) / .hs_at(t) / .describe() so the listener can log the switch.
#
# DETERMINISM (replayability)
#     Every component WaveField is seeded ONCE at construction; the cross-fade
#     weight is a pure function of sim time. So a logged run replays identically and
#     composes with WP-4's deterministic sim clock. No RNG is touched per sample.


def parse_schedule(spec: str) -> List[Tuple[float, int]]:
    """Parse a sea-state schedule string into sorted ``(t_seconds, sea_state)``
    set-points.

    Format: comma- (or ``;``-) separated ``t:ss`` pairs, e.g. ``"0:1, 90:4, 180:6"``
    -- sim-seconds : sea-state (0..9). Whitespace is ignored; set-points are sorted
    ascending and a duplicate time keeps the last value. Raises ``ValueError`` on an
    empty/malformed spec or an out-of-range sea state."""
    if spec is None:
        raise ValueError("empty sea-state schedule")
    points: dict = {}
    for chunk in spec.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            raise ValueError(f"bad schedule term '{chunk}' (expected t:ss, e.g. 90:4)")
        t_str, ss_str = chunk.split(":", 1)
        t = float(t_str.strip())
        ss = int(ss_str.strip())
        if t < 0.0:
            raise ValueError(f"schedule time must be >= 0 (got {t})")
        if not (0 <= ss <= 9):
            raise ValueError(f"sea state must be 0..9 (got {ss})")
        points[t] = ss
    if not points:
        raise ValueError("empty sea-state schedule")
    return sorted(points.items())


@dataclass
class ScheduledSeaState:
    """Time-varying sea state: cross-fades per-state :class:`WaveField` objects
    along a schedule. Duck-types WaveField so the listener uses it interchangeably.

    set_points   sorted list of ``(t_seconds, sea_state_int)``.
    heading_deg  mean direction the waves travel TOWARD (compass; passed to each field).
    seed         seeds every component field's phases/directions (replayable).
    """
    set_points: List[Tuple[float, int]]
    heading_deg: float = 0.0
    seed: int = 1337

    _fields: dict = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        if not self.set_points:
            raise ValueError("ScheduledSeaState needs >= 1 set-point")
        norm: List[Tuple[float, int]] = []
        for _t, ss in sorted(self.set_points):
            ss = max(0, min(9, int(ss)))
            norm.append((float(_t), ss))
            if ss not in self._fields:
                self._fields[ss] = WaveField(sea_state=ss, heading_deg=self.heading_deg,
                                             seed=self.seed)
        self.set_points = norm

    # --- schedule lookup ------------------------------------------------------
    def _bracket(self, t: float) -> Tuple[int, int, float]:
        """Return ``(ss_lo, ss_hi, w)`` such that the value at ``t`` is
        ``(1-w)*field[ss_lo] + w*field[ss_hi]``. Held flat before the first and
        after the last set-point."""
        pts = self.set_points
        if t <= pts[0][0]:
            return pts[0][1], pts[0][1], 0.0
        if t >= pts[-1][0]:
            return pts[-1][1], pts[-1][1], 0.0
        for i in range(len(pts) - 1):
            t0, ss0 = pts[i]
            t1, ss1 = pts[i + 1]
            if t0 <= t < t1:
                w = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
                return ss0, ss1, w
        return pts[-1][1], pts[-1][1], 0.0

    # --- WaveField-compatible queries (cross-faded, continuous in t) ----------
    def elevation(self, east: float, north: float, t: float) -> float:
        lo, hi, w = self._bracket(t)
        if w <= 0.0 or lo == hi:
            return self._fields[lo].elevation(east, north, t)
        e_lo = self._fields[lo].elevation(east, north, t)
        e_hi = self._fields[hi].elevation(east, north, t)
        return _clamp((1.0 - w) * e_lo + w * e_hi, HEAVE_CLAMP_M)

    def slope_rad(self, east: float, north: float, t: float) -> Tuple[float, float]:
        lo, hi, w = self._bracket(t)
        if w <= 0.0 or lo == hi:
            return self._fields[lo].slope_rad(east, north, t)
        de0, dn0 = self._fields[lo].slope_rad(east, north, t)
        de1, dn1 = self._fields[hi].slope_rad(east, north, t)
        return ((1.0 - w) * de0 + w * de1, (1.0 - w) * dn0 + w * dn1)

    @property
    def active(self) -> bool:
        """Active if ANY scheduled state raises waves (SS0-only schedules stay
        byte-identical to calm)."""
        return any(f.active for f in self._fields.values())

    # --- logging helpers (gate D3: record the runtime switch) -----------------
    def sea_state_at(self, t: float) -> float:
        """Continuous (interpolated) sea-state index at sim time ``t`` -- for the
        run log / events. Round for an integer label."""
        lo, hi, w = self._bracket(t)
        return (1.0 - w) * lo + w * hi

    def hs_at(self, t: float) -> float:
        """Representative significant wave height (m) at ``t`` (linear blend of the
        bracketing states' Hs) -- a human-readable log label, not a spectral Hs."""
        lo, hi, w = self._bracket(t)
        return (1.0 - w) * self._fields[lo].hs + w * self._fields[hi].hs

    @property
    def start_state(self) -> int:
        return self.set_points[0][1]

    @property
    def max_state(self) -> int:
        return max(ss for _t, ss in self.set_points)

    def describe(self) -> str:
        return " -> ".join(f"SS{ss}@{t:g}s" for t, ss in self.set_points)


def make_scheduled_sea_state(spec: str, heading_deg: float = 0.0,
                             seed: int = 1337) -> ScheduledSeaState:
    """Factory mirroring :func:`make_wave_field`: build a ScheduledSeaState from a
    schedule string (see :func:`parse_schedule`)."""
    return ScheduledSeaState(set_points=parse_schedule(spec),
                             heading_deg=heading_deg, seed=seed)
