#!/usr/bin/env python3
"""verify_20260709c -- WP-20260709C gate: terminal scenario runner + editor-spawn fix.

  G1  RUNNER-MAPPING -- run_colregs.py exposes exactly the four scenario flags
                        and --dry-run builds the right listener command
                        (--scenario colregs_overtaking --once; --ship appends
                        --target-name).
  G2  E2E-SELFTEST   -- a fresh `run_colregs --head-on --selftest` run exists in
                        logs/_selftest (isolated, 25x, run-id colregs-*-selftest)
                        and its per-scenario result file is PASS (auto-verify
                        fired on THAT run dir).
  G3  PICKER-FIXED   -- KI-036: the editor picker no longer Popens sys.executable
                        (which is UnrealEditor.exe inside editor Python -> a new
                        blank editor window); it prints the run_colregs command,
                        defaults to setup_scenery_target(), and keeps
                        pick()/reset_all().
  G4  REGRESSION     -- verify_20260709b still 5/5+3/3 (rc 0).

Negative controls:
  N1  no scenario flag  -> usage error (exit 2).
  N2  two scenario flags -> usage error (exit 2).
  N3  the pre-fix auto-launch pattern (Popen of sys.executable on the listener)
      is DETECTED by G3's source check on a tmp copy.

Writes Saved/NaviSense_Reports/wp_20260709c_result.json; exit 0 iff all pass.
"""
from __future__ import annotations
import glob, json, os, re, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports",
                   "wp_20260709c_result.json")
RUNNER = os.path.join(ROOT, "run_colregs.py")
PICKER = os.path.join(ROOT, "NaviSense_UE5", "Content", "NaviSense", "Python",
                      "Phase5_Systems", "10_colregs_encounter.py")
FLAGS = {"--head-on": "colregs_head_on", "--crossing-giveway": "colregs_crossing_giveway",
         "--crossing-standon": "colregs_crossing_standon", "--overtaking": "colregs_overtaking"}


def run(args):
    return subprocess.run([sys.executable, RUNNER] + args,
                          capture_output=True, text=True, cwd=ROOT)


def check_picker(src: str):
    if re.search(r"Popen\(\s*cmd", src) or "CREATE_NEW_CONSOLE" in src:
        return False, "picker still auto-launches a subprocess (KI-036 pattern present)"
    if "sys.executable" in src.replace("import sys", ""):
        return False, "picker still references sys.executable for launching"
    for needed in ("run_colregs.py", "setup_scenery_target", "def pick", "def reset_all"):
        if needed not in src:
            return False, f"picker missing '{needed}'"
    if "setup_scenery_target()" not in src.split('__main__')[-1]:
        return False, "picker __main__ does not default to setup_scenery_target()"
    return True, "no auto-launch; prints run_colregs command; scenery-setup default"


def main() -> int:
    checks, neg = [], []

    # G1 runner mapping
    ok, det = True, []
    lst = run(["--list"])
    for flag, sc in FLAGS.items():
        if sc not in lst.stdout:
            ok, det = False, [f"--list missing {sc}"]
            break
    if ok:
        d = run(["--overtaking", "--dry-run"])
        e = run(["--head-on", "--ship", "Yacht_with_interior", "--dry-run"])
        ok = (d.returncode == 0 and "--scenario colregs_overtaking" in d.stdout
              and "--once" in d.stdout
              and e.returncode == 0 and "--target-name Yacht_with_interior" in e.stdout)
        det = ["4 flags -> 4 scenarios; dry-run cmd correct incl. --ship passthrough"] if ok \
            else [f"dry-run wrong: {d.stdout.strip()[:100]} / {e.stdout.strip()[:100]}"]
    checks.append({"id": "G1", "name": "runner-mapping", "pass": ok, "detail": det[0]})

    # G2 e2e selftest evidence (produced this session by run_colregs --head-on --selftest)
    runs = sorted(glob.glob(os.path.join(ROOT, "logs", "_selftest",
                                         "colregs-colregs_head_on-selftest_*")),
                  key=os.path.getmtime)
    g2, det = False, "no run_colregs selftest run found"
    if runs:
        d = runs[-1]
        fresh = (time.time() - os.path.getmtime(d)) < 24 * 3600
        rp = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports",
                          "colregs_head_on_result.json")
        r = json.load(open(rp)) if os.path.isfile(rp) else {}
        g2 = fresh and r.get("pass") is True and os.path.basename(d) in str(r.get("run_dir"))
        det = (f"{os.path.basename(d)} fresh={fresh}; result pass={r.get('pass')}; "
               f"verified THAT run={os.path.basename(d) in str(r.get('run_dir'))}")
    checks.append({"id": "G2", "name": "e2e-selftest", "pass": g2, "detail": det})

    # G3 picker fixed
    ok, det = check_picker(open(PICKER, encoding="utf-8").read())
    checks.append({"id": "G3", "name": "picker-fixed", "pass": ok, "detail": det})

    # G4 regression
    r = subprocess.run([sys.executable, os.path.join(ROOT, "python", "verify_20260709b.py")],
                       capture_output=True, text=True, cwd=ROOT)
    checks.append({"id": "G4", "name": "regression", "pass": r.returncode == 0,
                   "detail": f"verify_20260709b rc={r.returncode}"})

    # negs
    r = run(["--dry-run"])
    neg.append({"id": "N1", "name": "no scenario flag rejected", "pass": r.returncode == 2,
                "detail": f"rc={r.returncode}"})
    r = run(["--head-on", "--overtaking", "--dry-run"])
    neg.append({"id": "N2", "name": "two scenario flags rejected", "pass": r.returncode == 2,
                "detail": f"rc={r.returncode}"})
    bad = open(PICKER, encoding="utf-8").read() + (
        "\ndef _old():\n    subprocess.Popen(cmd, cwd=ws, "
        "creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))\n")
    ok, det = check_picker(bad)
    neg.append({"id": "N3", "name": "auto-launch pattern detected", "pass": not ok, "detail": det})

    ok_all = all(c["pass"] for c in checks) and all(n["pass"] for n in neg)
    result = {"packet": "WP-20260709C", "date": time.strftime("%Y-%m-%d"),
              "title": "terminal COLREGS runner (run_colregs.py) + KI-036 editor-spawn fix",
              "pass": ok_all,
              "gates_passed": sum(c["pass"] for c in checks), "gates_total": len(checks),
              "neg_passed": sum(n["pass"] for n in neg), "neg_total": len(neg),
              "checks": checks, "neg_controls": neg}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(result, open(OUT, "w", encoding="utf-8"), indent=2)
    for c in checks + neg:
        print(f"  {c['id']} {c['name']:<28} {'PASS' if c['pass'] else 'FAIL'}  {c['detail']}")
    print(f"[wp_20260709c] {'PASS' if ok_all else 'FAIL'} -> {OUT}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
