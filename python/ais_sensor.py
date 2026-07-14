#!/usr/bin/env python3
"""ais_sensor -- own-ship AIS receiver feed (sensor.v1 ``ais.targets[]``).

Reusable, stdlib-only mirror of the C++ ``USensorBundleComponent::BuildSensorsJson``
AIS block (WP-20260701B). Given own-ship's pose and the scripted traffic contacts
the pawn is driving (``state.v1 traffic[]`` -> ``FNaviSenseTrafficTarget``), it
produces the AIS *receiver* picture the own-ship reports on ``sensor.v1``:
identity (mmsi/name) + course/speed from the contact, plus receiver-computed
**range** + **true/relative bearing** from own-ship, and a lat/lon via the same
geodetic origin the GPS sensor uses.

Convention (identical to ``python/ais_traffic`` and the C++): wire frame
``x=East, z=North`` (m); compass bearing ``0=N, 90=E``; relative bearing
``+ve = own starboard``. Deterministic -> replays bit-for-bit.

This is the honest AIS *receiver* view (what own-ship observes), distinct from the
post-run CPA/TCPA/COLREGS *scoring* in ``analyse_ais`` / ``colregs_score``.
"""
from __future__ import annotations
import math
from typing import Dict, List

# Geodetic origin shared with the GPS sensor (RefLatDeg/RefLonDeg on the sim
# subsystem; verify_sensors_fidelity D7). Flat-earth projection -- a live
# CesiumGeoreference is the separate D4 item #3.
GEO_LAT0 = 43.7350
GEO_LON0 = 7.4250
_MPD_LAT = 111320.0                      # metres per degree latitude


def _wrap360(d: float) -> float:
    return d % 360.0


def _wrap180(d: float) -> float:
    x = (d + 180.0) % 360.0 - 180.0
    return 180.0 if x == -180.0 else x


def ais_target_record(own_e: float, own_n: float, own_heading_deg: float,
                      tgt: Dict[str, object],
                      lat0: float = GEO_LAT0, lon0: float = GEO_LON0) -> Dict[str, object]:
    """One ``sensor.v1 ais.targets[]`` record from own pose + one wire traffic
    contact ``tgt`` (keys: ``id`` mmsi, ``name``, ``x`` East m, ``z`` North m,
    ``cogDeg``, ``sogKn``)."""
    t_e = float(tgt["x"])
    t_n = float(tgt["z"])
    d_e = t_e - own_e
    d_n = t_n - own_n
    rng = math.hypot(d_e, d_n)
    true_brg = _wrap360(math.degrees(math.atan2(d_e, d_n)))          # 0=N, 90=E
    rel_brg = _wrap180(true_brg - own_heading_deg)                   # +ve starboard
    mpd_lon = _MPD_LAT * math.cos(math.radians(lat0))
    lat = lat0 + t_n / _MPD_LAT
    lon = lon0 + (t_e / mpd_lon if mpd_lon > 1.0 else 0.0)
    return {
        "mmsi": int(tgt["id"]),
        "name": tgt.get("name", ""),
        "rangeM": rng,
        "trueBearingDeg": true_brg,
        "relBearingDeg": rel_brg,
        "cogDeg": float(tgt.get("cogDeg", 0.0)),
        "sogKn": float(tgt.get("sogKn", 0.0)),
        "latDeg": lat,
        "lonDeg": lon,
    }


def build_ais_targets(own_e: float, own_n: float, own_heading_deg: float,
                      wire_targets: List[Dict[str, object]],
                      lat0: float = GEO_LAT0, lon0: float = GEO_LON0) -> List[Dict[str, object]]:
    """The full ``sensor.v1 ais.targets[]`` array for one instant. Empty in ->
    empty out (back-compat: no traffic renders exactly as before)."""
    return [ais_target_record(own_e, own_n, own_heading_deg, t, lat0, lon0)
            for t in wire_targets]
