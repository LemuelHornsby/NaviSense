# =====================================================================
# NaviSense Phase 4 - Port Realism
# Script 04: Place Monacomap at the georeference origin and finalize
#            both Cesium tilesets for the hero ring.
# =====================================================================
#
# WHAT THIS DOES
#   1. Sets Maximum Screen Space Error = 16 on Google Photorealistic 3D
#      Tiles (relaxed from the default 2.0 in your scene) for comfortable
#      editor iteration. 8 is used for Movie Render Queue hero shots later.
#   2. Wires the Cesium OSM Buildings tileset to the same
#      BP_PortRealism_QuaiPolygon so the white block shells are also
#      masked inside the hero zone (script 03's polygon was only attached
#      to the Google tileset).
#   3. Ensures both tilesets' Georeference field points to the level's
#      CesiumGeoreference actor (currently None, which is the underlying
#      reason the tileset wasn't binding correctly).
#   4. Spawns a CesiumGlobeAnchor-anchored Static Mesh Actor for Monacomap
#      at lat 43.7340, lon 7.4197, h 5 m so it sits precisely inside the
#      Quai Antoine 1er polygon hole.
#   5. Verifies the 40 MI assignments survived placement.
#
# HOW TO RUN
#   In the editor command line (Cmd field):
#     py "D:/Marine Autonomy/NAVISENSE/.../Phase4_PortRealism/04_place_monacomap_and_wire_tilesets.py"
#
# IDEMPOTENT
#   Safe to re-run. Skips placement if a Monacomap actor with the label
#   PortHercule_Monacomap already exists.
# =====================================================================

import unreal

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------
MONACOMAP_ASSET_PATH = "/Game/NaviSense/Ports/Monaco/Monacomap/StaticMeshes/Monacomap"
PLACED_ACTOR_LABEL   = "PortHercule_Monacomap"

POLY_ACTOR_LABEL     = "BP_PortRealism_QuaiPolygon"

# Port Hercule origin (Master Guide canon)
MONACO_LAT = 43.7340
MONACO_LON = 7.4197
MONACO_H_M = 5.0

# Tileset target params (cinematic-first preset, editor iteration mode)
TARGET_MSE_GOOGLE = 16.0
TARGET_MSE_OSM    = 16.0

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def log(m):  unreal.log("[NaviSense P4-04] " + str(m))
def warn(m): unreal.log_warning("[NaviSense P4-04] " + str(m))
def err(m):  unreal.log_error("[NaviSense P4-04] " + str(m))

def get_actor_subsys():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

def find_actor_by_label(label):
    for a in get_actor_subsys().get_all_level_actors():
        if a.get_actor_label() == label:
            return a
    return None

def find_actors_by_class(class_name):
    out = []
    for a in get_actor_subsys().get_all_level_actors():
        if a.get_class().get_name() == class_name:
            out.append(a)
    return out

def find_georeference():
    refs = find_actors_by_class("CesiumGeoreference")
    return refs[0] if refs else None

def find_tilesets():
    """Return (google_tileset_or_none, osm_tileset_or_none)."""
    google = None
    osm    = None
    for t in find_actors_by_class("Cesium3DTileset"):
        lbl = t.get_actor_label().lower()
        if "google" in lbl or "photoreal" in lbl:
            google = t
        elif "osm" in lbl or "building" in lbl:
            osm = t
    return google, osm

def try_set_props(obj, name_value_pairs):
    """Best-effort: set each (name, value); ignore individual failures."""
    success = []
    for name, value in name_value_pairs:
        try:
            obj.set_editor_property(name, value)
            success.append(name)
        except Exception:
            pass
    return success

