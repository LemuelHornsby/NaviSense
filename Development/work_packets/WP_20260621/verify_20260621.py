"""WP-20260621 verify harness -- runtime sea-state schedule (D3) + scenario registry (D6).

Auto-verifies the pure-Python features added this packet:
  * python/sea_state.py     ScheduledSeaState / parse_schedule (cross-faded, time-varying sea)
  * python/scenarios.py     named demo-scenario registry
  * python_listener.py      --sea-state-schedule / --scenario wiring + per-change event logging
  * python/build_evidence_pack.py   surfaces scenario + schedule (read-side)

No Unreal / no recompile. It proves the scheduler is EXACT at set-points, CONTINUOUS
in time (vs a naive hard-switch that jumps), DETERMINISTIC, tracks the schedule
DIRECTION (builds up / eases down), and stays byte-identical to calm for an SS0-only
schedule. Two integration gates drive the real listener headless: D3 (a single run
sweeps >=3 sea states, logged to events.csv + manifest) and D6 (the evidence pack
surfaces the scenario + schedule and still computes IMO KPIs).

Negative controls (fails on purpose, not just passes clean data):
  V1 rejects malformed schedules; V3 a hard-switch trips the continuity bound the
  cross-fade clears; V5 an EASING schedule's energy goes DOWN (opposite of a build).

Gates:
  V1  parse_schedule_valid_and_rejects_bad
  V2  exact_at_setpoints
  V3  continuity_no_jump_vs_hardswitch     (neg. control: hard-switch jumps)
  V4  deterministic_and_seeded
  V5  energy_tracks_schedule_direction     (neg. control: easing goes down)
  V6  ss0_only_calm_backcompat
  V7  scenario_registry_valid
  V8  listener_d3_runtime_switch           (headless end-to-end)
  V9  evidence_pack_surfaces_scenario_readonly
  V10 scheduled_turning_circle_imo_kpis     (D6: IMO KPIs + schedule line)

Usage:
    python Development/work_packets/WP_20260621/verify_20260621.py
    python Development/work_packets/WP_20260621/verify_20260621.py --json out.json
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import os
import socket
import subprocess
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "Development", "work_packets", "WP_20260620"))

from python.sea_state import (WaveField, ScheduledSeaState, parse_schedule,  # noqa: E402
                              make_scheduled_sea_state)
from python import scenarios as SC                                           # noqa: E402
import python.build_evidence_pack as bep                                     # noqa: E402
import verify_20260620 as v20                                               # noqa: E402

DEFAULT_RESULT = os.path.join(ROOT, "NaviSense_UE5", "Saved",
                              "NaviSense_Reports", "wp_20260621_result.json")
KNOWN_CONTROLLERS = {"demo", "turning_circle", "zigzag10", "zigzag20",
                     "keyboard", "gamepad", "waypoint", "nmpc", "ppo"}


def _rms(samples):
    samples = list(samples)
    return (sum(x * x for x in samples) / len(samples)) ** 0.5 if samples else 0.0


def _elev_rms(field, lo, hi, step=0.5, e=0.0, n=0.0):
    return _rms(field.elevation(e, n, lo + i * step)
                for i in range(int((hi - lo) / step)))


def _heave_rms(rows, lo, hi):
    return _rms(r["heaveM"] for r in rows if lo <= r["t"] < hi)


def _collect_from_listener(extra_args, port, run_id, tmplog, max_t,
                           time_scale=80, hz=10, timeout=45):
    """Drive the real canonical listener headless: launch it, connect as the UE
    client would, read the wire until t>=max_t, return (rows, run_dir, manifest)."""
    proc = subprocess.Popen(
        [sys.executable, os.path.join(ROOT, "python_listener.py"),
         *extra_args, "--port", str(port), "--hz", str(hz),
         "--time-scale", str(time_scale), "--run-id", run_id,
         "--log-dir", tmplog, "--once"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    rows = []
    sock = None
    try:
        for _ in range(80):
            try:
                sock = socket.create_connection(("127.0.0.1", port), timeout=2.0)
                break
            except OSError:
                time.sleep(0.1)
        if not sock:
            raise RuntimeError("listener never accepted a connection")
        sock.settimeout(10.0)
        buf = b""
        last_t = -1.0
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                pkt = json.loads(line.decode("utf-8"))
                rows.append(pkt)
                last_t = pkt["t"]
            if last_t >= max_t:
                break
    finally:
        if sock:
            sock.close()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
    cand = sorted(glob.glob(os.path.join(tmplog, run_id + "_*")))
    run_dir = cand[-1] if cand else None
    man = {}
    if run_dir and os.path.exists(os.path.join(run_dir, "manifest.json")):
        man = json.load(open(os.path.join(run_dir, "manifest.json")))
    return rows, run_dir, man


def run() -> dict:
    g = v20.Gates()
    tmp = tempfile.mkdtemp(prefix="wp20260621_")
    try:
        # ---------- V1: parse valid, reject malformed (negative control) -----
        good = (parse_schedule("0:1, 90:4,180:6") == [(0.0, 1), (90.0, 4), (180.0, 6)])
        sortd = (parse_schedule("180:6, 0:1, 90:4") == [(0.0, 1), (90.0, 4), (180.0, 6)])
        bad = 0
        for spec in ["", "   ", "90", "90:99", "-5:3", "x:1", "90:-1"]:
            try:
                parse_schedule(spec)
            except ValueError:
                bad += 1
        g.check("V1", "parse_schedule_valid_and_rejects_bad",
                good and sortd and bad == 7,
                f"valid+sorted ok; rejected {bad}/7 malformed specs")

        # ---------- V2: scheduled == pure WaveField at each set-point ---------
        spec = "0:1, 90:4, 180:6"
        s = make_scheduled_sea_state(spec, heading_deg=90.0, seed=7)
        ok = True
        for t, ss in parse_schedule(spec):
            f = WaveField(sea_state=ss, heading_deg=90.0, seed=7)
            for (e, n) in [(0.0, 0.0), (13.0, -9.0)]:
                if abs(s.elevation(e, n, t) - f.elevation(e, n, t)) > 1e-9:
                    ok = False
        g.check("V2", "exact_at_setpoints", ok,
                "cross-faded elevation == pure WaveField(ss) at every set-point")

        # ---------- V3: continuity vs naive hard-switch (negative control) ---
        sc = make_scheduled_sea_state("0:2, 30:6", heading_deg=0.0, seed=7)
        fA = WaveField(sea_state=2, heading_deg=0.0, seed=7)
        fB = WaveField(sea_state=6, heading_deg=0.0, seed=7)
        hard = (lambda t: fA.elevation(0, 0, t) if t < 30.0 else fB.elevation(0, 0, t))
        cross_jump = abs(sc.elevation(0, 0, 30.0) - sc.elevation(0, 0, 30.0 - 1e-3))
        hard_jump = abs(hard(30.0) - hard(30.0 - 1e-3))
        g.check("V3", "continuity_no_jump_vs_hardswitch",
                cross_jump < 0.02 and hard_jump > cross_jump * 5.0,
                f"cross-fade boundary jump={cross_jump:.4f} m vs hard-switch={hard_jump:.4f} m")

        # ---------- V4: deterministic + actually seeded ----------------------
        s1 = make_scheduled_sea_state("0:3, 40:6", seed=11)
        s2 = make_scheduled_sea_state("0:3, 40:6", seed=11)
        s3 = make_scheduled_sea_state("0:3, 40:6", seed=99)
        pts = [(1.0, 2.0, 10.0), (5.0, 5.0, 35.0), (0.0, 0.0, 55.0)]
        same = all(s1.elevation(e, n, t) == s2.elevation(e, n, t) for (e, n, t) in pts)
        diff = any(abs(s1.elevation(e, n, t) - s3.elevation(e, n, t)) > 1e-9
                   for (e, n, t) in pts[:2])
        g.check("V4", "deterministic_and_seeded", same and diff,
                "same seed -> identical; different seed -> differs")

        # ---------- V5: energy tracks schedule direction (negative control) --
        build = make_scheduled_sea_state("0:1, 120:6", seed=7)
        ease = make_scheduled_sea_state("0:6, 120:1", seed=7)
        b_lo, b_hi = _elev_rms(build, 5, 25), _elev_rms(build, 95, 115)
        e_lo, e_hi = _elev_rms(ease, 5, 25), _elev_rms(ease, 95, 115)
        g.check("V5", "energy_tracks_schedule_direction",
                b_hi > b_lo * 2.0 and e_hi < e_lo * 0.5,
                f"build RMS {b_lo:.2f}->{b_hi:.2f} (up); ease {e_lo:.2f}->{e_hi:.2f} (down)")

        # ---------- V6: SS0-only schedule is byte-identical-calm --------------
        z = make_scheduled_sea_state("0:0, 100:0")
        zpts = [(1.0, 2.0, 3.0), (9.0, 9.0, 90.0), (0.0, 0.0, 150.0)]
        ok = ((not z.active)
              and all(z.elevation(e, n, t) == 0.0 for (e, n, t) in zpts)
              and all(z.slope_rad(e, n, t) == (0.0, 0.0) for (e, n, t) in zpts))
        g.check("V6", "ss0_only_calm_backcompat", ok,
                "active=False; elevation/slope==0 (rev<=1.3 / calm runs unaffected)")

        # ---------- V7: scenario registry integrity --------------------------
        ok = len(SC.list_scenarios()) >= 5
        for s_ in SC.list_scenarios():
            if s_.controller not in KNOWN_CONTROLLERS:
                ok = False
            if s_.sea_state_schedule:
                parse_schedule(s_.sea_state_schedule)  # raises if malformed
            if not (0 <= s_.sea_state <= 9):
                ok = False
        try:
            SC.get_scenario("definitely_not_a_scenario")
            rejected = False
        except KeyError:
            rejected = True
        g.check("V7", "scenario_registry_valid", ok and rejected,
                f"{len(SC.list_scenarios())} scenarios; controllers known; unknown rejected")

        # ---------- V8: listener end-to-end runtime switch (D3) ---------------
        rows, run_dir, man = _collect_from_listener(
            ["--scenario", "building_sea_transit"], port=5078,
            run_id="wp21v8", tmplog=tmp, max_t=185.0)
        he, hm, hl = (_heave_rms(rows, 5, 25), _heave_rms(rows, 85, 105),
                      _heave_rms(rows, 160, 180))
        events = [e for e in man.get("events", []) if e.get("name") == "sea_state_change"]
        states = sorted({int(e["details"].split("-> SS")[1].split(" ")[0]) for e in events})
        d3_ok = (len(rows) > 100 and he < hm < hl
                 and man.get("seaStateSchedule") == "0:1, 60:3, 120:5, 180:6"
                 and man.get("scenario") == "building_sea_transit"
                 and len(states) >= 3)
        g.check("V8", "listener_d3_runtime_switch", d3_ok,
                f"heave RMS {he:.2f}<{hm:.2f}<{hl:.2f}; logged states {states} (>=3)")

        # ---------- V9: evidence pack surfaces scenario+schedule, read-only ---
        if run_dir:
            sp = os.path.join(run_dir, "state.csv")
            before = hashlib.sha256(open(sp, "rb").read()).hexdigest()
            res = bep.build_pack(run_dir, make_plots=False)
            after = hashlib.sha256(open(sp, "rb").read()).hexdigest()
            meta = res["kpis"]["meta"]
            md = open(os.path.join(res["pack_dir"], "EVIDENCE.md"), encoding="utf-8").read()
            health = res["kpis"]["health"]
            v9_ok = (meta.get("scenario") == "building_sea_transit"
                     and meta.get("sea_state_schedule") == "0:1, 60:3, 120:5, 180:6"
                     and "Runtime sea-state schedule" in md
                     and "building_sea_transit" in md
                     and health.get("verdict") == "PASS"
                     and before == after)
            g.check("V9", "evidence_pack_surfaces_scenario_readonly", v9_ok,
                    f"scenario+schedule in pack; health={health.get('verdict')}; "
                    f"state.csv {'unchanged' if before == after else 'MUTATED'}")
        else:
            g.check("V9", "evidence_pack_surfaces_scenario_readonly", False,
                    "no run_dir from V8")

        # ---------- V10: scheduled turning_circle -> IMO KPIs + schedule -----
        man10 = v20._manifest("turning_circle")
        man10["seaStateSchedule"] = "0:0, 120:4"
        man10["scenario"] = "custom_sched_turn"
        d10 = v20._write_run(tmp, "sched_turn", v20._good_turn(turn_deg=270.0), man10)
        res10 = bep.build_pack(d10, make_plots=False)
        mv = res10["kpis"]["maneuver"]
        meta10 = res10["kpis"]["meta"]
        md10 = open(os.path.join(res10["pack_dir"], "EVIDENCE.md"), encoding="utf-8").read()
        v10_ok = (mv.get("kind") == "turning_circle"
                  and mv.get("advance_m") is not None
                  and mv.get("tactical_diameter_m") is not None
                  and meta10.get("sea_state_schedule") == "0:0, 120:4"
                  and "Runtime sea-state schedule" in md10)
        g.check("V10", "scheduled_turning_circle_imo_kpis", v10_ok,
                f"advance={mv.get('advance_m')} DT={mv.get('tactical_diameter_m')}; schedule surfaced")
    finally:
        # tmp is in the sandbox (/tmp), not on D:, so it cleans up fine.
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    verdict = "PASS" if g.passed == g.total else "FAIL"
    print(f"\n  {g.passed}/{g.total} gates => {verdict}")
    return {"gates": g.results, "gates_passed": g.passed,
            "gates_total": g.total, "verdict": verdict}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", default=DEFAULT_RESULT,
                   help=f"Result JSON path (default: {DEFAULT_RESULT}).")
    args = p.parse_args()
    print("WP-20260621 verify -- runtime sea-state schedule (D3) + scenario registry (D6)\n")
    res = run()
    payload = {
        "packet": "WP-20260621 (2026-06-21)",
        "theme": "Runtime sea-state schedule (D3) + named-scenario registry (D6)",
        "kind": "pure-Python; rides existing heaveM/rollDeg/pitchDeg wire keys; "
                "NO recompile, NO DTO/wire/schema change, NO new in-engine gate",
        "date": "2026-06-21",
        "tester": "Claude (sandbox, headless)",
        "gates": {r["id"] + "_" + r["name"]: r["status"] for r in res["gates"]},
        "gate_details": res["gates"],
        "gates_passed": res["gates_passed"],
        "gates_total": res["gates_total"],
        "auto_result": res["verdict"],
    }
    try:
        with open(args.json, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"\n[verify] wrote {args.json}")
    except OSError as e:
        print(f"\n[verify] could not write {args.json}: {e}")
    sys.exit(0 if res["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
