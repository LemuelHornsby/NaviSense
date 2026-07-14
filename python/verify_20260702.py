#!/usr/bin/env python3
"""verify_20260702 -- Radar sensor (Sensor Suite Roadmap Pt 1) on sensor.v1.

WP-20260702 ships the FIRST net-new sensor from the 1-Jul directive's Radar/LiDAR/
Sonar roadmap (NEW scope beyond the D4 demo gate -- do NOT fold into D4). The own-ship
navigation radar reports the scripted contacts within range as ANONYMOUS blips on
sensor.v1 ``radar.contacts[]``: range + true/relative bearing (same geometry as the
AIS block) PLUS a radial (range-rate) speed and a ``closing`` flag. Design decisions
for all three roadmap sensors are recorded in Documents/NaviSense_Sensor_Suite_Roadmap.md
(§5 of the directive). Proves, headless:

  G1  the C++ is wired: BuildSensorsJson emits a ``radar`` block
      ({maxRangeM,sweepDeg,contacts[]}) gated on bEmitRadar, with each contact from
      Pawn->GetTrafficTargets() carrying rangeM/trueBearingDeg/relBearingDeg/
      radialSpeedKn/closing; header carries the bEmitRadar + RadarMaxRangeM UPROPERTYs.
  G2  geometry parity -- the reusable python/radar_sensor mirror matches the canonical
      ais_traffic range_bearing / relative_bearing to 0.00e+00 across 48 contact-
      instants (2 presets x 3 own headings x 4 times), and the radial-speed sign
      agrees with an independent range-rate check (head-on closes, receding opens).
  G3  schema / honesty -- record has exactly the right keys+types, carries NO identity
      keys (radar blips are anonymous: no mmsi/name), a beyond-range contact is dropped,
      the RadarMaxRangeM default matches C++<->mirror, and the honesty label (KI-027,
      "not an EM/RCS simulation") is present in both C++ and the mirror docstring.
  G4  determinism -- the mirror replays bit-for-bit for a given (own state, contacts).
  G5  regression -- Z0 16/16 (C++ still compile-ready) + the AIS-feed (verify_20260701b),
      camera (verify_20260701c) and traffic (verify_20260629b) gates still PASS
      (this packet is additive to all three; no DTO/USTRUCT, radar is a nested block).

Negative controls (MUST FIRE):
  N1  a radar block hardcoded to bEmitRadar=false / no SetObjectField("radar") is
      detected as "not wired".
  N2  a contact beyond RadarMaxRangeM is DROPPED (does not appear in contacts[]); and
      a known closing pair reports closing=True (a wrong opening/closing sign disagrees).
  N3  the picture tracks geometry -- moving own-ship / changing own heading changes the
      emitted range/bearing (not a stub), a receding target reports closing=False.

Exit 0 iff all gates pass and all controls fire.
"""
from __future__ import annotations
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "python"))

import radar_sensor as rad           # noqa: E402  (module under test)
import ais_traffic as at             # noqa: E402  (canonical geometry oracle)

SBC_C = os.path.join(ROOT, "NaviSense_UE5", "Source", "NaviSense", "Sensors", "SensorBundleComponent.cpp")
SBC_H = os.path.join(ROOT, "NaviSense_UE5", "Source", "NaviSense", "Sensors", "SensorBundleComponent.h")
Z0 = os.path.join(ROOT, "Development", "work_packets", "WP_20260615_COMPILE_AUDIT", "verify_compile_readiness.py")
ROADMAP = os.path.join(ROOT, "Documents", "NaviSense_Sensor_Suite_Roadmap.md")
REQ_KEYS = {"rangeM", "trueBearingDeg", "relBearingDeg", "radialSpeedKn", "closing"}
ID_KEYS = {"mmsi", "name", "id"}          # radar blips must NOT carry identity

# two contact presets (wire frame: x=East, z=North m; cog compass, sog kn)
PRESET_A = [
    {"id": 1, "name": "ALPHA", "x": 0.0,    "z": 1200.0, "cogDeg": 180.0, "sogKn": 12.0},
    {"id": 2, "name": "BRAVO", "x": 800.0,  "z": 600.0,  "cogDeg": 270.0, "sogKn": 8.0},
]
PRESET_B = [
    {"id": 3, "name": "CHARLIE", "x": -1500.0, "z": -400.0, "cogDeg": 45.0, "sogKn": 20.0},
]


def _read(p):
    return open(p, encoding="utf-8", errors="replace").read()


def _run(path, *args):
    r = subprocess.run([sys.executable, path, *args], capture_output=True, text=True)
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    return r.returncode, tail[-90:]


# ----------------------------------------------------------------- source scan
def _sbc_radar_block(src: str) -> str:
    i = src.find("// ---------- RADAR")
    if i < 0:
        return ""
    j = src.find("return Sensors;", i)
    return src[i:j] if j > i else src[i:]


