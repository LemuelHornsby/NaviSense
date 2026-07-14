#!/usr/bin/env python3
"""One-command DEMO-SESSION closeout (WP-20260709D, T-2).

After the live PIE/capture session, run ONE command instead of four:

  python python/verify_demo_session.py --film-dir "%USERPROFILE%\\Videos\\Captures"

Sections (each is an existing, already-gated tool run as a subprocess):

  sensors  -> verify_sensor_suite.py --latest          G_AIS/G_RADAR/G_CAMERA (D4)
  capture  -> verify_capture_artifacts.py --latest     G_CAPTURE_UE (D6)
              [+ --film-dir => C3 film gate]           G_FILM_UE   (D7)
  colregs  -> verify_colregs.py --matrix               G_COLREGS_UE (4 scenarios)

Writes Saved/NaviSense_Reports/demo_session_result.json. Exit 0 iff every
non-skipped section passes. --skip sensors,capture,colregs to narrow (at least
one section must remain). HONESTY: G_TRAFFIC_UE (ships visibly moving, correct
orientation post-KI-034) and the D2 SS5 wave-ride remain EYE-CHECKS -- this
tool cannot close them and says so in the result file. Stdlib only.
"""
import argparse, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPORTS = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports")
DEFAULT_OUT = os.path.join(REPORTS, "demo_session_result.json")

SECTIONS = ("sensors", "capture", "colregs")

GATE_MAP = {
    "sensors": ["G_AIS_SENSOR_UE", "G_RADAR_UE", "G_CAMERA_UE"],
    "capture": ["G_CAPTURE_UE"],  # + G_FILM_UE when --film-dir given
    "colregs": ["G_COLREGS_UE"],
}
SUB_RESULT = {
    "sensors": os.path.join(REPORTS, "sensor_suite_result.json"),
    "capture": os.path.join(REPORTS, "capture_artifacts_result.json"),
    "colregs": os.path.join(REPORTS, "colregs_matrix_result.json"),
}


def _cmd(section, film_dir):
    py = sys.executable
    if section == "sensors":
        return [py, os.path.join(HERE, "verify_sensor_suite.py"), "--latest"]
    if section == "capture":
        c = [py, os.path.join(HERE, "verify_capture_artifacts.py"), "--latest"]
        if film_dir:
            c += ["--film-dir", film_dir]
        return c
    if section == "colregs":
        return [py, os.path.join(HERE, "verify_colregs.py"), "--matrix"]
    raise ValueError(section)


def _run(section, film_dir):
    cmd = _cmd(section, film_dir)
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           timeout=300)
        rc, tail = p.returncode, (p.stdout + p.stderr).strip()[-600:]
    except Exception as e:  # tool missing / timeout
        rc, tail = 97, f"launch failed: {e}"
    sub = None
    try:
        with open(SUB_RESULT[section], "r", encoding="utf-8") as f:
            sub = json.load(f)
    except Exception:
        pass
    gates = list(GATE_MAP[section])
    if section == "capture" and film_dir:
        gates.append("G_FILM_UE")
    return {"section": section, "cmd": " ".join(cmd), "rc": rc,
            "pass": rc == 0, "gates": gates, "tail": tail,
            "sub_result": os.path.basename(SUB_RESULT[section]) if sub else None,
            "sub_pass": (sub or {}).get("pass")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--film-dir", default=None,
                    help="pass through to verify_capture_artifacts (G_FILM_UE C3)")
    ap.add_argument("--skip", default="",
                    help="comma list of sections to skip: sensors,capture,colregs")
    ap.add_argument("--json-out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    skip = [s.strip() for s in args.skip.split(",") if s.strip()]
    bad = [s for s in skip if s not in SECTIONS]
    if bad:
        ap.error(f"unknown --skip section(s): {bad}; valid: {SECTIONS}")
    todo = [s for s in SECTIONS if s not in skip]
    if not todo:
        ap.error("all sections skipped -- nothing to verify")
    if args.film_dir and not os.path.isdir(args.film_dir):
        print(f"[demo-session] FAIL: --film-dir does not exist: {args.film_dir}")
        return 2

    results = [_run(s, args.film_dir) for s in todo]
    all_pass = all(r["pass"] for r in results)
    out = {
        "tool": "verify_demo_session",
        "packet": "WP-20260709D",
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pass": all_pass,
        "sections": results,
        "skipped": skip,
        "gates_closed": sorted(g for r in results if r["pass"] for g in r["gates"]),
        "gates_failed": sorted(g for r in results if not r["pass"] for g in r["gates"]),
        "eye_checks_remaining": [
            "G_TRAFFIC_UE: ships visibly move, orientation OK post-KI-034 recompile",
            "D2 SS5 wave-ride re-check (rough_turning_circle, hydrostatics active)",
        ],
        "honesty": "screen-recorded demo capture, not an MRQ cinematic render",
    }
    os.makedirs(REPORTS, exist_ok=True)
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    for r in results:
        print(f"[demo-session] {r['section']:8s} "
              f"{'PASS' if r['pass'] else 'FAIL':4s} rc={r['rc']} "
              f"gates={','.join(r['gates'])}")
    if skip:
        print(f"[demo-session] skipped: {','.join(skip)}")
    print(f"[demo-session] {'SESSION PASS' if all_pass else 'SESSION INCOMPLETE'}"
          f" -> {args.json_out}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