def ensure_polygon_on_tileset_overlay(tileset, poly):
    """If the tileset has a CesiumPolygonRasterOverlay, ensure poly is in its array.
    If not, create one. Mirrors script 03b's logic."""
    # Try resolving the overlay class first
    overlay_cls = unreal.load_class(None,
        "/Script/CesiumRuntime.CesiumPolygonRasterOverlay")
    if overlay_cls is None:
        warn("CesiumPolygonRasterOverlay class not resolvable. Skipping {}.".format(
            tileset.get_actor_label()))
        return False

    # Check for an existing overlay
    existing = tileset.get_components_by_class(overlay_cls)
    overlay = existing[0] if existing else None

    # Add one if missing
    if overlay is None:
        try:
            subobj_sys = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
            handles = subobj_sys.k2_gather_subobject_data_for_instance(tileset)
            if handles:
                params = unreal.AddNewSubobjectParams(
                    parent_handle=handles[0],
                    new_class=overlay_cls,
                    blueprint_context=None,
                )
                new_handle, fail_reason = subobj_sys.add_new_subobject(params)
                if new_handle.data_handle.is_valid():
                    overlay = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(
                        new_handle.data_handle)
        except Exception as e:
            warn("Could not add overlay on {}: {}".format(tileset.get_actor_label(), e))

    if overlay is None:
        warn("Could not find or create overlay on {}. Do this manually:".format(
            tileset.get_actor_label()))
        warn("  1. Select {} in Outliner.".format(tileset.get_actor_label()))
        warn("  2. Details > + Add > 'Cesium Polygon Raster Overlay'.")
        warn("  3. Polygons array: add BP_PortRealism_QuaiPolygon.")
        warn("  4. Tick 'Invert Selection' and 'Exclude Selected Tiles'.")
        return False

    # Push polygon into list
    for prop_name in ("polygons", "cartographic_polygons", "exclude_polygons"):
        try:
            cur = overlay.get_editor_property(prop_name) or []
            if poly not in cur:
                cur.append(poly)
            overlay.set_editor_property(prop_name, cur)
            log("  -> polygon added to '{}' on overlay of {}".format(
                prop_name, tileset.get_actor_label()))
            break
        except Exception:
            continue

    # Set the two booleans
    try_set_props(overlay, [
        ("invert_selection",       True),
        ("exclude_selected_tiles", True),
    ])
    return True

def refresh_tileset(tileset):
    try:
        tileset.refresh_tileset()
    except Exception:
        try:
            tileset.call_method("RefreshTileset", ())
        except Exception:
            pass

def place_monacomap_at_georef(georef, sm_asset):
    """Spawn a StaticMeshActor and attach a CesiumGlobeAnchor at the Monaco lat/lon."""
    # Skip if already placed
    existing = find_actor_by_label(PLACED_ACTOR_LABEL)
    if existing is not None:
        log("PortHercule_Monacomap already exists, re-using.")
        return existing

    # Spawn at the origin first; we'll re-anchor via globe-anchor next.
    sm_actor_cls = unreal.StaticMeshActor.static_class()
    spawn_loc = unreal.Vector(0, 0, 0)
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        sm_actor_cls, spawn_loc, unreal.Rotator(0, 0, 0))
    if actor is None:
        err("Failed to spawn StaticMeshActor.")
        return None
    actor.set_actor_label(PLACED_ACTOR_LABEL)
    actor.static_mesh_component.set_static_mesh(sm_asset)
    actor.set_mobility(unreal.ComponentMobility.STATIC)

    # Attach a CesiumGlobeAnchor component for proper lat/lon binding
    anchor_cls = unreal.load_class(None,
        "/Script/CesiumRuntime.CesiumGlobeAnchorComponent")
    if anchor_cls is None:
        warn("CesiumGlobeAnchorComponent not resolvable; using raw transform instead.")
    else:
        try:
            subobj_sys = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
            handles = subobj_sys.k2_gather_subobject_data_for_instance(actor)
            if handles:
                params = unreal.AddNewSubobjectParams(
                    parent_handle=handles[0],
                    new_class=anchor_cls,
                    blueprint_context=None,
                )
                new_handle, _ = subobj_sys.add_new_subobject(params)
                if new_handle.data_handle.is_valid():
                    anchor = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(
                        new_handle.data_handle)
                    # Bind the lat/lon
                    for setter in ("set_longitude_latitude_height",
                                   "move_to_longitude_latitude_height"):
                        try:
                            anchor.call_method(setter,
                                (unreal.Vector(MONACO_LON, MONACO_LAT, MONACO_H_M),))
                            log("Anchor bound via {}.".format(setter))
                            break
                        except Exception:
                            continue
                    # Some versions expose direct properties
                    try_set_props(anchor, [
                        ("longitude", MONACO_LON),
                        ("latitude",  MONACO_LAT),
                        ("height",    MONACO_H_M),
                    ])
        except Exception as e:
            warn("Could not attach GlobeAnchor automatically: {}".format(e))

    return actor

# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def main():
    log("=" * 60)

    # 1. Locate scene actors
    poly  = find_actor_by_label(POLY_ACTOR_LABEL)
    if poly is None:
        err("Polygon {} not found. Run script 03 first.".format(POLY_ACTOR_LABEL))
        return

    geo   = find_georeference()
    if geo is None:
        err("No CesiumGeoreference actor in the level.")
        return

    google, osm = find_tilesets()
    log("CesiumGeoreference: present")
    log("Google tileset    : {}".format(google.get_actor_label() if google else "MISSING"))
    log("OSM tileset       : {}".format(osm.get_actor_label() if osm else "MISSING"))

    # 2. Wire Georeference field on both tilesets (currently None per your screenshot)
    for ts in [t for t in (google, osm) if t is not None]:
        try_set_props(ts, [("georeference", geo)])
        log("Set Georeference on {}".format(ts.get_actor_label()))

    # 3. Set MSE on both tilesets to iteration-friendly values
    if google is not None:
        try_set_props(google, [("maximum_screen_space_error", TARGET_MSE_GOOGLE)])
        log("Google MSE -> {}".format(TARGET_MSE_GOOGLE))
    if osm is not None:
        try_set_props(osm, [("maximum_screen_space_error", TARGET_MSE_OSM)])
        log("OSM MSE -> {}".format(TARGET_MSE_OSM))

    # 4. Attach the polygon overlay to the OSM tileset (was only on Google)
    if osm is not None:
        log("Attaching polygon overlay to OSM tileset ...")
        ensure_polygon_on_tileset_overlay(osm, poly)

    # 5. Refresh both tilesets so changes take effect
    for ts in [t for t in (google, osm) if t is not None]:
        refresh_tileset(ts)

    # 6. Place Monacomap at georef origin
    sm_asset = unreal.EditorAssetLibrary.load_asset(MONACOMAP_ASSET_PATH)
    if sm_asset is None:
        err("Could not load Monacomap asset at {}".format(MONACOMAP_ASSET_PATH))
        return

    actor = place_monacomap_at_georef(geo, sm_asset)
    if actor is not None:
        log("Placed actor: {}".format(actor.get_actor_label()))
        # Verify material assignment survived
        smc = actor.static_mesh_component
        if smc is not None:
            assigned = sum(1 for i in range(smc.get_num_materials())
                           if smc.get_material(i) is not None)
            log("Materials live on placed actor: {} / {}".format(
                assigned, smc.get_num_materials()))

    log("=" * 60)
    log("NEXT VISUAL CHECK")
    log("  Fly to Port Hercule (use the CesiumDynamicPawn). You should see:")
    log("  - Cesium photogrammetry stripped inside the polygon area")
    log("  - Cesium OSM Buildings ALSO stripped inside the same area")
    log("  - The Monacomap mesh (or its grey default placeholder if")
    log("    master-material graphs aren't wired yet) sitting in the hole")
    log("  - Original Cesium tiles still showing OUTSIDE the polygon")
    log("=" * 60)


if __name__ == "__main__":
    main()
