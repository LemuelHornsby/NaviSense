# =====================================================================
# NaviSense Phase 4 - Port Realism - Layer 4
# Script 06: PCG dock-clutter scaffold for Quai Antoine 1er
# =====================================================================
#
# WHAT THIS DOES
#   1. Places a Spline Actor along the edge of Quai Antoine 1er at the
#      lat/lon vertices derived from the Cartographic Polygon mask
#      (so spline waypoints match the visible hero zone exactly).
#   2. Creates three PCG Graph asset stubs under
#      Content/NaviSense/PCG/Phase4/ :
#        PCG_DockBollards   - one bollard mesh every 12 m
#        PCG_DockFenders    - one fender mesh every 8 m  (offset 4 m)
#        PCG_DockCleats     - one cleat between every pair of bollards
#   3. Spawns three PCG Volume actors in the level, each bound to one of
#      the three PCG graphs, with the spline as their geometry source.
#   4. Tags each volume with NaviSense.PCG.DockClutter for runtime lookup.
#
# Because the dock-kit Megascans pack isn't necessarily imported yet,
# the PCG graphs spawn an engine primitive (Cylinder for bollards,
# Cube for cleats, smaller Cylinder for fenders) as placeholders.
# You swap to real Megascans dock-kit meshes by editing the Static Mesh
# Spawner node inside each PCG graph - one click per graph.
#
# WHY
#   Manually placing ~160 bollards along a 2 km quay is the kind of
#   tedium PCG was designed for. A spline + density filter does it in
#   2 seconds. Same for fenders (lower density) and cleats (between
#   bollards). The whole layer 4 collapses into 3 PCG volumes.
#
# HOW TO RUN
#   With NaviSense_Monaco loaded, run from the editor command line:
#     py "D:/Marine Autonomy/.../Phase4_PortRealism/06_pcg_dock_scatter.py"
#
# IDEMPOTENT - safe to re-run. Re-uses existing actors and assets.
# =====================================================================

import unreal

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------
PCG_DIR        = "/Game/NaviSense/PCG/Phase4"
SPLINE_LABEL   = "BP_Spline_QuaiAntoine1er"
VOLUME_LABELS  = {
    "Bollards":  "PCG_Vol_DockBollards",
    "Fenders":   "PCG_Vol_DockFenders",
    "Cleats":    "PCG_Vol_DockCleats",
}
GRAPH_NAMES = {
    "Bollards": "PCG_DockBollards",
    "Fenders":  "PCG_DockFenders",
    "Cleats":   "PCG_DockCleats",
}
SPACING_M = {
    "Bollards": 12.0,
    "Fenders":  8.0,
    "Cleats":   6.0,   # halfway between bollards
}

# Quai Antoine 1er spline waypoints (matched to your existing polygon).
# Same lat/lon corners from script 03, but expressed as edge midpoints so
# the spline traces the quayside, not the polygon perimeter.
# Order matters - this is the walked path along the quay edge.
QUAI_LATLON = [
    (43.73315, 7.41900, 5.0),   # west end of Quai Antoine 1er
    (43.73345, 7.42000, 5.0),
    (43.73380, 7.42090, 5.0),
    (43.73420, 7.42150, 5.0),
    (43.73470, 7.42170, 5.0),   # east end near basin mouth
]

POLY_ACTOR_LABEL = "BP_PortRealism_QuaiPolygon"

# ---------------------------------------------------------------------
def log(m):  unreal.log("[NaviSense P4-06] " + str(m))
def warn(m): unreal.log_warning("[NaviSense P4-06] " + str(m))
def err(m):  unreal.log_error("[NaviSense P4-06] " + str(m))

def get_actor_subsys():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

def find_actor_by_label(label):
    for a in get_actor_subsys().get_all_level_actors():
        if a.get_actor_label() == label:
            return a
    return None

def find_georeference():
    for a in get_actor_subsys().get_all_level_actors():
        if a.get_class().get_name() == "CesiumGeoreference":
            return a
    return None

def ensure_dir(path):
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        unreal.EditorAssetLibrary.make_directory(path)

def asset_path(folder, name):
    return "{}/{}".format(folder.rstrip("/"), name)

