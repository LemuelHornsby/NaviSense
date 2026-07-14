#!/usr/bin/env python3
"""Gate for WP-20260705 -- demo GO/NO-GO preflight (preflight_demo.py).

G1 preflight parses + exposes a pure decide(); GO/NO-GO logic is correct.
G2 e2e GO   -- a live preflight (--report-only) on the current green tree => GO,
               result json written with the expected keys.
G3 NO-GO    -- decide() flips to NO-GO on any single required failure (no false green).
G4 aggregation edge cases (empty => NO-GO; a non-required fail does NOT block).
G5 regression -- Z0 + verify_20260702b + verify_20260704 all exit 0.

Controls (must FIRE): N1 one failing required check detected; N2 empty checklist
detected NO-GO; N3 a GO result with a failing required check is impossible (guard).

stdlib-only. Exit 0 iff 5/5 gates PASS and 3/3 controls FIRE.
"""
from __future__ import annotations
import json, subprocess, sys, importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "NaviSense_UE5" / "Saved" / "NaviSense_Reports"


def _load():
    spec = importlib.util.spec_from_file_location("preflight_demo", ROOT / "preflight_demo.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _rc(pyfile, args=()):
    p = subprocess.run([sys.executable, str(pyfile), *args], cwd=str(ROOT),
                       capture_output=True, text=True, timeout=300)
    return p.returncode


def main():
    gates, controls = {}, {}
    pf = _load()

    # G1: decide() correctness
    all_ok = [{"name": "a", "passed": True}, {"name": "b", "passed": True}]
    d_go = pf.decide(all_ok)
    one_bad = [{"name": "a", "passed": True}, {"name": "b", "passed": False, "detail": "x"}]
    d_no = pf.decide(one_bad)
    gates["G1"] = (d_go["verdict"] == "GO" and d_go["go"] is True
                   and d_no["verdict"] == "NO-GO" and d_no["go"] is False
                   and "b" in d_no.get("failed", []))

    # G2: live e2e (report-only) on the current tree
    rc = _rc(ROOT / "preflight_demo.py", ["--report-only"])
    res_path = REPORTS / "demo_preflight_result.json"
    res = json.loads(res_path.read_text()) if res_path.exists() else {}
    keys_ok = all(k in res for k in ("verdict", "go", "checks", "reason", "packet"))
    # rc 0 <=> GO ; on a green tree we expect GO
    gates["G2"] = (rc == 0 and res.get("verdict") == "GO" and res.get("go") is True
                   and keys_ok and len(res.get("checks", [])) == 3)

    # G3: NO-GO path -- inject a failing required check
    inj = [{"name": "rebuild:x", "passed": False, "detail": "sim fail"},
           {"name": "ok", "passed": True}]
    d = pf.decide(inj)
    gates["G3"] = (d["verdict"] == "NO-GO" and d["go"] is False
                   and d["reason"].startswith("rebuild:x"))

    # G4: aggregation edge cases
    empty = pf.decide([])
    nonreq_fail = pf.decide([{"name": "req", "passed": True},
                             {"name": "opt", "passed": False, "required": False}])
    gates["G4"] = (empty["verdict"] == "NO-GO"
                   and nonreq_fail["verdict"] == "GO")

    # G5: regression
    z0 = _rc(ROOT / "Development" / "work_packets" / "WP_20260615_COMPILE_AUDIT" / "verify_compile_readiness.py")
    b = _rc(ROOT / "python" / "verify_20260702b.py")
    r704 = _rc(ROOT / "python" / "verify_20260704.py")
    gates["G5"] = (z0 == 0 and b == 0 and r704 == 0)

    # Controls
    controls["N1"] = pf.decide(one_bad)["go"] is False
    controls["N2"] = pf.decide([])["go"] is False
    # N3: a GO must never carry a failing required check
    controls["N3"] = pf.decide([{"name": "z", "passed": False}])["verdict"] != "GO"

    gp = sum(gates.values()); gt = len(gates)
    cf = sum(controls.values()); ct = len(controls)
    for k, v in gates.items():
        print(f"{'PASS' if v else 'FAIL'} {k}")
    for k, v in controls.items():
        print(f"{'FIRED' if v else 'MISS'} {k}")
    verdict = "PASS" if (gp == gt and cf == ct) else "FAIL"
    out = {"packet": "WP-20260705", "title": "Demo GO/NO-GO preflight",
           "gates": gates, "controls_fired": controls,
           "gates_passed": gp, "gates_total": gt,
           "controls_fired_n": cf, "controls_total": ct, "verdict": verdict}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "wp_20260705_result.json").write_text(json.dumps(out, indent=2))
    print(f"\n{verdict}  {gp}/{gt} gates + {cf}/{ct} controls")
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
