#!/usr/bin/env python3
"""verify_colregs -- ONE command that independently verifies a COLREGS run.

Each colregs_* scenario is run independently (editor picker or run_demo) and
verified independently by this tool -- no cross-scenario coupling. It reads the
run's own manifest (scenario, AIS preset, optional aisTargetName), so you never
pass the preset by hand:

  python python/verify_colregs.py --latest              # newest colregs run
  python python/verify_colregs.py --run-dir logs/<run>
  python python/verify_colregs.py --matrix              # roll-up of all four

Checks (per run):
  V1  HEALTH   -- verify_run_kinematics passes (no NaN/spin/clock fault).
  V2  VERDICT  -- colregs_score: 1 compliant / 0 non-compliant for the run's
                  own preset (geometry from state.csv, duty per Rules 8/13-17).
  V3  IDENTITY -- the target name on the wire is the REAL ship: manifest
                  aisTargetName (if swapped) or the preset default; never a
                  legacy fictional name. Cross-checked against sensor_raw.jsonl
                  when present (real PIE runs; headless selftest has no echo).

Writes Saved/NaviSense_Reports/colregs_<scenario>_result.json -- one file per
scenario, so all four can be green side by side. --matrix aggregates them into
colregs_matrix_result.json. Exit 0 iff the addressed run (or matrix) passes.
"""
from __future__ import annotations
import argparse, glob, json, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
REPORTS = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports")
LOGS = os.path.join(ROOT, "logs")
SCENARIOS = ["colregs_head_on", "colregs_crossing_giveway",
             "colregs_crossing_standon", "colregs_overtaking"]
FICTIONAL = {"MERIDIAN", "AZURFERRY", "SLOWBELLE", "PORTSTAR"}


def _manifest(run_dir):
    """Tolerant read: an interrupted run can leave a truncated manifest
    (KI-030 family) -- treat it as 'not a colregs run', never crash."""
    p = os.path.join(run_dir, "manifest.json")
    try:
        return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else {}
    except Exception:
        return {}


def find_latest_colregs(logs_dir=LOGS, scenario=None):
    """Newest run (incl. logs/_selftest) whose manifest scenario is colregs_*."""
    best, best_m = None, -1.0
    pools = [logs_dir, os.path.join(logs_dir, "_selftest")]
    for pool in pools:
        if not os.path.isdir(pool):
            continue
        for name in os.listdir(pool):
            d = os.path.join(pool, name)
            if not os.path.isdir(d) or name.startswith("_"):
                continue
            sc = _manifest(d).get("scenario", "")
            if not str(sc).startswith("colregs_"):
                continue
            if scenario and sc != scenario:
                continue
            m = os.path.getmtime(d)
            if m > best_m:
                best, best_m = d, m
    return best


def evaluate(run_dir):
    checks = []
    man = _manifest(run_dir)
    scenario, preset = man.get("scenario"), man.get("ais")
    target = man.get("aisTargetName")
    if not (scenario and str(scenario).startswith("colregs_") and preset):
        return scenario, [{"id": "V0", "name": "manifest", "pass": False,
                           "detail": f"not a colregs run (scenario={scenario!r}, ais={preset!r})"}]

    r = subprocess.run([sys.executable, os.path.join(ROOT, "python",
                        "verify_run_kinematics.py"), "--run-dir", run_dir],
                       capture_output=True, text=True, cwd=ROOT)
    checks.append({"id": "V1", "name": "health", "pass": r.returncode == 0,
                   "detail": (r.stdout.strip().splitlines()[-2:] or ["<no out>"])[0].strip()})

    cmd = [sys.executable, os.path.join(ROOT, "python", "colregs_score.py"),
           "--run-dir", run_dir, "--ais", preset]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    ok = r.returncode == 0 and "1 compliant / 0 non-compliant" in r.stdout
    tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "<no out>"
    checks.append({"id": "V2", "name": "verdict", "pass": ok, "detail": tail})

    from python.ais_traffic import make_field
    expected = target or make_field(preset, 0, 0, 0).targets[0].name
    ok, det = expected not in FICTIONAL and bool(expected), f"expected target '{expected}'"
    raw = os.path.join(run_dir, "sensor_raw.jsonl")
    if ok and os.path.isfile(raw):                     # real PIE run: cross-check the wire
        seen = set()
        with open(raw, encoding="utf-8") as f:
            for line in f:
                try:
                    for t in ((json.loads(line).get("msg", {}).get("sensors") or {})
                              .get("ais") or {}).get("targets", []):
                        seen.add(t.get("name"))
                except Exception:
                    pass
        if seen:
            ok = expected in seen
            det += f"; wire names {sorted(seen)} -> {'match' if ok else 'MISMATCH'}"
        else:
            det += "; wire had no populated ais.targets (headless echo?)"
    else:
        det += "; no sensor_raw.jsonl (headless selftest) -- manifest/preset only"
    checks.append({"id": "V3", "name": "identity", "pass": ok, "detail": det})
    return scenario, checks


