#!/usr/bin/env python3
"""
verify_20260708e.py -- WP-20260708E acceptance gate.

KI-033 fix: verify_sensors_fidelity.py's D4 (yaw-rate fidelity) gate had no
"not enough signal to gate" guard, unlike its sibling D5 (heading fidelity),
which already skips to INFO when a run barely turns (<5 deg). Found live
today re-running the sensor-fidelity gate against a straight-transit run
(logs/unreal-test-run_20260708_052109, controller=transit, monaco_capture):
the plant yaw rate never leaves 0.000 deg/s, so both `_pearson` and `_linfit`
hit their zero-variance branches and return corr=0.0/slope=0.0 -- a
mathematically degenerate result, not a real sensor defect -- which used to
score a hard FAIL (6/7). Straight-transit/AIS/COLREGS scenarios (WP-15,
WP-20260624, WP-20260703) all use steady-course controllers, so this false
FAIL could recur on any of them. Fix mirrors D5's existing pattern exactly:
D4 is INFO when the plant's own yaw-rate range is below a threshold, PASS/
FAIL as before otherwise. Also added the "frozen_yawrate" negative control
D4 never had (same pattern as D5's "frozen_heading"). Pure Python, read-only
analysis tool -- NO product/wire/C++/schema change, NO rebuild.

Gates:
  G1  flat-run no-false-FAIL : the real flat-transit run scores D4=INFO and
                                overall verdict PASS (was FAIL pre-fix).
  G2  turning-run unchanged  : the real turning-circle run
                                (unreal-test-run_20260622_054815, the run
                                WP-20260622 originally validated D4 1.0000
                                corr on) still scores D4=PASS with the same
                                numbers, verdict PASS -- the fix does not
                                weaken the real gate.
  G3  new control has teeth  : on the turning run, the new "frozen_yawrate"
                                selftest control FIRES (D4 -> FAIL).
  G4  new control applicability : on the flat run, "frozen_yawrate" reports
                                N/A (base D4 is INFO) instead of a false
                                requirement -- mirrors "frozen_heading".
  G5  regression + parses    : py_compile clean; Z0 16/16; preflight
                                --report-only still exits 0 (GO) -- this
                                tooling-only edit changed nothing it touches.

Negative controls (must behave as stated, else the test is not really
testing anything):
  N1  bug reproduction : replaying the OLD (unguarded) math directly against
      the flat run's real plant/sensor columns reproduces corr=0.0/
      slope=0.0 -- proving the false FAIL this fixes was real, not assumed.
  N2  threshold sane at the boundary : a synthetic run with plant yaw-rate
      range just ABOVE the threshold and a faithful sensor mirror gates
      normally to PASS, not stuck on INFO -- the guard doesn't over-suppress
      real signal near the boundary.
  N3  guard reads the PLANT, not the sensor : a synthetic run with a FLAT
      plant yaw-rate but a wildly corrupted sensor yaw-rate is still INFO --
      you cannot dodge or force the gate by corrupting the sensor side alone.
"""
import copy, csv, io, json, math, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import verify_sensors_fidelity as M  # module under test

REPORTS = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports")
FLAT_RUN = os.path.join(ROOT, "logs", "unreal-test-run_20260708_052109")
TURN_RUN = os.path.join(ROOT, "logs", "unreal-test-run_20260622_054815")
Z0 = os.path.join(ROOT, "Development", "work_packets", "WP_20260615_COMPILE_AUDIT",
                   "verify_compile_readiness.py")
PREFLIGHT = os.path.join(ROOT, "preflight_demo.py")


def _load(run_dir):
    sensor = M._load_csv(os.path.join(run_dir, "sensor.csv"))
    state = M._load_csv(os.path.join(run_dir, "state.csv"))
    return sensor, state


def g1_flat_run_no_false_fail():
    sensor, state = _load(FLAT_RUN)
    res = M.analyse_run_dir(FLAT_RUN)
    d4 = M._gate_status(res["checks"], "D4")
    ok = (d4 == "INFO") and (res["verdict"] == "PASS")
    return ok, f"D4={d4} verdict={res['verdict']} gates={res['gates_passed']}/{res['gates_total']} (want INFO, PASS)"


