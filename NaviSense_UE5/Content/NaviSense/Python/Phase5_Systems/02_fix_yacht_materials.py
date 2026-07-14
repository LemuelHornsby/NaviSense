# =====================================================================
# NaviSense Phase 5 - Yacht material / Nanite fixer
# =====================================================================
# Run from:  Tools > Execute Python Script...
#
# WHY: the editor log shows ~2,700+ warnings of the form
#   "Invalid material [water] used on Nanite static mesh [unity_yacht_model].
#    Only opaque or masked blend modes are supported, [BLEND_Translucent...]"
# The imported Unity hull has TRANSLUCENT material slots (water, glass,
# plastic) on a Nanite mesh. Nanite does not render translucency, so those
# slots are invisible AND spam the log every load.
#
# This script disables Nanite on the unity_yacht_model static mesh, which
# immediately silences the warnings and lets the translucent slots render.
# (Disabling Nanite on a single hull is the recommended fix; you re-enable
#  it later only if you author opaque/masked replacements for those slots.)
#
# It is conservative: it only touches unity_yacht_model, logs before/after,
# and saves the asset. Re-runnable.
# =====================================================================

import unreal

TAG = "[NaviSense P5-02]"
def log(m):  unreal.log(TAG + " " + str(m))
def warn(m): unreal.log_warning(TAG + " " + str(m))
def err(m):  unreal.log_error(TAG + " " + str(m))

MESH_PATH = "/Game/NaviSense/Ships/unity_yacht_model/StaticMeshes/unity_yacht_model"

def main():
    mesh = unreal.load_asset(MESH_PATH)
    if mesh is None:
        err("Could not load %s -- check the path in the Content Browser." % MESH_PATH)
        return
    if not isinstance(mesh, unreal.StaticMesh):
        err("Asset is not a StaticMesh: %s" % type(mesh))
        return

    nanite = mesh.get_editor_property("nanite_settings")
    log("Nanite currently enabled: %s" % nanite.enabled)

    if nanite.enabled:
        nanite.enabled = False
        mesh.set_editor_property("nanite_settings", nanite)
        unreal.EditorAssetLibrary.save_asset(MESH_PATH)
        log("Nanite DISABLED on unity_yacht_model and asset saved.")
        log("The translucent slots (water/glass/plastic) will now render and")
        log("the ~2,700 'Invalid material on Nanite' warnings will stop.")
    else:
        log("Nanite already disabled -- nothing to do.")

    # report the material slots so you know what is on the hull
    mats = mesh.static_materials
    log("---- %d material slots on unity_yacht_model ----" % len(mats))
    for i, m in enumerate(mats):
        name = m.material_slot_name
        log("  slot %2d: %s" % (i, name))

main()
