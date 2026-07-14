# =====================================================================
# NaviSense WP-2 — Place ANaviSenseShipPawn in NaviSense_Monaco
# =====================================================================
# Run from:  Tools > Execute Python Script...
#            (with NaviSense_Monaco open in the editor)
#
# WHAT IT DOES
#   1. Finds or spawns one ANaviSenseShipPawn actor at Monaco spawn coords.
#   2. Assigns the DOLPHIN hull mesh (first static mesh found under
#      /Game/NaviSense/Ships/Dolphin/hull/ — adjust HULL_MESH_PATH if needed).
#   3. Assigns the DA_DOLPHIN_VesselProfile data asset.
#   4. Sets Auto Possess Player = Player 0.
#   5. Hides any actor whose label contains "yacht" or "unity" (case-insensitive)
#      — the legacy Unity parity reference mesh.
#   6. Saves the level.
#
# IDEMPOTENT: re-running moves the pawn back to spawn, re-applies profile.
#
# REQUIRES
#   C++ module compiled.  Run 00_preflight_report.py first if unsure.
#   Run 04_create_vessel_profile.py first to ensure DA_DOLPHIN_VesselProfile exists.
#
# SPAWN POSITION  (per Execution Plan §3 WP-2)
#   UE coords: X=20580, Y=-23500, Z=-310  (cm, roughly Port Hercule, Monaco)
# =====================================================================

import unreal

TAG = "[NaviSense WP-2]"
def log(m):  unreal.log(TAG + " " + str(m))
def warn(m): unreal.log_warning(TAG + " " + str(m))
def err(m):  unreal.log_error(TAG + " " + str(m))

# ---------------------------------------------------------------------------
# Configuration — edit these if your asset paths differ.
# ---------------------------------------------------------------------------
SPAWN_X_CM      =  20580.0
SPAWN_Y_CM      = -23500.0
SPAWN_Z_CM      =   -310.0
SPAWN_YAW_DEG   =    0.0        # heading North (UE yaw 0 = East; 0 deg wire = North -> maps to UE yaw 90, but start at 0 for now)

PAWN_CLASS_PATH    = "/Script/NaviSense.NaviSenseShipPawn"
PROFILE_ASSET_PATH = "/Game/NaviSense/Settings/Vessels/DA_DOLPHIN_VesselProfile"

# Hull mesh: try the engine-generated path first; if it doesn't load we search.
HULL_MESH_HINT     = "/Game/NaviSense/Ships/Dolphin/hull"   # folder prefix for search

# ---------------------------------------------------------------------------

def find_actor_subsys():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

def get_all_actors():
    return find_actor_subsys().get_all_level_actors()

def find_hull_mesh():
    """Search /Game/NaviSense/Ships/Dolphin/hull/ for the first StaticMesh."""
    lib = unreal.EditorAssetLibrary
    candidates = lib.list_assets(HULL_MESH_HINT, recursive=True, include_folder=False)
    for path in candidates:
        asset = unreal.load_asset(path)
        if isinstance(asset, unreal.StaticMesh):
            log("Hull mesh found: %s" % path)
            return asset
    return None

