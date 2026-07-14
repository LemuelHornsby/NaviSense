#!/usr/bin/env python3
"""verify_20260711.py -- WP-20260711 T-0 demo-day final GO gate (TC-50).

Demo day (11 Jul 2026). No product code changes today by design: this gate
re-proves, FRESH on the day, that the headless tree is GO and that the live
run sheet (PENDING_EDITOR_GATES.md) is current, so Lemuel's ONE live session
(Steps 0-6) starts from a verified baseline.

Gates (live, no fixtures):
  G1  Z0 compile-readiness rc==0 AND result json 16/16
  G2  stacked link audit verify_20260702b rc==0
  G3  preflight_demo --report-only rc==0 AND result json verdict GO
  G4  run-sheet currency: PENDING_EDITOR_GATES.md still carries the Step-0
      KI-034 re-open marker + Step 5 (run_colregs) + Step 6 (verify_demo_session)
  G5  pytest 10 passed (mmg + python suites; UE5/editor trees excluded)

Negative controls (isolated tmp fixtures -- prove the checkers can fail):
  N1  a run sheet stripped of the Step-0/5/6 markers is REJECTED
  N2  a preflight result json with verdict NO-GO is REJECTED
  N3  a Z0 result json with 15/16 is REJECTED

Exit 0 iff G1-G5 all PASS and N1-N3 all FIRE.
Writes NaviSense_UE5/Saved/NaviSense_Reports/wp_20260711_result.json
"""
import json, os, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports")
RUNSHEET = os.path.join(ROOT, "Development", "work_packets", "PENDING_EDITOR_GATES.md")
Z0 = os.path.join(ROOT, "Development", "work_packets", "WP_20260615_COMPILE_AUDIT",
                  "verify_compile_readiness.py")
PY = sys.executable

RUNSHEET_MARKERS = [
    "RE-OPENED 9 Jul",              # Step 0: KI-034 Live Coding recompile still pending
    "run_colregs.py --head-on",     # Step 5 present
    "verify_demo_session.py",       # Step 6 present
]

def _run(args, timeout=240):
    p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout + p.stderr

def check_z0_json(path):
    """True iff the Z0 result file reports 16/16 passed (dict schema)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return False
    checks = d.get("checks", {})
    if not isinstance(checks, dict):
        return False
    n_pass = sum(1 for c in checks.values()
                 if isinstance(c, dict) and c.get("pass") is True)
    return len(checks) == 16 and n_pass == 16

def check_preflight_json(path):
    """True iff the preflight result file verdict is GO."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return False
    return str(d.get("verdict", "")).strip().upper() == "GO"

def check_runsheet(path):
    """True iff every currency marker is present in the run sheet."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return False
    return all(m in text for m in RUNSHEET_MARKERS)

def main():
    t0 = time.time()
    gates, controls = [], []

    # G1 -- Z0 fresh
    rc, _ = _run([PY, Z0])
    z0_json = os.path.join(REPORTS, "wp_20260615_compile_audit_result.json")
    g1 = (rc == 0) and check_z0_json(z0_json)
    gates.append(("G1_Z0_16_16", g1))

    # G2 -- stacked link audit fresh
    rc, _ = _run([PY, os.path.join(ROOT, "python", "verify_20260702b.py")])
    gates.append(("G2_link_audit", rc == 0))

    # G3 -- preflight fresh, verdict GO
    rc, _ = _run([PY, os.path.join(ROOT, "preflight_demo.py"), "--report-only"])
    pf_json = os.path.join(REPORTS, "demo_preflight_result.json")
    g3 = (rc == 0) and check_preflight_json(pf_json)
    gates.append(("G3_preflight_GO", g3))

    # G4 -- run sheet current
    gates.append(("G4_runsheet_current", check_runsheet(RUNSHEET)))

    # G5 -- pytest
    rc, out = _run([PY, "-m", "pytest", ".", "-q",
                    "--ignore=NaviSense_UE5", "--ignore=.venv"])
    g5 = (rc == 0) and ("10 passed" in out)
    gates.append(("G5_pytest_10", g5))

    # Negative controls on tmp fixtures
    with tempfile.TemporaryDirectory() as td:
        # N1 tampered run sheet
        with open(RUNSHEET, "r", encoding="utf-8") as f:
            sheet = f.read()
        for m in RUNSHEET_MARKERS:
            sheet = sheet.replace(m, "")
        bad_sheet = os.path.join(td, "sheet.md")
        with open(bad_sheet, "w", encoding="utf-8") as f:
            f.write(sheet)
        controls.append(("N1_tampered_runsheet_rejected", not check_runsheet(bad_sheet)))

        # N2 NO-GO preflight json
        bad_pf = os.path.join(td, "pf.json")
        with open(bad_pf, "w", encoding="utf-8") as f:
            json.dump({"verdict": "NO-GO"}, f)
        controls.append(("N2_nogo_preflight_rejected", not check_preflight_json(bad_pf)))

        # N3 15/16 Z0 json
        with open(z0_json, "r", encoding="utf-8") as f:
            zd = json.load(f)
        zchecks = zd.get("checks", {})
        first = next(iter(zchecks))
        zchecks[first]["pass"] = False
        bad_z0 = os.path.join(td, "z0.json")
        with open(bad_z0, "w", encoding="utf-8") as f:
            json.dump(zd, f)
        controls.append(("N3_partial_z0_rejected", not check_z0_json(bad_z0)))

    ok = all(v for _, v in gates) and all(v for _, v in controls)
    result = {
        "packet": "WP_20260711",
        "tc": "TC-50",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_s": round(time.time() - t0, 1),
        "gates": {k: ("PASS" if v else "FAIL") for k, v in gates},
        "neg_controls": {k: ("FIRED" if v else "DID_NOT_FIRE") for k, v in controls},
        "verdict": "PASS" if ok else "FAIL",
    }
    os.makedirs(REPORTS, exist_ok=True)
    out_path = os.path.join(REPORTS, "wp_20260711_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    for k, v in gates:
        print(("PASS " if v else "FAIL ") + k)
    for k, v in controls:
        print(("FIRED " if v else "MISS  ") + k)
    print(("PASS  " if ok else "FAIL  ") +
          f"{sum(v for _, v in gates)}/{len(gates)} gates + "
          f"{sum(v for _, v in controls)}/{len(controls)} controls -> {out_path}")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
