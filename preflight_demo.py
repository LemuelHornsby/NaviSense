#!/usr/bin/env python3
"""NaviSense demo GO / NO-GO preflight (WP-20260705).

ONE command Lemuel runs right before the single demo-critical in-engine session
(the C++ rebuild + PIE run described in
Development/work_packets/PENDING_EDITOR_GATES.md). It re-confirms, on TODAY's disk,
that:

  A. REBUILD-SAFETY  -- the stacked 28 Jun -> 2 Jul C++ still compiles + links:
       * Z0 compile-readiness audit                 (16/16 invariants/includes)
       * verify_20260702b  (stacked link audit)     (all UFUNCTION decls defined,
                                                      Build.cs module deps present)
  B. STORYLINE READY  -- the headless demo storyline still scores DEMO READY:
       * demo_rehearsal.py  -> demo_readiness.json  (overall_ready == True)

It RE-RUNS the already-verified tools and only READS their verdicts; it re-derives
no physics of its own, so it cannot drift from them. It aggregates to a single
GO / NO-GO and writes NaviSense_Reports/demo_preflight_result.json.

GO here means the HEADLESS tree is safe to rebuild and the storyline is green -- it
does NOT confirm the in-engine demo (the G_*_UE eye-checks in PENDING_EDITOR_GATES.md
remain). NO-GO means fix the flagged check BEFORE burning the PIE session.

stdlib-only (matches repro_doctor.py). Exit 0 = GO, 1 = NO-GO.
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "NaviSense_UE5" / "Saved" / "NaviSense_Reports"
Z0 = ROOT / "Development" / "work_packets" / "WP_20260615_COMPILE_AUDIT" / "verify_compile_readiness.py"
LINK_AUDIT = ROOT / "python" / "verify_20260702b.py"
REHEARSAL = ROOT / "demo_rehearsal.py"
READINESS_JSON = ROOT / "logs" / "_rehearsal" / "demo_readiness.json"
READINESS_JSON_ALT = REPORTS / "demo_readiness.json"
RESULT = REPORTS / "demo_preflight_result.json"


def decide(checks):
    """Pure aggregation: GO iff every REQUIRED check passed. Empty => NO-GO."""
    required = [c for c in checks if c.get("required", True)]
    if not required:
        return {"verdict": "NO-GO", "go": False,
                "reason": "no required checks evaluated"}
    failed = [c for c in required if not c.get("passed")]
    if failed:
        first = failed[0]
        return {"verdict": "NO-GO", "go": False,
                "reason": f"{first['name']}: {first.get('detail', 'failed')}",
                "failed": [c["name"] for c in failed]}
    return {"verdict": "GO", "go": True, "reason": "all required checks passed"}


def _run(pyfile, args, timeout):
    if not Path(pyfile).exists():
        return 127, f"missing tool: {pyfile}"
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, str(pyfile), *args],
                           cwd=str(ROOT), capture_output=True, text=True,
                           timeout=timeout)
        return p.returncode, f"rc={p.returncode} ({time.time()-t0:.1f}s)"
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"


def _readiness_verdict():
    for j in (READINESS_JSON, READINESS_JSON_ALT):
        if j.exists():
            try:
                d = json.loads(j.read_text())
                return bool(d.get("overall_ready")), d.get("verdict", "?"), d.get("generated_at", "?")
            except Exception as e:  # noqa
                return False, f"unreadable ({e})", "?"
    return False, "no demo_readiness.json", "?"


def run_preflight(rehearse_mode="fast"):
    checks = []

    # A. rebuild-safety
    rc, det = _run(Z0, [], 180)
    checks.append({"name": "rebuild:Z0_compile_readiness", "passed": rc == 0,
                   "detail": det, "group": "rebuild-safety"})
    rc, det = _run(LINK_AUDIT, [], 180)
    checks.append({"name": "rebuild:stacked_link_audit", "passed": rc == 0,
                   "detail": det, "group": "rebuild-safety"})

    # B. storyline readiness
    if rehearse_mode == "report-only":
        rc, det = _run(REHEARSAL, ["--report-only"], 120)
    elif rehearse_mode == "full":
        rc, det = _run(REHEARSAL, ["--no-plot"], 600)
    else:  # fast (default)
        rc, det = _run(REHEARSAL, ["--fast", "--no-plot"], 300)
    ready, verdict, gen = _readiness_verdict()
    checks.append({"name": "storyline:demo_rehearsal",
                   "passed": (rc == 0) and ready,
                   "detail": f"{det}; verdict={verdict}; generated={gen}",
                   "group": "storyline"})

    result = decide(checks)
    result.update({
        "packet": "WP-20260705",
        "title": "Demo GO/NO-GO preflight",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rehearse_mode": rehearse_mode,
        "checks": checks,
        "note": ("GO = headless tree is rebuild-safe + storyline DEMO READY. "
                 "Does NOT confirm the in-engine demo; the G_*_UE eye-checks in "
                 "Development/work_packets/PENDING_EDITOR_GATES.md remain."),
    })
    return result


def _print(result):
    print("=" * 64)
    print(f"NaviSense demo preflight -- {result['verdict']}")
    print("=" * 64)
    for c in result["checks"]:
        mark = "OK " if c["passed"] else "XX "
        print(f"  [{mark}] {c['name']:<34} {c['detail']}")
    print("-" * 64)
    print(f"  verdict : {result['verdict']}  ({result['reason']})")
    if result["go"]:
        print("  next    : Development/work_packets/PENDING_EDITOR_GATES.md is the "
              "source of truth for what's left -- check its header for the current "
              "Step 0 (rebuild) status BEFORE rebuilding again (it is a ONE-TIME "
              "action once cleared); otherwise proceed with the next open step.")
    else:
        print("  next    : FIX the flagged check BEFORE the PIE session "
              "(do not burn the in-engine slot on a NO-GO tree).")
    print("=" * 64)


def main():
    ap = argparse.ArgumentParser(description="NaviSense demo GO/NO-GO preflight.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--report-only", action="store_true",
                   help="Aggregate the latest existing rehearsal (fastest; may be stale).")
    g.add_argument("--full", action="store_true",
                   help="Re-run the full 4-scenario rehearsal (slowest, most thorough).")
    args = ap.parse_args()
    mode = "report-only" if args.report_only else "full" if args.full else "fast"

    result = run_preflight(mode)
    REPORTS.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(result, indent=2))
    _print(result)
    print(f"[preflight] wrote {RESULT}")
    sys.exit(0 if result["go"] else 1)


if __name__ == "__main__":
    main()
