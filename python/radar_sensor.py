#!/usr/bin/env python3
"""radar_sensor -- own-ship navigation radar feed (sensor.v1 ``radar.contacts[]``).

Reusable, stdlib-only mirror of the C++ ``USensorBundleComponent::BuildSensorsJson``
radar block (WP-20260702, Sensor Suite Roadmap Pt 1). Given own-ship's pose + speed +
heading and the scripted traffic contacts the pawn is driving (``state.v1 traffic[]``
-> ``FNaviSenseTrafficTarget``), it produces the radar picture own-ship reports on
``sensor.v1``: an ANONYMOUS blip per in-range contact -- receiver-computed **range** +
**true/relative bearing** (same geometry as the AIS block) PLUS a **radial (range-rate)
speed** from own + target velocity, and a **closing** flag. Unlike AIS a radar return
carries NO identity (no mmsi/name).

Convention (identical to ``python/ais_traffic`` and the C++): wire frame
``x=East, z=North`` (m); compass bearing ``0=N, 90=E``; relative bearing
``+ve = own starboard``. Radial speed sign: ``+ve = opening`` (range increasing),
so ``closing = radialSpeedKn < 0``. Deterministic -> replays bit-for-bit.

HONESTY (KI-019 / KI-027 family): this is a GEOMETRIC radar model derived from the
known scripted-contact set -- it is NOT an EM-propagation / RCS radar simulation.
There is no beam physics, sea clutter, shadowing, or false-positive model in this
first pass. Contacts beyond ``max_range_m`` are simply not reported. Label it
"geometric radar (derived contacts)", never "radar simulation".
"""
from __future__ import annotations
import math
from typing import Dict, List

# Max detection range default: 12 NM (marine navigation radar typical). Mirrors the
# SBC UPROPERTY RadarMaxRangeM = 22224.f; verify_20260702 asserts they match.
DEFAULT_MAX_RANGE_M = 22224.0            # 12 * 1852 m
SWEEP_DEG = 360.0                        # marine radar rotates a full circle
_KN_PER_MPS = 1.943844
_MPS_PER_KN = 0.5144444


def _wrap360(d: float) -> float:
    return d % 360.0


def _wrap180(d: float) -> float:
    x = (d + 180.0) % 360.0 - 180.0
    return 180.0 if x == -180.0 else x


def radar_contact(own_e: float, own_n: float, own_heading_deg: float,
                  own_speed_mps: float, tgt: Dict[str, object]) -> Dict[str, object]:
    """One ``sensor.v1 radar.contacts[]`` blip from own pose/speed/heading + one wire
    traffic contact ``tgt`` (keys: ``x`` East m, ``z`` North m, ``cogDeg``, ``sogKn``).
    Returns keys ``{rangeM, trueBearingDeg, relBearingDeg, radialSpeedKn, closing}``
    -- deliberately NO identity (mmsi/name); a radar blip is anonymous."""
    t_e = float(tgt["x"])
    t_n = float(tgt["z"])
    d_e = t_e - own_e
    d_n = t_n - own_n
    rng = math.hypot(d_e, d_n)
    true_brg = _wrap360(math.degrees(math.atan2(d_e, d_n)))          # 0=N, 90=E
    rel_brg = _wrap180(true_brg - own_heading_deg)                   # +ve starboard
    own_hdg = math.radians(own_heading_deg)
    own_ve = own_speed_mps * math.sin(own_hdg)
    own_vn = own_speed_mps * math.cos(own_hdg)
    sog_mps = float(tgt.get("sogKn", 0.0)) * _MPS_PER_KN
    cog = math.radians(float(tgt.get("cogDeg", 0.0)))
    tgt_ve = sog_mps * math.sin(cog)
    tgt_vn = sog_mps * math.cos(cog)
    radial_mps = 0.0                                                 # +ve = opening
    if rng > 1e-6:
        radial_mps = ((tgt_ve - own_ve) * d_e + (tgt_vn - own_vn) * d_n) / rng
    return {
        "rangeM": rng,
        "trueBearingDeg": true_brg,
        "relBearingDeg": rel_brg,
        "radialSpeedKn": radial_mps * _KN_PER_MPS,
        "closing": radial_mps < 0.0,
    }


def build_radar(own_e: float, own_n: float, own_heading_deg: float,
                own_speed_mps: float, wire_targets: List[Dict[str, object]],
                max_range_m: float = DEFAULT_MAX_RANGE_M) -> Dict[str, object]:
    """The full ``sensor.v1 radar`` block for one instant:
    ``{maxRangeM, sweepDeg, contacts[]}``. Contacts beyond ``max_range_m`` are
    dropped (out of range -> no blip). Empty / none-in-range -> ``contacts: []``."""
    contacts: List[Dict[str, object]] = []
    for t in wire_targets:
        c = radar_contact(own_e, own_n, own_heading_deg, own_speed_mps, t)
        if c["rangeM"] > max_range_m:
            continue                                                # out of range
        contacts.append(c)
    return {"maxRangeM": float(max_range_m), "sweepDeg": SWEEP_DEG, "contacts": contacts}