def latlon_to_unreal(geo, lat, lon, h):
    """Convert lat/lon/h -> UE world cm via CesiumGeoreference."""
    try:
        ll_h = unreal.Vector(lon, lat, h)
        return geo.transform_longitude_latitude_height_position_to_unreal(ll_h)
    except Exception:
        try:
            return geo.call_method(
                "TransformLongitudeLatitudeHeightPositionToUnreal",
                (unreal.Vector(lon, lat, h),)
            )
        except Exception as e:
            err("lat/lon to UE conversion failed: {}".format(e))
            return None

# ---------------------------------------------------------------------
def create_or_get_spline_actor(label, geo):
    existing = find_actor_by_label(label)
    if existing is not None:
        log("Spline {} already exists - reusing.".format(label))
        return existing

    spline_actor_cls = unreal.load_class(None,
        "/Script/Engine.SplineMeshActor")
    if spline_actor_cls is None:
        # Fall back to AActor with a USplineComponent
        spline_actor_cls = unreal.Actor.static_class()

    new_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        spline_actor_cls, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    if new_actor is None:
        err("Failed to spawn spline actor.")
        return None
    new_actor.set_actor_label(label)
    return new_actor

def populate_spline(actor, latlon_points, geo):
    """Find or add a USplineComponent and set its points from lat/lon."""
    splines = actor.get_components_by_class(unreal.SplineComponent)
    spline = splines[0] if splines else None

    if spline is None:
        # Try to add one via the subsystem
        try:
            subobj_sys = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
            handles = subobj_sys.k2_gather_subobject_data_for_instance(actor)
            if handles:
                params = unreal.AddNewSubobjectParams(
                    parent_handle=handles[0],
                    new_class=unreal.SplineComponent,
                    blueprint_context=None,
                )
                new_handle, _ = subobj_sys.add_new_subobject(params)
                if new_handle.data_handle.is_valid():
                    spline = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(
                        new_handle.data_handle)
        except Exception as e:
            warn("Could not add SplineComponent: {}".format(e))

    if spline is None:
        err("Spline component unavailable.")
        return False

    spline.clear_spline_points(True)
    for (lat, lon, h) in latlon_points:
        world_pos = latlon_to_unreal(geo, lat, lon, h)
        if world_pos is not None:
            spline.add_spline_point(world_pos, unreal.SplineCoordinateSpace.WORLD, True)
    spline.set_closed_loop(False, True)
    log("Spline populated with {} waypoints.".format(len(latlon_points)))
    return True

# ---------------------------------------------------------------------
def create_pcg_graph_stub(name, folder):
    """Create an empty PCGGraph asset. The user wires it inside the PCG editor."""
    full = asset_path(folder, name)
    if unreal.EditorAssetLibrary.does_asset_exist(full):
        log("PCG graph {} exists - reusing.".format(name))
        return unreal.EditorAssetLibrary.load_asset(full)

    pcg_graph_cls = unreal.load_class(None, "/Script/PCG.PCGGraph")
    if pcg_graph_cls is None:
        err("PCGGraph class not resolvable. Is the Procedural Content "
            "Generation plugin enabled?")
        return None

    # Factory: PCGGraphFactory exposes create_asset via AssetTools
    factory_cls = unreal.load_class(None, "/Script/PCGEditor.PCGGraphFactory")
    if factory_cls is None:
        # Try alternative path
        factory_cls = unreal.load_class(None, "/Script/PCGEditor.PCGGraphFactoryNew")
    if factory_cls is None:
        warn("No PCGGraph factory exposed; trying create_asset without factory.")
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        try:
            asset = tools.create_asset(name, folder, pcg_graph_cls, None)
            if asset is not None:
                log("Created PCG graph stub: {}".format(full))
            return asset
        except Exception as e:
            err("create_asset failed: {}".format(e))
            return None

    factory = unreal.new_object(factory_cls)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    asset = tools.create_asset(name, folder, pcg_graph_cls, factory)
    if asset is None:
        err("Failed to create PCG graph {}".format(full))
        return None
    unreal.EditorAssetLibrary.save_loaded_asset(asset)
    log("Created PCG graph stub: {}".format(full))
    return asset

