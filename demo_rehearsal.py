#!/usr/bin/env python3
"""demo_rehearsal.py -- NaviSense headless DEMO-READINESS rehearsal harness.

Work packet WP-20260704. De-risks the 11 Jul 2026 demo.

WHY THIS EXISTS
  run_demo.py runs ONE scenario end-to-end. With the whole in-engine queue
  stacked behind a single C++ rebuild, the last-week risk is *drift*: a change
  that quietly breaks one of the scenarios the live demo will show. This harness
  runs the whole DEMO STORYLINE headless (each scenario via `run_demo.py
  --selftest`, no Unreal / no GPU), reads each run's evidence pack, and reduces
  the lot to ONE objective **DEMO READY / NOT READY** verdict + a per-scenario,
  per-gate readiness matrix. Run it nightly / before every in-engine session.

WHAT IT CHECKS PER SCENARIO (from the already-verified evidence pack -- it
re-derives nothing itself, so it cannot drift from the tools):
  * the run was logged and run_demo exited 0 (preflight + pack + health),
  * `health.verdict == PASS` (verify_run_kinematics gate),
  * for IMO maneuvering scenarios: the IMO KPI pass flags are True,
  * for COLREGS scenarios: the conformance verdict matches the expectation.

Pure orchestration over the existing, verified tools (run_demo -> listener ->
client -> build_evidence_pack -> verify_run_kinematics). NO wire / schema / C++
change. Removing it cannot affect a run.

USAGE
  python demo_rehearsal.py                 # full storyline, headless
  python demo_rehearsal.py --fast          # 2-scenario smoke (turning + head-on)
  python demo_rehearsal.py --scenarios imo_turning_circle,colregs_head_on
  python demo_rehearsal.py --no-plot       # faster (skip evidence-pack plots)

EXIT CODE: 0 iff every REQUIRED storyline scenario is READY. Non-zero otherwise.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time
from typing import Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "python"
RUN_DEMO = os.path.join(ROOT, "run_demo.py")
PYDIR = os.path.join(ROOT, "python")
DEFAULT_LOG_DIR = os.path.join(ROOT, "logs", "_rehearsal")
DEFAULT_JSON = os.path.join(ROOT, "NaviSense_UE5", "Saved",
                            "NaviSense_Reports", "demo_readiness.json")

# ---------------------------------------------------------------------------
# The DEMO STORYLINE -- the scenarios the 11 Jul live demo will actually show,
# each tagged with the demo gate(s) it exercises and its pass expectation.
# `required=False` scenarios are rehearsed + reported but do not gate the
# overall verdict (spare / stretch footage).
# ---------------------------------------------------------------------------
DEMO_STORYLINE: List[dict] = [
    {"scenario": "imo_turning_circle", "gates": ["D1", "D6"],
     "expect": {"health": True,
                "imo": ["imo_tactical_diameter_pass", "imo_advance_pass"]},
     "required": True,
     "note": "IMO turning circle, calm -- advance / tactical-diameter KPIs."},
    {"scenario": "imo_zigzag10", "gates": ["D1", "D6"],
     "expect": {"health": True,
                "imo": ["imo_first_overshoot_pass", "imo_second_overshoot_pass"]},
     "required": True,
     "note": "IMO 10/10 zig-zag, calm -- 1st/2nd overshoot KPIs."},
    {"scenario": "building_sea_transit", "gates": ["D2", "D3"],
     "expect": {"health": True},
     "required": True,
     "note": "Runtime sea-state sweep SS1->SS6 in one run (D3 runtime switch)."},
    {"scenario": "colregs_head_on", "gates": ["D4"],
     "expect": {"health": True, "conformance": "compliant"},
     "required": True,
     "note": "COLREGS Rule 14 head-on, scripted starboard avoidance -- scored."},
]

FAST_SUBSET = ["imo_turning_circle", "colregs_head_on"]


def _say(msg: str) -> None:
    print(f"[rehearsal] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Evaluation -- reads a run's evidence pack and scores it against expectations.
# Kept as a pure function of (kpis, expect) so the verifier can unit-test it.
# ---------------------------------------------------------------------------
def evaluate_kpis(kpis: Optional[dict], expect: dict) -> Tuple[bool, List[dict]]:
    """Return (ready, checks). Each check = {name, status(bool), detail}."""
    checks: List[dict] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "status": bool(ok), "detail": detail})

    if not kpis:
        add("evidence_pack", False, "no kpis.json (pack not built / no run)")
        return False, checks
    add("evidence_pack", True, "kpis.json present")

    if expect.get("health"):
        verdict = ((kpis.get("health") or {}).get("verdict"))
        add("health", verdict == "PASS", f"health.verdict={verdict}")

    for key in expect.get("imo", []):
        val = (kpis.get("maneuver") or {}).get(key)
        add(f"imo:{key}", val is True, f"{key}={val}")

    want = expect.get("conformance")
    if want:
        conf = (kpis.get("ais") or {}).get("conformance") or {}
        comp = conf.get("compliant", 0)
        noncomp = conf.get("non_compliant", 0)
        if want == "compliant":
            ok = (noncomp == 0 and comp >= 1)
        elif want == "non_compliant":
            ok = (noncomp >= 1)
        else:  # exact-verdict match on every scored target
            verdicts = [t.get("verdict") for t in conf.get("targets", [])]
            ok = bool(verdicts) and all(v == want for v in verdicts)
        add("conformance", ok,
            f"want={want} compliant={comp} non_compliant={noncomp}")

    ready = all(c["status"] for c in checks)
    return ready, checks


# ---------------------------------------------------------------------------
# Run one scenario end-to-end via run_demo.py --selftest, then locate its run.
# ---------------------------------------------------------------------------
def run_scenario(scenario: str, log_dir: str, plots: bool,
                 seconds: float, send_hz: float,
                 timeout: float = 600.0) -> Tuple[int, Optional[str], Optional[dict]]:
    os.makedirs(log_dir, exist_ok=True)
    run_id = f"demo-{scenario}"
    pre = set(glob.glob(os.path.join(log_dir, f"{run_id}_*")))
    cmd = [PY, "-u", RUN_DEMO, "--scenario", scenario, "--selftest",
           "--log-dir", log_dir, "--seconds", f"{seconds:g}",
           "--send-hz", f"{send_hz:g}"]
    if not plots:
        cmd.append("--no-plot")
    env = dict(os.environ, PYTHONUNBUFFERED="1", MPLBACKEND="Agg")
    try:
        rc = subprocess.call(cmd, cwd=ROOT, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, None, None
    # newest run dir that appeared during THIS run (never reuse a stale one)
    fresh = [d for d in glob.glob(os.path.join(log_dir, f"{run_id}_*"))
             if os.path.isdir(d) and d not in pre]
    run_dir = max(fresh, key=os.path.getmtime) if fresh else None
    kpis = None
    if run_dir:
        kj = os.path.join(run_dir, "evidence_pack", "kpis.json")
        if os.path.isfile(kj):
            try:
                with open(kj) as fh:
                    kpis = json.load(fh)
            except Exception:
                kpis = None
    return rc, run_dir, kpis


# ---------------------------------------------------------------------------
# Rehearse a storyline -> a structured readiness result.
# ---------------------------------------------------------------------------
def overall_ready(results: List[dict]) -> bool:
    """DEMO READY iff every REQUIRED scenario in the results is ready.
    Single source of the aggregation rule (rehearse + the verifier use it)."""
    required = [r for r in results if r.get("required", True)]
    return bool(required) and all(r.get("ready") for r in required)


def _looks_truncated(rc: int, run_dir: Optional[str], kpis: Optional[dict],
                     expect: dict) -> bool:
    """True when a not-ready result looks like a wall-clock-STARVED / truncated
    self-test run (KI-012) rather than a deterministic content failure -- i.e.
    worth retrying. We retry a flaky launch (no run / no pack) and an IMO
    maneuver whose KPIs came back None (the turn never reached 180 deg because
    the 14s wall-clock window was CPU-starved). We do NOT retry a genuine
    content failure (health FAIL, a wrong conformance verdict) -- those are
    deterministic and would just loop."""
    if run_dir is None or not kpis:
        return True
    man = kpis.get("maneuver") or {}
    for key in expect.get("imo", []):
        if man.get(key) is None:
            return True
    return False


def rehearse(storyline: List[dict], log_dir: str, plots: bool,
             seconds: float, send_hz: float, retries: int = 2) -> dict:
    results: List[dict] = []
    for item in storyline:
        scenario = item["scenario"]
        _say(f"--- {scenario}  (gates {'/'.join(item.get('gates', []))}) ---")
        attempt = 0
        while True:
            attempt += 1
            t0 = time.time()
            rc, run_dir, kpis = run_scenario(scenario, log_dir, plots,
                                             seconds, send_hz)
            ok_pack, checks = evaluate_kpis(kpis, item.get("expect", {}))
            # run_demo's own exit code (0 = preflight + pack + health) is a check too
            checks.insert(0, {"name": "run_demo_exit",
                              "status": rc == 0, "detail": f"rc={rc}"})
            ready = (rc == 0) and ok_pack
            dt = time.time() - t0
            if ready or attempt > retries or not _looks_truncated(
                    rc, run_dir, kpis, item.get("expect", {})):
                break
            _say(f"    NOT READY on attempt {attempt} -- looks like a truncated / "
                 f"CPU-starved self-test run (KI-012 wall-clock sim); "
                 f"retrying ({attempt}/{retries})")
        if attempt > 1:
            _say(f"    [retry] '{scenario}' settled after {attempt} attempt(s)")
        _say(f"    {'READY' if ready else 'NOT READY'} "
             f"({dt:.0f}s, {os.path.basename(run_dir) if run_dir else 'no run'})")
        for c in checks:
            print(f"      [{'ok' if c['status'] else 'XX'}] "
                  f"{c['name']:32s} {c['detail']}")
        results.append({
            "scenario": scenario,
            "gates": item.get("gates", []),
            "required": item.get("required", True),
            "note": item.get("note", ""),
            "ready": ready,
            "attempts": attempt,
            "run_dir": os.path.basename(run_dir) if run_dir else None,
            "checks": checks,
            "elapsed_s": round(dt, 1),
        })

    return _assemble(results)


def _read_kpis(run_dir: str):
    """Return the parsed evidence-pack kpis.json for a run, or None if the pack
    is absent / unparseable (i.e. the run is incomplete)."""
    kj = os.path.join(run_dir, "evidence_pack", "kpis.json")
    if not os.path.isfile(kj):
        return None
    try:
        with open(kj) as fh:
            return json.load(fh)
    except Exception:
        return None


def _latest_run(scenario: str, log_dir: str):
    run_id = f"demo-{scenario}"
    dirs = [d for d in glob.glob(os.path.join(log_dir, f"{run_id}_*"))
            if os.path.isdir(d)]
    if not dirs:
        return None, None
    dirs.sort(key=os.path.getmtime, reverse=True)  # newest first
    # KI-030: prefer the newest run that has a COMPLETE evidence pack
    # (kpis.json present + parseable). An interrupted newer run (crash / Ctrl-C /
    # killed mid-pack) leaves no kpis.json and must NOT shadow a good earlier run
    # and flip the whole preflight to a false NOT READY. If NO run is complete we
    # still surface the newest one (kpis=None) so the honest NOT READY stands.
    for run_dir in dirs:
        kpis = _read_kpis(run_dir)
        if kpis is not None:
            return run_dir, kpis
    return dirs[0], None


def rehearse_report_only(storyline: List[dict], log_dir: str) -> dict:
    """Aggregate the LATEST existing run per scenario -- no runs executed.
    Use after driving each scenario, or for a nightly re-report."""
    results: List[dict] = []
    for item in storyline:
        scenario = item["scenario"]
        run_dir, kpis = _latest_run(scenario, log_dir)
        ok_pack, checks = evaluate_kpis(kpis, item.get("expect", {}))
        checks.insert(0, {"name": "run_present",
                          "status": run_dir is not None,
                          "detail": os.path.basename(run_dir) if run_dir
                          else "no prior run in log-dir"})
        ready = (run_dir is not None) and ok_pack
        results.append({
            "scenario": scenario, "gates": item.get("gates", []),
            "required": item.get("required", True), "note": item.get("note", ""),
            "ready": ready,
            "run_dir": os.path.basename(run_dir) if run_dir else None,
            "checks": checks, "elapsed_s": 0.0,
        })
    return _assemble(results)


def _assemble(results: List[dict]) -> dict:
    overall = overall_ready(results)
    required = [r for r in results if r["required"]]
    gates_covered = sorted({g for r in results if r["ready"] for g in r["gates"]})
    return {
        "packet": "WP-20260704",
        "title": "Headless demo-readiness rehearsal harness",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "storyline_size": len(results),
        "required_size": len(required),
        "ready_count": sum(1 for r in required if r["ready"]),
        "gates_covered_headless": gates_covered,
        "verdict": "DEMO READY" if overall else "NOT READY",
        "overall_ready": overall,
        "scenarios": results,
    }


def write_reports(result: dict, json_out: str, md_out: str) -> None:
    os.makedirs(os.path.dirname(json_out), exist_ok=True)
    with open(json_out, "w") as fh:
        json.dump(result, fh, indent=2)
    lines: List[str] = []
    lines.append("# NaviSense demo-readiness rehearsal")
    lines.append("")
    lines.append(f"**Generated:** {result['generated_at']} · "
                 f"**Verdict:** {result['verdict']} · "
                 f"ready {result['ready_count']}/{result['required_size']} "
                 f"required · gates covered headless: "
                 f"{', '.join(result['gates_covered_headless']) or '-'}")
    lines.append("")
    lines.append("> Headless (`run_demo --selftest`, no Unreal). In-engine "
                 "eye-checks (G_*_UE) are tracked separately in "
                 "`Development/work_packets/PENDING_EDITOR_GATES.md`.")
    lines.append("")
    lines.append("| Scenario | Gates | Required | Ready | Run | Notes |")
    lines.append("|---|---|---|---|---|---|")
    for r in result["scenarios"]:
        fails = [c["name"] for c in r["checks"] if not c["status"]]
        note = r["note"] if r["ready"] else ("FAILED: " + ", ".join(fails))
        lines.append(
            f"| {r['scenario']} | {'/'.join(r['gates'])} | "
            f"{'yes' if r['required'] else 'no'} | "
            f"{'READY' if r['ready'] else 'NOT READY'} | "
            f"{r['run_dir'] or '-'} | {note} |")
    lines.append("")
    with open(md_out, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def resolve_storyline(scenarios_arg: Optional[str], fast: bool) -> List[dict]:
    if scenarios_arg:
        want = [s.strip() for s in scenarios_arg.split(",") if s.strip()]
    elif fast:
        want = FAST_SUBSET
    else:
        return list(DEMO_STORYLINE)
    by_name = {item["scenario"]: item for item in DEMO_STORYLINE}
    out: List[dict] = []
    for name in want:
        if name in by_name:
            out.append(by_name[name])
        else:  # not in the curated storyline -> health-only expectation
            out.append({"scenario": name, "gates": [], "expect": {"health": True},
                        "required": True, "note": "(ad-hoc, health-only)"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="NaviSense headless demo-readiness rehearsal.")
    ap.add_argument("--scenarios", default=None,
                    help="Comma-separated scenario override.")
    ap.add_argument("--fast", action="store_true",
                    help="2-scenario smoke (turning circle + head-on).")
    ap.add_argument("--log-dir", default=DEFAULT_LOG_DIR)
    ap.add_argument("--json-out", default=DEFAULT_JSON)
    ap.add_argument("--md-out", default=None,
                    help="Default: <log-dir>/DEMO_READINESS.md")
    ap.add_argument("--no-plot", action="store_true")
    ap.add_argument("--report-only", action="store_true",
                    help="Aggregate latest existing runs; run nothing.")
    ap.add_argument("--seconds", type=float, default=14.0)
    ap.add_argument("--send-hz", type=float, default=5.0)
    ap.add_argument("--retries", type=int, default=2,
                    help="Retries per scenario on a truncated/starved run "
                         "(KI-012). Default 2 (=> up to 3 attempts).")
    args = ap.parse_args()

    storyline = resolve_storyline(args.scenarios, args.fast)
    # validate scenario names against the registry before running anything
    if PYDIR not in sys.path:
        sys.path.insert(0, PYDIR)
    import scenarios as _sc
    unknown = [it["scenario"] for it in storyline
               if it["scenario"] not in {s.name for s in _sc.list_scenarios()}]
    if unknown:
        _say(f"unknown scenario(s): {', '.join(unknown)}")
        return 2

    log_dir = os.path.abspath(args.log_dir)
    md_out = args.md_out or os.path.join(log_dir, "DEMO_READINESS.md")
    if args.report_only:
        _say(f"report-only: aggregating latest runs in {log_dir}")
        result = rehearse_report_only(storyline, log_dir)
    else:
        _say(f"rehearsing {len(storyline)} scenario(s) -> {log_dir}")
        result = rehearse(storyline, log_dir, plots=not args.no_plot,
                          seconds=args.seconds, send_hz=args.send_hz,
                          retries=args.retries)
    write_reports(result, os.path.abspath(args.json_out), os.path.abspath(md_out))

    print("\n" + "=" * 64)
    _say(f"{result['verdict']} "
         f"({result['ready_count']}/{result['required_size']} required ready; "
         f"gates {', '.join(result['gates_covered_headless']) or '-'})")
    _say(f"report: {md_out}")
    print("=" * 64)
    return 0 if result["overall_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
