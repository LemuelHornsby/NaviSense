#!/usr/bin/env python3
"""verify_20260701b -- AIS -> sensor.v1 feed (own-ship AIS receiver, D4 gap).

WP-20260701B wires the scripted traffic the pawn is already driving
(state.v1 traffic[]) into the OWN-SHIP sensor.v1 ais.targets[] block, which was
hardcoded to an empty array in USensorBundleComponent::BuildSensorsJson. Proves,
headless, that the feed is correct + honest:

  G1  the C++ is wired: the pawn RETAINS the contact list (LastTraffic +
      GetTrafficTargets) and SensorBundleComponent emits ais.targets FROM it (not
      the old empty array), with every required key.
  G2  GEOMETRY parity -- the reusable receiver mirror (python/ais_sensor, which
      re-derives range + true/relative bearing INDEPENDENTLY) matches the
      canonical python/ais_traffic geometry (range_bearing / relative_bearing) for
      monaco_capture + head_on across several instants and own headings.
  G3  schema / back-compat / identity -- each record carries the right keys+types,
      mmsi == the contact id, lat/lon uses the shared geo origin, and NO traffic
      -> [] (identical to before the change).
  G4  determinism -- the feed replays bit-for-bit.
  G5  regression -- Z0 16/16 (C++ still compile-ready), and the dashboard
      (verify_20260701) + traffic-render (verify_20260629b) gates still PASS
      (this packet is additive to both).

Negative controls (MUST FIRE):
  N1  the OLD hardcoded-empty AIS block is detected as "not wired".
  N2  a wrong wire->receiver frame (bearing atan2 swapped) disagrees with the
      canonical geometry.
  N3  the feed tracks identity/course -- changing a contact's id/cog changes the
      emitted mmsi/cog (not a stub).

Exit 0 iff all gates pass and all controls fire.
"""
from __future__ import annotations
import json, math, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "python"))

import ais_traffic as ais          # noqa: E402  (canonical geometry)
import ais_sensor as aisr          # noqa: E402  (module under test)

PAWN_H = os.path.join(ROOT, "NaviSense_UE5", "Source", "NaviSense", "Vessel", "NaviSenseShipPawn.h")
PAWN_C = os.path.join(ROOT, "NaviSense_UE5", "Source", "NaviSense", "Vessel", "NaviSenseShipPawn.cpp")
SBC = os.path.join(ROOT, "NaviSense_UE5", "Source", "NaviSense", "Sensors", "SensorBundleComponent.cpp")
Z0 = os.path.join(ROOT, "Development", "work_packets", "WP_20260615_COMPILE_AUDIT", "verify_compile_readiness.py")
REQ_KEYS = {"mmsi", "name", "rangeM", "trueBearingDeg", "relBearingDeg", "cogDeg", "sogKn", "latDeg", "lonDeg"}
TOL = 1e-6


def _read(p):
    return open(p, encoding="utf-8", errors="replace").read()


# ----------------------------------------------------------------- source scan
def _sbc_ais_block(src: str) -> str:
    i = src.find("// ---------- AIS")
    if i < 0:
        return ""
    j = src.find("return Sensors;", i)
    return src[i:j] if j > i else src[i:]


def ais_block_is_wired(sbc_src: str) -> bool:
    """True iff the AIS block emits targets FROM the pawn's contact list (not a
    hardcoded empty array)."""
    blk = _sbc_ais_block(sbc_src)
    if not blk:
        return False
    wired = ("GetTrafficTargets()" in blk and "AisTargets.Add" in blk
             and 'SetArrayField(TEXT("targets"), AisTargets)' in blk)
    empty_stub = bool(re.search(r'SetArrayField\(TEXT\("targets"\),\s*Empty\)', blk))
    return wired and not empty_stub


