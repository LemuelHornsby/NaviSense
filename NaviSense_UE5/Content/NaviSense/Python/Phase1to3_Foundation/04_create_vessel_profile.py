# =====================================================================
# NaviSense Phase A - Create the DOLPHIN vessel profile data asset
# =====================================================================
# Run from:  Tools > Execute Python Script...
#
# WHY
#   Creating a Data Asset via Miscellaneous > Data Asset opens a class-picker
#   dialog that enumerates every Data Asset class (incl. Cesium) and, on a
#   heavy Cesium scene, can stress the GPU driver into a hard freeze. This
#   script creates the asset DIRECTLY - no dialog, no enumeration, no freeze.
#
# WHAT IT DOES
#   Creates /Game/NaviSense/Settings/Vessels/DA_DOLPHIN_VesselProfile of class
#   UNaviSenseVesselProfile (your compiled C++ data asset). Idempotent: if it
#   already exists, it just reports and stops.
#
# REQUIRES
#   The C++ module compiled (it is). Run 00_preflight_report.py first if unsure.
# =====================================================================
import unreal

TAG = "[NaviSense P-A 04]"
def log(m):  unreal.log(TAG + " " + str(m))
def warn(m): unreal.log_warning(TAG + " " + str(m))
def err(m):  unreal.log_error(TAG + " " + str(m))

ASSET_DIR  = "/Game/NaviSense/Settings/Vessels"
ASSET_NAME = "DA_DOLPHIN_VesselProfile"
ASSET_PATH = ASSET_DIR + "/" + ASSET_NAME
CLASS_PATH = "/Script/NaviSense.NaviSenseVesselProfile"

def main():
    # Verify the C++ class exists (i.e. the module is compiled).
    cls = unreal.load_class(None, CLASS_PATH)
    if cls is None:
        err("Class %s not found. Compile the C++ module first, then re-run." % CLASS_PATH)
        return

    # Idempotent: skip if already present.
    if unreal.EditorAssetLibrary.does_asset_exist(ASSET_PATH):
        log("Already exists: %s  (nothing to do)" % ASSET_PATH)
        return

    # Ensure the folder exists.
    if not unreal.EditorAssetLibrary.does_directory_exist(ASSET_DIR):
        unreal.EditorAssetLibrary.make_directory(ASSET_DIR)
        log("Created folder: %s" % ASSET_DIR)

    # Create the Data Asset directly via AssetTools + DataAssetFactory.
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.DataAssetFactory()
    asset = tools.create_asset(ASSET_NAME, ASSET_DIR, cls, factory)
    if asset is None:
        err("create_asset returned None for %s" % ASSET_PATH)
        return

    unreal.EditorAssetLibrary.save_asset(ASSET_PATH)
    log("Created and saved: %s" % ASSET_PATH)
    log("Now assign it on your ship pawn: Details > Vessel Profile = %s" % ASSET_NAME)

main()
