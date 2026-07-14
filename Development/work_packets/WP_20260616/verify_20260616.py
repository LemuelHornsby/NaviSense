#!/usr/bin/env python3
# =====================================================================
# NaviSense WP-5 Verify — tests + nightly automation skeleton (F7, §6)
# for 2026-06-16 (pre-authored 2026-06-14 in the autonomous run).
#
# Auto-checks (runnable here, no UE):
#   T1  pytest suite (plant + wire contract) passes
#   T2  bridge verifies pass (root re-accept, WP-3, WP-4 clock)
#   T3  all nightly automation deliverables exist
#   T4  C++ Automation test + golden contract files exist
#
# Manual (UE): G_UE  `Automation RunTests NaviSense` green from CLI + one PNG
#              under Saved/NaviSense_Reports/nightly/<date>/.
#
# Writes: NaviSense_UE5/Saved/NaviSense_Reports/wp_20260616_result.json
# =====================================================================
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
# HERE = .../Development/work_packets/WP_20260616  -> up 3 = "...UE Engine"
PROJ = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
HARNESS = os.path.join(PROJ, "Development", "bridge_harness")
AUTO = os.path.join(PROJ, "Development", "automation")
REPORT_DIR = os.path.join(PROJ, "NaviSense_UE5", "Saved", "NaviSense_Reports")
REPORT_FILE = os.path.join(REPORT_DIR, "wp_20260616_result.json")

results, passed, total = {}, 0, 0


def check(name, ok, detail):
    global passed, total
    total += 1
    passed += bool(ok)
    results[name] = {"pass": bool(ok), "detail": detail}
    print(("PASS" if ok else "FAIL"), name, "-", detail)


# T1 - pytest
r = subprocess.run([sys.executable, "-m", "pytest", os.path.join(HARNESS, "tests"), "-q"],
                   capture_output=True, text=True)
tail = (r.stdout.strip().splitlines() or ["(no output)"])[-1]
check("T1_pytest", r.returncode == 0, f"pytest rc={r.returncode}: {tail}")

# T2 - bridge verifies
ok2 = True
for v in [os.path.join(HARNESS, "verify_root_reaccept.py"),
          os.path.join(PROJ, "Development", "work_packets", "WP_20260614", "verify_20260614.py"),
          os.path.join(PROJ, "Development", "work_packets", "WP_20260615", "verify_20260615.py")]:
    rr = subprocess.run([sys.executable, v], capture_output=True, text=True)
    ok2 = ok2 and rr.returncode == 0
check("T2_bridge_verifies", ok2, "root re-accept + WP-3 + WP-4 clock verifies all rc=0")

# T3 - automation deliverables
auto_files = ["automation_config.ps1", "nightly_tests.ps1", "nightly_render.ps1",
              "nightly_sweep.ps1", "nightly.ps1", "register_nightly_tasks.ps1", "README.md"]
missing = [f for f in auto_files if not os.path.isfile(os.path.join(AUTO, f))]
check("T3_automation_scripts", not missing,
      "all present" if not missing else f"missing: {missing}")

# T4 - C++ test + golden
cpp = os.path.join(PROJ, "NaviSense_UE5", "Source", "NaviSense", "Tests", "NaviSenseCoordsTests.cpp")
golden = os.path.join(HARNESS, "tests", "golden_state_v1.json")
check("T4_cpp_and_golden", os.path.isfile(cpp) and os.path.isfile(golden),
      f"coords spec={os.path.isfile(cpp)}, golden={os.path.isfile(golden)}")

results["G_UE_runtests"] = {
    "pass": "MANUAL_REQUIRED",
    "detail": ("Run Development/automation/nightly_tests.ps1 (or nightly.ps1): "
               "tests.json.results.ue_automation==true AND a beauty PNG under "
               "nightly/<date>/. That closes the WP-5 gate."),
}

os.makedirs(REPORT_DIR, exist_ok=True)
with open(REPORT_FILE, "w") as f:
    json.dump({"packet": "WP-5", "date": "2026-06-16", "preauthored": "2026-06-14",
               "theme": "In-engine tests + nightly automation skeleton (F7, §6)",
               "gates_passed": passed, "gates_total": total, "gates_manual": 1,
               "auto_result": "PASS" if passed == total else "PARTIAL",
               "checks": results,
               "note": "T1-T4 auto-verified here. G_UE (UE Automation green + nightly PNG) "
                       "is the in-editor gate that closes WP-5."}, f, indent=2)

print("=" * 60)
print(f"WP-5 verify: {passed}/{total} automated checks PASS  -> {REPORT_FILE}")
sys.exit(0 if passed == total else 1)
