#!/usr/bin/env python3
"""verify_20260623.py -- gates for WP-20260623 (Scenario Runner v0 / run_demo.py).

Drives ``run_demo.py`` end to end (headless, via the bundled UE client sim) and
checks that the ONE-COMMAND demo path produces a valid IMO evidence pack + a
kinematic-health verdict -- and that its negative controls have teeth. Writes
``NaviSense_UE5/Saved/NaviSense_Reports/wp_20260623_result.json``.

Exit 0 iff every gate PASSES and every negative control FIRES.

Pure orchestration / read-only over logs. No wire / schema / C++ change.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from typing import List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RUN_DEMO = os.path.join(ROOT, "run_demo.py")
PYDIR = os.path.join(ROOT, "python")
LOGS = os.path.join(ROOT, "logs")
SELFTEST_LOGS = os.path.join(LOGS, "_selftest")
REPORTS = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports")
PY = sys.executable or "python"
ENV = dict(os.environ, PYTHONUNBUFFERED="1", MPLBACKEND="Agg")

if PYDIR not in sys.path:
    sys.path.insert(0, PYDIR)


def _demo(args: List[str], timeout: float) -> subprocess.CompletedProcess:
    # Route every invocation under logs/_selftest so the suite never leaves an
    # artifact in the top-level run list (even the interactive N3 control).
    os.makedirs(SELFTEST_LOGS, exist_ok=True)
    return subprocess.run([PY, "-u", RUN_DEMO, "--log-dir", SELFTEST_LOGS] + args,
                          cwd=ROOT, capture_output=True, text=True,
                          timeout=timeout, env=ENV)


def _newest_run(scenario: str, since: float) -> Optional[str]:
    pat = os.path.join(SELFTEST_LOGS, f"demo-{scenario}_*")
    cands = [d for d in glob.glob(pat)
             if os.path.isdir(d) and os.path.getmtime(d) >= since - 2.0]
    return max(cands, key=os.path.getmtime) if cands else None


def _kpis(run_dir: str) -> Optional[dict]:
    p = os.path.join(run_dir, "evidence_pack", "kpis.json")
    if not os.path.isfile(p):
        return None
    try:
        return json.load(open(p))
    except Exception:
        return None


def _cleanup_scratch(t0: float) -> int:
    """Remove the demo-* runs + sidecar logs THIS verify created (mtime >= t0)
    so the headless rehearsals don't accumulate in logs/ or shadow a real run
    for --latest tooling. Anything older than this run is left untouched."""
    removed = 0
    for p in glob.glob(os.path.join(SELFTEST_LOGS, "demo-*")):
        try:
            if os.path.getmtime(p) >= t0 - 1.0:
                shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
                removed += 1
        except OSError:
            pass
    return removed


# --------------------------------------------------------------------------
# Gates
# --------------------------------------------------------------------------
def gate_preflight() -> dict:
    cp = _demo(["--preflight", "--scenario", "imo_turning_circle"], 60)
    ok = cp.returncode == 0 and "preflight PASS" in cp.stdout
    return {"id": "G1", "name": "preflight_pass", "passed": ok,
            "detail": "rc=%d" % cp.returncode}


def gate_list_parity() -> dict:
    import scenarios as sc
    cp = _demo(["--list"], 30)
    names = [s.name for s in sc.list_scenarios()]
    missing = [n for n in names if n not in cp.stdout]
    ok = cp.returncode == 0 and not missing
    return {"id": "G2", "name": "list_parity", "passed": ok,
            "detail": ("lists all %d scenarios" % len(names)) if ok
                      else f"missing {missing}"}


def gate_e2e_turning(port: int) -> dict:
    since = time.time()
    cp = _demo(["--scenario", "imo_turning_circle", "--selftest",
                "--seconds", "8", "--time-scale", "40", "--port", str(port)], 80)
    rd = _newest_run("imo_turning_circle", since)
    detail, ok = [], False
    if cp.returncode != 0:
        detail.append("rc=%d" % cp.returncode)
    if not rd:
        detail.append("no run dir")
    else:
        k = _kpis(rd)
        has_state = os.path.isfile(os.path.join(rd, "state.csv"))
        has_md = os.path.isfile(os.path.join(rd, "evidence_pack", "EVIDENCE.md"))
        pngs = glob.glob(os.path.join(rd, "evidence_pack", "*.png"))
        dt = (k or {}).get("maneuver", {}).get("tactical_diameter_m")
        ok = (cp.returncode == 0 and has_state and has_md and k is not None
              and dt is not None and len(pngs) >= 1)
        detail.append(f"dir={os.path.basename(rd)} DT={dt} plots={len(pngs)} "
                      f"md={has_md}")
    return {"id": "G3", "name": "e2e_turning_circle_with_plots", "passed": ok,
            "detail": "; ".join(detail), "run_dir": os.path.basename(rd) if rd else None}


def gate_kpi_parity(g3: dict) -> dict:
    """run_demo's pack must equal a standalone build_evidence_pack on the same run."""
    rd_name = g3.get("run_dir")
    if not rd_name:
        return {"id": "G4", "name": "kpi_parity", "passed": False,
                "detail": "no G3 run"}
    rd = os.path.join(SELFTEST_LOGS, rd_name)
    k_runner = _kpis(rd)
    dt_runner = (k_runner or {}).get("maneuver", {}).get("tactical_diameter_m")
    cp = subprocess.run([PY, os.path.join(PYDIR, "build_evidence_pack.py"),
                         "--run-dir", rd, "--no-plot"], cwd=ROOT,
                        capture_output=True, text=True, timeout=60, env=ENV)
    k_std = _kpis(rd)
    dt_std = (k_std or {}).get("maneuver", {}).get("tactical_diameter_m")
    ok = (dt_runner is not None and dt_std is not None
          and abs(dt_runner - dt_std) < 1e-6)
    return {"id": "G4", "name": "kpi_parity", "passed": ok,
            "detail": f"runner DT={dt_runner} vs standalone DT={dt_std}"}


