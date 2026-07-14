#!/usr/bin/env python3
"""verify_20260709 -- WP-20260709 gate: single-ship COLREGS with the REAL vessels.

  G1  CPP-FIX     -- ApplyTraffic no longer stomps the placed roll/pitch (KI-034):
                     the FRotator(0, yaw, 0) hard-set is gone, TrafficPlacedRot is
                     declared (.h) and used (.cpp), and Z0 compile-readiness = 16/16.
  G2  REAL-NAMES  -- (revised WP-20260709B) all four colregs presets name the
                     ONE default target ship (DEFAULT_COLREGS_TARGET ==
                     the picker's TARGET_SHIP == marine_rescue_boat), and
                     monaco_capture's 3 slots match the tag-scan sort order
                     (case-insensitive, as FName::Compare sorts).
  G3  SCENARIO-PLANT -- the four colregs_* scenarios carry plant="mmg" and the
                     listener resolves it when --plant is left at default
                     (kills the 28-Jun stub footgun for COLREGS runs).
  G4  E2E-COMPLIANT -- the freshest headless colregs_head_on selftest run scores
                     COLREGS COMPLIANT with the renamed target + health PASS.
  G5  REGRESSION  -- verify_20260629b (updated names) exits 0; today's stacked
                     link audit result still reads pass=true.

Negative controls:
  N1  the pre-fix rotation line (FRotator(0.0, NewYaw, 0.0)) makes G1's source
      check FAIL on a tmp copy.
  N2  a fictional name (SLOWBELLE) in a rendered slot makes G2's check FAIL.
  N3  G4's reader FAILs on a run dir with no state.csv (cannot fake a verdict).

Writes Saved/NaviSense_Reports/wp_20260709_result.json; exit 0 iff all pass.
"""
from __future__ import annotations
import glob, io, json, os, re, shutil, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports",
                   "wp_20260709_result.json")
CPP = os.path.join(ROOT, "NaviSense_UE5", "Source", "NaviSense", "Vessel",
                   "NaviSenseShipPawn.cpp")
HDR = os.path.join(ROOT, "NaviSense_UE5", "Source", "NaviSense", "Vessel",
                   "NaviSenseShipPawn.h")
PICKER = os.path.join(ROOT, "NaviSense_UE5", "Content", "NaviSense", "Python",
                      "Phase5_Systems", "10_colregs_encounter.py")
LABELS = ["excursion_vessel", "marine_rescue_boat", "Yacht_with_interior"]


def check_cpp_fix(cpp_path: str, hdr_path: str):
    cpp = open(cpp_path, encoding="utf-8").read()
    hdr = open(hdr_path, encoding="utf-8").read()
    if "FRotator(0.0, NewYaw, 0.0)" in cpp:
        return False, "pre-fix hard-set FRotator(0.0, NewYaw, 0.0) still present"
    if "TrafficPlacedRot" not in hdr:
        return False, "TrafficPlacedRot not declared in the header"
    if cpp.count("TrafficPlacedRot") < 2:
        return False, "TrafficPlacedRot not captured+used in ApplyTraffic"
    if "Placed->Pitch, NewYaw, Placed->Roll" not in cpp:
        return False, "ApplyTraffic does not compose placed pitch/roll with wire yaw"
    return True, "yaw-only drive; placed pitch/roll captured once per actor"


def picker_mapping():
    """(encounter -> scenario, TARGET_SHIP) parsed from the editor picker source
    (WP-20260709B model: ONE default ship for all encounters)."""
    src = open(PICKER, encoding="utf-8").read()
    m = re.search(r'^TARGET_SHIP\s*=\s*"([\w_]+)"', src, re.M)
    target_ship = m.group(1) if m else None
    body = src[src.index("ENCOUNTERS = {"):]
    pairs = re.findall(r'"(\w+)":\s*"([\w_]+)"', body[:body.index("}")])
    return dict(pairs), target_ship, src


def check_real_names(name_of_preset):
    """name_of_preset: callable preset -> list of target names (injectable for N2)."""
    mapping, target_ship, _ = picker_mapping()
    if len(mapping) != 4:
        return False, f"picker mapping has {len(mapping)} encounters (expected 4)"
    from python.ais_traffic import DEFAULT_COLREGS_TARGET
    if target_ship != DEFAULT_COLREGS_TARGET:
        return False, (f"picker TARGET_SHIP {target_ship!r} != "
                       f"DEFAULT_COLREGS_TARGET {DEFAULT_COLREGS_TARGET!r}")
    import python.scenarios as scn
    for enc, scenario in mapping.items():
        sc = scn.get_scenario(scenario)
        names = name_of_preset(sc.ais)
        if len(names) != 1 or names[0] != DEFAULT_COLREGS_TARGET:
            return False, (f"{enc}: preset '{sc.ais}' names {names} != default "
                           f"target '{DEFAULT_COLREGS_TARGET}'")
    slots = name_of_preset("monaco_capture")
    want = sorted(LABELS, key=str.lower)   # FName::Compare is case-insensitive
    if slots != want:
        return False, f"monaco_capture slots {slots} != tag-scan order {want}"
    return True, ("4 encounters -> default target "
                  f"'{DEFAULT_COLREGS_TARGET}'; monaco_capture slots = real labels")


def check_scenario_plant():
    import python.scenarios as scn
    bad = [n for n in ("colregs_head_on", "colregs_crossing_giveway",
                       "colregs_crossing_standon", "colregs_overtaking")
           if getattr(scn.get_scenario(n), "plant", None) != "mmg"]
    if bad:
        return False, f"scenarios missing plant='mmg': {bad}"
    listener = open(os.path.join(ROOT, "python_listener.py"), encoding="utf-8").read()
    if 'sc.plant' not in listener or 'parser.get_default("plant")' not in listener:
        return False, "listener does not resolve the scenario-required plant"
    return True, "4 colregs scenarios carry plant='mmg'; listener resolves it"