def main():
    # ---- 0. Verify C++ class is available --------------------------------
    pawn_cls = unreal.load_class(None, PAWN_CLASS_PATH)
    if pawn_cls is None:
        err("ANaviSenseShipPawn class not found at %s" % PAWN_CLASS_PATH)
        err("Make sure the C++ module is compiled (right-click .uproject > Generate VS files, then build).")
        return

    # ---- 1. Load/verify VesselProfile data asset -------------------------
    profile = unreal.load_asset(PROFILE_ASSET_PATH)
    if profile is None:
        warn("DA_DOLPHIN_VesselProfile not found at %s" % PROFILE_ASSET_PATH)
        warn("Run 04_create_vessel_profile.py first, then re-run this script.")
        warn("Continuing without profile — you can assign it manually in Details.")

    # ---- 2. Load hull mesh -----------------------------------------------
    hull_mesh = find_hull_mesh()
    if hull_mesh is None:
        warn("No StaticMesh found under %s" % HULL_MESH_HINT)
        warn("Pawn will be placed without a hull mesh. Assign one manually in Details > Hull.")

    # ---- 3. Find existing pawn or spawn a new one ------------------------
    existing_pawns = [a for a in get_all_actors()
                      if a.get_class().get_name() == "NaviSenseShipPawn"]

    spawn_loc = unreal.Vector(SPAWN_X_CM, SPAWN_Y_CM, SPAWN_Z_CM)
    spawn_rot = unreal.Rotator(0.0, SPAWN_YAW_DEG, 0.0)   # (pitch, yaw, roll)

    if existing_pawns:
        pawn = existing_pawns[0]
        pawn.set_actor_location_and_rotation(spawn_loc, spawn_rot,
                                              sweep=False, teleport=True)
        log("Moved existing NaviSenseShipPawn to spawn location.")
        if len(existing_pawns) > 1:
            warn("%d extra NaviSenseShipPawn actors found — delete duplicates manually." %
                 (len(existing_pawns) - 1))
    else:
        pawn = find_actor_subsys().spawn_actor_from_class(
            pawn_cls, spawn_loc, spawn_rot)
        if pawn is None:
            err("spawn_actor_from_class returned None. Check the log for spawn errors.")
            return
        pawn.set_actor_label("NaviSenseShipPawn_DOLPHIN")
        log("Spawned new NaviSenseShipPawn at (%g, %g, %g) yaw=%g°" %
            (SPAWN_X_CM, SPAWN_Y_CM, SPAWN_Z_CM, SPAWN_YAW_DEG))

    # ---- 4. Assign hull mesh to the Hull component -----------------------
    if hull_mesh is not None:
        hull_comp = pawn.get_component_by_class(unreal.StaticMeshComponent)
        if hull_comp is not None:
            hull_comp.set_static_mesh(hull_mesh)
            log("Hull mesh assigned: %s" % hull_mesh.get_path_name())
        else:
            warn("Could not find StaticMeshComponent on pawn — assign hull mesh manually.")

    # ---- 5. Assign VesselProfile -----------------------------------------
    if profile is not None:
        try:
            pawn.set_editor_property("vessel_profile", profile)
            log("VesselProfile assigned: %s" % PROFILE_ASSET_PATH)
        except Exception as e:
            warn("Could not set vessel_profile property: %s" % e)
            warn("Assign DA_DOLPHIN_VesselProfile manually in Details > NaviSense.")

    # ---- 6. Set Auto Possess Player 0 ------------------------------------
    try:
        pawn.set_editor_property("auto_possess_player",
                                  unreal.AutoReceiveInput.PLAYER0)
        log("Auto Possess set to Player 0.")
    except Exception as e:
        warn("Could not set auto_possess_player: %s" % e)
        warn("Set it manually: Details > Pawn > Auto Possess Player = Player 0.")

    # ---- 7. Hide legacy Unity/yacht reference meshes ---------------------
    hidden_count = 0
    for actor in get_all_actors():
        label = actor.get_actor_label().lower()
        if actor is pawn:
            continue
        if "yacht" in label or "unity" in label or "ship_model" in label:
            actor.set_actor_hidden_in_game(True)
            actor.set_is_temporarily_hidden_in_editor(True)
            log("Hidden legacy actor: %s" % actor.get_actor_label())
            hidden_count += 1
    if hidden_count == 0:
        log("No legacy yacht/unity actors found to hide (that's fine if the level is clean).")

    # ---- 8. Save level ---------------------------------------------------
    unreal.EditorLevelLibrary.save_current_level()
    log("Level saved.")

    # ---- 9. Summary -------------------------------------------------------
    log("=" * 60)
    log("WP-2 placement COMPLETE.")
    log("  Pawn: NaviSenseShipPawn_DOLPHIN")
    log("  Location: X=%.0f Y=%.0f Z=%.0f cm" % (SPAWN_X_CM, SPAWN_Y_CM, SPAWN_Z_CM))
    log("  Profile: %s" % (PROFILE_ASSET_PATH if profile else "NOT ASSIGNED — do manually"))
    log("  Hull mesh: %s" % (hull_mesh.get_path_name() if hull_mesh else "NOT ASSIGNED — do manually"))
    log("")
    log("NEXT STEPS (in-editor, <5 min):")
    log("  1. Verify the pawn appears in the Monaco viewport near Port Hercule.")
    log("  2. Press Play — no Python needed yet; pawn should sit still at spawn.")
    log("  3. Open a terminal, run: python python_listener.py --controller zigzag10 --target unreal")
    log("     (then press Play again — the zig-zag sign test should show heading swinging)")
    log("  4. Run verify_20260613.py (via Tools > Execute Python Script) to record the gate result.")
    log("=" * 60)

main()
