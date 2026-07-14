#!/usr/bin/env python3
# =====================================================================
# NaviSense WP-INTEGRATION (2026-06-15) — Static compile-readiness audit
# of the combined C++ surface from the 6 stacked packets
# (WP-3, WP-4, WP-5, WP-6, WP-SENSOR-1, WP-ACTUATOR-RIG).
#
# WHY: all six packets' C++ was authored to UE 5.7 conventions but NEVER
# compiler-checked, and they must build together in ONE recompile (Step 0
# of PENDING_EDITOR_GATES.md) that gates the entire pending editor backlog.
# The bash sandbox cannot run the UE compiler, so this mechanically checks
# the things a human reviewer checks: cross-file symbol contracts, the
# DTO<->wire-key parity invariant, FTickableGameObject completeness, module
# wiring, include sanity, the two threading/coords invariants, AND a
# truncation guard (KI-004: D: drive truncates large writes — this is how
# the WP-4 subsystem + pawn + bridge .cpp were silently corrupted on disk).
# It turns the manual audit into a REPEATABLE regression check.
#
# This is NOT a substitute for the compiler — it is a pre-flight that catches
# the cheap, high-frequency breakers (truncated file, renamed method, missing
# field, missing include, broken wire-key parity) before Lemuel spends a
# recompile on them.
#
# Run (no UE needed):  python3 verify_compile_readiness.py
# Writes: NaviSense_UE5/Saved/NaviSense_Reports/wp_20260615_compile_audit_result.json
# =====================================================================
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
# HERE = .../Development/work_packets/WP_20260615_COMPILE_AUDIT -> up 3 = workspace root
PROJ = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(PROJ, "NaviSense_UE5", "Source", "NaviSense")
LISTENER = os.path.join(PROJ, "python_listener.py")
UPROJECT = os.path.join(PROJ, "NaviSense_UE5", "NaviSense_UE5.uproject")
REPORT_DIR = os.path.join(PROJ, "NaviSense_UE5", "Saved", "NaviSense_Reports")
REPORT_FILE = os.path.join(REPORT_DIR, "wp_20260615_compile_audit_result.json")

results = {}
npass = 0
ntotal = 0

