#!/usr/bin/env python3
"""run_demo.py -- NaviSense one-command demo runner (Scenario Runner v0).

Work packet WP-20260623. Advances demo gate **D6** (single-command run) and
seeds **D8** (clean-machine reproducibility).

WHAT IT DOES (the whole demo in one command):
  1. PREFLIGHT the environment   -- python version, workspace layout, the
     named scenario, a free TCP port, and that the analysis tools import.
  2. LAUNCH the bridge listener  -- python_listener.py with the scenario's
     controller + sea state resolved from python/scenarios.py, --once so it
     serves exactly one run.
  3. DRIVE one run:
       * interactive (default): waits for your Unreal PIE session to connect
         and for you to Stop PIE -- you press Play, the runner does the rest;
       * --selftest: a bundled pure-Python client (ue5_client_sim.py) plays
         the vessel, so the FULL pipeline runs with NO Unreal and NO GPU.
  4. POST-RUN: auto-builds the IMO evidence pack (build_evidence_pack.py ->
     logs/<run>/evidence_pack/) and runs the kinematic health gate
     (verify_run_kinematics.py), then prints a one-line demo summary.

USAGE
  python run_demo.py --scenario imo_turning_circle              # real UE
  python run_demo.py --scenario imo_turning_circle --selftest   # headless
  python run_demo.py --list                                     # scenarios
  python run_demo.py --preflight                                # checks only

EXIT CODE: 0 iff preflight passed, a run was produced, AND the kinematic
health gate returned PASS. Non-zero otherwise (handy for CI / the nightly).

Pure orchestration: this script writes NOTHING into a run except by invoking
the existing, already-verified tools as subprocesses. Removing it cannot
affect a run. No wire / schema / C++ change.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import socket
import subprocess
import sys
import time
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Paths are resolved against THIS file so the command behaves identically no
# matter which folder it is launched from (same rule as python_listener.py).
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "python"
LISTENER = os.path.join(ROOT, "python_listener.py")
CLIENT = os.path.join(ROOT, "Development", "bridge_harness", "ue5_client_sim.py")
PYDIR = os.path.join(ROOT, "python")
DEFAULT_LOG_DIR = os.path.join(ROOT, "logs")

C_OK, C_WARN, C_BAD = "[ OK ]", "[WARN]", "[FAIL]"


def _say(msg: str) -> None:
    print(f"[run_demo] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Preflight  (also the seed of the D8 clean-machine check)
# ---------------------------------------------------------------------------
def _port_is_free(host: str, port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def preflight(scenario: Optional[str], host: str, port: int,
              plant: str) -> Tuple[bool, List[dict]]:
    """Return (ok, checks). ok is False if any check FAILs (WARN does not block)."""
    checks: List[dict] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    # 1. Python version
    v = sys.version_info
    add("python_version",
        C_OK if v >= (3, 8) else C_BAD,
        f"{v.major}.{v.minor}.{v.micro}")

    # 2. Workspace layout (the irreducible files the demo needs)
    needed = {
        "python_listener.py": LISTENER,
        "python/scenarios.py": os.path.join(PYDIR, "scenarios.py"),
        "python/build_evidence_pack.py": os.path.join(PYDIR, "build_evidence_pack.py"),
        "python/verify_run_kinematics.py": os.path.join(PYDIR, "verify_run_kinematics.py"),
        "ue5_client_sim.py": CLIENT,
    }
    missing = [n for n, p in needed.items() if not os.path.isfile(p)]
    add("workspace_layout",
        C_OK if not missing else C_BAD,
        "all present" if not missing else f"missing: {', '.join(missing)}")

    # 3. MMG plant data (WARN -> falls back to the stub plant, demo still runs)
    mmg = os.path.join(ROOT, "Maneuvering", "maniobrabilidad", "mmg")
    if plant == "mmg":
        add("mmg_plant",
            C_OK if os.path.isdir(mmg) else C_WARN,
            "MMG present" if os.path.isdir(mmg)
            else "MMG dir absent -- pass --plant stub")
    else:
        add("mmg_plant", C_OK, f"plant={plant} (MMG not required)")

    # 4. Analysis tools import (so the post-run step cannot surprise us)
    try:
        if PYDIR not in sys.path:
            sys.path.insert(0, PYDIR)
        import scenarios as _sc  # noqa: F401
        add("tools_import", C_OK, "scenarios import ok")
    except Exception as e:  # pragma: no cover - defensive
        add("tools_import", C_BAD, f"{type(e).__name__}: {e}")

    # 5. Scenario name valid
    if scenario and scenario != "list":
        try:
            import scenarios as _sc
            sc = _sc.get_scenario(scenario)
            add("scenario", C_OK,
                f"{sc.name} -> controller={sc.controller}, "
                + (f"schedule[{sc.sea_state_schedule}]" if sc.sea_state_schedule
                   else f"SS{sc.sea_state}"))
        except Exception as e:
            add("scenario", C_BAD, str(e).splitlines()[0])

    # 6. TCP port free
    add("port_free",
        C_OK if _port_is_free(host, port) else C_BAD,
        f"{host}:{port} " + ("free" if _port_is_free(host, port) else "in use"))

    ok = all(c["status"] != C_BAD for c in checks)
    return ok, checks


def _print_checks(title: str, checks: List[dict]) -> None:
    _say(title)
    for c in checks:
        print(f"    {c['status']} {c['name']:18s} {c['detail']}")


# ---------------------------------------------------------------------------
# Launch + drive
# ---------------------------------------------------------------------------
def _wait_for_listening(logfile: str, proc: subprocess.Popen,
                        timeout: float = 20.0) -> bool:
    """Poll the listener log until it reports it is listening (or it dies)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False  # listener exited before binding
        try:
            with open(logfile, "r", errors="replace") as fh:
                if "listening on" in fh.read():
                    return True
        except FileNotFoundError:
            pass
        time.sleep(0.2)
    return False


