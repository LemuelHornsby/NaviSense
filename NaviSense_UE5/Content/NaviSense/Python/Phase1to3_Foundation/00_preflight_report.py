# =====================================================================
# NaviSense Phase 1-3 - Preflight report (READ-ONLY)
# =====================================================================
# Run from:  Tools > Execute Python Script...  (any NaviSense map open)
#
# WHAT THIS DOES (writes nothing except a JSON report)
#   Prints a one-shot readiness snapshot to the Output Log and writes
#   <project>/Saved/NaviSense_Reports/preflight.json:
#     - Engine version + whether this is a C++ project (Source/ present)
#     - Whether the NaviSense module compiled (class lookups resolve)
#     - Plugin enablement (Water, Cesium, MovieRenderPipeline, ...)
#     - Presence of the maps, the SimulatorBase map, and the Sea wave assets
#     - Cesium georeference + tileset count in the CURRENT level
#   Use this first each PC session to see exactly what is and isn't done.
#
# SAFE: read-only except the JSON report file.
# =====================================================================
import unreal, json, os

TAG = "[NaviSense P1-00]"
def log(m):  unreal.log(TAG + " " + str(m))
def warn(m): unreal.log_warning(TAG + " " + str(m))

def has_class(path):
    try:
        return unreal.load_class(None, path) is not None
    except Exception:
        return False

def asset_exists(p):
    return unreal.EditorAssetLibrary.does_asset_exist(p)

def actor_subsys():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

def main():
    rep = {}

    # --- Engine / project type ---
    rep["engine_version"] = unreal.SystemLibrary.get_engine_version()
    proj = unreal.Paths.project_dir()
    rep["project_dir"] = proj
    rep["is_cpp_project"] = os.path.isdir(os.path.join(proj, "Source"))
    rep["navisense_module_compiled"] = has_class(
        "/Script/NaviSense.NaviSenseShipPawn")

    # --- Plugins we depend on (by a known class each) ---
    rep["plugins"] = {
        "Water":             has_class("/Script/Water.WaterBodyOcean"),
        "Cesium":            has_class("/Script/CesiumRuntime.CesiumGeoreference"),
        "MovieRenderPipeline": has_class("/Script/MovieRenderPipeline.MoviePipelineQueue"),
        "Niagara":           has_class("/Script/Niagara.NiagaraComponent"),
    }

    # --- Maps + key assets ---
    rep["maps"] = {
        "Monaco":        asset_exists("/Game/NaviSense/Maps/NaviSense_Monaco"),
        "Base":          asset_exists("/Game/NaviSense/Maps/NaviSense_Base"),
        "Longbeach":     asset_exists("/Game/NaviSense/Maps/NaviSense_Longbeach"),
        "SimulatorBase": asset_exists("/Game/NaviSense/Maps/NaviSense_SimulatorBase"),
    }
    rep["sea_assets"] = {
        n: asset_exists("/Game/NaviSense/Settings/Sea/" + n)
        for n in ("WaveAsset_Calm", "WaveAsset_Moderate", "WaveAsset_Rough")
    }

    # --- Current level: georeference + tilesets + water ---
    actors = actor_subsys().get_all_level_actors()
    def count_cls(sub):
        return sum(1 for a in actors if sub.lower() in a.get_class().get_name().lower())
    rep["current_level"] = {
        "georeference": count_cls("CesiumGeoreference"),
        "tilesets":     count_cls("Cesium3DTileset"),
        "water_ocean":  count_cls("WaterBodyOcean"),
        "water_zone":   count_cls("WaterZone"),
        "ship_pawn":    count_cls("NaviSenseShipPawn"),
    }

    out_dir = os.path.join(proj, "Saved", "NaviSense_Reports")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "preflight.json")
    with open(out, "w") as f:
        json.dump(rep, f, indent=2)

    log("=" * 56)
    log("PREFLIGHT READINESS SNAPSHOT")
    log("  Engine            : %s" % rep["engine_version"])
    log("  C++ project (Source/) : %s" % rep["is_cpp_project"])
    log("  NaviSense compiled    : %s" % rep["navisense_module_compiled"])
    for k, v in rep["plugins"].items():
        log("  plugin %-18s: %s" % (k, "OK" if v else "missing"))
    for k, v in rep["maps"].items():
        log("  map %-20s : %s" % (k, "present" if v else "MISSING"))
    cl = rep["current_level"]
    log("  level: georef=%d tilesets=%d ocean=%d zone=%d ship=%d" % (
        cl["georeference"], cl["tilesets"], cl["water_ocean"],
        cl["water_zone"], cl["ship_pawn"]))
    log("Full JSON -> %s" % out)
    log("=" * 56)

main()