def rd(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""

def check(name, ok, detail):
    global npass, ntotal
    ntotal += 1
    if ok:
        npass += 1
    results[name] = {"pass": bool(ok), "detail": detail}
    print(("PASS " if ok else "FAIL ") + name + " :: " + detail)

# Load every source file once. Walk the Source/ ROOT so the *.Target.cs files
# (which sit in Source/, not Source/NaviSense/) are included alongside the module.
files = {}
for root, _dirs, fns in os.walk(os.path.dirname(SRC)):
    for fn in fns:
        if fn.endswith((".h", ".cpp", ".cs")):
            files[fn] = rd(os.path.join(root, fn))

def f(name):
    return files.get(name, "")

# =====================================================================
# 0. Truncation guard (KI-004) — every C++ TU must be brace-balanced and
#    end on a real terminator. This is the check that would have caught the
#    silent WP-4/pawn/bridge corruption before a wasted recompile.
# =====================================================================
trunc = []
for fn, txt in files.items():
    if not fn.endswith((".h", ".cpp")):
        continue
    if not txt.strip():
        trunc.append(fn + "(empty)"); continue
    opens, closes = txt.count("{"), txt.count("}")
    end_ok = bool(re.search(r"(\}\s*;?|#endif.*|\)\s*;)\s*$", txt.rstrip()))
    if opens != closes or not end_ok:
        trunc.append("%s(braces %d/%d,end_ok=%s)" % (fn, opens, closes, end_ok))
check("Z0_no_truncated_files",
      not trunc,
      "all C++ translation units brace-balanced + cleanly terminated (KI-004 guard)"
      + (" :: TRUNCATED: %s" % trunc if trunc else ""))

# =====================================================================
# A. Cross-file symbol contracts (the integration spine)
# =====================================================================
pawn_h = f("NaviSenseShipPawn.h")
check("A1_pawn_bridge_contract",
      ("ApplyOwnShipState" in pawn_h) and ("NotifyBridgeStale" in pawn_h),
      "ANaviSenseShipPawn declares ApplyOwnShipState + NotifyBridgeStale (called by NaviSenseBridgeComponent.cpp)")

act_h = f("ActuatorComponent.h")
check("A2_actuator_contract",
      ("SetFromState" in act_h) and re.search(r"FActuatorState\s+State\s*;", act_h) is not None,
      "UActuatorComponent exposes SetFromState(const FNaviSenseState&) + public FActuatorState State (used by pawn + bridge)")

sb_h = f("SensorBundleComponent.h")
check("A3_sensorbundle_contract",
      re.search(r"TSharedRef<\s*FJsonObject\s*>\s*BuildSensorsJson", sb_h) is not None,
      "USensorBundleComponent::BuildSensorsJson() returns TSharedRef<FJsonObject> (SetObjectField-compatible)")

sim_h = f("NaviSenseSimSubsystem.h")
sim_api = ["StartRun", "StopRun", "IsRunActive", "GetSimTime", "RunId"]
miss_sim = [m for m in sim_api if m not in sim_h]
check("A4_simsubsystem_api",
      not miss_sim,
      "UNaviSenseSimSubsystem exposes the bridge-called API " + str(sim_api) + (" (missing: %s)" % miss_sim if miss_sim else ""))

act_fields = ["PortRpm", "StarboardRpm", "RudderDeg", "BowThrusterNorm",
              "PortRpmCmd", "StarboardRpmCmd", "RudderCmdDeg", "BowThrusterCmdNorm"]
miss_af = [x for x in act_fields if not re.search(r"\b%s\b" % x, act_h)]
check("A5_actuatorstate_fields",
      not miss_af,
      "FActuatorState has all 8 fields read by the pawn rig" + (" (missing: %s)" % miss_af if miss_af else ""))

vp_h = f("NaviSenseVesselProfile.h")
vp_fields = ["RudderMaxDeg", "PoseLerpSpeed", "FreeboardCm", "RpmMax",
             "RudderRateDegPerSec", "RpmRatePerSec", "ThrusterRatePerSec"]
miss_vp = [x for x in vp_fields if x not in vp_h]
check("A6_vesselprofile_fields",
      not miss_vp,
      "UNaviSenseVesselProfile has every field referenced by pawn/actuator" + (" (missing: %s)" % miss_vp if miss_vp else ""))

# =====================================================================
# B. DTO <-> wire-key parity (Invariant #3: DTO names == JSON keys)
# =====================================================================
dto_h = f("NaviSenseBridgeTypes.h")
dto_fields = set(re.findall(r"UPROPERTY\(\)\s+(?:FString|double|int32|int64|float|bool)\s+(\w+)", dto_h))

# Pull the state.v1 dict keys from the listener. Anchor on the actual dict KEY
# ("schema": "navisense.state.v1"), NOT a docstring mention of the schema name.
listener = rd(LISTENER)
wire_keys = set()
lines = listener.splitlines()
start = next((i for i, ln in enumerate(lines)
              if re.search(r'"schema"\s*:\s*"navisense\.state\.v1"', ln)), None)
if start is not None:
    for ln in lines[start:start + 40]:
        m = re.match(r"\s*\"(\w+)\"\s*:", ln)
        if m:
            wire_keys.add(m.group(1))
        if wire_keys and re.match(r"\s*\}", ln):
            break

only_dto = sorted(dto_fields - wire_keys)
only_wire = sorted(wire_keys - dto_fields)
check("B1_dto_wire_parity",
      bool(dto_fields) and bool(wire_keys) and not only_dto and not only_wire,
      "FNaviSenseState fields == state.v1 JSON keys (%d each); DTO-only=%s wire-only=%s"
      % (len(dto_fields), only_dto, only_wire))

# Schema-string agreement both directions.
bridge_cpp = f("NaviSenseBridgeComponent.cpp")
check("B2_schema_strings",
      'navisense.state' in bridge_cpp
      and 'navisense.sensor.v1' in bridge_cpp
      and 'navisense.sensor' in listener and 'navisense.state.v1' in listener,
      "UE matches inbound 'navisense.state', emits 'navisense.sensor.v1'; listener emits state.v1 / accepts sensor")

# =====================================================================
# C. FTickableGameObject completeness (WP-4 — flagged Live-Coding risk)
# =====================================================================
tick_required = ["virtual void Tick(", "GetStatId", "IsTickable",
                 "GetTickableGameObjectWorld", "IsTickableWhenPaused"]
miss_tick = [x for x in tick_required if x not in sim_h]
sim_cpp = f("NaviSenseSimSubsystem.cpp")
check("C1_ftickable_overrides",
      (not miss_tick)
      and ("FTickableGameObject" in sim_h)
      and ("RETURN_QUICK_DECLARE_CYCLE_STAT" in sim_cpp),
      "SimSubsystem overrides all FTickableGameObject members + defines GetStatId" + (" (missing: %s)" % miss_tick if miss_tick else ""))

# =====================================================================
# D. Module / build wiring
# =====================================================================
ns_cpp = f("NaviSense.cpp")
ns_h = f("NaviSense.h")
m = re.search(r"IMPLEMENT_PRIMARY_GAME_MODULE\([^,]+,\s*(\w+)\s*,", ns_cpp)
mod_name = m.group(1) if m else None
upr = rd(UPROJECT)
upr_mod = None
try:
    upr_json = json.loads(upr) if upr else {}
    mods = upr_json.get("Modules", [])
    upr_mod = mods[0]["Name"] if mods else None
except json.JSONDecodeError:
    upr_mod = None
tgt_game = f("NaviSense_UE5.Target.cs")
tgt_edit = f("NaviSense_UE5Editor.Target.cs")
both_extra = bool(mod_name) and \
    ('ExtraModuleNames.Add("%s")' % mod_name in tgt_game) and \
    ('ExtraModuleNames.Add("%s")' % mod_name in tgt_edit)
check("D1_module_name_match",
      bool(mod_name) and mod_name == upr_mod and both_extra,
      "module '%s' == .uproject Modules[0]='%s' and both Target.cs ExtraModuleNames=%s" % (mod_name, upr_mod, both_extra))

build_cs = f("NaviSense.Build.cs")
need_dep = ["Json", "JsonUtilities", "Sockets", "Networking"]
miss_dep = [d for d in need_dep if ('"%s"' % d) not in build_cs]
check("D2_build_deps",
      not miss_dep,
      "Build.cs PublicDependencyModuleNames covers bridge usage " + str(need_dep) + (" (missing: %s)" % miss_dep if miss_dep else ""))

check("D3_log_category",
      ("DECLARE_LOG_CATEGORY_EXTERN(LogNaviSense" in ns_h) and ("DEFINE_LOG_CATEGORY(LogNaviSense" in ns_cpp),
      "LogNaviSense DECLARE in NaviSense.h + DEFINE exactly once in NaviSense.cpp")

# =====================================================================
# E. Invariants (#1 coords single-source, #2 RX thread no UObjects)
# =====================================================================
coord_defs_elsewhere = []
for fn, txt in files.items():
    if fn == "NaviSenseCoords.h":
        continue
    if re.search(r"FORCEINLINE[^;{]*\b(WireToUE|UEToWire|WireYawToUE)\s*\(", txt):
        coord_defs_elsewhere.append(fn)
check("E1_coords_single_source",
      "WireToUE" in f("NaviSenseCoords.h") and not coord_defs_elsewhere,
      "coordinate/yaw conversion DEFINED only in NaviSenseCoords.h" + (" (also in: %s)" % coord_defs_elsewhere if coord_defs_elsewhere else ""))

runnable = f("BridgeSocketRunnable.h") + "\n" + f("BridgeSocketRunnable.cpp")
forbidden = ["Cast<", "GetWorld(", "NewObject", "GetOwner(", "AddOnScreenDebugMessage", "->ApplyOwnShipState"]
hit = [tok for tok in forbidden if tok in runnable]
check("E2_rxthread_no_uobjects",
      not hit,
      "FBridgeSocketRunnable touches no UObjects/scene (SPSC queue + atomic only)" + (" (found: %s)" % hit if hit else ""))

# =====================================================================
# F. Include sanity (the classic 'used but not included' breaker)
# =====================================================================
inc_fail = []
for fn, txt in files.items():
    if not fn.endswith(".cpp"):
        continue
    if re.search(r"UE_LOG\(\s*LogNaviSense", txt) and '"NaviSense.h"' not in txt:
        inc_fail.append("%s uses LogNaviSense without including NaviSense.h" % fn)
    if "FNaviSenseCoords::" in txt and "NaviSenseCoords.h" not in txt:
        inc_fail.append("%s uses FNaviSenseCoords without including Core/NaviSenseCoords.h" % fn)
    if fn != "ActuatorComponent.cpp" and re.search(r"\bFActuatorState\b", txt) and "ActuatorComponent.h" not in txt:
        inc_fail.append("%s references FActuatorState without including Vessel/ActuatorComponent.h" % fn)
check("F1_include_sanity",
      not inc_fail,
      "every .cpp includes the headers for the symbols it uses (LogNaviSense / Coords / FActuatorState)" + (" :: %s" % inc_fail if inc_fail else ""))

# =====================================================================
# Write result
# =====================================================================
os.makedirs(REPORT_DIR, exist_ok=True)
auto_result = "PASS" if npass == ntotal else "FAIL"
out = {
    "packet": "WP-INTEGRATION (compile-readiness audit)",
    "date": "2026-06-15",
    "theme": "Static compile-readiness audit of the combined 6-packet C++ surface",
    "scope": "WP-3, WP-4, WP-5, WP-6, WP-SENSOR-1, WP-ACTUATOR-RIG (one recompile, never compiler-checked)",
    "checks_passed": npass,
    "checks_total": ntotal,
    "auto_result": auto_result,
    "is_compiler": False,
    "note": ("Static pre-flight only; the bash sandbox cannot run the UE compiler. "
             "All-green here means no truncated TUs, and the cross-file contracts, wire-key parity, "
             "module wiring, FTickable completeness, invariants and includes are internally consistent, "
             "so the Step-0 recompile in PENDING_EDITOR_GATES.md is de-risked. The authoritative gate is "
             "still Lemuel's recompile (Live Coding Ctrl+Alt+F11, or a clean Build if the WP-4 "
             "FTickableGameObject base won't hot-swap)."),
    "checks": results,
}
with open(REPORT_FILE, "w", encoding="utf-8") as fp:
    json.dump(out, fp, indent=2)
print("\n%s  %d/%d checks passed -> %s" % (auto_result, npass, ntotal, REPORT_FILE))
sys.exit(0 if auto_result == "PASS" else 1)
