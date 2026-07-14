"""Verify WP-20260624 — scripted AIS traffic + CPA/TCPA + COLREGS encounters (D4/WP-15).

Gates (exit 0 iff all gates pass AND all negative controls fire):
  G1 core_geometry      cpa/tcpa/range/bearing match the analytic closed form.
  G2 colregs_classify   head_on/crossing/overtaking presets classify correctly on a
                        synthetic STEADY own-ship track (controller-independent).
  G3 range_bearing_gate the WP-15 gate: the AIS block lists the target with the
                        correct range & bearing from own-ship (vs hand geometry).
  G4 evidence_integration  build_evidence_pack --ais on a real run emits a finite
                        AIS block + ais.csv + ais_cpa.png + an EVIDENCE.md section,
                        WITHOUT disturbing the IMO maneuver KPIs / health gate.
  G5 determinism        analysing the same run+preset twice is bit-identical.
  G6 manifest_chain     the listener records the preset in the manifest and the
                        evidence pack AUTO-reads it (no --ais needed) -> AIS block.

Negative controls (must FIRE = produce the deliberately-different/again-rejected result):
  N1 unknown_preset_rejected   make_field('bogus') raises; listener --ais bogus exits !=0.
  N2 receding_no_false_alarm   a target opening astern -> no_risk, never alerts.
  N3 port_starboard_flip       a crossing target on the PORT bow -> stand_on (not give_way).

Writes NaviSense_UE5/Saved/NaviSense_Reports/wp_20260624_result.json.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PYDIR = os.path.join(ROOT, "python")
for p in (ROOT, PYDIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import ais_traffic as ais            # noqa: E402
import analyse_ais as aais           # noqa: E402
import build_evidence_pack as bep    # noqa: E402
import verify_run_kinematics as vrk  # noqa: E402
from python.run_logger import RunLogger  # noqa: E402

REPORTS = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports")
RESULT = os.path.join(REPORTS, "wp_20260624_result.json")

gates = []
controls = []


def gate(gid, name, ok, detail=""):
    gates.append({"id": gid, "name": name, "passed": bool(ok), "detail": str(detail)[:240]})


def control(cid, name, fired, detail=""):
    controls.append({"id": cid, "name": name, "fired": bool(fired), "detail": str(detail)[:240]})


def approx(a, b, tol):
    return abs(a - b) <= tol


# ----------------------------------------------------------------- synthetic track
def straight_track(speed=5.0, dt=0.1, dur=300.0):
    """Own-ship at origin steaming due NORTH (compass 0) at constant speed.
    Columns mirror state.csv (x=east, z=north, yawDeg=heading)."""
    rows = []
    n = int(dur / dt)
    for i in range(n + 1):
        t = i * dt
        rows.append({"t": str(t), "x": "0.0", "z": str(speed * t), "yawDeg": "0.0",
                     "u": str(speed), "v": "0.0", "r": "0.0",
                     "speed_mag": str(speed)})
    return rows


# ----------------------------------------------------------------- G1 core geometry
def g1_core_geometry():
    try:
        # head-on, 40 m lateral offset, closing 10 m/s over 1000 m
        cpa, tcpa = ais.cpa_tcpa(0, 0, 0, 5, 40, 1000, 0, -5)
        ok_cpa = approx(cpa, 40.0, 1e-6) and approx(tcpa, 100.0, 1e-6)
        # range/bearing: target due east at 500 m
        rng, brg = ais.range_bearing(0, 0, 500, 0)
        ok_rb = approx(rng, 500.0, 1e-6) and approx(brg, 90.0, 1e-6)
        # receding pair -> tcpa clamps to 0, cpa = current range
        cpa2, tcpa2 = ais.cpa_tcpa(0, 0, 0, 5, 0, 100, 0, 5)
        ok_rec = approx(tcpa2, 0.0, 1e-9) and approx(cpa2, 100.0, 1e-6)
        # lat/lon projection matches the GPS sensor origin
        lat, lon = ais.project_latlon(0, 0)
        ok_geo = approx(lat, 43.7350, 1e-9) and approx(lon, 7.4250, 1e-9)
        ok = ok_cpa and ok_rb and ok_rec and ok_geo
        gate("G1", "core_geometry", ok,
             f"cpa={cpa:.3f}/tcpa={tcpa:.1f} rng={rng:.1f}/brg={brg:.1f} "
             f"recede(tcpa={tcpa2:.1f},cpa={cpa2:.1f}) origin=({lat:.4f},{lon:.4f})")
    except Exception as e:
        gate("G1", "core_geometry", False, f"{type(e).__name__}: {e}")


# ----------------------------------------------------------------- G2 classification
EXPECT = {
    "head_on": ("head_on", "give_way"),
    "crossing": ("crossing_give_way", "give_way"),
    "overtaking": ("overtaking_give_way", "give_way"),
}


def g2_colregs_classify():
    rows = straight_track()
    results = {}
    ok = True
    for preset, (enc, duty) in EXPECT.items():
        an = aais.analyse(rows, preset)
        tg = an.targets[0]
        got = (tg.encounter_primary, tg.duty_primary, tg.alerted)
        results[preset] = got
        if not (got[0] == enc and got[1] == duty and got[2]):
            ok = False
    gate("G2", "colregs_classify", ok,
         "; ".join(f"{k}:{v[0]}/{v[1]}/alert={v[2]}" for k, v in results.items()))


# ----------------------------------------------------------------- G3 range/bearing
def g3_range_bearing_gate():
    rows = straight_track()
    an = aais.analyse(rows, "head_on")
    mmsi = an.targets[0].mmsi
    first = an.series[mmsi][0]            # t≈0 sample
    # Hand geometry: head_on template = 1600 m ahead + 35 m starboard of a
    # north-heading own-ship at the origin -> target at (e=35, n=1600).
    exp_rng = math.hypot(35.0, 1600.0)
    exp_brg = math.degrees(math.atan2(35.0, 1600.0))
    ok = approx(first["range_m"], exp_rng, 1.0) and approx(first["true_bearing_deg"], exp_brg, 0.5) \
        and approx(first["rel_bearing_deg"], exp_brg, 0.5)
    gate("G3", "range_bearing_gate", ok,
         f"reported range={first['range_m']:.2f} (exp {exp_rng:.2f}) "
         f"bearing={first['true_bearing_deg']:.2f} (exp {exp_brg:.2f})")


# ----------------------------------------------------------------- G4 evidence pack
def _latest_real_run():
    log_root = os.path.join(ROOT, "logs")
    cands = [os.path.join(log_root, n) for n in os.listdir(log_root)
             if n.startswith("unreal-test-run")
             and os.path.exists(os.path.join(log_root, n, "state.csv"))]
    cands.sort(key=os.path.getmtime, reverse=True)
    return cands[0] if cands else vrk._latest_run(log_root)


def g4_evidence_integration():
    try:
        run = _latest_real_run()
        res = bep.build_pack(run, ais_preset="head_on", make_plots=True)
        k = res["kpis"]
        a = k.get("ais")
        pack = res["pack_dir"]
        ais_csv = os.path.join(pack, "ais.csv")
        cpa_png = os.path.join(pack, "ais_cpa.png")
        evid = os.path.join(pack, "EVIDENCE.md")
        csv_rows = 0
        if os.path.exists(ais_csv):
            with open(ais_csv) as f:
                csv_rows = sum(1 for _ in f) - 1
        md = open(evid).read() if os.path.exists(evid) else ""
        tgt = (a or {}).get("targets", [{}])[0]
        finite = all(math.isfinite(tgt.get(x, float("nan")))
                     for x in ("min_range_m", "min_cpa_m", "tcpa_at_min_cpa_s"))
        # AIS must be additive: maneuver KPIs + health gate unchanged.
        health_ok = k["health"]["verdict"] == "PASS"
        man_ok = k["maneuver"].get("kind") == "turning_circle"
        ok = (a is not None and not a.get("error") and finite and csv_rows > 1
              and os.path.exists(cpa_png) and "AIS traffic & COLREGS" in md
              and health_ok and man_ok)
        gate("G4", "evidence_integration", ok,
             f"run={os.path.basename(run)} ais_targets={a.get('n_targets') if a else None} "
             f"csv_rows={csv_rows} cpa_png={os.path.exists(cpa_png)} health={k['health']['verdict']} "
             f"man={k['maneuver'].get('kind')}")
    except Exception as e:
        gate("G4", "evidence_integration", False, f"{type(e).__name__}: {e}")


# ----------------------------------------------------------------- G5 determinism
def g5_determinism():
    rows = straight_track()
    a1 = aais.analyse(rows, "harbor_mix").to_json()
    a2 = aais.analyse(rows, "harbor_mix").to_json()
    ok = json.dumps(a1, sort_keys=True) == json.dumps(a2, sort_keys=True)
    gate("G5", "determinism", ok, f"identical={ok} targets={a1['n_targets']}")


# ----------------------------------------------------------------- G6 manifest chain
def g6_manifest_chain():
    try:
        # (a) RunLogger writes manifest["ais"] when given a preset.
        tmp = tempfile.mkdtemp(prefix="wp24_")
        lg = RunLogger.create(tmp, "chain", "stub", "transit", 30.0, ais_preset="head_on")
        # minimal state so the pack has a track (straight north)
        for i in range(0, 1200):
            t = i * 0.1
            lg.record_state({"t": t, "x": 0.0, "z": 5.0 * t, "yawDeg": 0.0,
                             "u": 5.0, "v": 0.0, "r": 0.0, "mode": "transit"})
        lg.finalise()
        run_dir = lg.run_dir
        man = json.load(open(os.path.join(run_dir, "manifest.json")))
        wrote = man.get("ais") == "head_on"
        # (b) the pack AUTO-reads the manifest preset (no ais_preset override).
        res = bep.build_pack(run_dir, make_plots=False)
        a = res["kpis"].get("ais")
        read = a is not None and not a.get("error") and a.get("preset") == "head_on"
        enc_val = a["targets"][0]["encounter_primary"] if read and a.get("targets") else None
        enc_ok = enc_val == "head_on"
        pack_preset = a.get("preset") if a else None
        gate("G6", "manifest_chain", wrote and read and enc_ok,
             f"manifest_ais={man.get('ais')} pack_preset={pack_preset} encounter={enc_val}")
    except Exception as e:
        gate("G6", "manifest_chain", False, f"{type(e).__name__}: {e}")


# ----------------------------------------------------------------- negative controls
def n1_unknown_preset():
    raised = False
    try:
        ais.make_field("bogus", 0, 0, 0)
    except KeyError:
        raised = True
    # listener must reject --ais bogus with a non-zero exit (before binding).
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "python_listener.py"),
                           "--ais", "bogus", "--once"],
                          capture_output=True, text=True, cwd=ROOT, timeout=30)
    rejected = proc.returncode != 0
    control("N1", "unknown_preset_rejected", raised and rejected,
            f"make_field_raised={raised} listener_rc={proc.returncode}")


def n2_receding_no_false_alarm():
    # Own-ship north@5; target far ahead but RECEDING north@9 (opening) -> no risk.
    rows = straight_track()
    # author a custom field directly (faster vessel dead ahead pulling away)
    field = ais.AISTrafficField(targets=[ais.AISTarget(
        mmsi=1, name="RUNNER", ship_type="cargo", e0=0.0, n0=300.0,
        cog_deg=0.0, sog_mps=9.0)])
    closing_seen = False
    alerted = False
    enc_set = set()
    for i in range(0, len(rows), 25):
        t = float(rows[i]["t"])
        on = 5.0 * t
        st = field.targets[0].state_at(t)
        tve, tvn = field.targets[0].velocity_at(t)
        snap = ais.encounter_snapshot(t, 0.0, on, 0.0, 5.0, st, tve, tvn)
        enc_set.add(snap.encounter)
        if snap.closing:
            closing_seen = True
        if snap.closing and snap.cpa_m <= ais.DEFAULT_CPA_ALERT_M and snap.tcpa_s >= 0:
            alerted = True
    fired = (not closing_seen) and (not alerted) and enc_set == {"no_risk"}
    control("N2", "receding_no_false_alarm", fired,
            f"closing_seen={closing_seen} alerted={alerted} encounters={sorted(enc_set)}")


def n3_port_starboard_flip():
    # Mirror the crossing target to the PORT bow -> duty must flip to stand_on.
    rows = straight_track()
    an_stbd = aais.analyse(rows, "crossing").targets[0]            # starboard -> give_way
    # build a port-side mirror by hand (negate the starboard offset & course)
    field = ais.make_field("crossing", 0.0, 0.0, 0.0)
    base = field.targets[0]
    # reflect east about own track (port mirror): e -> -e, course -> -course
    mirror = ais.AISTrafficField(targets=[ais.AISTarget(
        mmsi=base.mmsi, name="PORTSIDE", ship_type=base.ship_type,
        e0=-base.e0, n0=base.n0, cog_deg=ais.wrap360(-base.cog_deg), sog_mps=base.sog_mps)])
    # classify the port mirror at first alert
    enc = None
    duty = None
    for i in range(0, len(rows), 10):
        t = float(rows[i]["t"])
        on = 5.0 * t
        st = mirror.targets[0].state_at(t)
        tve, tvn = mirror.targets[0].velocity_at(t)
        snap = ais.encounter_snapshot(t, 0.0, on, 0.0, 5.0, st, tve, tvn)
        if snap.closing and snap.cpa_m <= ais.DEFAULT_CPA_ALERT_M and snap.tcpa_s >= 0:
            enc, duty = snap.encounter, snap.duty
            break
    if enc is None:
        # fall back to min-range classification if no alert
        enc, duty = "n/a", "n/a"
    fired = (an_stbd.duty_primary == "give_way" and duty == "stand_on"
             and enc == "crossing_stand_on")
    control("N3", "port_starboard_flip", fired,
            f"starboard={an_stbd.encounter_primary}/{an_stbd.duty_primary} "
            f"port={enc}/{duty}")


# ----------------------------------------------------------------- main
def main():
    g1_core_geometry()
    g2_colregs_classify()
    g3_range_bearing_gate()
    g4_evidence_integration()
    g5_determinism()
    g6_manifest_chain()
    n1_unknown_preset()
    n2_receding_no_false_alarm()
    n3_port_starboard_flip()

    passed = sum(1 for g in gates if g["passed"])
    all_fired = all(c["fired"] for c in controls)
    overall = "PASS" if (passed == len(gates) and all_fired) else "FAIL"
    out = {
        "packet": "WP-20260624",
        "theme": "Scripted AIS traffic + CPA/TCPA + COLREGS encounters (gate D4 / WP-15)",
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "gates_passed": passed,
        "gates_total": len(gates),
        "all_negative_controls_fired": all_fired,
        "overall": overall,
        "gates": gates,
        "negative_controls": controls,
    }
    os.makedirs(REPORTS, exist_ok=True)
    with open(RESULT, "w") as f:
        json.dump(out, f, indent=2)
    print(f"[verify_20260624] {overall} — {passed}/{len(gates)} gates, "
          f"controls fired={all_fired}")
    for g in gates:
        print(f"  {g['id']} {g['name']:22s} {'PASS' if g['passed'] else 'FAIL'}  {g['detail']}")
    for c in controls:
        print(f"  {c['id']} {c['name']:24s} {'FIRED' if c['fired'] else 'MISS'}  {c['detail']}")
    print(f"[verify_20260624] wrote {RESULT}")
    sys.exit(0 if overall == "PASS" else 1)


if __name__ == "__main__":
    main()