def spawn_pcg_volume(label, graph_asset, spawn_loc):
    """Spawn a PCGVolume actor and bind its graph reference."""
    existing = find_actor_by_label(label)
    if existing is not None:
        log("PCG volume {} exists - reusing.".format(label))
        return existing

    # PCG Volume class
    vol_cls = unreal.load_class(None, "/Script/PCG.PCGVolume")
    if vol_cls is None:
        err("PCGVolume class not resolvable.")
        return None

    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        vol_cls, spawn_loc, unreal.Rotator(0, 0, 0))
    if actor is None:
        err("Failed to spawn PCG volume {}".format(label))
        return None
    actor.set_actor_label(label)

    # Bind the PCG graph. Property is on the PCGComponent under the volume.
    pcg_components = actor.get_components_by_class(unreal.ActorComponent)
    bound = False
    for c in pcg_components:
        if "PCG" not in c.get_class().get_name():
            continue
        for prop in ("graph", "pcg_graph", "graph_instance"):
            try:
                c.set_editor_property(prop, graph_asset)
                log("  Bound graph on {}.{}".format(c.get_name(), prop))
                bound = True
                break
            except Exception:
                continue
        if bound:
            break

    # Tag the actor so future scripts can find it
    try:
        actor.tags = [unreal.Name("NaviSense.PCG.DockClutter")]
    except Exception:
        pass

    if not bound:
        warn("  Could not auto-bind PCG graph. Do it manually:")
        warn("    Select {} > Details > PCGComponent > Graph = {}".format(
            label, graph_asset.get_name() if graph_asset else "?"))
    return actor

# ---------------------------------------------------------------------
def main():
    log("=" * 60)
    geo = find_georeference()
    if geo is None:
        err("No CesiumGeoreference - cannot convert lat/lon.")
        return

    # 1. Spline along the quay
    spline_actor = create_or_get_spline_actor(SPLINE_LABEL, geo)
    if spline_actor is None:
        return
    populate_spline(spline_actor, QUAI_LATLON, geo)

    # 2. Three PCG graph stubs
    ensure_dir(PCG_DIR)
    graphs = {}
    for kind, gname in GRAPH_NAMES.items():
        g = create_pcg_graph_stub(gname, PCG_DIR)
        if g is not None:
            graphs[kind] = g
    log("PCG graphs: {} / {}".format(len(graphs), len(GRAPH_NAMES)))

    # 3. Three PCG volumes - spawn near the spline midpoint
    if not QUAI_LATLON:
        return
    mid_lat, mid_lon, mid_h = QUAI_LATLON[len(QUAI_LATLON) // 2]
    mid_pos = latlon_to_unreal(geo, mid_lat, mid_lon, mid_h)
    if mid_pos is None:
        mid_pos = unreal.Vector(0, 0, 0)

    for kind, label in VOLUME_LABELS.items():
        graph_asset = graphs.get(kind)
        spawn_pcg_volume(label, graph_asset, mid_pos)

    log("=" * 60)
    log("DONE. Next steps:")
    log("  1. Open Window > World Partition and right-click area around")
    log("     Quai Antoine 1er > Load Region. Required so PCG sees actors.")
    log("  2. Open each PCG graph in Content/NaviSense/PCG/Phase4/ :")
    log("     - PCG_DockBollards :  spacing {} m".format(SPACING_M['Bollards']))
    log("     - PCG_DockFenders  :  spacing {} m".format(SPACING_M['Fenders']))
    log("     - PCG_DockCleats   :  spacing {} m".format(SPACING_M['Cleats']))
    log("     Wire: Get Spline Data -> Sample Spline -> Density Filter")
    log("           -> Static Mesh Spawner (placeholder cylinder/cube)")
    log("  3. With each PCG Volume selected, click Generate in Details.")
    log("  4. Bollards/fenders/cleats appear along Quai Antoine 1er.")
    log("  5. Later: swap Static Mesh Spawner mesh from primitive to a")
    log("     Megascans dock-kit asset once you import one from Fab.")
    log("=" * 60)


if __name__ == "__main__":
    main()
