# =====================================================================
# NaviSense WP-2 Verify — Gate check for 2026-06-13
# =====================================================================
# Run from:  Tools > Execute Python Script...
#            (with NaviSense_Monaco open and after running
#             01_place_ship_pawn_monaco.py)
#
# Checks:
#   G1  ANaviSenseShipPawn exists in NaviSense_Monaco
#   G2  Pawn is near the Monaco spawn point (within 500 cm)
#   G3  Pawn has Auto Possess Player 0
#   G4  Pawn VesselProfile is assigned
#   G5  Hull StaticMesh is assigned on the pawn
#   G6  No legacy unity/yacht actors are visible
#
# Writes result to:
#   Saved/NaviSense_Reports/wp_20260613_result.json
#
# NOTE: G7 (sign test — +10 deg rudder => bow swings starboard) requires
#       Lemuel to run with python_listener.py in a terminal and observe
#       the HUD log during PIE. It is recorded as MANUAL_REQUIRED here
#       and must be confirmed by Lemuel to close WP-2.
# =====================================================================

import unreal
import json
import os
import math

TAG = "[NaviSense WP-2 Verify]"
def log(m):  unreal.log(TAG + " " + str(m))
def warn(m): unreal.log_warning(TAG + " " + str(m))
def err(m):  unreal.log_error(TAG + " " + str(m))

SPAWN_X_CM      =  20580.0
SPAWN_Y_CM      = -23500.0
SPAWN_Z_CM      =   -310.0
SPAWN_TOL_CM    =  500.0    # accept within 5 m of nominal spawn

REPORT_DIR  = os.path.join(
    unreal.SystemLibrary.get_project_saved_directory(),
    "NaviSense_Reports"
)
REPORT_FILE = os.path.join(REPORT_DIR, "wp_20260613_result.json")


def actor_subsys():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

def dist_cm(v1, v2):
    dx = v1.x - v2.x; dy = v1.y - v2.y; dz = v1.z - v2.z
    return math.sqrt(dx*dx + dy*dy + dz*dz)