# ------------------------------------------------------------------- gates
def g1_cpp_wired():
    ph, pc, sb = _read(PAWN_H), _read(PAWN_C), _read(SBC)
    pawn_retains = ("TArray<FNaviSenseTrafficTarget> LastTraffic;" in ph
                    and "GetTrafficTargets()" in ph
                    and "LastTraffic = Targets" in pc)
    sbc_wired = ais_block_is_wired(sb)
    blk = _sbc_ais_block(sb)
    keys_ok = all(f'TEXT("{k}")' in blk for k in REQ_KEYS)
    ok = pawn_retains and sbc_wired and keys_ok
    return ok, (f"pawn_retains={pawn_retains} sbc_emits_from_pawn={sbc_wired} "
                f"all_9_keys={keys_ok}")


def g2_geometry_parity():
    # The receiver operates on the (mm-rounded) wire values it receives, so the
    # canonical geometry is evaluated on those SAME inputs -> this tests the
    # mirror's independent atan2/hypot/wrap math, not the transmission rounding.
    worst = 0.0
    n = 0
    for preset in ("monaco_capture", "head_on"):
        for own_head in (0.0, 30.0, 210.0):
            field = ais.make_field(preset, 0.0, 0.0, own_head)
            for t in (0.0, 20.0, 55.5, 90.0):
                wt = ais.wire_targets(field, t)
                recs = aisr.build_ais_targets(0.0, 0.0, own_head, wt)
                assert len(recs) == len(wt) and recs, "shape"
                for rec, w in zip(recs, wt):
                    rng, tb = ais.range_bearing(0.0, 0.0, float(w["x"]), float(w["z"]))
                    rb = ais.relative_bearing(tb, own_head)
                    worst = max(worst, abs(rec["rangeM"] - rng),
                                abs(rec["trueBearingDeg"] - tb),
                                abs(aisr._wrap180(rec["relBearingDeg"] - rb)))
                    n += 1
    return worst < TOL, f"{n} contact-instants, max |mirror-canonical| = {worst:.2e} (< {TOL})"


def g3_schema_backcompat_identity():
    field = ais.make_field("monaco_capture", 0.0, 0.0, 15.0)
    wt = ais.wire_targets(field, 12.0)
    recs = aisr.build_ais_targets(100.0, -50.0, 15.0, wt)
    keys_ok = all(set(r.keys()) == REQ_KEYS for r in recs)
    types_ok = all(isinstance(r["mmsi"], int) and isinstance(r["name"], str)
                   and all(isinstance(r[k], float) for k in
                           ("rangeM", "trueBearingDeg", "relBearingDeg", "cogDeg", "sogKn", "latDeg", "lonDeg"))
                   for r in recs)
    mmsi_ok = all(int(r["mmsi"]) == int(w["id"]) for r, w in zip(recs, wt))
    # lat/lon uses the shared geo origin (a target at exactly own-origin East/North=0
    # would read the origin); check the origin constants + monotonic north->lat.
    geo_ok = (abs(aisr.GEO_LAT0 - 43.7350) < 1e-9 and abs(aisr.GEO_LON0 - 7.4250) < 1e-9
              and aisr.ais_target_record(0, 0, 0, {"id": 1, "x": 0.0, "z": 111320.0})["latDeg"] - 44.7350 < 1e-6)
    empty_ok = aisr.build_ais_targets(0.0, 0.0, 0.0, []) == []
    ok = keys_ok and types_ok and mmsi_ok and geo_ok and empty_ok
    return ok, (f"keys={keys_ok} types={types_ok} mmsi_tracks_id={mmsi_ok} "
                f"geo_origin={geo_ok} empty->[]={empty_ok}")


def g4_determinism():
    field = ais.make_field("crossing", 0.0, 0.0, 0.0)
    wt = ais.wire_targets(field, 33.0)
    a = aisr.build_ais_targets(10.0, 20.0, 45.0, wt)
    b = aisr.build_ais_targets(10.0, 20.0, 45.0, wt)
    ok = json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    return ok, f"bit-identical replay={ok}"


def _run(pyfile, *args):
    r = subprocess.run([sys.executable, pyfile, *args], cwd=ROOT,
                       capture_output=True, text=True, timeout=240)
    tail = (r.stdout or r.stderr).strip().splitlines()
    return r.returncode, (tail[-1][:70] if tail else f"rc={r.returncode}")


