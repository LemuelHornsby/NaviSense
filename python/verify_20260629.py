#!/usr/bin/env python3
"""verify_20260629 -- canonical run-clock gate (closes KI-024).

Background
----------
``state.csv`` (plant, TX side) and ``sensor.csv`` (UE, RX side) used to share
no common clock: ``state.t`` is the Python plant clock and ``sensor.t`` is the
UE engine clock, and under high PIE FPS the plant free-ran (3.0x wall) while
the engine clock ran 1.0x wall -- so anything fusing the two CSVs by ``t`` got
badly misaligned data (KI-024).

The fix: ``run_logger`` now stamps a single **monotonic, run-relative** clock
``t_mono`` onto EVERY row of BOTH logs (and events.csv), from one
``time.monotonic()`` source in the single logger process. ``t_mono`` is the
canonical join key; ``verify_sensors_fidelity`` prefers it (falling back to
``wall_time`` for legacy runs). ``t`` stays the raw per-side clock for
reference; nothing on the wire / DTO / schema changed.

This harness proves the fix end to end on a synthetic run whose raw ``t``
columns are made to diverge 1x (sensor) vs 3x (plant) -- exactly the KI-024
shape -- and shows the canonical join recovers the plant signal while a raw-t
join corrupts it.

Gates (G1-G6) must PASS; negative controls (N1-N3) must FIRE. Exit 0 iff all.
"""
from __future__ import annotations

import csv
import math
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "python"))

import run_logger as rl                       # noqa: E402
import verify_sensors_fidelity as vsf         # noqa: E402

TOL_START = 0.05      # t_mono must start within 50 ms of 0 (run-relative)
TOL_SPAN = 0.50       # the two logs' t_mono spans must agree within 0.5 s
TOL_MONO_RMS = 0.05   # canonical-join recovery rms (m/s) on the ramp
RAW_WORSE_FACTOR = 8.0  # raw-t join must be >=8x worse than the canonical join


# --------------------------------------------------------------- synthetic run
def make_run(tmp, *, n=60, faithful=True, t_state_rate=3.0, t_sensor_rate=1.0,
             dt_wall=0.01, break_mono=False, desync_scale=None):
    """Drive a real RunLogger with interleaved RX/TX packets.

    The plant speed is a ramp (so a mis-aligned join is visibly wrong). Raw
    ``t`` is written at deliberately different rates per side to reproduce
    KI-024; ``t_mono`` is stamped by the logger from one monotonic clock.

    ``break_mono`` / ``desync_scale`` are used only by the negative controls
    to corrupt t_mono AFTER logging (the logger itself never produces those).
    """
    import time
    lg = rl.RunLogger.create(tmp, run_id="clk", plant_kind="mmg",
                             controller_kind="turning_circle", tick_hz=50.0)
    true_speed = []
    for i in range(n):
        spd = 1.0 + 1.5 * (i / max(1, n - 1))      # ramp 1.0 -> 2.5 m/s
        true_speed.append(spd)
        heading = (i * 2.0) % 360.0
        # RX first (engine clock), then TX (plant clock) -- same loop tick
        lg.record_sensor({
            "t": i * 0.10 * t_sensor_rate,
            "sensors": {
                "gps": {"speed": spd if faithful else 0.0,
                        "worldPosition": {"x": i, "y": 0.0, "z": 0.0},
                        "latDeg": 43.7350, "lonDeg": 7.4250, "hasFix": True},
                "imu": {"headingDeg": heading, "yawRateDegPerSec": 2.0 * 50.0 / 50.0,
                        "acceleration": {"x": 0.0, "y": 0.0, "z": 0.0}},
                "ais": {"targets": []},
            }})
        lg.record_state({
            "t": i * 0.10 * t_state_rate, "mode": "turning_circle",
            "x": i, "y": 0.0, "z": 0.0, "yawDeg": heading,
            "u": spd, "v": 0.0, "r": 0.0,
            "portRpm": 100, "starboardRpm": 100, "rudderDeg": 10, "bowThrusterNorm": 0,
            "portRpmCmd": 100, "starboardRpmCmd": 100, "rudderCmdDeg": 10, "bowThrusterCmdNorm": 0,
            "rollDeg": 0, "pitchDeg": 0, "heaveM": 0})
        time.sleep(dt_wall)
    lg.finalise()
    run = [d for d in os.listdir(tmp) if os.path.isdir(os.path.join(tmp, d))][0]
    rd = os.path.join(tmp, run)

    if break_mono or desync_scale is not None:
        # Corrupt sensor.csv t_mono to model a fault the gate must catch.
        sp = os.path.join(rd, "sensor.csv")
        rows = list(csv.DictReader(open(sp)))
        cols = list(rows[0].keys())
        for k, r in enumerate(rows):
            if break_mono and k == len(rows) // 2:
                r["t_mono"] = f"{-1.0:.6f}"           # step backwards
            if desync_scale is not None:
                r["t_mono"] = f"{float(r['t_mono']) * desync_scale + 1000.0:.6f}"
        with open(sp, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    return rd, true_speed


def _col(rd, fn, name):
    rows = list(csv.DictReader(open(os.path.join(rd, fn))))
    return [float(r[name]) for r in rows], rows


def _interp(xs, ys, x):
    if not xs:
        return float("nan")
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    lo, hi = 0, len(xs) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid
        else:
            hi = mid
    if xs[hi] == xs[lo]:
        return ys[lo]
    return ys[lo] + (ys[hi] - ys[lo]) * (x - xs[lo]) / (xs[hi] - xs[lo])


def _rms(a, b):
    n = min(len(a), len(b))
    if n == 0:
        return float("nan")
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(n)) / n)