def check_e2e(run_dir):
    if not run_dir or not os.path.isfile(os.path.join(run_dir, "state.csv")):
        return False, f"no state.csv in {run_dir!r}"
    kp = os.path.join(run_dir, "evidence_pack", "kpis.json")
    if not os.path.isfile(kp):
        return False, "no evidence_pack/kpis.json"
    k = json.load(open(kp))
    if (k.get("health") or {}).get("verdict") != "PASS":
        return False, f"health={k.get('health')}"
    tgt = ((k.get("ais") or {}).get("targets") or [{}])[0]
    # WP-20260709B: any REAL placed ship is valid (default marine_rescue_boat,
    # or a --target-name swap); fictional legacy names must be gone.
    if tgt.get("name") not in LABELS:
        return False, f"target name {tgt.get('name')!r} is not a placed Traffic ship"
    r = subprocess.run([sys.executable, os.path.join(ROOT, "python", "colregs_score.py"),
                        "--run-dir", run_dir, "--ais", "head_on_avoid"],
                       capture_output=True, text=True, cwd=ROOT)
    ok = r.returncode == 0 and "1 compliant / 0 non-compliant" in r.stdout
    return ok, (f"colregs_score rc={r.returncode}: "
                + (r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "<no out>"))


def main() -> int:
    checks, neg = [], []

    ok, det = check_cpp_fix(CPP, HDR)
    z0 = subprocess.run([sys.executable, os.path.join(
        ROOT, "Development", "work_packets", "WP_20260615_COMPILE_AUDIT",
        "verify_compile_readiness.py")], capture_output=True, text=True, cwd=ROOT)
    ok = ok and z0.returncode == 0
    checks.append({"id": "G1", "name": "cpp-fix", "pass": ok,
                   "detail": f"{det}; Z0 rc={z0.returncode}"})

    from python.ais_traffic import make_field
    def names(preset):
        return [t.name for t in make_field(preset, own_e0=0, own_n0=0,
                                           own_heading_deg=0).targets]
    ok, det = check_real_names(names)
    checks.append({"id": "G2", "name": "real-names", "pass": ok, "detail": det})

    ok, det = check_scenario_plant()
    checks.append({"id": "G3", "name": "scenario-plant", "pass": ok, "detail": det})

    runs = sorted(glob.glob(os.path.join(ROOT, "logs", "_selftest",
                                         "demo-colregs_head_on_*")), key=os.path.getmtime)
    ok, det = check_e2e(runs[-1] if runs else None)
    checks.append({"id": "G4", "name": "e2e-compliant", "pass": ok, "detail": det})

    r29b = subprocess.run([sys.executable, os.path.join(ROOT, "python",
                           "verify_20260629b.py")], capture_output=True, text=True, cwd=ROOT)
    audit = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports",
                         "wp_20260702b_result.json")
    a = json.load(open(audit)) if os.path.isfile(audit) else {}
    a_ok = a.get("verdict") == "PASS" or a.get("pass") is True
    checks.append({"id": "G5", "name": "regression", "pass": r29b.returncode == 0 and a_ok,
                   "detail": f"verify_20260629b rc={r29b.returncode}; link-audit pass={a_ok}"})

    # ---- negative controls --------------------------------------------------
    tmp = tempfile.mkdtemp(prefix="wp09_")
    try:
        bad_cpp = os.path.join(tmp, "pawn.cpp")
        src = open(CPP, encoding="utf-8").read().replace(
            "Actor->SetActorLocationAndRotation(NewLoc, FRotator(Placed->Pitch, NewYaw, Placed->Roll));",
            "Actor->SetActorLocationAndRotation(NewLoc, FRotator(0.0, NewYaw, 0.0));")
        open(bad_cpp, "w", encoding="utf-8").write(src)
        ok, det = check_cpp_fix(bad_cpp, HDR)
        neg.append({"id": "N1", "name": "pre-fix rotation caught", "pass": not ok,
                    "detail": det})

        def bad_names(preset):
            return ["SLOWBELLE"] if preset != "monaco_capture" else names(preset)
        ok, det = check_real_names(bad_names)
        neg.append({"id": "N2", "name": "fictional name caught", "pass": not ok,
                    "detail": det})

        empty = os.path.join(tmp, "empty_run"); os.makedirs(empty)
        ok, det = check_e2e(empty)
        neg.append({"id": "N3", "name": "unverifiable run caught", "pass": not ok,
                    "detail": det})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok_all = all(c["pass"] for c in checks) and all(n["pass"] for n in neg)
    result = {"packet": "WP-20260709", "date": time.strftime("%Y-%m-%d"),
              "title": "single-ship COLREGS with real vessels (roll fix + names + plant)",
              "pass": ok_all,
              "gates_passed": sum(c["pass"] for c in checks), "gates_total": len(checks),
              "neg_passed": sum(n["pass"] for n in neg), "neg_total": len(neg),
              "checks": checks, "neg_controls": neg}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(result, open(OUT, "w", encoding="utf-8"), indent=2)
    for c in checks + neg:
        print(f"  {c['id']} {c['name']:<26} {'PASS' if c['pass'] else 'FAIL'}  {c['detail']}")
    print(f"[wp_20260709] {'PASS' if ok_all else 'FAIL'} -> {OUT}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
