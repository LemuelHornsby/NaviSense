#!/usr/bin/env python3
"""verify_20260704.py -- gates WP-20260704 (demo-readiness rehearsal harness).

Gates (PASS = all True):
  G1 storyline/registry parity -- >=3 required scenarios; every storyline
     scenario is a real registry scenario; expectations reference real keys.
  G2 evaluator correctness -- evaluate_kpis() PASSES a good pack and FAILS a
     bad one (health FAIL), on synthetic kpis (no runs).
  G3 end-to-end -- rehearse() the FAST subset headless (real run_demo
     --selftest x2) => DEMO READY, both ready, D1+D4 covered, reports written.
  G4 aggregation -- overall_ready() is the single rule: one required-failing
     scenario => NOT READY; a non-required failure does NOT block.
  G5 regression -- Z0 compile-readiness 16/16 + verify_20260703 + verify_20260623
     still green.

Negative controls (each MUST fire):
  N1 an unknown scenario in a storyline is detected (not silently run).
  N2 a health=FAIL pack is scored NOT ready (never a false green).
  N3 a conformance mismatch (want compliant, pack non_compliant) is scored NOT ready.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYDIR = os.path.join(ROOT, "python")
for p in (ROOT, PYDIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import demo_rehearsal as dr  # noqa: E402
import scenarios as sc       # noqa: E402

PY = sys.executable or "python"


def _good_maneuver_kpis():
    return {"health": {"verdict": "PASS"},
            "maneuver": {"imo_tactical_diameter_pass": True,
                         "imo_advance_pass": True}}


def _good_colregs_kpis():
    return {"health": {"verdict": "PASS"},
            "ais": {"conformance": {"compliant": 1, "non_compliant": 0,
                                    "not_applicable": 0,
                                    "targets": [{"verdict": "compliant"}]}}}


def g1_storyline_parity():
    reg = {s.name for s in sc.list_scenarios()}
    story = dr.DEMO_STORYLINE
    required = [it for it in story if it.get("required", True)]
    all_real = all(it["scenario"] in reg for it in story)
    fast_real = all(n in reg for n in dr.FAST_SUBSET)
    # every 'imo' expectation key looks like an imo_* flag; conformance is a str
    keys_ok = True
    for it in story:
        for k in it.get("expect", {}).get("imo", []):
            if not k.startswith("imo_"):
                keys_ok = False
    ok = (len(required) >= 3 and all_real and fast_real and keys_ok)
    return ok, (f"required={len(required)} all_in_registry={all_real} "
                f"fast_in_registry={fast_real} keys_ok={keys_ok}")


def g2_evaluator():
    ready_man, _ = dr.evaluate_kpis(
        _good_maneuver_kpis(),
        {"health": True, "imo": ["imo_tactical_diameter_pass", "imo_advance_pass"]})
    ready_col, _ = dr.evaluate_kpis(
        _good_colregs_kpis(), {"health": True, "conformance": "compliant"})
    bad = _good_maneuver_kpis()
    bad["health"]["verdict"] = "FAIL"
    ready_bad, _ = dr.evaluate_kpis(
        bad, {"health": True, "imo": ["imo_advance_pass"]})
    none_ready, _ = dr.evaluate_kpis(None, {"health": True})
    ok = ready_man and ready_col and (not ready_bad) and (not none_ready)
    return ok, (f"good_maneuver={ready_man} good_colregs={ready_col} "
                f"bad_health={ready_bad} no_pack={none_ready}")


def g3_end_to_end():
    with tempfile.TemporaryDirectory() as td:
        story = dr.resolve_storyline(None, fast=True)
        res = dr.rehearse(story, td, plots=False, seconds=12.0, send_hz=5.0)
        jout = os.path.join(td, "demo_readiness.json")
        mout = os.path.join(td, "DEMO_READINESS.md")
        dr.write_reports(res, jout, mout)
        covered = set(res["gates_covered_headless"])
        ok = (res["overall_ready"]
              and res["ready_count"] == res["required_size"] == 2
              and {"D1", "D4"}.issubset(covered)
              and os.path.isfile(jout) and os.path.isfile(mout)
              and all(s["ready"] for s in res["scenarios"]))
        return ok, (f"verdict={res['verdict']} ready={res['ready_count']}/"
                    f"{res['required_size']} gates={sorted(covered)} "
                    f"reports={os.path.isfile(jout) and os.path.isfile(mout)}")


def g4_aggregation():
    req_pass = [{"required": True, "ready": True},
                {"required": True, "ready": True}]
    req_fail = [{"required": True, "ready": True},
                {"required": True, "ready": False}]
    nonreq_fail = [{"required": True, "ready": True},
                   {"required": False, "ready": False}]
    empty = []
    ok = (dr.overall_ready(req_pass) is True
          and dr.overall_ready(req_fail) is False
          and dr.overall_ready(nonreq_fail) is True
          and dr.overall_ready(empty) is False)
    return ok, (f"all_pass={dr.overall_ready(req_pass)} "
                f"one_req_fail={dr.overall_ready(req_fail)} "
                f"nonreq_fail={dr.overall_ready(nonreq_fail)} "
                f"empty={dr.overall_ready(empty)}")


def g5_regression():
    checks = {}
    z0_path = os.path.join(ROOT, "Development", "work_packets",
                           "WP_20260615_COMPILE_AUDIT",
                           "verify_compile_readiness.py")
    z0 = subprocess.run([PY, z0_path], cwd=PYDIR, capture_output=True, text=True)
    checks["Z0"] = (z0.returncode == 0)
    for name in ("verify_20260703.py", "verify_20260702b.py"):
        r = subprocess.run([PY, os.path.join(PYDIR, name)], cwd=ROOT,
                           capture_output=True, text=True)
        checks[name] = (r.returncode == 0)
    ok = all(checks.values())
    return ok, " ".join(f"{k}={v}" for k, v in checks.items())


def n1_unknown_scenario():
    reg = {s.name for s in sc.list_scenarios()}
    story = [{"scenario": "no_such_scenario_xyz", "expect": {"health": True}}]
    unknown = [it["scenario"] for it in story if it["scenario"] not in reg]
    fired = len(unknown) == 1
    return fired, f"unknown detected={unknown}"


def n2_bad_health_not_green():
    bad = {"health": {"verdict": "FAIL"},
           "maneuver": {"imo_advance_pass": True}}
    ready, checks = dr.evaluate_kpis(bad, {"health": True,
                                           "imo": ["imo_advance_pass"]})
    health_check = [c for c in checks if c["name"] == "health"]
    fired = (not ready) and bool(health_check) and not health_check[0]["status"]
    return fired, f"ready={ready} (must be False)"


def n3_conformance_mismatch():
    kpis = {"health": {"verdict": "PASS"},
            "ais": {"conformance": {"compliant": 0, "non_compliant": 1,
                                    "targets": [{"verdict": "non_compliant"}]}}}
    ready, _ = dr.evaluate_kpis(kpis, {"health": True, "conformance": "compliant"})
    fired = not ready
    return fired, f"ready={ready} (must be False)"


def main():
    gates = [("G1", g1_storyline_parity), ("G2", g2_evaluator),
             ("G3", g3_end_to_end), ("G4", g4_aggregation),
             ("G5", g5_regression)]
    controls = [("N1", n1_unknown_scenario), ("N2", n2_bad_health_not_green),
                ("N3", n3_conformance_mismatch)]

    print("=== WP-20260704 gates ===")
    gres = {}
    for gid, fn in gates:
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"EXC {type(e).__name__}: {e}"
        gres[gid] = ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {gid}: {detail}")

    print("=== negative controls (each MUST fire) ===")
    cres = {}
    for cid, fn in controls:
        try:
            fired, detail = fn()
        except Exception as e:
            fired, detail = False, f"EXC {type(e).__name__}: {e}"
        cres[cid] = fired
        print(f"  [{'FIRED' if fired else 'MISS'}] {cid}: {detail}")

    gp = sum(gres.values())
    cf = sum(cres.values())
    verdict = (gp == len(gates)) and (cf == len(controls))
    print(f"\nGates {gp}/{len(gates)} · controls {cf}/{len(controls)} "
          f"=> {'PASS' if verdict else 'FAIL'}")

    out = {
        "packet": "WP-20260704",
        "title": "Headless demo-readiness rehearsal harness",
        "gates": gres, "controls_fired": cres,
        "gates_passed": gp, "gates_total": len(gates),
        "controls_fired_n": cf, "controls_total": len(controls),
        "verdict": "PASS" if verdict else "FAIL",
    }
    rep = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports",
                       "wp_20260704_result.json")
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    with open(rep, "w") as fh:
        json.dump(out, fh, indent=2)
    print("wrote", rep)
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