# --------------------------------------------------------------------- gates
def g1_schema(rd):
    s_cols = list(csv.DictReader(open(os.path.join(rd, "sensor.csv"))).fieldnames)
    p_cols = list(csv.DictReader(open(os.path.join(rd, "state.csv"))).fieldnames)
    e_cols = list(csv.DictReader(open(os.path.join(rd, "events.csv"))).fieldnames)
    import json
    mani = json.load(open(os.path.join(rd, "manifest.json")))
    jk = (mani.get("timeBase") or {}).get("joinKey")
    ok = ("t_mono" in s_cols and "t_mono" in p_cols and "t_mono" in e_cols and jk == "t_mono")
    return ok, (f"t_mono in sensor={('t_mono' in s_cols)} state={('t_mono' in p_cols)} "
                f"events={('t_mono' in e_cols)} manifest.joinKey={jk}")


def g2_monotonic(rd):
    s, _ = _col(rd, "sensor.csv", "t_mono")
    p, _ = _col(rd, "state.csv", "t_mono")
    s_mono = all(s[i + 1] >= s[i] for i in range(len(s) - 1))
    p_mono = all(p[i + 1] >= p[i] for i in range(len(p) - 1))
    rel = abs(s[0]) <= TOL_START and abs(p[0]) <= TOL_START
    ok = s_mono and p_mono and rel
    return ok, (f"sensor mono={s_mono} state mono={p_mono} "
                f"start sensor={s[0]:.4f}/state={p[0]:.4f}<= {TOL_START}")


def g3_one_timeline(rd):
    s, _ = _col(rd, "sensor.csv", "t_mono")
    p, _ = _col(rd, "state.csv", "t_mono")
    st, _ = _col(rd, "sensor.csv", "t")
    pt, _ = _col(rd, "state.csv", "t")
    span_agree = abs((s[-1] - s[0]) - (p[-1] - p[0])) <= TOL_SPAN
    overlap = (s[0] >= p[0] - TOL_SPAN) and (s[-1] <= p[-1] + TOL_SPAN)
    # raw t DOES diverge (this is the KI-024 condition we want present)
    rs = (pt[-1] - pt[0]) / max(1e-9, (s[-1] - s[0]) if False else 1.0)
    ratio_state = (pt[-1] - pt[0])
    ratio_sensor = (st[-1] - st[0])
    raw_diverged = ratio_sensor > 1e-6 and abs(ratio_state - ratio_sensor) / ratio_sensor > 0.5
    ok = span_agree and overlap and raw_diverged
    return ok, (f"t_mono spans sensor={s[-1]-s[0]:.3f}/state={p[-1]-p[0]:.3f} agree={span_agree} "
                f"overlap={overlap}; raw t spans sensor={ratio_sensor:.2f}/state={ratio_state:.2f} "
                f"diverged={raw_diverged}")