def _new_run_dir(log_dir: str, run_id: str, pre: set,
                 timeout: float = 5.0) -> Optional[str]:
    """Newest logs/<run_id>_* dir that did NOT exist before this run started.
    Never falls back to a pre-existing run: if nothing new appeared (e.g. no
    client/UE ever connected) it returns None so the caller reports 'no run
    logged' instead of silently reusing a stale run and faking success."""
    deadline = time.time() + timeout
    pat = os.path.join(log_dir, f"{run_id}_*")
    while time.time() < deadline:
        fresh = [d for d in glob.glob(pat) if os.path.isdir(d) and d not in pre]
        if fresh:
            return max(fresh, key=os.path.getmtime)
        time.sleep(0.2)
    return None


def launch_listener(scenario: str, host: str, port: int, plant: str,
                    run_id: str, log_dir: str, time_scale: float,
                    logfile: str, target_name: str = None) -> subprocess.Popen:
    cmd = [PY, "-u", LISTENER,
           "--host", host, "--port", str(port),
           "--plant", plant,
           "--scenario", scenario,
           "--run-id", run_id,
           "--target", "unreal",
           "--once",
           "--time-scale", f"{time_scale:g}",
           "--log-dir", log_dir]
    if target_name:
        cmd += ["--target-name", target_name]
    _say("launch: listener " + " ".join(c for c in cmd[1:]
                                        if c not in (LISTENER, "-u")))
    fh = open(logfile, "w")
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    return subprocess.Popen(cmd, cwd=ROOT, stdout=fh,
                            stderr=subprocess.STDOUT, text=True, env=env)


def drive_selftest(host: str, port: int, seconds: float, send_hz: float,
                   logfile: str) -> int:
    cmd = [PY, "-u", CLIENT, "--host", host, "--port", str(port),
           "--seconds", f"{seconds:g}", "--send-hz", f"{send_hz:g}"]
    _say(f"self-test client: driving the vessel for {seconds:g}s "
         f"(headless, no Unreal)")
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    with open(logfile, "w") as fh:
        return subprocess.call(cmd, cwd=ROOT, stdout=fh,
                               stderr=subprocess.STDOUT, env=env)


# ---------------------------------------------------------------------------
# Post-run: evidence pack + health gate
# ---------------------------------------------------------------------------
def build_evidence(run_dir: str, make_plots: bool) -> Tuple[bool, Optional[dict]]:
    cmd = [PY, os.path.join(PYDIR, "build_evidence_pack.py"),
           "--run-dir", run_dir]
    if not make_plots:
        cmd.append("--no-plot")
    env = dict(os.environ, MPLBACKEND="Agg")
    rc = subprocess.call(cmd, cwd=ROOT, env=env)
    kj = os.path.join(run_dir, "evidence_pack", "kpis.json")
    kpis = None
    if os.path.isfile(kj):
        try:
            with open(kj) as fh:
                kpis = json.load(fh)
        except Exception:
            kpis = None
    return rc == 0, kpis


def health_gate(run_dir: str) -> bool:
    cmd = [PY, os.path.join(PYDIR, "verify_run_kinematics.py"),
           "--run-dir", run_dir]
    return subprocess.call(cmd, cwd=ROOT) == 0


