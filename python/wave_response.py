"""Wave-induced roll/pitch coupling -- schema v1 rev 1.4 (wave-coupled attitude).

WHY THIS EXISTS
    WP-7 (rev 1.2) added a *maneuvering* heel/trim proxy (heel in turns, bow-up
    under accel; python/attitude_proxy.py). WP-8 (rev 1.3) added a vertical HEAVE
    sampled from a deterministic sea-state wave field (python/sea_state.py). The
    hull therefore bobs straight up and down on the swell but stays level on it.
    This module closes that gap: it reads the wave-field SLOPE already exposed by
    WaveField.slope_rad() and turns it into a small wave-induced ROLL and PITCH, so
    in a beam sea the hull rolls with the swell and in a head/following sea it
    pitches -- the "rides the water" half of demo gate D2.

    It rides the EXISTING wire fields rollDeg/pitchDeg (the listener ADDS this to
    the maneuvering attitude). NO new wire key, NO DTO change, NO recompile: the UE
    pawn already consumes rollDeg/pitchDeg via NaviSenseCoords::WireRollToUE /
    WirePitchToUE. It remains a VISUAL PROXY: the 3-DOF plant is untouched, so the
    IMO maneuvering KPIs are unchanged. True radiation/diffraction is out of scope.

    Sampling the *rendered* UE water surface (so the hull rides the actual water
    mesh, not this analytic twin) is still F1 part 3, engine-side.

DETERMINISM
    Pure function of (field, east, north, yaw, t). The field's phases/directions
    are seeded once at construction (sea_state.py), so this replays identically and
    composes with WP-4's deterministic sim clock. No RNG is touched per sample.

GEOMETRY / SIGN CONVENTIONS (wire frame; mirrored in NaviSenseCoords.h on UE side)
    Horizontal frame: x = East, z = North (matches the wire pose + sea_state.py).
    yaw_deg: compass heading, 0 = bow points NORTH, + = clockwise = turning to
             STARBOARD (matches attitude_proxy r-sign + the plant yaw).
        bow_hat  = (sin yaw, cos yaw)   in (East, North)
        stbd_hat = (cos yaw, -sin yaw)  (90 deg CW of the bow)
    grad eta = (de, dn) = WaveField.slope_rad(): local surface rise per metre East
               / North (small-angle radians, + = surface rising that way).
    The hull tends to lie parallel to the local water surface (raft-on-a-slope):
        pitchDeg : + = bow UP  => bow up when the surface rises toward the bow
                   pitch_rad =  + grad . bow_hat
        rollDeg  : + = starboard DOWN => stbd down when the surface is LOWER to
                   starboard  =>  roll_rad = - grad . stbd_hat
    To invert a rendered axis, flip the sign in NaviSenseCoords (WireRollToUE /
    WirePitchToUE) -- never here, never per-call (invariant #1).

    A FOLLOW_GAIN (<1) acknowledges a real hull only partially follows the wave
    slope (it filters short waves); clamps keep the deck out of the sea even in SS9.
    Keep this module dependency-free (duck-types field.slope_rad / field.active) so
    it unit-tests headlessly and imports into the listener with no side effects.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# --- Tunable gains (visual proxy; not fitted to towing-tank data) -------------
FOLLOW_GAIN     = 0.80   # fraction of the geometric wave slope the hull takes on
WAVE_ROLL_CLAMP_DEG  = 6.0   # max wave-induced heel (on top of maneuvering heel)
WAVE_PITCH_CLAMP_DEG = 4.0   # max wave-induced trim  (on top of maneuvering trim)


@dataclass(frozen=True)
class WaveAttitude:
    """Wave-induced visual attitude, degrees (wire sign convention)."""
    roll_deg: float
    pitch_deg: float


def _clamp(x: float, lim: float) -> float:
    return lim if x > lim else (-lim if x < -lim else x)


def wave_attitude_deg(
    field,                       # python.sea_state.WaveField | None (duck-typed)
    east: float,
    north: float,
    yaw_deg: float,
    t: float,
    *,
    follow_gain: float = FOLLOW_GAIN,
    roll_clamp: float = WAVE_ROLL_CLAMP_DEG,
    pitch_clamp: float = WAVE_PITCH_CLAMP_DEG,
) -> WaveAttitude:
    """Map the local wave-field slope -> (roll_deg, pitch_deg) the hull takes on.

    Returns (0, 0) when there is no field or the field is calm (SS0) -- so a
    rev<=1.3 sender / SS0 run is byte-identical (backward compatible).
    """
    if field is None or not getattr(field, "active", False):
        return WaveAttitude(0.0, 0.0)

    de, dn = field.slope_rad(east, north, t)   # d(eta)/dEast, d(eta)/dNorth (rad)

    y = math.radians(yaw_deg)
    sy, cy = math.sin(y), math.cos(y)
    # Body-frame projection of the surface gradient.
    slope_bow  = de * sy + dn * cy            # rise per metre toward the bow
    slope_stbd = de * cy - dn * sy            # rise per metre toward starboard

    pitch_deg = _clamp(math.degrees(follow_gain * slope_bow),  pitch_clamp)
    roll_deg  = _clamp(math.degrees(-follow_gain * slope_stbd), roll_clamp)
    return WaveAttitude(roll_deg=roll_deg, pitch_deg=pitch_deg)
