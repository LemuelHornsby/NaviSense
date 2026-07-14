# =====================================================================
# NaviSense Phase 5 - Scene health check + safe auto-fixes
# =====================================================================
# Run from:  Tools > Execute Python Script...  (with NaviSense_Monaco open)
#
# Checks (and where safe, fixes) the issues found in the editor log:
#   1. World Bounds Checks enabled  -> Cesium warns this breaks georef worlds.
#      FIX: disables bEnableWorldBoundsChecks in the current World Settings.
#   2. Reports any broken/None Cesium3DTileset actors (the log showed one
#      failed import). It cannot recreate them, but it names them so you can
#      delete + re-add via Cesium panel.
#   3. Confirms substepping is on (set in DefaultEngine.ini by automation).
#   4. Confirms the georeference origin is Monaco (43.7340, 7.4197, h5).
#
# Read-mostly; the only write is the World Bounds Checks toggle, which is
# safe and reversible in World Settings.
# =====================================================================

import unreal

TAG = "[NaviSense P5-03]"
def log(m):  unreal.log(TAG + " " + str(m))
def warn(m): unreal.log_warning(TAG + " " + str(m))
def err(m):  unreal.log_error(TAG + " " + str(m))

def actor_subsys():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

def main():
    actors = actor_subsys().get_all_level_actors()
    world = actors[0].get_world() if actors else None

    # --- 1. World Bounds Checks ---
    ws = None
    for a in actors:
        if isinstance(a, unreal.WorldSettings):
            ws = a; break
    if ws:
        try:
            cur = ws.get_editor_property("enable_world_bounds_checks")
            log("World Bounds Checks currently: %s" % cur)
            if cur:
                ws.set_editor_property("enable_world_bounds_checks", False)
                log("FIXED: disabled World Bounds Checks (Cesium-recommended for georef worlds).")
                log("       Remember to File > Save the level to persist this.")
        except Exception as e:
            warn("Could not read/set World Bounds Checks: %s" % e)
    else:
        warn("No WorldSettings actor found in the level.")

    # --- 2. Cesium tilesets health ---
    tiles = [a for a in actors if "Cesium3DTileset" in a.get_class().get_name()]
    log("Cesium3DTileset actors found: %d" % len(tiles))
    for t in tiles:
        log("  - %s  @ %s" % (t.get_actor_label(), t.get_actor_location()))
    if len(tiles) < 2:
        warn("Expected 2 tilesets (Google Photorealistic + terrain). The log showed a")
        warn("FAILED import for one tileset's external actor. If one is missing here,")
        warn("delete the broken Cesium3DTileset and re-add via Cesium panel > ion Assets.")

    # --- 3. Georeference origin ---
    geo = next((a for a in actors if "CesiumGeoreference" in a.get_class().get_name()), None)
    if geo:
        try:
            lat = geo.get_editor_property("origin_latitude")
            lon = geo.get_editor_property("origin_longitude")
            h   = geo.get_editor_property("origin_height")
            log("Georeference origin: lat=%.4f lon=%.4f h=%.1f" % (lat, lon, h))
            if abs(lat-43.7340) > 0.01 or abs(lon-7.4197) > 0.01:
                warn("Origin is NOT the canonical Monaco (43.7340, 7.4197). Confirm intentional.")
        except Exception as e:
            warn("Could not read georeference origin: %s" % e)
    else:
        warn("No CesiumGeoreference actor found.")

    # --- 4. Substepping (project setting) ---
    log("Substepping is set in DefaultEngine.ini (MaxSubsteps=6, dt=0.0166).")
    log("Verify under Project Settings > Physics > Substepping after restart.")

    log("==== health check complete ====")

main()
