#!/usr/bin/env python3
"""repro_doctor.py -- NaviSense clean-machine readiness / reproducibility doctor.

Work packet WP-20260625. Advances demo gate **D8** (everything reproducible after
`git clone` + documented setup on a clean machine; Cesium tokens documented).

WHY THIS EXISTS
  run_demo.py has a light 5-check preflight (the seed of D8). This is the deep,
  demo-day "is this machine actually ready?" check: it enumerates the FULL set of
  reproducibility prerequisites a fresh clone needs and reports exactly what is
  missing and how to fix it. It is the headless half of D8; the in-engine half
  (open the UE project on a clean box and Play) stays Lemuel's optional manual gate.

DESIGN
  * STDLIB ONLY. The doctor must run on a truly clean machine BEFORE
    `pip install -r requirements.txt`, so it never imports numpy/pyyaml/etc.; it
    probes them with importlib.util.find_spec (no execution).
  * Every check returns OK / WARN / FAIL + a one-line, actionable detail and a
    `required` flag. Exit code is non-zero iff a REQUIRED check FAILs. `--strict`
    (demo-day mode) also fails on any required WARN.
  * Writes a machine-readable verdict to Saved/NaviSense_Reports/repro.json
    (override with --out; --json also prints it to stdout) so the nightly / CI and
    the evidence trail can read the readiness state.

USAGE
  python python/repro_doctor.py            # human table + repro.json, exit 0/1
  python python/repro_doctor.py --strict   # demo-day: WARN on a required item fails
  python python/repro_doctor.py --json      # also print the JSON verdict
  python python/repro_doctor.py --out X     # write the JSON verdict to X

It changes NOTHING in the repo and runs nothing on the wire; pure inspection.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import socket
import sys
import time

# Paths resolve against THIS file (python/ -> workspace root), so the command
# behaves identically no matter where it is launched from.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPORTS = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports")

OK, WARN, FAIL = "OK", "WARN", "FAIL"
_GLYPH = {OK: "[ OK ]", WARN: "[WARN]", FAIL: "[FAIL]"}

# pip distribution name -> importable module name (when they differ).
_IMPORT_NAME = {"pyyaml": "yaml", "pillow": "PIL", "opencv-python": "cv2",
                "scikit-learn": "sklearn", "stable-baselines3": "stable_baselines3"}

# The core Python tools the demo pipeline invokes. Parsing them (py_compile,
# no execution => no third-party deps needed) doubles as a KI-004 truncation
# guard: a silently-cut file fails to compile and is caught here.
_CORE_TOOLS = [
    "python_listener.py",
    os.path.join("python", "scenarios.py"),
    os.path.join("python", "scenario_controllers.py"),
    os.path.join("python", "build_evidence_pack.py"),
    os.path.join("python", "verify_run_kinematics.py"),
    os.path.join("python", "sea_state.py"),
    os.path.join("python", "ais_traffic.py"),
    os.path.join("python", "analyse_ais.py"),
    os.path.join("python", "run_logger.py"),
    "run_demo.py",
    os.path.join("Development", "bridge_harness", "ue5_client_sim.py"),
]

# Key C++ the in-engine build needs (presence + non-truncation, not compilation).
_CORE_CPP = [
    os.path.join("NaviSense_UE5", "Source", "NaviSense", "Core", "NaviSenseCoords.h"),
    os.path.join("NaviSense_UE5", "Source", "NaviSense", "Vessel", "NaviSenseShipPawn.cpp"),
    os.path.join("NaviSense_UE5", "Source", "NaviSense", "Bridge", "NaviSenseBridgeComponent.cpp"),
]

_DATA_ASSETS = [
    os.path.join("NaviSense_UE5", "Content", "NaviSense", "Settings", "Vessels",
                 "DA_DOLPHIN_VesselProfile.uasset"),
    os.path.join("NaviSense_UE5", "Content", "NaviSense", "Settings", "Vessels",
                 "DA_DOLPHIN_HydrostaticsConfig.uasset"),
]

# Cesium ion token env vars we recognise (BYO-token; documented in SETUP.md).
_CESIUM_ENV = ["CESIUM_ION_TOKEN", "CESIUM_ION_ACCESS_TOKEN", "NAVISENSE_CESIUM_TOKEN"]


class Check:
    __slots__ = ("name", "status", "detail", "required", "fix")

    def __init__(self, name, status, detail, required=True, fix=""):
        self.name = name
        self.status = status
        self.detail = detail
        self.required = required
        self.fix = fix

    def as_dict(self):
        return {"name": self.name, "status": self.status, "detail": self.detail,
                "required": self.required, "fix": self.fix}


# ---------------------------------------------------------------------------
# Individual probes
# ---------------------------------------------------------------------------
def _parse_requirements(path):
    """Return [(dist_name, import_name), ...] for the non-optional, uncommented
    lines of requirements.txt (optional deps are commented out in the file)."""
    out = []
    if not os.path.isfile(path):
        return out
    with open(path, "r", errors="replace") as fh:
        for raw in fh:
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            # strip version specifiers / extras / env markers
            dist = re.split(r"[<>=!~;\[ ]", line, 1)[0].strip().lower()
            if not dist:
                continue
            imp = _IMPORT_NAME.get(dist, dist.replace("-", "_"))
            out.append((dist, imp))
    return out


def _module_available(import_name):
    try:
        return importlib.util.find_spec(import_name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def _is_lfs_pointer(path):
    """A not-yet-pulled Git-LFS asset is a tiny text stub, not the real binary."""
    try:
        if os.path.getsize(path) > 1024:
            return False
        with open(path, "rb") as fh:
            head = fh.read(64)
        return head.startswith(b"version https://git-lfs")
    except OSError:
        return False


def _py_compiles(path):
    import py_compile
    try:
        py_compile.compile(path, doraise=True)
        return True, ""
    except py_compile.PyCompileError as e:
        return False, str(e).splitlines()[-1][:120]
    except OSError as e:
        return False, str(e)[:120]


def _port_free(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def run_checks(host="127.0.0.1", port=5005):
    checks = []

    # 1. Python version (>=3.8 required, >=3.10 recommended)
    v = sys.version_info
    if v < (3, 8):
        st = FAIL
    elif v < (3, 10):
        st = WARN
    else:
        st = OK
    checks.append(Check("python_version", st, f"{v.major}.{v.minor}.{v.micro}",
                        required=True, fix="install Python 3.10+"))

    # 2. Required Python deps importable (the clean-machine pip gate)
    reqs = _parse_requirements(os.path.join(ROOT, "requirements.txt"))
    if not reqs:
        checks.append(Check("python_deps", WARN, "requirements.txt not found/empty",
                            required=True, fix="restore requirements.txt"))
    else:
        missing = [d for d, imp in reqs if not _module_available(imp)]
        checks.append(Check(
            "python_deps",
            OK if not missing else FAIL,
            f"{len(reqs)-len(missing)}/{len(reqs)} present"
            + (f"; missing: {', '.join(missing)}" if missing else ""),
            required=True,
            fix="pip install -r requirements.txt" if missing else ""))

    # 3. Core Python tools present AND parse (KI-004 truncation guard)
    miss = [t for t in _CORE_TOOLS if not os.path.isfile(os.path.join(ROOT, t))]
    bad = []
    if not miss:
        for t in _CORE_TOOLS:
            okc, why = _py_compiles(os.path.join(ROOT, t))
            if not okc:
                bad.append(f"{t} ({why})")
    if miss:
        checks.append(Check("core_tools", FAIL, f"missing: {', '.join(miss)}",
                            required=True, fix="restore from the repo / git checkout"))
    elif bad:
        checks.append(Check("core_tools", FAIL, f"syntax/truncation: {'; '.join(bad)}",
                            required=True, fix="re-pull the file (KI-004 truncation)"))
    else:
        checks.append(Check("core_tools", OK,
                            f"{len(_CORE_TOOLS)} tools present + parse clean",
                            required=True))

    # 4. MMG plant data
    mmg = os.path.join(ROOT, "Maneuvering", "maniobrabilidad", "mmg")
    dolphin = os.path.join(mmg, "DOLPHIN.yaml")
    if os.path.isdir(mmg) and os.path.isfile(dolphin):
        checks.append(Check("mmg_plant", OK, "MMG dir + DOLPHIN.yaml present",
                            required=True))
    elif os.path.isdir(mmg):
        checks.append(Check("mmg_plant", WARN, "MMG dir present, DOLPHIN.yaml missing",
                            required=True, fix="restore DOLPHIN.yaml (or use --plant stub)"))
    else:
        checks.append(Check("mmg_plant", FAIL, "MMG dir absent",
                            required=True, fix="git checkout Maneuvering/ (or --plant stub)"))

    # 5. UE project file present + parses + plugin references
    uproj = os.path.join(ROOT, "NaviSense_UE5", "NaviSense_UE5.uproject")
    if not os.path.isfile(uproj):
        checks.append(Check("ue_project", FAIL, "NaviSense_UE5.uproject missing",
                            required=True, fix="git checkout NaviSense_UE5/"))
    else:
        try:
            with open(uproj, "r", errors="replace") as fh:
                up = json.load(fh)
            eng = up.get("EngineAssociation", "?")
            plugins = {p.get("Name", "") for p in up.get("Plugins", [])}
            water = "Water" in plugins
            ces = any("Cesium" in p for p in plugins)
            checks.append(Check(
                "ue_project", OK,
                f"engine {eng}; Water={'on' if water else 'off'}, "
                f"Cesium={'ref' if ces else 'none'}", required=True))
        except (json.JSONDecodeError, OSError) as e:
            checks.append(Check("ue_project", FAIL, f"unparseable: {e}",
                                required=True, fix="restore a valid .uproject"))

    # 6. Core C++ present + non-truncated (brace-balanced heuristic; KI-004/KI-015)
    cmiss, ctrunc = [], []
    for c in _CORE_CPP:
        p = os.path.join(ROOT, c)
        if not os.path.isfile(p):
            cmiss.append(os.path.basename(c))
            continue
        try:
            with open(p, "r", errors="replace") as fh:
                txt = fh.read()
            if txt.count("{") != txt.count("}"):
                ctrunc.append(os.path.basename(c))
        except OSError:
            ctrunc.append(os.path.basename(c))
    if cmiss:
        checks.append(Check("ue_source", FAIL, f"missing: {', '.join(cmiss)}",
                            required=True, fix="git checkout the Source tree"))
    elif ctrunc:
        checks.append(Check("ue_source", FAIL, f"brace-unbalanced: {', '.join(ctrunc)}",
                            required=True, fix="re-pull (KI-004/KI-015 truncation)"))
    else:
        checks.append(Check("ue_source", OK,
                            f"{len(_CORE_CPP)} key C++ files present + brace-balanced",
                            required=True))

    # 7. Vessel data assets present + actually pulled (not bare LFS pointers)
    amiss = [os.path.basename(a) for a in _DATA_ASSETS
             if not os.path.isfile(os.path.join(ROOT, a))]
    aptr = [os.path.basename(a) for a in _DATA_ASSETS
            if os.path.isfile(os.path.join(ROOT, a))
            and _is_lfs_pointer(os.path.join(ROOT, a))]
    if amiss:
        checks.append(Check("data_assets", FAIL, f"missing: {', '.join(amiss)}",
                            required=True,
                            fix="recreate via Tools->06_create_hydrostatics_config.py (KI-013)"))
    elif aptr:
        checks.append(Check("data_assets", FAIL,
                            f"LFS not pulled (stub): {', '.join(aptr)}",
                            required=True, fix="git lfs pull"))
    else:
        checks.append(Check("data_assets", OK,
                            "DA_DOLPHIN VesselProfile + HydrostaticsConfig present",
                            required=True))

    # 8. Cesium ion token (BYO; optional -- documented, not needed headless)
    tok = next((e for e in _CESIUM_ENV if os.environ.get(e)), None)
    if tok:
        checks.append(Check("cesium_token", OK, f"{tok} set", required=False))
    else:
        checks.append(Check(
            "cesium_token", WARN,
            "no Cesium ion token in env (photoreal 3D Tiles only; headless "
            "pipeline + synthetic GPS do NOT need it -- see SETUP.md)",
            required=False, fix="set CESIUM_ION_TOKEN (SETUP.md 'Cesium token')"))

    # 9. git + git-lfs available (needed to pull binary assets on a fresh clone)
    git = shutil.which("git")
    lfs = shutil.which("git-lfs") or _git_has_lfs(git)
    gattr = os.path.join(ROOT, ".gitattributes")
    lfs_cfg = False
    if os.path.isfile(gattr):
        try:
            with open(gattr, "r", errors="replace") as fh:
                lfs_cfg = "filter=lfs" in fh.read()
        except OSError:
            pass
    if git and lfs and lfs_cfg:
        checks.append(Check("git_lfs", OK, "git + git-lfs available, .gitattributes LFS-configured",
                            required=False))
    elif not git:
        checks.append(Check("git_lfs", WARN, "git not found (only needed to clone/pull)",
                            required=False, fix="install Git"))
    elif not lfs:
        checks.append(Check("git_lfs", WARN, "git-lfs not found -> .uasset assets won't pull",
                            required=False, fix="install Git LFS, then: git lfs install"))
    else:
        checks.append(Check("git_lfs", WARN, ".gitattributes missing LFS filter",
                            required=False, fix="restore .gitattributes"))

    # 10. Logs dir writable (the run pipeline writes logs/<run>/)
    logs = os.path.join(ROOT, "logs")
    probe = os.path.join(logs, ".repro_doctor_write_probe")
    try:
        os.makedirs(logs, exist_ok=True)
        with open(probe, "w") as fh:
            fh.write("ok")
        try:
            os.remove(probe)
        except OSError:
            pass  # sandbox can't unlink on D: (KI-004); the write succeeding is the test
        checks.append(Check("logs_writable", OK, "logs/ writable", required=True))
    except OSError as e:
        checks.append(Check("logs_writable", FAIL, f"logs/ not writable: {e}",
                            required=True, fix="check folder permissions / disk full"))

    # 11. Scenario registry loads (deferred if deps not yet installed)
    try:
        if os.path.join(ROOT, "python") not in sys.path:
            sys.path.insert(0, os.path.join(ROOT, "python"))
        import scenarios as _sc  # noqa
        names = _sc.list_scenarios() if hasattr(_sc, "list_scenarios") else []
        checks.append(Check("scenario_registry", OK,
                            f"{len(names)} scenarios registered", required=False))
    except ImportError as e:
        checks.append(Check("scenario_registry", WARN,
                            f"deferred (install deps first): {type(e).__name__}",
                            required=False, fix="pip install -r requirements.txt"))
    except Exception as e:  # pragma: no cover - defensive
        checks.append(Check("scenario_registry", WARN, f"{type(e).__name__}: {e}",
                            required=False))

    # 12. Default bridge port free (transient; informational)
    free = _port_free(host, port)
    checks.append(Check("port_free", OK if free else WARN,
                        f"{host}:{port} " + ("free" if free else "in use"),
                        required=False,
                        fix="" if free else "stop the other listener / pick --port"))

    return checks


def _git_has_lfs(git):
    if not git:
        return False
    try:
        import subprocess
        r = subprocess.run([git, "lfs", "version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Verdict + reporting
# ---------------------------------------------------------------------------
def verdict(checks, strict=False):
    req_fail = [c for c in checks if c.required and c.status == FAIL]
    req_warn = [c for c in checks if c.required and c.status == WARN]
    opt_issue = [c for c in checks if not c.required and c.status in (WARN, FAIL)]
    if req_fail:
        ok = False
    elif strict and req_warn:
        ok = False
    else:
        ok = True
    return {
        "ready": ok,
        "strict": strict,
        "counts": {
            "ok": sum(c.status == OK for c in checks),
            "warn": sum(c.status == WARN for c in checks),
            "fail": sum(c.status == FAIL for c in checks),
            "total": len(checks),
        },
        "required_failures": [c.name for c in req_fail],
        "required_warnings": [c.name for c in req_warn],
        "optional_issues": [c.name for c in opt_issue],
    }


def print_report(checks, vd):
    print("NaviSense clean-machine readiness (D8)  --  repro_doctor")
    print("-" * 64)
    for c in checks:
        tag = "" if c.required else " (optional)"
        line = f"  {_GLYPH[c.status]} {c.name:18s} {c.detail}{tag}"
        print(line)
        if c.status != OK and c.fix:
            print(f"         -> fix: {c.fix}")
    print("-" * 64)
    cnt = vd["counts"]
    print(f"  {cnt['ok']} OK / {cnt['warn']} WARN / {cnt['fail']} FAIL"
          f"   (strict={vd['strict']})")
    print("  VERDICT: " + ("READY" if vd["ready"] else "NOT READY"))
    if vd["required_failures"]:
        print("  blocking: " + ", ".join(vd["required_failures"]))
    if vd["strict"] and vd["required_warnings"]:
        print("  blocking (strict): " + ", ".join(vd["required_warnings"]))


def main():
    ap = argparse.ArgumentParser(
        description="NaviSense clean-machine readiness / reproducibility doctor (D8).")
    ap.add_argument("--strict", action="store_true",
                    help="Demo-day mode: a required WARN also fails the verdict.")
    ap.add_argument("--json", action="store_true", help="Also print the JSON verdict.")
    ap.add_argument("--out", default=None,
                    help="Write the JSON verdict here (default: "
                         "Saved/NaviSense_Reports/repro.json).")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5005)
    ap.add_argument("--quiet", action="store_true", help="Suppress the table.")
    args = ap.parse_args()

    checks = run_checks(args.host, args.port)
    vd = verdict(checks, strict=args.strict)
    report = {
        "tool": "repro_doctor",
        "packet": "WP-20260625",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "verdict": vd,
        "checks": [c.as_dict() for c in checks],
    }

    if not args.quiet:
        print_report(checks, vd)
    if args.json:
        print(json.dumps(report, indent=2))

    out = args.out or os.path.join(REPORTS, "repro.json")
    try:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w") as fh:
            json.dump(report, fh, indent=2)
        if not args.quiet:
            print(f"  wrote {out}")
    except OSError as e:
        print(f"  (could not write {out}: {e})", file=sys.stderr)

    return 0 if vd["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