def g4_key_selection(rd, legacy_run):
    sensor = vsf._load_csv(os.path.join(rd, "sensor.csv"))
    state = vsf._load_csv(os.path.join(rd, "state.csv"))
    key_new = vsf._join_key(sensor, state)
    j = vsf._join_to_plant(sensor, state)
    used = j.get("join_key")
    # legacy run (no t_mono) must fall back to wall_time
    key_legacy = "n/a"
    if legacy_run and os.path.isdir(legacy_run):
        ls = vsf._load_csv(os.path.join(legacy_run, "sensor.csv"))
        lp = vsf._load_csv(os.path.join(legacy_run, "state.csv"))
        key_legacy = vsf._join_key(ls, lp)
    ok = (key_new == "t_mono" and used == "t_mono" and key_legacy in ("wall_time", "n/a"))
    return ok, f"fresh-run key={key_new} join_used={used}; legacy-run key={key_legacy}"


def g5_canonical_accurate(rd, true_speed):
    """Canonical (t_mono) join recovers the plant ramp; rms small, corr~1."""
    s_tm, srows = _col(rd, "sensor.csv", "t_mono")
    p_tm, _ = _col(rd, "state.csv", "t_mono")
    p_spd, _ = _col(rd, "state.csv", "speed_mag")
    rec = [_interp(p_tm, p_spd, w) for w in s_tm]
    gps = [float(r["gps_speed"]) for r in srows]
    rms = _rms(rec, gps)
    ok = math.isfinite(rms) and rms <= TOL_MONO_RMS
    return ok, f"t_mono-join recovers plant speed vs gps rms={rms:.4f} m/s (tol {TOL_MONO_RMS})"


