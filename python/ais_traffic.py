"""Scripted AIS traffic + CPA/TCPA + COLREGS encounter geometry (WP-15 / gate D4).

WHY THIS EXISTS
    Demo gate **D4** wants the AIS block to carry >=1 scripted traffic target with
    the *correct range/bearing from own-ship*. Beyond the demo, CPA (closest point
    of approach) / TCPA (time to CPA) and the COLREGS encounter type are the
    literature-standard V&V metrics the week 5-6 "COLREGS scoring" differentiator
    is built on (Master Execution Plan section 5.1). This module is that seed: a
    deterministic, dependency-free traffic generator + the encounter geometry.

    Pure math + data. It does NOT change the wire/DTO/schema and needs no recompile:
    own-ship truth is read from the existing run log (state.csv) by ``analyse_ais``,
    and the targets are a closed-form function of sim-time, so the same numbers come
    out headless on a real run as would come out live. Rendering the targets as UE
    pawns + putting mmsi/cog/sog on sensor.v1 is a separate, later in-engine packet
    (WP-15B); this packet delivers + validates the *data/analysis* half of D4.

FRAME CONVENTIONS (match state.csv, the GPS sensor, and FNaviSenseCoords)
    * Horizontal plane: east = +x, north = +z  (Unity/UE ground plane).
    * Heading / COG: compass degrees, 0 = north (+z), 90 = east (+x), clockwise.
        velocity(heading H, speed S) = (S*sin H, S*cos H)  in (east, north).
    * lat/lon: the SAME linear WGS84 projection the GPS sensor uses
        lat = lat0 + north/111320 ; lon = lon0 + east/(111320*cos lat0)
      with the Monaco geo-origin (43.7350 N, 7.4250 E) so AIS targets and the
      own-ship GPS sit in one geodetic frame (verify_sensors_fidelity D7).

DETERMINISM
    Targets are constant-velocity (or piecewise-constant via legs), so cpa/tcpa is
    the exact analytic closed form and a preset replays bit-for-bit.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

# --- geodetic origin (shared with the GPS sensor / verify_sensors_fidelity) ----
GEO_LAT0_DEG = 43.7350
GEO_LON0_DEG = 7.4250
M_PER_DEG_LAT = 111320.0

# --- unit conversions ----------------------------------------------------------
KN_TO_MPS = 0.514444          # 1 knot
MPS_TO_KN = 1.0 / KN_TO_MPS
NM_TO_M = 1852.0
M_TO_NM = 1.0 / NM_TO_M

# --- COLREGS sector constants (degrees) ----------------------------------------
HEAD_ON_HALF_DEG = 13.0       # "nearly reciprocal", each near the other's bow
OVERTAKE_ABAFT_DEG = 112.5    # 22.5 deg abaft the beam (Rule 13)

# Default risk gate for "is this a real encounter": a CPA inside this range with a
# non-negative TCPA. ~1.5 cables; tunable per call.
DEFAULT_CPA_ALERT_M = 300.0
DEFAULT_TCPA_HORIZON_S = 600.0


# ------------------------------------------------------------------ angle helpers
def wrap180(deg: float) -> float:
    """Wrap an angle to (-180, 180]."""
    d = (deg + 180.0) % 360.0 - 180.0
    return 180.0 if d == -180.0 else d


def wrap360(deg: float) -> float:
    """Wrap an angle to [0, 360)."""
    return deg % 360.0


def compass_from_vec(east: float, north: float) -> float:
    """Compass heading [0,360) of the vector (east, north). 0=N, 90=E."""
    return wrap360(math.degrees(math.atan2(east, north)))


def vec_from_compass(heading_deg: float, speed: float = 1.0) -> Tuple[float, float]:
    """(east, north) components of a compass heading at the given speed."""
    h = math.radians(heading_deg)
    return (speed * math.sin(h), speed * math.cos(h))


def project_latlon(east_m: float, north_m: float,
                   lat0_deg: float = GEO_LAT0_DEG,
                   lon0_deg: float = GEO_LON0_DEG) -> Tuple[float, float]:
    """Local east/north metres -> (latDeg, lonDeg), same projection as the GPS sensor."""
    lat = lat0_deg + north_m / M_PER_DEG_LAT
    mpd_lon = M_PER_DEG_LAT * math.cos(math.radians(lat0_deg))
    lon = lon0_deg + (east_m / mpd_lon if mpd_lon > 1.0 else 0.0)
    return (lat, lon)


# ------------------------------------------------------------------ CPA / TCPA
def cpa_tcpa(oe: float, on: float, ove: float, ovn: float,
             te: float, tn: float, tve: float, tvn: float) -> Tuple[float, float]:
    """Closest Point of Approach distance (m) and Time to CPA (s) for two
    constant-velocity vessels.

    own at (oe,on) velocity (ove,ovn); target at (te,tn) velocity (tve,tvn).
    Relative position r = target - own; relative velocity v = target_vel - own_vel.
        tcpa = -(r . v) / (v . v)     (clamped to >= 0; a receding pair -> tcpa 0)
        cpa  = | r + v * tcpa |
    If closing speed is ~0 (parallel, same speed) tcpa=0 and cpa = current range.
    """
    rx, ry = te - oe, tn - on
    vx, vy = tve - ove, tvn - ovn
    vv = vx * vx + vy * vy
    if vv < 1e-12:
        return (math.hypot(rx, ry), 0.0)
    tcpa = -(rx * vx + ry * vy) / vv
    if tcpa < 0.0:
        tcpa = 0.0                      # already past CPA -> report current range
    cx = rx + vx * tcpa
    cy = ry + vy * tcpa
    return (math.hypot(cx, cy), tcpa)


def range_bearing(oe: float, on: float, te: float, tn: float) -> Tuple[float, float]:
    """Range (m) and TRUE compass bearing (deg) of target from own-ship."""
    de, dn = te - oe, tn - on
    return (math.hypot(de, dn), compass_from_vec(de, dn))


def relative_bearing(true_bearing_deg: float, own_heading_deg: float) -> float:
    """Bearing of the target relative to own-ship's bow, (-180,180].
    +ve = on own STARBOARD side, -ve = own PORT side."""
    return wrap180(true_bearing_deg - own_heading_deg)


def target_aspect(oe: float, on: float, te: float, tn: float,
                  target_heading_deg: float) -> float:
    """Own-ship's bearing relative to the TARGET's bow, (-180,180]. |aspect|~0 =>
    own-ship is dead ahead of the target; |aspect|~180 => own-ship astern of it."""
    _, bearing_to_own = range_bearing(te, tn, oe, on)
    return wrap180(bearing_to_own - target_heading_deg)


def is_closing(oe: float, on: float, ove: float, ovn: float,
               te: float, tn: float, tve: float, tvn: float) -> bool:
    """True if the range is currently decreasing (r . v < 0)."""
    rx, ry = te - oe, tn - on
    vx, vy = tve - ove, tvn - ovn
    return (rx * vx + ry * vy) < 0.0


# ------------------------------------------------------------------ COLREGS class
ENCOUNTER_TYPES = (
    "head_on", "crossing_give_way", "crossing_stand_on",
    "overtaking_give_way", "being_overtaken_stand_on", "no_risk",
)


def classify_encounter(rel_bearing_deg: float, aspect_deg: float,
                       closing: bool) -> str:
    """Classify a two-vessel encounter from own-ship's perspective (COLREGS 13-15).

    rel_bearing_deg : target bearing relative to own bow (+stbd / -port).
    aspect_deg      : own-ship's bearing relative to the target's bow.
    closing         : whether the range is currently decreasing.

    Returns one of ENCOUNTER_TYPES. The give-way / stand-on tag follows the Rules:
      * head_on (Rule 14): both vessels near each other's bow on reciprocal courses
        -> both give way (each alters to starboard). Tagged ``head_on``.
      * overtaking (Rule 13): a vessel approaching another from >22.5 deg abaft her
        beam is overtaking and must keep clear.
          - own-ship within the TARGET's stern arc (|aspect|>=112.5) -> WE overtake
            -> ``overtaking_give_way``.
          - target within OUR stern arc (|rel_bearing|>=112.5) -> we are being
            overtaken -> ``being_overtaken_stand_on``.
      * crossing (Rule 15): target on our starboard -> we give way; on our port ->
        we stand on.
    """
    if not closing:
        return "no_risk"
    rb = wrap180(rel_bearing_deg)
    asp = wrap180(aspect_deg)
    # Head-on: each sees the other near dead ahead, reciprocal headings.
    if abs(rb) <= HEAD_ON_HALF_DEG and abs(asp) <= HEAD_ON_HALF_DEG:
        return "head_on"
    # Overtaking: we approach the target from within its stern arc.
    if abs(asp) >= OVERTAKE_ABAFT_DEG:
        return "overtaking_give_way"
    # Being overtaken: the target approaches from within our stern arc.
    if abs(rb) >= OVERTAKE_ABAFT_DEG:
        return "being_overtaken_stand_on"
    # Crossing: starboard => give way, port => stand on.
    if rb > 0.0:
        return "crossing_give_way"
    return "crossing_stand_on"


GIVE_WAY = {"head_on", "crossing_give_way", "overtaking_give_way"}
STAND_ON = {"crossing_stand_on", "being_overtaken_stand_on"}


def own_ship_duty(encounter: str) -> str:
    """'give_way', 'stand_on', or 'none' for an encounter type (own-ship's role)."""
    if encounter in GIVE_WAY:
        return "give_way"
    if encounter in STAND_ON:
        return "stand_on"
    return "none"


# ------------------------------------------------------------------ traffic model
@dataclass(frozen=True)
class AISTarget:
    """A scripted AIS contact. Motion is piecewise-constant velocity.

    Position is held in WORLD east/north metres (same frame as state.csv x/z). For
    presets that place a target relative to own-ship, ``make_field`` fills e0/n0/cog
    from the own-ship start pose; a target authored in absolute world coords sets
    them directly.
    """
    mmsi: int
    name: str
    ship_type: str
    e0: float                       # initial east (m)
    n0: float                       # initial north (m)
    cog_deg: float                  # course over ground (compass)
    sog_mps: float                  # speed over ground (m/s)
    length_m: float = 25.0
    beam_m: float = 8.0
    legs: Tuple[Tuple[float, float, float], ...] = ()  # (duration_s, cog_deg, sog_mps)*

    def state_at(self, t: float) -> Dict[str, float]:
        """Dead-reckoned state at sim-time ``t`` (>=0). Honours ``legs`` if present
        (each leg overrides cog/sog for its duration; after the last leg the final
        leg's cog/sog continue)."""
        e, n = self.e0, self.n0
        cog, sog = self.cog_deg, self.sog_mps
        remaining = max(0.0, t)
        for dur, leg_cog, leg_sog in self.legs:
            cog, sog = leg_cog, leg_sog
            step = min(remaining, dur)
            ve, vn = vec_from_compass(cog, sog)
            e += ve * step
            n += vn * step
            remaining -= step
            if remaining <= 0.0:
                break
        if remaining > 0.0:
            ve, vn = vec_from_compass(cog, sog)
            e += ve * remaining
            n += vn * remaining
        lat, lon = project_latlon(e, n)
        return {"mmsi": self.mmsi, "name": self.name, "ship_type": self.ship_type,
                "e": e, "n": n, "cog_deg": wrap360(cog), "sog_mps": sog,
                "lat": lat, "lon": lon, "length_m": self.length_m, "beam_m": self.beam_m}

    def velocity_at(self, t: float) -> Tuple[float, float]:
        """(east, north) velocity at ``t`` (honours legs)."""
        cog, sog = self.cog_deg, self.sog_mps
        remaining = max(0.0, t)
        for dur, leg_cog, leg_sog in self.legs:
            cog, sog = leg_cog, leg_sog
            if remaining <= dur:
                break
            remaining -= dur
        return vec_from_compass(cog, sog)


@dataclass
class AISTrafficField:
    """A set of scripted AIS targets sharing the run's sim clock."""
    targets: List[AISTarget] = field(default_factory=list)
    preset: Optional[str] = None

    def state_at(self, t: float) -> List[Dict[str, float]]:
        return [tg.state_at(t) for tg in self.targets]

    def __len__(self) -> int:
        return len(self.targets)


def encode_position_report(state: Dict[str, float], t: float) -> Dict[str, object]:
    """An AIS-style position report (Type-18 flavour) for one target state.
    This is the shape a future sensor.v1 ``ais.targets[]`` entry would carry."""
    return {
        "mmsi": int(state["mmsi"]),
        "name": state["name"],
        "shipType": state["ship_type"],
        "latDeg": round(state["lat"], 7),
        "lonDeg": round(state["lon"], 7),
        "cogDeg": round(state["cog_deg"], 2),
        "sogKn": round(state["sog_mps"] * MPS_TO_KN, 2),
        "trueHeadingDeg": round(state["cog_deg"], 1),
        "navStatus": "under_way_using_engine",
        "t": round(t, 3),
    }


# ------------------------------------------------------------------ encounter calc
@dataclass
class EncounterSnapshot:
    mmsi: int
    name: str
    ship_type: str
    t: float
    range_m: float
    true_bearing_deg: float
    rel_bearing_deg: float
    aspect_deg: float
    cpa_m: float
    tcpa_s: float
    closing: bool
    encounter: str
    duty: str


def encounter_snapshot(t: float,
                       oe: float, on: float, ove: float, ovn: float,
                       tgt_state: Dict[str, float],
                       tve: float, tvn: float) -> EncounterSnapshot:
    """All per-target geometry at one instant, given own + target kinematics.
    own heading is taken as own COG (atan2 of own velocity) when moving."""
    te, tn = tgt_state["e"], tgt_state["n"]
    own_cog = compass_from_vec(ove, ovn) if (ove * ove + ovn * ovn) > 1e-6 else 0.0
    rng, tb = range_bearing(oe, on, te, tn)
    rb = relative_bearing(tb, own_cog)
    asp = target_aspect(oe, on, te, tn, tgt_state["cog_deg"])
    cpa, tcpa = cpa_tcpa(oe, on, ove, ovn, te, tn, tve, tvn)
    closing = is_closing(oe, on, ove, ovn, te, tn, tve, tvn)
    enc = classify_encounter(rb, asp, closing)
    return EncounterSnapshot(
        mmsi=int(tgt_state["mmsi"]), name=tgt_state["name"], ship_type=tgt_state["ship_type"],
        t=t, range_m=rng, true_bearing_deg=tb, rel_bearing_deg=rb, aspect_deg=asp,
        cpa_m=cpa, tcpa_s=tcpa, closing=closing, encounter=enc, duty=own_ship_duty(enc))


# ------------------------------------------------------------------ preset library
# DEFAULT COLREGS TARGET (WP-20260709B): ALL four colregs presets target the
# SAME default ship -- marine_rescue_boat (it imported world-aligned, needs no
# roll correction). Swap ships per run with the listener's --target-name (the
# editor picker passes it automatically from its TARGET_SHIP setting).
DEFAULT_COLREGS_TARGET = "marine_rescue_boat"
SHIP_TYPES = {  # Outliner label -> AIS ship type (used when --target-name swaps)
    "marine_rescue_boat": "rescue",
    "excursion_vessel": "passenger",
    "Yacht_with_interior": "yacht",
}

# NAMING RULE (WP-20260709): presets that are RENDERED in-engine use the EXACT
# Outliner labels of the placed Traffic ships (excursion_vessel /
# marine_rescue_boat / Yacht_with_interior), matched to the slot each preset
# drives (single-target presets -> the ship the COLREGS picker assigns as
# TrafficActors[0]; monaco_capture -> the tag-scan slot order, sorted by name).
# The legacy analysis-only presets (head_on/crossing/overtaking/harbor_mix)
# keep their fictional names -- they are never rendered by the picker workflow.
# A preset is authored RELATIVE to own-ship's start pose: each template gives the
# target's position as (ahead_m, starboard_m) in own-ship's initial body frame, a
# course relative to own heading, and a speed. ``make_field`` resolves them to world
# coords once the own-ship start pose is known (from the run log or a live run).
@dataclass(frozen=True)
class _Template:
    mmsi: int
    name: str
    ship_type: str
    ahead_m: float
    starboard_m: float
    rel_course_deg: float
    sog_mps: float
    length_m: float = 25.0
    beam_m: float = 8.0


_PRESETS: Dict[str, Tuple[str, Tuple[_Template, ...]]] = {
    "head_on": (
        "One vessel inbound on a near-reciprocal course, fine on the bow (Rule 14).",
        (_Template(211000001, "MERIDIAN", "cargo", 1600.0, 35.0, 180.0, 6.0, 90.0, 14.0),),
    ),
    "crossing": (
        "A ferry crossing left-to-right from own starboard bow (Rule 15 give-way).",
        (_Template(227000002, "AZURFERRY", "passenger", 1100.0, 850.0, 250.0, 6.5, 70.0, 12.0),),
    ),
    "overtaking": (
        "Own-ship overtakes a slow vessel close ahead on the same course (Rule 13).",
        (_Template(232000003, "SLOWBELLE", "fishing", 480.0, 10.0, 0.0, 1.8, 22.0, 7.0),),
    ),
    "crossing_standon": (
        "A vessel crossing left-to-right from own PORT bow (Rule 17: own-ship is "
        "the STAND-ON vessel and must hold course/speed; the target is give-way).",
        (_Template(228000004, "marine_rescue_boat", "rescue", 750.0, -550.0, 105.0, 5.0, 70.0, 12.0),),
    ),
    # WP-20260703: dedicated single-target geometries tuned for the SCRIPTED-avoidance
    # own-ship (colregs_* scenarios). Kept separate from head_on/crossing/overtaking so
    # the transit-own-ship scenarios + their verifies are unchanged.
    "head_on_avoid": (
        "Head-on target fine on the PORT bow (reciprocal) so own-ship's starboard "
        "alteration opens a clean port-to-port pass (Rule 14).",
        (_Template(211000001, "marine_rescue_boat", "rescue", 500.0, -30.0, 180.0, 1.2, 90.0, 14.0),)  # 14 Jul camera staging: 800 m start + slow target (2 m/s) + later/deeper turn (t=40 s, 40 deg)  # keeps miss >= 200 m (selftest-proved); naive 900 m @ 6 m/s scored 85 m and was rejected,
    ),
    "crossing_avoid": (
        "Target crossing from the STARBOARD bow on a collision bearing (Rule 15 "
        "give-way): own-ship alters starboard to pass astern.",
        (_Template(227000002, "marine_rescue_boat", "rescue", 350.0, 630.0, 280.0, 3.5, 70.0, 12.0),)  # 14 Jul camera staging: 720 m start, 3.5 m/s (was 1030 m, 5 m/s); compliance selftest-proved,
    ),
    "overtaking_avoid": (
        "Slow target close ahead, offset to PORT (Rule 13): own-ship overtakes and "
        "alters starboard to keep clear.",
        (_Template(232000003, "marine_rescue_boat", "rescue", 350.0, -80.0, 0.0, 0.8, 22.0, 7.0),),
    ),
    "harbor_mix": (
        "Mixed Port-Hercule approach: a crossing ferry, a slow vessel ahead, and a "
        "head-on inbound cargo (three AIS contacts).",
        (
            _Template(227000002, "AZURFERRY", "passenger", 1100.0, 850.0, 250.0, 6.5, 70.0, 12.0),
            _Template(232000003, "SLOWBELLE", "fishing", 480.0, 12.0, 0.0, 1.8, 22.0, 7.0),
            _Template(211000001, "MERIDIAN", "cargo", 1700.0, -40.0, 180.0, 6.0, 90.0, 14.0),
        ),
    ),
    "monaco_capture": (
        "WP-15B capture scene: own-ship transits north into THREE simultaneous "
        "encounters rendered by the placed Traffic ships -- a slow vessel close "
        "ahead to overtake (Rule 13), a ferry crossing from the starboard bow "
        "(Rule 15), and an inbound cargo fine on the bow head-on (Rule 14); own-ship "
        "is give-way to all three. Ranges stagger (450 / 950 / 1550 m) so each peaks "
        "in turn. Tune the (ahead_m, starboard_m, rel_course_deg, sog_mps) below to "
        "reframe the shot -- the rendered ships + the scored encounter both follow it.",
        (
            _Template(232000003, "excursion_vessel",    "passenger", 450.0,   15.0,   0.0, 1.8, 22.0,  7.0),
            _Template(227000002, "marine_rescue_boat",  "rescue",    950.0,  750.0, 255.0, 6.5, 70.0, 12.0),
            _Template(211000001, "Yacht_with_interior", "yacht",    1550.0,  -30.0, 180.0, 6.0, 90.0, 14.0),
        ),
    ),
}


def list_presets() -> List[str]:
    return sorted(_PRESETS)


def format_presets() -> str:
    lines = ["Available AIS traffic presets (use --ais <name>):", ""]
    for name in list_presets():
        desc, tmpls = _PRESETS[name]
        lines.append(f"  {name:12s} ({len(tmpls)} target{'s' if len(tmpls) != 1 else ''})  {desc}")
    return "\n".join(lines)


def make_field(preset: str,
               own_e0: float, own_n0: float, own_heading_deg: float,
               target_name: Optional[str] = None) -> AISTrafficField:
    """Build an AISTrafficField for ``preset`` placed relative to own-ship's start
    pose (east, north, compass heading). Raises KeyError on an unknown preset.

    ``target_name`` (WP-20260709B): swap the rendered ship for a SINGLE-TARGET
    preset -- the target takes this exact name (and its known ship type from
    SHIP_TYPES) so the wire/logs/evidence always name the actor that is actually
    driven. Raises ValueError on a multi-target preset (monaco_capture etc. have
    a fixed slot->ship mapping that a single name cannot describe).
    """
    key = (preset or "").strip()
    if key not in _PRESETS:
        raise KeyError(f"unknown AIS preset '{preset}'. Available: {', '.join(list_presets())}")
    _desc, templates = _PRESETS[key]
    if target_name:
        if len(templates) != 1:
            raise ValueError(
                f"--target-name only applies to single-target presets; '{key}' has "
                f"{len(templates)} targets (its slot->ship mapping is fixed)")
        import dataclasses as _dc
        tm = templates[0]
        templates = (_dc.replace(tm, name=target_name,
                                 ship_type=SHIP_TYPES.get(target_name, tm.ship_type)),)
    ahead = vec_from_compass(own_heading_deg, 1.0)              # unit ahead (e,n)
    stbd = vec_from_compass(own_heading_deg + 90.0, 1.0)       # unit starboard
    targets: List[AISTarget] = []
    for tm in templates:
        e0 = own_e0 + tm.ahead_m * ahead[0] + tm.starboard_m * stbd[0]
        n0 = own_n0 + tm.ahead_m * ahead[1] + tm.starboard_m * stbd[1]
        targets.append(AISTarget(
            mmsi=tm.mmsi, name=tm.name, ship_type=tm.ship_type,
            e0=e0, n0=n0, cog_deg=wrap360(own_heading_deg + tm.rel_course_deg),
            sog_mps=tm.sog_mps, length_m=tm.length_m, beam_m=tm.beam_m))
    return AISTrafficField(targets=targets, preset=key)


def wire_targets(field: "AISTrafficField", t: float) -> List[Dict[str, object]]:
    """Per-target wire poses (state.v1 'traffic' entries) at sim-time ``t``.

    Mirrors own-ship's wire frame EXACTLY (x=East, y=Up=0, z=North, yawDeg=cog),
    so UE applies the same NaviSenseCoords conversion + spawn anchor and the
    rendered ship lands where the scored target is. Deterministic
    (constant-velocity) => replays bit-for-bit; this is the only per-tick traffic
    work and it is pure arithmetic (no allocation beyond the small list)."""
    out: List[Dict[str, object]] = []
    for tg in field.targets:
        st = tg.state_at(t)
        out.append({
            "id": int(tg.mmsi),
            "name": tg.name,
            "x": round(st["e"], 3),       # East  (m) == wire x
            "y": 0.0,                     # Up    (m) -- horizontal plane
            "z": round(st["n"], 3),       # North (m) == wire z
            "yawDeg": round(st["cog_deg"], 2),
            "sogKn": round(st["sog_mps"] * MPS_TO_KN, 2),
            "cogDeg": round(st["cog_deg"], 2),
        })
    return out