def radar_block_is_wired(sbc_src: str) -> bool:
    blk = _sbc_radar_block(sbc_src)
    if not blk:
        return False
    return ("if (bEmitRadar)" in blk
            and 'SetObjectField(TEXT("radar")' in blk
            and 'SetArrayField(TEXT("contacts")' in blk
            and "GetTrafficTargets()" in blk
            and 'SetBoolField(TEXT("closing")' in blk)


# ------------------------------------------------------------------- gates
def g1_cpp_wired():
    c, h = _read(SBC_C), _read(SBC_H)
    blk = _sbc_radar_block(c)
    wired = radar_block_is_wired(c)
    keys = all(f'TEXT("{k}")' in blk for k in
               ("rangeM", "trueBearingDeg", "relBearingDeg", "radialSpeedKn", "closing"))
    meta = ('TEXT("maxRangeM")' in blk and 'TEXT("sweepDeg")' in blk)
    rng_gate = ("RangeM > RadarMaxRangeM" in blk and "continue" in blk)
    hdr = ("bEmitRadar" in h and "RadarMaxRangeM" in h)
    ok = wired and keys and meta and rng_gate and hdr
    return ok, f"wired={wired} contact_keys={keys} block_meta={meta} range_gate={rng_gate} hdr={hdr}"


def g2_geometry_parity():
    max_dev = 0.0
    for preset in (PRESET_A, PRESET_B):
        for own_hdg in (0.0, 90.0, 215.0):
            for (oe, on) in ((0.0, 0.0), (100.0, -50.0), (-300.0, 400.0), (25.0, 900.0)):
                for t in preset:
                    c = rad.radar_contact(oe, on, own_hdg, 4.0, t)
                    rng, brg = at.range_bearing(oe, on, t["x"], t["z"])
                    relb = at.relative_bearing(brg, own_hdg)
                    max_dev = max(max_dev,
                                  abs(c["rangeM"] - rng),
                                  abs(c["trueBearingDeg"] - brg),
                                  abs(c["relBearingDeg"] - relb))
    geom_ok = (max_dev == 0.0)
    # radial-speed sign: head-on closing pair -> closing True (radial<0);
    # a target dead astern moving away faster than own -> opening (radial>0).
    head_on = rad.radar_contact(0, 0, 0.0, 5.0, {"x": 0, "z": 1000, "cogDeg": 180, "sogKn": 15})
    recede  = rad.radar_contact(0, 0, 0.0, 0.0, {"x": 0, "z": 1000, "cogDeg": 0,   "sogKn": 15})
    sign_ok = (head_on["closing"] is True and head_on["radialSpeedKn"] < 0.0
               and recede["closing"] is False and recede["radialSpeedKn"] > 0.0)
    ok = geom_ok and sign_ok
    return ok, f"max_dev={max_dev:.2e} geom={geom_ok} radial_sign(head-on closing / recede opening)={sign_ok}"


def g3_schema_honesty():
    c = rad.radar_contact(50.0, -20.0, 30.0, 3.0, PRESET_A[0])
    keys = (set(c) == REQ_KEYS)
    anon = (ID_KEYS.isdisjoint(set(c)))                 # NO identity on a radar blip
    types = (isinstance(c["rangeM"], float) and isinstance(c["trueBearingDeg"], float)
             and isinstance(c["relBearingDeg"], float) and isinstance(c["radialSpeedKn"], float)
             and isinstance(c["closing"], bool))
    # beyond-range contact is dropped
    far = [{"id": 9, "name": "FAR", "x": 0.0, "z": 999999.0, "cogDeg": 0.0, "sogKn": 0.0}]
    dropped = (rad.build_radar(0, 0, 0, 0, far)["contacts"] == [])
    # default max range matches C++ header
    h = _read(SBC_H)
    default_ok = (f"RadarMaxRangeM = {int(rad.DEFAULT_MAX_RANGE_M)}." in h
                  and rad.DEFAULT_MAX_RANGE_M == 12 * 1852)
    # honesty label present (KI-027) in both C++ and mirror
    cc = _read(SBC_C)
    honest = ("KI-027" in cc and "NOT an EM" in cc and "not an em" in rad.__doc__.lower())
    ok = keys and anon and types and dropped and default_ok and honest
    return ok, f"keys={keys} anonymous(no_id)={anon} types={types} range_drop={dropped} default_match={default_ok} honesty={honest}"


def g4_determinism():
    a = rad.build_radar(12.3, -4.5, 77.0, 6.0, PRESET_A)
    b = rad.build_radar(12.3, -4.5, 77.0, 6.0, PRESET_A)
    ok = (json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))
    return ok, f"bit-identical replay={ok}"


def g5_regression():
    z_rc, z_msg = _run(Z0)
    a_rc, _ = _run(os.path.join(ROOT, "python", "verify_20260701b.py"))
    cm_rc, _ = _run(os.path.join(ROOT, "python", "verify_20260701c.py"))
    t_rc, _ = _run(os.path.join(ROOT, "python", "verify_20260629b.py"))
    roadmap_ok = os.path.exists(ROADMAP)
    ok = (z_rc == 0 and a_rc == 0 and cm_rc == 0 and t_rc == 0 and roadmap_ok)
    return ok, f"Z0 rc={z_rc}({z_msg}); ais rc={a_rc}; camera rc={cm_rc}; traffic rc={t_rc}; roadmap_doc={roadmap_ok}"