def g6_backcompat(rd):
    """A run with t_mono stripped still loads + joins via wall_time fallback."""
    tmp = tempfile.mkdtemp()
    leg = os.path.join(tmp, "legacy")
    os.makedirs(leg)
    for fn in ("sensor.csv", "state.csv"):
        rows = list(csv.DictReader(open(os.path.join(rd, fn))))
        cols = [c for c in rows[0].keys() if c != "t_mono"]
        with open(os.path.join(leg, fn), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    sensor = vsf._load_csv(os.path.join(leg, "sensor.csv"))
    state = vsf._load_csv(os.path.join(leg, "state.csv"))
    key = vsf._join_key(sensor, state)
    j = vsf._join_to_plant(sensor, state)          # must not raise
    ok = (key == "wall_time" and j.get("join_key") == "wall_time" and j["n"] > 0)
    return ok, f"t_mono-stripped run -> key={key}, joined n={j['n']} (no crash)"


# ----------------------------------------------------------------- controls
def n1_break_mono(tmp):
    rd, _ = make_run(tmp, break_mono=True)
    s, _ = _col(rd, "sensor.csv", "t_mono")
    mono = all(s[i + 1] >= s[i] for i in range(len(s) - 1))
    fired = not mono           # control fires iff the monotonic check would FAIL
    return fired, f"backwards t_mono detected: monotonic={mono} -> fired={fired}"


def n2_desync(tmp):
    rd, _ = make_run(tmp, desync_scale=5.0)   # sensor t_mono on a different scale+offset
    s, _ = _col(rd, "sensor.csv", "t_mono")
    p, _ = _col(rd, "state.csv", "t_mono")
    span_agree = abs((s[-1] - s[0]) - (p[-1] - p[0])) <= TOL_SPAN
    overlap = (s[0] >= p[0] - TOL_SPAN) and (s[-1] <= p[-1] + TOL_SPAN)
    fired = not (span_agree and overlap)
    return fired, f"desynced t_mono: span_agree={span_agree} overlap={overlap} -> fired={fired}"


def n3_rawt_corrupts(tmp, true_speed_holder):
    """The bug the fix prevents: joining on raw t (not t_mono) corrupts fusion."""
    rd, true_speed = make_run(tmp)
    s_tm, srows = _col(rd, "sensor.csv", "t_mono")
    s_t, _ = _col(rd, "sensor.csv", "t")
    p_tm, _ = _col(rd, "state.csv", "t_mono")
    p_t, _ = _col(rd, "state.csv", "t")
    p_spd, _ = _col(rd, "state.csv", "speed_mag")
    gps = [float(r["gps_speed"]) for r in srows]
    rec_mono = [_interp(p_tm, p_spd, w) for w in s_tm]   # canonical (correct)
    rec_rawt = [_interp(p_t, p_spd, w) for w in s_t]     # KI-024 bug (wrong)
    rms_mono = _rms(rec_mono, gps)
    rms_rawt = _rms(rec_rawt, gps)
    fired = math.isfinite(rms_rawt) and rms_rawt >= RAW_WORSE_FACTOR * max(rms_mono, 1e-6)
    return fired, (f"raw-t join rms={rms_rawt:.3f} vs t_mono rms={rms_mono:.4f} "
                   f"(>= {RAW_WORSE_FACTOR}x worse -> fired={fired})")


# --------------------------------------------------------------------- main
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy-run", default=os.path.join(ROOT, "logs",
                    "unreal-test-run_20260624_055244"),
                    help="A pre-t_mono run to prove wall_time fallback.")
    ap.add_argument("--json", default=os.path.join(
        ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports", "wp_20260629_result.json"))
    args = ap.parse_args()

    tmproot = tempfile.mkdtemp()
    rd, true_speed = make_run(os.path.join(tmproot, "main"))

    gates = []
    gates.append(("G1", "schema_t_mono_both_logs+manifest", *g1_schema(rd)))
    gates.append(("G2", "monotonic_and_run_relative", *g2_monotonic(rd)))
    gates.append(("G3", "one_timeline_while_raw_t_diverges", *g3_one_timeline(rd)))
    gates.append(("G4", "fidelity_prefers_t_mono+legacy_fallback", *g4_key_selection(rd, args.legacy_run)))
    gates.append(("G5", "canonical_join_accurate", *g5_canonical_accurate(rd, true_speed)))
    gates.append(("G6", "backcompat_t_mono_stripped", *g6_backcompat(rd)))

    controls = []
    controls.append(("N1", "backwards_t_mono_caught", *n1_break_mono(os.path.join(tmproot, "n1"))))
    controls.append(("N2", "desynced_t_mono_caught", *n2_desync(os.path.join(tmproot, "n2"))))
    controls.append(("N3", "raw_t_join_corrupts", *n3_rawt_corrupts(os.path.join(tmproot, "n3"), None)))

    print("verify_20260629 -- canonical run-clock (KI-024)\n")
    gp = 0
    for cid, name, ok, detail in gates:
        print(f"  [{'PASS' if ok else 'FAIL'}] {cid} {name}: {detail}")
        gp += 1 if ok else 0
    print()
    cf = 0
    for cid, name, fired, detail in controls:
        print(f"  [{'FIRED' if fired else 'MISS'}] {cid} {name}: {detail}")
        cf += 1 if fired else 0

    all_ok = (gp == len(gates) and cf == len(controls))
    print(f"\n  Gates {gp}/{len(gates)}  Controls {cf}/{len(controls)}  => {'PASS' if all_ok else 'FAIL'}")

    import json
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, "w") as f:
        json.dump({
            "packet": "WP-20260629",
            "title": "Canonical run-clock t_mono (closes KI-024)",
            "gates": {c: bool(o) for c, _, o, _ in gates},
            "gates_detail": {c: d for c, _, _, d in gates},
            "controls_fired": {c: bool(x) for c, _, x, _ in controls},
            "controls_detail": {c: d for c, _, _, d in controls},
            "gates_passed": gp, "gates_total": len(gates),
            "controls_fired_n": cf, "controls_total": len(controls),
            "verdict": "PASS" if all_ok else "FAIL",
        }, f, indent=2)
    print(f"  wrote {args.json}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