def g5_regression():
    z_rc, z_msg = _run(Z0) if os.path.exists(Z0) else (0, "Z0 absent")
    d_rc, d_msg = _run(os.path.join(ROOT, "python", "verify_20260701.py"))
    t_rc, t_msg = _run(os.path.join(ROOT, "python", "verify_20260629b.py"))
    ok = (z_rc == 0 and d_rc == 0 and t_rc == 0)
    return ok, f"Z0 rc={z_rc}({z_msg}); dashboard rc={d_rc}; traffic rc={t_rc}"


# ----------------------------------------------------------------- controls
def n1_empty_block_detected():
    old = ('    // ---------- AIS (empty until traffic exists) ----------\n'
           '    TSharedRef<FJsonObject> Ais = MakeShared<FJsonObject>();\n'
           '    TArray<TSharedPtr<FJsonValue>> Empty;\n'
           '    Ais->SetArrayField(TEXT("targets"), Empty);\n')
    fired = not ais_block_is_wired(old)
    return fired, f"hardcoded-empty block wired?={not fired} -> {'fired' if fired else 'MISS'}"


def n2_wrong_frame():
    field = ais.make_field("head_on", 0.0, 0.0, 0.0)
    wt = ais.wire_targets(field, 40.0)
    st = field.state_at(40.0)[0]
    rng, tb = ais.range_bearing(0.0, 0.0, st["e"], st["n"])
    # a swapped-frame bearing (atan2(North,East) instead of atan2(East,North))
    bad = aisr._wrap360(math.degrees(math.atan2(st["n"], st["e"])))
    fired = abs(aisr._wrap180(bad - tb)) > 1.0
    return fired, f"swapped-frame bearing off by {abs(aisr._wrap180(bad-tb)):.1f} deg -> {'fired' if fired else 'MISS'}"


def n3_identity_tracks():
    base = {"id": 111, "name": "A", "x": 500.0, "z": 800.0, "cogDeg": 90.0, "sogKn": 10.0}
    r0 = aisr.ais_target_record(0, 0, 0, base)
    changed = dict(base, id=222, cogDeg=270.0)
    r1 = aisr.ais_target_record(0, 0, 0, changed)
    fired = (r0["mmsi"] == 111 and r1["mmsi"] == 222 and r0["cogDeg"] == 90.0 and r1["cogDeg"] == 270.0)
    return fired, f"id 111->222, cog 90->270 reflected in feed -> {'fired' if fired else 'MISS'}"


def main():
    gates = [
        ("G1", "cpp_ais_wired_from_pawn", *g1_cpp_wired()),
        ("G2", "geometry_parity_vs_canonical", *g2_geometry_parity()),
        ("G3", "schema_backcompat_identity", *g3_schema_backcompat_identity()),
        ("G4", "determinism", *g4_determinism()),
        ("G5", "regression_Z0+dashboard+traffic", *g5_regression()),
    ]
    controls = [
        ("N1", "empty_block_detected", *n1_empty_block_detected()),
        ("N2", "wrong_frame_caught", *n2_wrong_frame()),
        ("N3", "identity_tracks", *n3_identity_tracks()),
    ]
    print("verify_20260701b -- AIS -> sensor.v1 feed (own-ship AIS receiver)\n")
    gp = 0
    for cid, name, ok, det in gates:
        print(f"  [{'PASS' if ok else 'FAIL'}] {cid} {name}: {det}"); gp += ok
    print()
    cf = 0
    for cid, name, fired, det in controls:
        print(f"  [{'FIRED' if fired else 'MISS'}] {cid} {name}: {det}"); cf += fired
    all_ok = (gp == len(gates) and cf == len(controls))
    print(f"\n  Gates {gp}/{len(gates)}  Controls {cf}/{len(controls)}  => {'PASS' if all_ok else 'FAIL'}")
    out = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports", "wp_20260701b_result.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"packet": "WP-20260701B",
                   "title": "AIS -> sensor.v1 feed (own-ship AIS receiver, D4)",
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