def _summary_line(run_dir: str, health_ok: bool, kpis: Optional[dict]) -> str:
    name = os.path.basename(run_dir)
    bits = [f"run={name}", f"health={'PASS' if health_ok else 'FAIL'}"]
    if kpis:
        man = kpis.get("meta", {})
        bits.append(f"scenario={man.get('scenario')}")
        man_kpi = kpis.get("maneuver", {}) or {}
        dt = man_kpi.get("tactical_diameter_m")
        if dt is not None:
            imo = man_kpi.get("imo_tactical_diameter_pass")
            bits.append(f"DT={dt:.1f}m"
                        + (f" (IMO {'PASS' if imo else 'FAIL'})" if imo is not None else ""))
        ov = man_kpi.get("first_overshoot_deg")
        if ov is not None:
            bits.append(f"1st-overshoot={ov:.1f}deg")
    bits.append(f"pack={os.path.join(name, 'evidence_pack')}")
    return "  ".join(bits)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description="NaviSense one-command demo runner (Scenario Runner v0).",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default=None,
                    help="Named demo scenario (see --list).")
    ap.add_argument("--selftest", action="store_true",
                    help="Headless: a bundled client plays the vessel (no Unreal).")
    ap.add_argument("--list", action="store_true", help="List scenarios and exit.")
    ap.add_argument("--preflight", action="store_true",
                    help="Run environment checks and exit (no run).")
    ap.add_argument("--target-name", default=None, metavar="LABEL",
                    help="Swap the rendered COLREGS target ship (passed through "
                         "to the listener; single-target presets only).")
    ap.add_argument("--plant", default="mmg", choices=["mmg", "stub"],
                    help="Plant model (default mmg).")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5005)
    ap.add_argument("--seconds", type=float, default=14.0,
                    help="[selftest] wall seconds to drive the vessel.")
    ap.add_argument("--send-hz", type=float, default=5.0,
                    help="[selftest] client sensor send rate.")
    ap.add_argument("--time-scale", type=float, default=None,
                    help="Sim speed-up (default 25x for --selftest, 1x for real UE).")
    ap.add_argument("--wait", type=float, default=1800.0,
                    help="[interactive] max seconds to wait for the UE run to finish.")
    ap.add_argument("--no-plot", action="store_true",
                    help="Skip evidence-pack plots (faster).")
    ap.add_argument("--log-dir", default=None,
                    help="Write the run here (default: logs/, or logs/_selftest "
                         "for --selftest). An explicit value always wins.")
    ap.add_argument("--no-preflight", action="store_true")
    args = ap.parse_args()

    if PYDIR not in sys.path:
        sys.path.insert(0, PYDIR)

    # --list
    if args.list or args.scenario == "list":
        import scenarios as sc
        print(sc.format_scenarios())
        return 0

    # --preflight only
    if args.preflight:
        ok, checks = preflight(args.scenario, args.host, args.port, args.plant)
        _print_checks("preflight:", checks)
        _say("preflight PASS" if ok else "preflight FAIL")
        return 0 if ok else 1

    if not args.scenario:
        ap.error("a --scenario is required (or use --list / --preflight)")

    # Preflight (gates the run unless explicitly skipped)
    if not args.no_preflight:
        ok, checks = preflight(args.scenario, args.host, args.port, args.plant)
        _print_checks("preflight:", checks)
        if not ok:
            _say("preflight FAILED -- fix the [FAIL] items above, then re-run.")
            return 1

    # Headless self-test rehearsals go in a subdir so they never shadow a real
    # UE run for --latest tooling (and are trivial to purge); real UE runs land
    # in the top-level logs/ like any other run.
    log_dir = (os.path.abspath(args.log_dir) if args.log_dir
               else (os.path.join(DEFAULT_LOG_DIR, "_selftest") if args.selftest
                     else DEFAULT_LOG_DIR))
    os.makedirs(log_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    run_id = f"demo-{args.scenario}"
    listener_log = os.path.join(log_dir, f"{run_id}-{stamp}.listener.log")
    client_log = os.path.join(log_dir, f"{run_id}-{stamp}.client.log")
    time_scale = args.time_scale if args.time_scale is not None else (
        25.0 if args.selftest else 1.0)

    pre_dirs = set(glob.glob(os.path.join(log_dir, f"{run_id}_*")))
    proc = launch_listener(args.scenario, args.host, args.port, args.plant,
                           run_id, log_dir, time_scale, listener_log,
                           target_name=args.target_name)
    try:
        if not _wait_for_listening(listener_log, proc):
            _say("listener did not start -- see " + listener_log)
            return 1
        _say(f"bridge up on {args.host}:{args.port} (run-id {run_id}).")

        if args.selftest:
            drive_selftest(args.host, args.port, args.seconds, args.send_hz,
                           client_log)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.terminate()
        else:
            print("\n" + "=" * 64)
            _say("NOW: in Unreal, press PLAY to start the run, drive/observe the")
            _say("scenario, then press STOP. The runner will build the evidence")
            _say("pack automatically when the PIE session ends.")
            print("=" * 64 + "\n")
            try:
                proc.wait(timeout=args.wait)
            except subprocess.TimeoutExpired:
                _say(f"no PIE run within {args.wait:g}s -- stopping the bridge.")
                proc.terminate()
    except KeyboardInterrupt:
        _say("interrupted -- stopping the bridge and building what was logged.")
        proc.terminate()
    finally:
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    run_dir = _new_run_dir(log_dir, run_id, pre_dirs)
    if not run_dir or not os.path.isfile(os.path.join(run_dir, "state.csv")):
        _say("no run was logged (did a client/UE connect?). See " + listener_log)
        return 1
    _say(f"run logged: {os.path.basename(run_dir)}")

    _say("building evidence pack ...")
    pack_ok, kpis = build_evidence(run_dir, make_plots=not args.no_plot)
    _say("kinematic health gate ...")
    health_ok = health_gate(run_dir)

    print("\n" + "=" * 64)
    _say("DEMO COMPLETE")
    print("    " + _summary_line(run_dir, health_ok, kpis))
    print("=" * 64)
    return 0 if (pack_ok and health_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
