# =====================================================================
# NaviSense Phase 4 - Manual bollards, GROUNDED
# =====================================================================
#
# Script 15 had the bollards inherit the spline's height (17-36m above
# sea level for the user's current spline waypoints) so they spawned
# floating in mid-air, invisible from a yacht-eye view.
#
# This version: traces a ray straight DOWN from each sample point to
# find the actual ground/Monacomap surface, then places the bollard
# on that surface. Result: bollards rest on the dock no matter what
# height the spline waypoints are at.
# =====================================================================

import unreal


SPLINE_LABEL = "BP_Spline_QuaiAntoine1er"
CYLINDER_PATH = "/Engine/BasicShapes/Cylinder"
NUM_BOLLARDS = 12
NUM_FENDERS  = 18

BOLLARD_SCALE = unreal.Vector(0.2, 0.2, 0.8)
FENDER_SCALE  = unreal.Vector(0.3, 0.3, 0.5)

TRACE_UP_OFFSET   = 5000.0   # start 50m ABOVE the sample point
TRACE_DOWN_LENGTH = 20000.0  # search 200m DOWN for a surface


def log(m):  unreal.log("[NaviSense P4-15b] " + str(m))
def warn(m): unreal.log_warning("[NaviSense P4-15b] " + str(m))
def err(m):  unreal.log_error("[NaviSense P4-15b] " + str(m))


def get_actor_subsys():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def find_spline():
    for a in get_actor_subsys().get_all_level_actors():
        if a.get_actor_label() == SPLINE_LABEL:
            comps = a.get_components_by_class(unreal.SplineComponent)
            if comps:
                return a, comps[0]
    return None, None


def ground_z(world_pos):
    """Line-trace down from above to find the ground/Monacomap surface.
    Returns the ground Z, or world_pos.z if no hit."""
    try:
        editor_world = unreal.UnrealEditorSubsystem().get_editor_world()
    except Exception:
        try:
            editor_world = unreal.get_editor_subsystem(
                unreal.UnrealEditorSubsystem).get_editor_world()
        except Exception:
            return world_pos.z

    start = unreal.Vector(world_pos.x, world_pos.y,
                          world_pos.z + TRACE_UP_OFFSET)
    end   = unreal.Vector(world_pos.x, world_pos.y,
                          world_pos.z - TRACE_DOWN_LENGTH)
    hit = unreal.SystemLibrary.line_trace_single(
        editor_world,
        start, end,
        unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
        False,  # bTraceComplex
        [],     # ActorsToIgnore
        unreal.DrawDebugTrace.NONE,
        ignore_self=True,
    )
    if hit:
        # hit is a HitResult struct
        try:
            hit_loc = hit.location
            return hit_loc.z
        except Exception:
            pass
    return world_pos.z


def spawn_cylinder(label, position, scale):
    cyl_mesh = unreal.EditorAssetLibrary.load_asset(CYLINDER_PATH)
    if cyl_mesh is None:
        warn("Cylinder mesh missing at {}".format(CYLINDER_PATH))
        return None
    sm_actor_cls = unreal.StaticMeshActor.static_class()
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        sm_actor_cls, position, unreal.Rotator(0, 0, 0))
    if actor is None:
        warn("Failed to spawn {}".format(label))
        return None
    actor.set_actor_label(label)
    actor.set_actor_scale3d(scale)
    smc = actor.static_mesh_component
    if smc is not None:
        smc.set_static_mesh(cyl_mesh)
    actor.set_mobility(unreal.ComponentMobility.STATIC)
    return actor


def main():
    log("=" * 60)

    spline_actor, spline_comp = find_spline()
    if spline_comp is None:
        err("No spline found ({}). Aborting.".format(SPLINE_LABEL))
        return

    spline_length = spline_comp.get_spline_length()
    log("Spline length: {:.1f} m".format(spline_length / 100.0))

    # Bollards
    log("")
    log("Spawning bollards (with ground-snap):")
    bollard_count = 0
    for i in range(NUM_BOLLARDS):
        t = i * spline_length / max(1, NUM_BOLLARDS - 1)
        sample = spline_comp.get_location_at_distance_along_spline(
            t, unreal.SplineCoordinateSpace.WORLD)
        # Ground-snap
        z = ground_z(sample)
        # Place 5 cm above the ground so the base sits on it
        snapped = unreal.Vector(sample.x, sample.y, z + 5.0)
        actor = spawn_cylinder(
            "SM_Bollard_{:02d}".format(i),
            snapped,
            BOLLARD_SCALE,
        )
        if actor is not None:
            bollard_count += 1
            if i < 3 or i == NUM_BOLLARDS - 1:
                log("  [{}] sample z={:.0f}cm, ground z={:.0f}cm, placed".format(
                    i, sample.z, z))
    log("Bollard total: {}".format(bollard_count))

    # Fenders
    log("")
    log("Spawning fenders:")
    fender_count = 0
    for i in range(NUM_FENDERS):
        t = i * spline_length / max(1, NUM_FENDERS - 1)
        sample = spline_comp.get_location_at_distance_along_spline(
            t, unreal.SplineCoordinateSpace.WORLD)
        z = ground_z(sample)
        # Fenders hang BELOW the dock edge - 30 cm below ground level
        snapped = unreal.Vector(sample.x, sample.y, z - 30.0)
        actor = spawn_cylinder(
            "SM_Fender_{:02d}".format(i),
            snapped,
            FENDER_SCALE,
        )
        if actor is not None:
            fender_count += 1
    log("Fender total: {}".format(fender_count))

    # Save
    try:
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    except Exception:
        try:
            unreal.EditorLevelLibrary.save_current_level()
        except Exception as e:
            warn("Auto-save failed: {}. Press Ctrl+S manually.".format(e))

    log("=" * 60)
    log("DONE.")
    log("Spawned {} bollards and {} fenders.".format(bollard_count, fender_count))
    log("If you don't see them: select SM_Bollard_00 in Outliner, press F.")
    log("To redo: select all SM_Bollard_* + SM_Fender_* and Delete, then re-run.")
    log("=" * 60)


if __name__ == "__main__":
    main()