def write_result(scenario, run_dir, checks, out_dir):
    npass = sum(1 for c in checks if c["pass"])
    result = {"tool": "verify_colregs", "scenario": scenario,
              "run_dir": os.path.abspath(run_dir) if run_dir else None,
              "date": time.strftime("%Y-%m-%d %H:%M:%S"),
              "pass": npass == len(checks),
              "gates_passed": npass, "gates_total": len(checks), "checks": checks}
    os.makedirs(out_dir, exist_ok=True)
    stem = scenario or "unknown"
    stem = stem if stem.startswith("colregs_") else f"colregs_{stem}"
    path = os.path.join(out_dir, f"{stem}_result.json")
    json.dump(result, open(path, "w", encoding="utf-8"), indent=2)
    return result, path


def _load_result(path):
    """Load a scenario result JSON, tolerating trailing NUL / whitespace padding
    (KI-042: the D: mount can NUL-pad a freshly written result file; the JSON body is
    intact). Returns (obj, note); (None, reason) if the JSON body itself is unparseable
    so a genuinely truncated/corrupt file still FAILs rather than crashing the matrix."""
    try:
        raw = open(path, "rb").read()
    except OSError as e:
        return None, f"unreadable ({e})"
    stripped = raw.rstrip(b"\x00").rstrip()
    padded = len(stripped) != len(raw)
    try:
        obj = json.loads(stripped.decode("utf-8", "replace"))
    except json.JSONDecodeError as e:
        return None, f"corrupt JSON ({e})"
    return obj, ("recovered (stripped trailing padding)" if padded else None)


def matrix(out_dir):
    rows, all_pass = [], True
    for sc in SCENARIOS:
        p = os.path.join(out_dir, f"{sc}_result.json")
        if not os.path.isfile(p):
            rows.append({"scenario": sc, "status": "MISSING", "run_dir": None})
            all_pass = False
            continue
        r, note = _load_result(p)
        if r is None:
            rows.append({"scenario": sc, "status": "CORRUPT", "run_dir": None, "note": note})
            all_pass = False
            continue
        row = {"scenario": sc, "status": "PASS" if r.get("pass") else "FAIL",
               "run_dir": r.get("run_dir"), "date": r.get("date")}
        if note:
            row["note"] = note
        rows.append(row)
        all_pass = all_pass and r.get("pass") is True
    result = {"tool": "verify_colregs --matrix", "pass": all_pass,
              "date": time.strftime("%Y-%m-%d %H:%M:%S"), "scenarios": rows}
    json.dump(result, open(os.path.join(out_dir, "colregs_matrix_result.json"),
                           "w", encoding="utf-8"), indent=2)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run-dir")
    g.add_argument("--latest", action="store_true")
    g.add_argument("--matrix", action="store_true",
                   help="aggregate the four per-scenario result files")
    ap.add_argument("--scenario", default=None,
                    help="with --latest: restrict to one scenario name")
    ap.add_argument("--out-dir", default=REPORTS)
    args = ap.parse_args(argv)

    if args.matrix:
        res = matrix(args.out_dir)
        for row in res["scenarios"]:
            print(f"  {row['scenario']:<28} {row['status']}"
                  + (f"  ({os.path.basename(row['run_dir'] or '')})" if row.get("run_dir") else ""))
        print(f"[colregs] matrix {'PASS 4/4' if res['pass'] else 'INCOMPLETE'} "
              f"-> {os.path.join(args.out_dir, 'colregs_matrix_result.json')}")
        return 0 if res["pass"] else 1

    run_dir = args.run_dir or find_latest_colregs(scenario=args.scenario)
    if not run_dir or not os.path.isdir(run_dir):
        print("[colregs] FAIL: no colregs run found (run one via the picker or "
              "run_demo --scenario colregs_<name>)")
        return 1
    scenario, checks = evaluate(run_dir)
    result, path = write_result(scenario, run_dir, checks, args.out_dir)
    for c in checks:
        print(f"  {c['id']} {c['name']:<9} {'PASS' if c['pass'] else 'FAIL'}  {c['detail']}")
    print(f"[colregs] {scenario}: {'PASS' if result['pass'] else 'FAIL'} "
          f"{result['gates_passed']}/{result['gates_total']} on {os.path.basename(run_dir)} -> {path}")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