def g2_turning_run_unchanged():
    res = M.analyse_run_dir(TURN_RUN)
    d4 = next(c for c in res["checks"] if c["id"] == "D4")
    ok = (d4["status"] == "PASS") and (res["verdict"] == "PASS") and ("corr=1.0000" in d4["detail"])
    return ok, f"D4={d4['status']} detail={d4['detail']} verdict={res['verdict']} (want PASS, corr=1.0000)"


def g3_new_control_has_teeth():
    sensor, state = _load(TURN_RUN)
    st = M.run_selftest(TURN_RUN)
    ctrl = next(c for c in st["controls"] if c["control"] == "frozen_yawrate")
    ok = ctrl["fired"] and ctrl["gate_status"] == "FAIL"
    return ok, f"frozen_yawrate: fired={ctrl['fired']} gate_status={ctrl['gate_status']} (want True, FAIL)"


def g4_new_control_applicability():
    st = M.run_selftest(FLAT_RUN)
    ctrl = next(c for c in st["controls"] if c["control"] == "frozen_yawrate")
    ok = ctrl["gate_status"] == "N/A"
    return ok, f"frozen_yawrate on flat run: gate_status={ctrl['gate_status']} (want N/A)"


def _run(pyfile, args=()):
    r = subprocess.run([sys.executable, pyfile, *args], cwd=ROOT,
                        capture_output=True, text=True)
    return r.returncode


def g5_regression_and_parses():
    import py_compile
    try:
        py_compile.compile(os.path.join(HERE, "verify_sensors_fidelity.py"), doraise=True)
        parses = True
    except py_compile.PyCompileError:
        parses = False
    rc_z0 = _run(Z0)
    rc_pre = _run(PREFLIGHT, ["--report-only"])
    ok = parses and (rc_z0 == 0) and (rc_pre == 0)
    return ok, f"parses={parses} Z0 rc={rc_z0} preflight rc={rc_pre} (want True, 0, 0)"


def n1_bug_reproduction():
    sensor, state = _load(FLAT_RUN)
    j = M._join_to_plant(sensor, state)
    g_yr = M._fcol(sensor, "imu_yawRateDegPerSec")
    old_slope, _ = M._linfit(j["plant_r_degps"], g_yr)
    old_corr = M._pearson(j["plant_r_degps"], g_yr)
    old_ok = (M.YAWRATE_SLOPE_ABS[0] <= abs(old_slope) <= M.YAWRATE_SLOPE_ABS[1]) and \
             old_corr >= M.YAWRATE_CORR_MIN
    # old_ok False means the pre-fix code would have scored this FAIL
    ok = (old_corr == 0.0) and (old_slope == 0.0) and (old_ok is False)
    return ok, f"pre-fix math: slope={old_slope} corr={old_corr} would_pass={old_ok} (want 0.0, 0.0, False)"


