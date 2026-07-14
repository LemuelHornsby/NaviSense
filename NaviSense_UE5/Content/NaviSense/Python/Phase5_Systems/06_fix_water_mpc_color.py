# =====================================================================
# NaviSense - Recolor the ocean at its real source: MPC_Water
# =====================================================================
# Run from: Tools > Execute Python Script...
#
# WHY
#   The UE Water plugin's surface colour is driven by the MPC_Water Material
#   Parameter Collection, NOT by the water material instance's Absorption/
#   Scattering params - so editing MI_NaviSense_Ocean does nothing to the sea.
#   This finds MPC_Water, PRINTS every parameter (so we see the exact names),
#   and sets the absorption/scattering to a natural Monaco blue. Idempotent.
#
# TUNE: edit NEW_ABSORP / NEW_SCATTER, re-run, look at the Monaco viewport.
# =====================================================================
import unreal

TAG = "[NaviSense WATER MPC]"
def log(m):  unreal.log(TAG + " " + str(m))
def err(m):  unreal.log_error(TAG + " " + str(m))

NEW_ABSORP  = unreal.LinearColor(8.0, 70.0, 420.0, 8.0)   # R>=G>=B => deep blue depth
NEW_SCATTER = unreal.LinearColor(0.0, 0.25, 0.40, 0.5)    # dim cool body, not neon


def find_mpc():
    try:
        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        cp = unreal.TopLevelAssetPath("/Script/Engine", "MaterialParameterCollection")
        for d in ar.get_assets_by_class(cp, True):
            if str(d.asset_name) == "MPC_Water":
                return unreal.load_asset("%s.%s" % (d.package_name, d.asset_name))
    except Exception as e:
        err("registry query failed (%s); trying known paths" % e)
    for p in ("/Water/Materials/MPC/MPC_Water", "/Water/MPC_Water",
              "/Water/Materials/Util/MPC_Water", "/Water/Materials/MPC_Water"):
        if unreal.EditorAssetLibrary.does_asset_exist(p):
            return unreal.load_asset(p)
    return None


mpc = find_mpc()
if not mpc:
    err("MPC_Water not found - tell Claude.")
else:
    log("MPC_Water = " + mpc.get_path_name())
    try:
        vparams = list(mpc.get_editor_property("vector_parameters"))
    except Exception as e:
        vparams = []; err("could not read vector_parameters: %s" % e)
    log("--- VECTOR PARAMS (%d) ---" % len(vparams))
    for p in vparams:
        log("  [V] %s = %s" % (p.get_editor_property("parameter_name"),
                               p.get_editor_property("default_value")))
    try:
        for p in list(mpc.get_editor_property("scalar_parameters")):
            log("  [S] %s = %s" % (p.get_editor_property("parameter_name"),
                                   p.get_editor_property("default_value")))
    except Exception:
        pass

    changed = False
    for p in vparams:
        n = str(p.get_editor_property("parameter_name")).lower()
        if "absorp" in n:
            p.set_editor_property("default_value", NEW_ABSORP); changed = True
            log("  -> SET %s = absorption" % n)
        elif "scatter" in n and "foam" not in n:
            p.set_editor_property("default_value", NEW_SCATTER); changed = True
            log("  -> SET %s = scattering" % n)

    if changed:
        try:
            mpc.set_editor_property("vector_parameters", vparams)
            ok = unreal.EditorAssetLibrary.save_asset(mpc.get_path_name())
            log("Saved MPC_Water (%s) -> LOOK AT THE MONACO VIEWPORT." % ok)
        except Exception as e:
            err("save failed (engine asset may be read-only): %s -- tell Claude, "
                "we'll use a Post Process grade instead." % e)
    else:
        log("No absorption/scattering VECTOR param matched by name -- paste the "
            "VECTOR PARAMS list above to Claude and I'll target the exact one.")