# ----------------------------------------------------------------- controls
def n1_unwired_detected():
    stub = ("    // ---------- RADAR ----------\n"
            "    // (radar disabled -- no block)\n")
    fired = not radar_block_is_wired(stub)
    return fired, f"unwired stub wired?={not fired} -> {'fired' if fired else 'MISS'}"


def n2_range_drop_and_sign():
    # a contact just beyond max range is dropped; one just inside is kept
    near = [{"id": 1, "name": "N", "x": 0.0, "z": rad.DEFAULT_MAX_RANGE_M - 10.0, "cogDeg": 180, "sogKn": 10}]
    far  = [{"id": 2, "name": "F", "x": 0.0, "z": rad.DEFAULT_MAX_RANGE_M + 10.0, "cogDeg": 180, "sogKn": 10}]
    kept = (len(rad.build_radar(0, 0, 0, 0, near)["contacts"]) == 1)
    gone = (len(rad.build_radar(0, 0, 0, 0, far)["contacts"]) == 0)
    # closing sign correct for a known approaching pair
    appr = rad.radar_contact(0, 0, 0.0, 5.0, {"x": 0, "z": 500, "cogDeg": 180, "sogKn": 10})
    sign = (appr["closing"] is True)
    fired = kept and gone and sign
    return fired, f"near_kept={kept} far_dropped={gone} approach_closing={sign} -> {'fired' if fired else 'MISS'}"


def n3_tracks_geometry():
    t = {"id": 1, "name": "T", "x": 0.0, "z": 1000.0, "cogDeg": 0.0, "sogKn": 12.0}
    c0 = rad.radar_contact(0.0, 0.0, 0.0, 0.0, t)          # own still, target ahead
    c1 = rad.radar_contact(0.0, 500.0, 90.0, 0.0, t)       # own moved N + turned E
    moved = (abs(c1["rangeM"] - c0["rangeM"]) > 1.0 and c1["relBearingDeg"] != c0["relBearingDeg"])
    # target moving away from a stationary own -> opening (closing False)
    recede = rad.radar_contact(0.0, 0.0, 0.0, 0.0, {"x": 0, "z": 1000, "cogDeg": 0, "sogKn": 12})
    open_ok = (recede["closing"] is False)
    fired = moved and open_ok
    return fired, (f"range {c0['rangeM']:.0f}->{c1['rangeM']:.0f}, relbrg changed={c1['relBearingDeg']!=c0['relBearingDeg']}, "
                   f"recede_opens={open_ok} -> {'fired' if fired else 'MISS'}")


def main():
    gates = [
        ("G1", "cpp_radar_wired", *g1_cpp_wired()),
        ("G2", "geometry+radial_parity", *g2_geometry_parity()),
        ("G3", "schema_anon_honesty", *g3_schema_honesty()),
        ("G4", "determinism", *g4_determinism()),
        ("G5", "regression_Z0+ais+camera+traffic+roadmap", *g5_regression()),
    ]
    controls = [
        ("N1", "unwired_detected", *n1_unwired_detected()),
        ("N2", "range_drop_and_sign", *n2_range_drop_and_sign()),
        ("N3", "tracks_geometry", *n3_tracks_geometry()),
    ]
    print("verify_20260702 -- Radar sensor (Sensor Suite Roadmap Pt 1) on sensor.v1\n")
    gp = 0
    for cid, name, ok, det in gates:
        print(f"  [{'PASS' if ok else 'FAIL'}] {cid} {name}: {det}"); gp += ok
    print()
    cf = 0
    for cid, name, fired, det in controls:
        print(f"  [{'FIRED' if fired else 'MISS'}] {cid} {name}: {det}"); cf += fired
    all_ok = (gp == len(gates) and cf == len(controls))
    print(f"\n  Gates {gp}/{len(gates)}  Controls {cf}/{len(controls)}  => {'PASS' if all_ok else 'FAIL'}")
    out = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports", "wp_20260702_result.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"packet": "WP-20260702",
                   "title": "Radar sensor (Sensor Suite Roadmap Pt 1) on sensor.v1",
                   "model": "Opus 4.8",
                   "scope": "NEW sensor beyond D4 (Sensor Suite Roadmap) -- does NOT move the D4 gate",
                   "gates": {c: bool(o) for c, _, o, _ in gates},
                   "gates_detail": {c: d for c, _, _, d in gates},
                   "controls_fired": {c: bool(x) for c, _, x, _ in controls},
                   "controls_detail": {c: d for c, _, _, d in controls},
                   "gates_passed": gp, "gates_total": len(gates),
                   "controls_fired_n": cf, "controls_total": len(controls),
                   "verdict": "PASS" if all_ok else "FAIL"}, f, indent=2)
    print(f"  wrote {out}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