def _mk_run(tmp, name, t_list, plant_r_degps, sensor_yr_degps, sensor_speed=None):
    """Minimal synthetic sensor.csv/state.csv pair joinable on wall_time."""
    d = os.path.join(tmp, name)
    os.makedirs(d, exist_ok=True)
    n = len(t_list)
    speed = sensor_speed or [1.0] * n
    with open(os.path.join(d, "state.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["wall_time", "t", "speed_mag", "r", "yawDeg", "x", "z"])
        yaw = 0.0
        for i in range(n):
            r_rad = plant_r_degps[i] * math.pi / 180.0
            w.writerow([t_list[i], t_list[i], speed[i], r_rad, yaw, 0.0, 0.0])
    with open(os.path.join(d, "sensor.csv"), "w", newline="") as f:
        w = csv.writer(f)
        cols = ["wall_time", "t", "gps_x", "gps_y", "gps_z", "gps_speed",
                "gps_latDeg", "gps_lonDeg", "gps_hasFix",
                "imu_headingDeg", "imu_yawRateDegPerSec",
                "imu_acc_x", "imu_acc_y", "imu_acc_z", "ais_target_count"]
        w.writerow(cols)
        for i in range(n):
            w.writerow([t_list[i], t_list[i], 0.0, 0.0, 0.0, speed[i],
                        43.735, 7.425, 1, 0.0, sensor_yr_degps[i], 0.0, 0.0, 0.0, 0])
    return d


def n2_threshold_boundary_sane():
    with tempfile.TemporaryDirectory() as tmp:
        n = 20
        t = [i * 0.1 for i in range(n)]
        # plant yaw-rate ramps to just above the 0.5 deg/s threshold; sensor mirrors it exactly
        plant_r = [0.6 * (i / (n - 1)) for i in range(n)]
        sensor_yr = list(plant_r)  # perfect mirror -> should gate PASS, not INFO
        d = _mk_run(tmp, "boundary", t, plant_r, sensor_yr)
        res = M.analyse_run_dir(d)
        d4 = next(c for c in res["checks"] if c["id"] == "D4")
        ok = d4["status"] == "PASS"
        return ok, f"range=0.6 deg/s mirror sensor -> D4={d4['status']} {d4['detail']} (want PASS)"


def n3_guard_reads_plant_not_sensor():
    with tempfile.TemporaryDirectory() as tmp:
        n = 20
        t = [i * 0.1 for i in range(n)]
        plant_r = [0.0] * n  # flat plant -> must be INFO regardless of sensor
        sensor_yr = [50.0 * ((-1) ** i) for i in range(n)]  # wildly corrupted sensor
        d = _mk_run(tmp, "corrupted_sensor", t, plant_r, sensor_yr)
        res = M.analyse_run_dir(d)
        d4 = next(c for c in res["checks"] if c["id"] == "D4")
        ok = d4["status"] == "INFO"
        return ok, f"flat plant + corrupted sensor -> D4={d4['status']} {d4['detail']} (want INFO)"


def main():
    gates = [("G1", "flat-run no false FAIL", g1_flat_run_no_false_fail),
             ("G2", "turning-run unchanged", g2_turning_run_unchanged),
             ("G3", "new control has teeth", g3_new_control_has_teeth),
             ("G4", "new control applicability", g4_new_control_applicability),
             ("G5", "regression + parses", g5_regression_and_parses)]
    negs = [("N1", "bug reproduction (pre-fix math)", n1_bug_reproduction),
            ("N2", "threshold boundary sane", n2_threshold_boundary_sane),
            ("N3", "guard reads plant not sensor", n3_guard_reads_plant_not_sensor)]

    checks, passed = [], 0
    print("=" * 64)
    print("WP-20260708E verify -- D4 yaw-rate false-FAIL fix (KI-033)")
    print("=" * 64)
    for gid, name, fn in gates:
        ok, detail = fn()
        passed += bool(ok)
        checks.append({"id": gid, "name": name, "pass": bool(ok), "detail": detail})
        print(f"  [{'OK ' if ok else 'XX '}] {gid} {name:32s} {detail}")
    print("  " + "-" * 60)
    neg_ok = 0
    negs_out = []
    for nid, name, fn in negs:
        ok, detail = fn()
        neg_ok += bool(ok)
        negs_out.append({"id": nid, "name": name, "pass": bool(ok), "detail": detail})
        print(f"  [{'OK ' if ok else 'XX '}] {nid} {name:32s} {detail}")

    all_ok = (passed == len(gates)) and (neg_ok == len(negs))
    print("  " + "-" * 60)
    print(f"  gates {passed}/{len(gates)} + neg {neg_ok}/{len(negs)} -> "
          f"{'PASS' if all_ok else 'FAIL'}")
    print("=" * 64)

    out = {
        "packet": "WP-20260708E",
        "date": "2026-07-08",
        "title": "Sensor-fidelity D4 yaw-rate false-FAIL fix (KI-033)",
        "pass": all_ok,
        "gates_passed": passed, "gates_total": len(gates),
        "neg_passed": neg_ok, "neg_total": len(negs),
        "checks": checks, "neg_controls": negs_out,
        "note": ("verify_sensors_fidelity.py D4 now mirrors D5's existing "
                 "insufficient-signal guard: INFO (not FAIL) when the plant's "
                 "own yaw-rate range is below 0.5 deg/s, e.g. straight-transit/"
                 "AIS/COLREGS scenarios. Added the missing frozen_yawrate "
                 "negative control (same pattern as frozen_heading). "
                 "Test-tooling only -- no product/wire/C++/schema change, no "
                 "rebuild."),
    }
    os.makedirs(REPORTS, exist_ok=True)
    dest = os.path.join(REPORTS, "wp_20260708e_result.json")
    with open(dest, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"[verify] wrote {dest}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