def run_checks():
    actors   = actor_subsys().get_all_level_actors()
    results  = {}
    passed   = 0
    total    = 0

    # G1 — pawn exists
    total += 1
    pawns = [a for a in actors if a.get_class().get_name() == "NaviSenseShipPawn"]
    g1 = len(pawns) > 0
    results["G1_pawn_exists"] = {
        "pass": g1,
        "detail": f"Found {len(pawns)} NaviSenseShipPawn actor(s)"
    }
    if g1: passed += 1
    log(("PASS" if g1 else "FAIL") + " G1 pawn_exists: %d actor(s)" % len(pawns))

    pawn = pawns[0] if pawns else None

    # G2 — spawn location
    total += 1
    if pawn:
        loc   = pawn.get_actor_location()
        spawn = unreal.Vector(SPAWN_X_CM, SPAWN_Y_CM, SPAWN_Z_CM)
        d     = dist_cm(loc, spawn)
        g2    = d <= SPAWN_TOL_CM
        results["G2_spawn_location"] = {
            "pass": g2,
            "detail": f"Distance from nominal spawn: {d:.1f} cm (tol {SPAWN_TOL_CM} cm)",
            "location": {"x": round(loc.x, 1), "y": round(loc.y, 1), "z": round(loc.z, 1)}
        }
        if g2: passed += 1
        log(("PASS" if g2 else "FAIL") + " G2 spawn_location: %.1f cm from nominal" % d)
    else:
        results["G2_spawn_location"] = {"pass": False, "detail": "No pawn to check"}
        log("FAIL G2 (no pawn)")

    # G3 — Auto Possess Player 0
    total += 1
    if pawn:
        try:
            ap   = pawn.get_editor_property("auto_possess_player")
            g3   = str(ap) in ("AutoReceiveInput.PLAYER0", "PLAYER0", "0")
            results["G3_auto_possess"] = {"pass": g3, "detail": f"auto_possess_player={ap}"}
            if g3: passed += 1
            log(("PASS" if g3 else "FAIL") + " G3 auto_possess: %s" % ap)
        except Exception as e:
            results["G3_auto_possess"] = {"pass": False, "detail": str(e)}
            warn("G3 check error: %s" % e)
    else:
        results["G3_auto_possess"] = {"pass": False, "detail": "No pawn"}

    # G4 — VesselProfile assigned
    total += 1
    if pawn:
        try:
            vp   = pawn.get_editor_property("vessel_profile")
            g4   = vp is not None
            results["G4_vessel_profile"] = {
                "pass": g4,
                "detail": vp.get_path_name() if g4 else "None"
            }
            if g4: passed += 1
            log(("PASS" if g4 else "FAIL") + " G4 vessel_profile: %s" % (vp.get_path_name() if g4 else "None"))
        except Exception as e:
            results["G4_vessel_profile"] = {"pass": False, "detail": str(e)}
            warn("G4 check error: %s" % e)
    else:
        results["G4_vessel_profile"] = {"pass": False, "detail": "No pawn"}

    # G5 — Hull mesh assigned
    total += 1
    if pawn:
        hull_comp = pawn.get_component_by_class(unreal.StaticMeshComponent)
        if hull_comp:
            mesh = hull_comp.get_editor_property("static_mesh")
            g5   = mesh is not None
            results["G5_hull_mesh"] = {
                "pass": g5,
                "detail": mesh.get_path_name() if g5 else "None (no mesh assigned)"
            }
            if g5: passed += 1
            log(("PASS" if g5 else "FAIL") + " G5 hull_mesh: %s" % (mesh.get_path_name() if g5 else "NONE"))
        else:
            results["G5_hull_mesh"] = {"pass": False, "detail": "No StaticMeshComponent on pawn"}
            warn("G5: No StaticMeshComponent found on pawn")
    else:
        results["G5_hull_mesh"] = {"pass": False, "detail": "No pawn"}

    # G6 — legacy actors hidden
    total += 1
    visible_legacy = []
    for a in actors:
        label = a.get_actor_label().lower()
        if "yacht" in label or "unity" in label or "ship_model" in label:
            if not a.is_actor_hidden_in_game() and not a.is_temporarily_hidden_in_editor():
                visible_legacy.append(a.get_actor_label())
    g6 = len(visible_legacy) == 0
    results["G6_legacy_hidden"] = {
        "pass": g6,
        "detail": ("No visible legacy actors" if g6
                   else f"Still visible: {visible_legacy}")
    }
    if g6: passed += 1
    log(("PASS" if g6 else "FAIL") + " G6 legacy_hidden: %s" % (
        "ok" if g6 else str(visible_legacy)))

    # G7 — sign test (manual)
    results["G7_sign_test"] = {
        "pass": "MANUAL_REQUIRED",
        "detail": ("Run: python python_listener.py --controller zigzag10 --target unreal\n"
                   "     Press Play in UE. Observe: +10 deg rudder -> bow swings STARBOARD.\n"
                   "     Confirm in HUD log AND python log. Then update this field to true.")
    }
    log("INFO  G7 sign_test: MANUAL_REQUIRED — see PACKET.md for steps")

    # ---- Write report -------------------------------------------------------
    os.makedirs(REPORT_DIR, exist_ok=True)
    report = {
        "packet":      "WP-2",
        "date":        "2026-06-13",
        "gates_passed": passed,
        "gates_total":  total,
        "gates_manual": 1,
        "auto_result":  "PASS" if passed == total else "PARTIAL",
        "checks":       results,
        "note": ("G7 (sign test) requires Lemuel to run with python_listener.py and "
                 "confirm heading convention in PIE. All other gates must be PASS to "
                 "close WP-2.")
    }
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)

    log("=" * 60)
    log("WP-2 Verify complete: %d/%d automated gates PASS" % (passed, total))
    log("Report: %s" % REPORT_FILE)
    if passed < total:
        err("Some gates FAILED — see report for details.")
        err("Re-run 01_place_ship_pawn_monaco.py to fix placement issues.")
    else:
        log("All automated gates PASS. Complete G7 (sign test) in PIE, then WP-2 is closed.")
    log("=" * 60)


run_checks()