def gate_e2e_zigzag(port: int) -> dict:
    since = time.time()
    cp = _demo(["--scenario", "imo_zigzag10", "--selftest",
                "--seconds", "9", "--time-scale", "40", "--no-plot",
                "--port", str(port)], 80)
    rd = _newest_run("imo_zigzag10", since)
    ok, detail = False, []
    if cp.returncode != 0:
        detail.append("rc=%d" % cp.returncode)
    if not rd:
        detail.append("no run dir")
    else:
        k = _kpis(rd)
        man = (k or {}).get("maneuver", {})
        kind = man.get("kind")
        o1 = man.get("first_overshoot_deg")
        ok = kind == "zigzag" and o1 is not None
        detail.append(f"kind={kind} first_overshoot={o1}")
    return {"id": "G5", "name": "e2e_zigzag_other_controller", "passed": ok,
            "detail": "; ".join(detail)}


# --------------------------------------------------------------------------
# Negative controls (must FIRE)
# --------------------------------------------------------------------------
def neg_invalid_scenario() -> dict:
    cp = _demo(["--preflight", "--scenario", "no_such_scenario"], 30)
    fired = cp.returncode == 1 and "preflight FAIL" in cp.stdout
    return {"id": "N1", "name": "invalid_scenario_rejected", "fired": fired,
            "detail": "rc=%d" % cp.returncode}


def neg_busy_port(port: int) -> dict:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    fired = False
    detail = ""
    try:
        s.bind(("127.0.0.1", port))
        s.listen(1)
        cp = _demo(["--preflight", "--scenario", "imo_turning_circle",
                    "--port", str(port)], 30)
        fired = cp.returncode == 1 and "port_free" in cp.stdout and "in use" in cp.stdout
        detail = "rc=%d" % cp.returncode
    finally:
        s.close()
    return {"id": "N2", "name": "busy_port_detected", "fired": fired, "detail": detail}


def neg_no_vessel(port: int) -> dict:
    """Interactive mode with no client must NOT fake a pass."""
    cp = _demo(["--scenario", "imo_turning_circle", "--wait", "2",
                "--port", str(port)], 30)
    fired = cp.returncode == 1 and "no run was logged" in cp.stdout
    return {"id": "N3", "name": "no_vessel_no_fake_pass", "fired": fired,
            "detail": "rc=%d" % cp.returncode}


def main() -> int:
    t0 = time.time()
    print("=" * 64)
    print("WP-20260623 verify -- Scenario Runner v0 (run_demo.py)")
    print("=" * 64)

    gates: List[dict] = []
    gates.append(gate_preflight())
    gates.append(gate_list_parity())
    g3 = gate_e2e_turning(5021)
    gates.append(g3)
    gates.append(gate_kpi_parity(g3))
    gates.append(gate_e2e_zigzag(5023))

    negs: List[dict] = []
    negs.append(neg_invalid_scenario())
    negs.append(neg_busy_port(5027))
    negs.append(neg_no_vessel(5025))

    print("\nGATES")
    for g in gates:
        print(f"  [{'PASS' if g['passed'] else 'FAIL'}] {g['id']} "
              f"{g['name']:32s} {g['detail']}")
    print("\nNEGATIVE CONTROLS (must fire)")
    for n in negs:
        print(f"  [{'FIRED' if n['fired'] else 'MISS'}] {n['id']} "
              f"{n['name']:32s} {n['detail']}")

    n_pass = sum(1 for g in gates if g["passed"])
    n_tot = len(gates)
    all_fired = all(n["fired"] for n in negs)
    overall = (n_pass == n_tot) and all_fired
    print("\n" + "-" * 64)
    print(f"  Gates: {n_pass}/{n_tot}   Negative controls fired: "
          f"{sum(n['fired'] for n in negs)}/{len(negs)}")
    print(f"  OVERALL: {'PASS' if overall else 'FAIL'}  "
          f"({time.time() - t0:.1f}s)")

    result = {
        "packet": "WP-20260623",
        "theme": "Scenario Runner v0 (one-command demo, gate D6 / seeds D8)",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "gates_passed": n_pass, "gates_total": n_tot,
        "all_negative_controls_fired": all_fired,
        "overall": "PASS" if overall else "FAIL",
        "gates": gates, "negative_controls": negs,
    }
    os.makedirs(REPORTS, exist_ok=True)
    out = os.path.join(REPORTS, "wp_20260623_result.json")
    with open(out, "w") as fh:
        json.dump(result, fh, indent=2)
    print(f"  wrote {out}")
    n_rm = _cleanup_scratch(t0)
    print(f"  cleaned {n_rm} scratch demo run(s)/log(s) from logs/")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
