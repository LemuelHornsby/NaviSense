#!/usr/bin/env python3
"""verify_20260709b -- WP-20260709B gate: rescue-boat default target +
independently runnable / independently verifiable COLREGS scenarios.

  G1  DEFAULT-TARGET -- all four colregs presets name DEFAULT_COLREGS_TARGET
                        ("marine_rescue_boat"), and the editor picker's
                        TARGET_SHIP equals it (one source of truth).
  G2  SWAP-PATH      -- make_field(target_name=...) renames a single-target
                        preset (name + known ship type); the picker source
                        passes --target-name; the listener exposes the flag and
                        threads it to make_field + the run manifest
                        (aisTargetName).
  G3  INDEPENDENT-VERIFY -- verify_colregs exists and its four per-scenario
                        result files are PASS on disk (each from its OWN run),
                        and the --matrix roll-up is PASS 4/4.
  G4  SWAP-E2E       -- the freshest head_on selftest run used
                        --target-name Yacht_with_interior: manifest
                        aisTargetName recorded, verdict COMPLIANT, identity
                        gate PASS (proves swap flows preset->wire->manifest->verify).
  G5  REGRESSION     -- verify_20260709 (revised) 5/5+3/3 and
                        verify_20260629b (monaco_capture untouched) exit 0.

Negative controls:
  N1  a fictional target name in a colregs preset FAILS the G1-style check.
  N2  make_field(target_name=...) on a MULTI-target preset raises ValueError
      (monaco_capture's slot mapping cannot be renamed by one label).
  N3  verify_colregs on a non-colregs run dir FAILS (cannot fake a verdict).

Writes Saved/NaviSense_Reports/wp_20260709b_result.json; exit 0 iff all pass.
"""
from __future__ import annotations
import glob, json, os, re, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports",
                   "wp_20260709b_result.json")
REPORTS = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports")
PICKER = os.path.join(ROOT, "NaviSense_UE5", "Content", "NaviSense", "Python",
                      "Phase5_Systems", "10_colregs_encounter.py")
PRESETS = ["head_on_avoid", "crossing_avoid", "overtaking_avoid", "crossing_standon"]
SCENARIOS = ["colregs_head_on", "colregs_crossing_giveway",
             "colregs_crossing_standon", "colregs_overtaking"]


def check_default_target(names_of):
    from python.ais_traffic import DEFAULT_COLREGS_TARGET as D
    for p in PRESETS:
        names = names_of(p)
        if names != [D]:
            return False, f"preset '{p}' names {names} != ['{D}']"
    psrc = open(PICKER, encoding="utf-8").read()
    m = re.search(r'^TARGET_SHIP\s*=\s*"([\w_]+)"', psrc, re.M)
    if not m or m.group(1) != D:
        return False, f"picker TARGET_SHIP {m.group(1) if m else None!r} != '{D}'"
    return True, f"4 presets + picker TARGET_SHIP all '{D}'"


