#!/usr/bin/env python3
"""WP-20260707 verify -- demo-week hold-the-line (T-4).

Pure read/aggregate: confirms today's preflight verdict == GO and that the two
current stacked regression verifies exit 0. Re-derives nothing, so it cannot drift
from the tools it reads. Writes Saved/NaviSense_Reports/wp_20260707_result.json.
Exit 0 = PASS, 1 = FAIL.
"""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "NaviSense_UE5" / "Saved" / "NaviSense_Reports"


def _run(py_rel):
    p = subprocess.run([sys.executable, str(ROOT / py_rel)],
                       capture_output=True, text=True)
    return p.returncode


def main():
    checks = []

    # G1 -- today's preflight verdict must be GO (freshly written by preflight_demo.py)
    pf = REPORTS / "demo_preflight_result.json"
    verdict = None
    if pf.exists():
        try:
            verdict = json.loads(pf.read_text(encoding="utf-8")).get("verdict")
        except Exception:
            verdict = None
    g1 = verdict == "GO"
    checks.append({"id": "G1", "name": "preflight verdict == GO", "pass": g1,
                   "detail": f"verdict={verdict}"})

    # G2 -- regression: the two current stacked verifies exit 0
    rc_link = _run("python/verify_20260702b.py")
    rc_rehearsal = _run("python/verify_20260704.py")
    g2 = rc_link == 0 and rc_rehearsal == 0
    checks.append({"id": "G2", "name": "regression verify_20260702b + verify_20260704 exit 0",
                   "pass": g2, "detail": f"link_rc={rc_link} rehearsal_rc={rc_rehearsal}"})

    ok = g1 and g2
    result = {
        "packet": "WP-20260707",
        "date": "2026-07-07",
        "go": ok,
        "checks": checks,
        "regression": {"verify_20260702b": rc_link, "verify_20260704": rc_rehearsal},
        "note": ("GO = headless tree rebuild-safe + storyline green on today's disk. "
                 "Does NOT confirm the in-engine demo; G_*_UE eye-checks remain. T-4 to 11 Jul."),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "wp_20260707_result.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    passed = sum(1 for c in checks if c["pass"])
    print(f"WP-20260707 verify -- {'PASS' if ok else 'FAIL'} {passed}/{len(checks)} gates")
    for c in checks:
        print(f"  [{'OK ' if c['pass'] else 'FAIL'}] {c['id']} {c['name']} :: {c['detail']}")
    print(f"wrote {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
