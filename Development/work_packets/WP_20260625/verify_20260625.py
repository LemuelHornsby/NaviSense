#!/usr/bin/env python3
"""verify_20260625.py -- gates WP-20260625 (D8 clean-machine reproducibility).

Checks the repro_doctor + the documented setup + that the headless demo pipeline
reproduces, with negative controls that FIRE (so a green result is meaningful, not
just "clean data passes").

  G1 doctor_real_tree     -- run_checks() on the real workspace: every REQUIRED
                             check OK, verdict READY, exit 0.
  G2 deps_enumeration     -- _parse_requirements reads requirements.txt exactly
                             (3 active deps, commented optionals excluded, pyyaml
                             -> yaml mapping), and all 3 import.
  G3 ue_and_assets        -- .uproject parses (engine 5.7, Water on); both
                             DA_DOLPHIN assets present and NOT bare LFS stubs.
  G4 cesium_documented    -- with no token in env, cesium_token = WARN, OPTIONAL,
                             verdict still READY; SETUP.md documents the token.
  G5 reproducibility      -- run_demo --selftest twice (isolated dirs): both exit
                             0 + health PASS + same IMO verdict + DT within 2%.
  G6 json_and_setup       -- doctor writes a schema-valid repro.json; SETUP.md
                             references the run command, git lfs, and Cesium.

Negative controls (each MUST fire):
  N1 missing_dep_blocks   -- an absent module is detected missing AND a required
                             python_deps FAIL flips verdict -> NOT ready.
  N2 strict_warn_blocks   -- a required WARN is READY by default but NOT ready
                             under --strict.
  N3 lfs_pointer_detected -- a 130-byte 'version https://git-lfs' stub is flagged
                             a pointer; a real binary blob is not.

G5 runs both demos FRESH by default. For a CI/sandbox with a short per-command
time budget, pre-stage two runs and point NS_G5_DIR_A / NS_G5_DIR_B at their log
dirs; G5 then reads those instead of re-running (the rest is sub-second).

Writes Saved/NaviSense_Reports/wp_20260625_result.json. Exit 0 iff 6/6 + 3/3.
Pure inspection + headless self-test; no wire/schema/C++ change.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PYDIR = os.path.join(ROOT, "python")
REPORTS = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports")
PY = sys.executable or "python"

if PYDIR not in sys.path:
    sys.path.insert(0, PYDIR)
import repro_doctor as rd  # noqa: E402

_gates, _controls = [], []


def gate(gid, name, passed, detail):
    _gates.append({"id": gid, "name": name, "passed": bool(passed), "detail": detail})
    print(f"  [{'PASS' if passed else 'FAIL'}] {gid} {name}: {detail}")


def control(cid, name, fired, detail):
    _controls.append({"id": cid, "name": name, "fired": bool(fired), "detail": detail})
    print(f"  [{'FIRE' if fired else 'MISS'}] {cid} {name}: {detail}")


# ---------------------------------------------------------------------------
# G1 -- doctor on the real tree
# ---------------------------------------------------------------------------
def g1():
    checks = rd.run_checks()
    vd = rd.verdict(checks, strict=False)
    by = {c.name: c for c in checks}
    req = ["python_version", "python_deps", "core_tools", "mmg_plant",
           "ue_project", "ue_source", "data_assets", "logs_writable"]
    bad = [n for n in req if by.get(n) is None or by[n].status == rd.FAIL]
    ok = vd["ready"] and not bad
    gate("G1", "doctor_real_tree", ok,
         f"ready={vd['ready']} ok/warn/fail={vd['counts']['ok']}/"
         f"{vd['counts']['warn']}/{vd['counts']['fail']} req_fail={bad or 'none'}")
    return by


# ---------------------------------------------------------------------------
# G2 -- requirements enumeration + importability
# ---------------------------------------------------------------------------
def g2():
    reqs = rd._parse_requirements(os.path.join(ROOT, "requirements.txt"))
    dists = {d for d, _ in reqs}
    imps = {d: i for d, i in reqs}
    expected = {"numpy", "pyyaml", "matplotlib"}
    optional_excluded = not ({"casadi", "torch", "stable-baselines3"} & dists)
    mapping_ok = imps.get("pyyaml") == "yaml"
    all_import = all(rd._module_available(i) for _, i in reqs)
    ok = dists == expected and optional_excluded and mapping_ok and all_import
    gate("G2", "deps_enumeration", ok,
         f"active={sorted(dists)} pyyaml->{imps.get('pyyaml')} "
         f"optional_excluded={optional_excluded} all_import={all_import}")


# ---------------------------------------------------------------------------
# G3 -- UE project + data assets
# ---------------------------------------------------------------------------
def g3(by):
    up = by.get("ue_project")
    src = by.get("ue_source")
    da = by.get("data_assets")
    ue_ok = up is not None and up.status == rd.OK and "5.7" in up.detail and "Water=on" in up.detail
    src_ok = src is not None and src.status == rd.OK
    da_ok = da is not None and da.status == rd.OK  # present + not LFS stubs
    ok = ue_ok and src_ok and da_ok
    gate("G3", "ue_and_assets", ok,
         f"ue='{up.detail if up else 'n/a'}' src={src.status if src else '?'} "
         f"assets={da.status if da else '?'}")


# ---------------------------------------------------------------------------
# G4 -- Cesium token documented (optional WARN, non-blocking) + SETUP.md
# ---------------------------------------------------------------------------
def g4(by):
    saved = {e: os.environ.pop(e, None) for e in rd._CESIUM_ENV}
    try:
        checks = rd.run_checks()
        vd = rd.verdict(checks, strict=False)
        ces = next((c for c in checks if c.name == "cesium_token"), None)
        warn_optional = ces is not None and ces.status == rd.WARN and not ces.required
        still_ready = vd["ready"]
    finally:
        for e, v in saved.items():
            if v is not None:
                os.environ[e] = v
    setup = os.path.join(ROOT, "SETUP.md")
    doc_ok = False
    if os.path.isfile(setup):
        with open(setup, "r", errors="replace") as fh:
            txt = fh.read().lower()
        doc_ok = ("cesium" in txt and "token" in txt
                  and ("ion" in txt) and ("repro_doctor" in txt))
    ok = warn_optional and still_ready and doc_ok
    gate("G4", "cesium_documented", ok,
         f"warn_optional={warn_optional} ready_without_token={still_ready} "
         f"setup_documents_token={doc_ok}")


# ---------------------------------------------------------------------------
# G5 -- the headless demo pipeline reproduces (the core of D8)
# ---------------------------------------------------------------------------
def _find_kpis(log_dir):
    run_dir = None
    if not os.path.isdir(log_dir):
        return None, None
    for d in sorted(os.listdir(log_dir)):
        p = os.path.join(log_dir, d)
        if os.path.isdir(p) and d.startswith("demo-imo_turning_circle_"):
            run_dir = p
    kpis = None
    if run_dir:
        kj = os.path.join(run_dir, "evidence_pack", "kpis.json")
        if os.path.isfile(kj):
            with open(kj) as fh:
                kpis = json.load(fh)
    return run_dir, kpis


def _health_pass(kpis):
    if not kpis:
        return False
    h = kpis.get("health", {}) or {}
    v = str(h.get("verdict", "")).upper()
    if v:
        return v == "PASS"
    gp, gt = h.get("gates_passed"), h.get("gates_total")
    return gp is not None and gp == gt


def _selftest_fresh(log_dir):
    cmd = [PY, "-u", os.path.join(ROOT, "run_demo.py"),
           "--scenario", "imo_turning_circle", "--selftest",
           "--seconds", "22", "--no-plot", "--log-dir", log_dir]
    env = dict(os.environ, MPLBACKEND="Agg", PYTHONUNBUFFERED="1")
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       env=env, timeout=240)
    return r.returncode


def _run_or_reuse(slot):
    """Return (rc, kpis, health_bool). Reuse a pre-staged dir if NS_G5_DIR_<slot>
    is set (lets a short-budget CI stage the runs separately); else run fresh."""
    env_dir = os.environ.get(f"NS_G5_DIR_{slot}")
    if env_dir:
        _, kpis = _find_kpis(env_dir)
        return (0 if kpis else 1), kpis, _health_pass(kpis)
    d = tempfile.mkdtemp(prefix=f"ns_repro_{slot.lower()}_")
    rc = _selftest_fresh(d)
    _, kpis = _find_kpis(d)
    return rc, kpis, _health_pass(kpis)


def _dt(kpis):
    return ((kpis or {}).get("maneuver", {}) or {}).get("tactical_diameter_m")


def _imo(kpis):
    return ((kpis or {}).get("maneuver", {}) or {}).get("imo_tactical_diameter_pass")


def g5():
    rc1, k1, h1 = _run_or_reuse("A")
    rc2, k2, h2 = _run_or_reuse("B")
    dt1, dt2 = _dt(k1), _dt(k2)
    imo1, imo2 = _imo(k1), _imo(k2)
    both_pass = rc1 == 0 and rc2 == 0 and h1 and h2
    imo_same = imo1 == imo2 and imo1 is not None
    dt_close = (dt1 is not None and dt2 is not None
                and abs(dt1 - dt2) <= 0.02 * max(dt1, dt2))
    ok = both_pass and imo_same and dt_close
    dts = (f"DT={dt1:.2f},{dt2:.2f}" if (dt1 is not None and dt2 is not None)
           else f"DT={dt1},{dt2}")
    gate("G5", "reproducibility", ok,
         f"rc={rc1},{rc2} health={h1},{h2} {dts} IMO={imo1}=={imo2}")


# ---------------------------------------------------------------------------
# G6 -- repro.json schema + SETUP.md content
# ---------------------------------------------------------------------------
def g6():
    out = os.path.join(tempfile.mkdtemp(prefix="ns_json_"), "repro.json")
    rc = subprocess.run([PY, os.path.join(PYDIR, "repro_doctor.py"),
                         "--quiet", "--out", out],
                        cwd=ROOT, capture_output=True, text=True, timeout=60)
    schema_ok = False
    if os.path.isfile(out):
        with open(out) as fh:
            rep = json.load(fh)
        vd = rep.get("verdict", {})
        schema_ok = (isinstance(vd.get("ready"), bool)
                     and "counts" in vd and isinstance(rep.get("checks"), list)
                     and all({"name", "status", "required"} <= set(c)
                             for c in rep["checks"]))
    setup = os.path.join(ROOT, "SETUP.md")
    setup_ok = False
    if os.path.isfile(setup):
        with open(setup, "r", errors="replace") as fh:
            t = fh.read().lower()
        setup_ok = ("git lfs" in t and "run_demo.py" in t and "cesium" in t
                    and "repro_doctor" in t)
    ok = schema_ok and setup_ok and rc.returncode in (0, 1)
    gate("G6", "json_and_setup", ok,
         f"repro_json_schema={schema_ok} setup_complete={setup_ok} rc={rc.returncode}")


# ---------------------------------------------------------------------------
# Negative controls
# ---------------------------------------------------------------------------
def n1():
    absent = rd._module_available("totally_absent_pkg_navisense_xyz") is False
    synthetic = [
        rd.Check("python_version", rd.OK, "3.10", required=True),
        rd.Check("python_deps", rd.FAIL, "missing: numpy", required=True),
    ]
    vd = rd.verdict(synthetic, strict=False)
    fired = absent and (vd["ready"] is False) and ("python_deps" in vd["required_failures"])
    control("N1", "missing_dep_blocks", fired,
            f"absent_detected={absent} verdict_ready={vd['ready']}")


def n2():
    synthetic = [
        rd.Check("python_version", rd.OK, "3.10", required=True),
        rd.Check("mmg_plant", rd.WARN, "DOLPHIN.yaml missing", required=True),
    ]
    lax = rd.verdict(synthetic, strict=False)["ready"]
    strict = rd.verdict(synthetic, strict=True)["ready"]
    fired = (lax is True) and (strict is False)
    control("N2", "strict_warn_blocks", fired,
            f"ready_lax={lax} ready_strict={strict}")


def n3():
    tmp = tempfile.mkdtemp(prefix="ns_lfs_")
    stub = os.path.join(tmp, "stub.uasset")
    real = os.path.join(tmp, "real.uasset")
    with open(stub, "wb") as fh:
        fh.write(b"version https://git-lfs.github.com/spec/v1\n"
                 b"oid sha256:deadbeef\nsize 12345\n")
    with open(real, "wb") as fh:
        fh.write(os.urandom(4096))
    is_stub = rd._is_lfs_pointer(stub) is True
    is_real = rd._is_lfs_pointer(real) is False
    fired = is_stub and is_real
    control("N3", "lfs_pointer_detected", fired,
            f"stub_flagged={is_stub} real_passed={is_real}")


def main():
    print("=== verify_20260625 (D8 clean-machine reproducibility) ===")
    by = g1()
    g2()
    g3(by)
    g4(by)
    g5()
    g6()
    print("--- negative controls ---")
    n1()
    n2()
    n3()

    passed = sum(g["passed"] for g in _gates)
    total = len(_gates)
    all_fired = all(c["fired"] for c in _controls)
    overall = (passed == total) and all_fired
    report = {
        "packet": "WP-20260625",
        "theme": "Clean-machine reproducibility -- environment doctor + repro gate (D8)",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "gates_passed": passed,
        "gates_total": total,
        "all_negative_controls_fired": all_fired,
        "overall": "PASS" if overall else "FAIL",
        "gates": _gates,
        "negative_controls": _controls,
    }
    os.makedirs(REPORTS, exist_ok=True)
    out = os.path.join(REPORTS, "wp_20260625_result.json")
    with open(out, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"\n  {passed}/{total} gates, controls {'all fired' if all_fired else 'MISSED'}"
          f"  => {report['overall']}")
    print(f"  wrote {out}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
