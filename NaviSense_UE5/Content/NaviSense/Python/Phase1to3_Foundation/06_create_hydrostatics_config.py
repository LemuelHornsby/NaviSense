# =====================================================================
# NaviSense - Ensure the DOLPHIN data assets exist (script, no UI dialog)
# =====================================================================
# Run from:  Tools > Execute Python Script...
#
# WHY
#   Right-click > Miscellaneous > Data Asset opens a class-picker that
#   enumerates every Data Asset class (incl. Cesium) and HARD-CRASHES the
#   editor on this Cesium scene (KI-013, confirmed 21 Jun). This script
#   creates the assets DIRECTLY via AssetTools - no dialog, no crash.
#
# WHAT IT DOES (idempotent - skips any that already exist)
#   - /Game/NaviSense/Settings/Vessels/DA_DOLPHIN_VesselProfile      (UNaviSenseVesselProfile)
#   - /Game/NaviSense/Settings/Vessels/DA_DOLPHIN_HydrostaticsConfig (UNaviSenseHydrostaticsConfig)
#   Defaults are already the DOLPHIN figures.
#
# AFTER
#   Select BP_ShipPawn_Yacht and assign on its components:
#     Details > Vessel Profile        = DA_DOLPHIN_VesselProfile
#     Hydrostatics component > Config  = DA_DOLPHIN_HydrostaticsConfig
# =====================================================================
import unreal

TAG = "[NaviSense HYDRO 06]"
def log(m):  unreal.log(TAG + " " + str(m))
def err(m):  unreal.log_error(TAG + " " + str(m))

DIR = "/Game/NaviSense/Settings/Vessels"
ASSETS = [
    ("DA_DOLPHIN_VesselProfile",      "/Script/NaviSense.NaviSenseVesselProfile"),
    ("DA_DOLPHIN_HydrostaticsConfig", "/Script/NaviSense.NaviSenseHydrostaticsConfig"),
]

def ensure(name, class_path):
    path = DIR + "/" + name
    cls = unreal.load_class(None, class_path)
    if cls is None:
        err("Class %s not found - recompile the C++ module first, then re-run." % class_path)
        return False
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        log("OK (exists): %s" % path)
        return True
    if not unreal.EditorAssetLibrary.does_directory_exist(DIR):
        unreal.EditorAssetLibrary.make_directory(DIR)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    asset = tools.create_asset(name, DIR, cls, unreal.DataAssetFactory())
    if asset is None:
        err("create_asset returned None for %s" % path)
        return False
    unreal.EditorAssetLibrary.save_asset(path)
    log("CREATED + saved: %s" % path)
    return True

def main():
    ok = True
    for name, cls in ASSETS:
        ok = ensure(name, cls) and ok
    if ok:
        log("Done. Assign on BP_ShipPawn_Yacht: VesselProfile + Hydrostatics.Config (see header).")
    else:
        err("One or more assets failed - see errors above (usually: needs a recompile).")

main()