def main() -> int:
    checks, neg = [], []
    from python.ais_traffic import make_field

    def names_of(preset, **kw):
        return [t.name for t in make_field(preset, 0, 0, 0, **kw).targets]

    ok, det = check_default_target(names_of)
    checks.append({"id": "G1", "name": "default-target", "pass": ok, "detail": det})

    # G2 swap path
    try:
        f = make_field("head_on_avoid", 0, 0, 0, target_name="Yacht_with_interior")
        t = f.targets[0]
        swap_ok = t.name == "Yacht_with_interior" and t.ship_type == "yacht"
        det = f"override -> ({t.name}, {t.ship_type})"
    except Exception as e:
        swap_ok, det = False, f"override raised {e!r}"
    psrc = open(PICKER, encoding="utf-8").read()
    lsrc = open(os.path.join(ROOT, "python_listener.py"), encoding="utf-8").read()
    plumbing = ("--target-name" in psrc and "--target-name" in lsrc
                and "target_name=ais_target_name" in lsrc
                and "aisTargetName" in open(os.path.join(ROOT, "python", "run_logger.py"),
                                            encoding="utf-8").read())
    checks.append({"id": "G2", "name": "swap-path", "pass": swap_ok and plumbing,
                   "detail": det + f"; picker/listener/manifest plumbing={plumbing}"})

    # G3 independent verify: four per-scenario PASS files from four distinct runs + matrix
    runs, all_ok = set(), True
    for sc in SCENARIOS:
        p = os.path.join(REPORTS, f"{sc}_result.json")
        r = json.load(open(p)) if os.path.isfile(p) else {}
        all_ok = all_ok and r.get("pass") is True
        runs.add(r.get("run_dir"))
    m = subprocess.run([sys.executable, os.path.join(ROOT, "python", "verify_colregs.py"),
                        "--matrix"], capture_output=True, text=True, cwd=ROOT)
    g3 = all_ok and len(runs) == 4 and None not in runs and m.returncode == 0
    checks.append({"id": "G3", "name": "independent-verify", "pass": g3,
                   "detail": f"4 per-scenario PASS files from {len(runs)} distinct runs; "
                             f"matrix rc={m.returncode}"})

    # G4 swap e2e: newest head_on selftest run with aisTargetName
    cands = sorted(glob.glob(os.path.join(ROOT, "logs", "_selftest", "demo-colregs_head_on_*")),
                   key=os.path.getmtime)
    g4, det = False, "no head_on selftest run found"
    for d in reversed(cands):
        try:
            man = json.load(open(os.path.join(d, "manifest.json")))
        except Exception:
            continue
        if man.get("aisTargetName") == "Yacht_with_interior":
            # --out-dir tmp: the swap-e2e check must NOT overwrite the canonical
            # per-scenario result file (that one belongs to the DEFAULT-target run).
            with tempfile.TemporaryDirectory(prefix="wp09b_g4_") as g4tmp:
                v = subprocess.run([sys.executable,
                                    os.path.join(ROOT, "python", "verify_colregs.py"),
                                    "--run-dir", d, "--out-dir", g4tmp],
                                   capture_output=True, text=True, cwd=ROOT)
            g4 = v.returncode == 0 and "PASS 3/3" in v.stdout
            det = f"{os.path.basename(d)}: manifest aisTargetName recorded; verify rc={v.returncode}"
            break
    checks.append({"id": "G4", "name": "swap-e2e", "pass": g4, "detail": det})

    # G5 regression
    r09 = subprocess.run([sys.executable, os.path.join(ROOT, "python", "verify_20260709.py")],
                         capture_output=True, text=True, cwd=ROOT)
    r29 = subprocess.run([sys.executable, os.path.join(ROOT, "python", "verify_20260629b.py")],
                         capture_output=True, text=True, cwd=ROOT)
    checks.append({"id": "G5", "name": "regression",
                   "pass": r09.returncode == 0 and r29.returncode == 0,
                   "detail": f"verify_20260709 rc={r09.returncode}; verify_20260629b rc={r29.returncode}"})

    # ---- negative controls ----
    ok, det = check_default_target(lambda p: ["SLOWBELLE"])
    neg.append({"id": "N1", "name": "fictional default caught", "pass": not ok, "detail": det})
    try:
        make_field("monaco_capture", 0, 0, 0, target_name="x")
        neg.append({"id": "N2", "name": "multi-target rename rejected", "pass": False,
                    "detail": "no ValueError raised"})
    except ValueError as e:
        neg.append({"id": "N2", "name": "multi-target rename rejected", "pass": True,
                    "detail": str(e)[:80]})
    with tempfile.TemporaryDirectory(prefix="wp09b_") as tmp:
        os.makedirs(os.path.join(tmp, "not_colregs"))
        json.dump({"scenario": "imo_turning_circle", "ais": None},
                  open(os.path.join(tmp, "not_colregs", "manifest.json"), "w"))
        v = subprocess.run([sys.executable, os.path.join(ROOT, "python", "verify_colregs.py"),
                            "--run-dir", os.path.join(tmp, "not_colregs"),
                            "--out-dir", tmp], capture_output=True, text=True, cwd=ROOT)
        neg.append({"id": "N3", "name": "non-colregs run rejected", "pass": v.returncode == 1,
                    "detail": f"rc={v.returncode}"})

    ok_all = all(c["pass"] for c in checks) and all(n["pass"] for n in neg)
    result = {"packet": "WP-20260709B", "date": time.strftime("%Y-%m-%d"),
              "title": "rescue-boat default target + independently verifiable COLREGS",
              "pass": ok_all,
              "gates_passed": sum(c["pass"] for c in checks), "gates_total": len(checks),
              "neg_passed": sum(n["pass"] for n in neg), "neg_total": len(neg),
              "checks": checks, "neg_controls": neg}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(result, open(OUT, "w", encoding="utf-8"), indent=2)
    for c in checks + neg:
        print(f"  {c['id']} {c['name']:<28} {'PASS' if c['pass'] else 'FAIL'}  {c['detail']}")
    print(f"[wp_20260709b] {'PASS' if ok_all else 'FAIL'} -> {OUT}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
