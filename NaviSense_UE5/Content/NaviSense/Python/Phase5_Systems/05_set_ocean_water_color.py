# =====================================================================
# NaviSense - Natural Monaco-blue ocean (D6 capture look)
# =====================================================================
# Run from: Tools > Execute Python Script...
#
# WHY
#   The UE Water plugin default ocean reads as bright tropical cyan. This sets
#   the SingleLayerWater Absorption/Scattering on EXACTLY the material instances
#   the WaterBodyOcean is using (Water Material, Water Static Mesh Material, HLOD),
#   so the whole visible sea recolors - no missed instance, no guesswork.
#   Idempotent + reproducible (good for the clean-repro / demo build, D8).
#
# TUNE: edit ABSORP / SCATTER below, re-run, look at the Monaco viewport.
#   Absorption (0..~500 scale): R>=G>=B => red dies first => deep blue depth.
#   Scattering (0..1 scale): the water's body glow; low + blue = natural, not neon.
# =====================================================================
import unreal

TAG = "[NaviSense WATER]"
def log(m):  unreal.log(TAG + " " + str(m))
def err(m):  unreal.log_error(TAG + " " + str(m))

# --- the look (tweak these two lines, re-run) -----------------------
ABSORP  = unreal.LinearColor(8.0, 70.0, 420.0, 8.0)   # was (10,150,350,8)
SCATTER = unreal.LinearColor(0.0, 0.25, 0.40, 0.5)    # was (1,1,1,0.5)
# --------------------------------------------------------------------

mel = unreal.MaterialEditingLibrary
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
MAT_PROPS = ("water_material", "water_static_mesh_material", "water_hlod_material")

def recolor(mi):
    mel.set_material_instance_vector_parameter_value(mi, "Absorption", ABSORP)
    mel.set_material_instance_vector_parameter_value(mi, "Scattering", SCATTER)
    unreal.EditorAssetLibrary.save_asset(mi.get_path_name())

done = set()
oceans = 0
for a in sub.get_all_level_actors():
    if not a or "WaterBodyOcean" not in a.get_class().get_name():
        continue
    oceans += 1
    comps = a.get_components_by_class(unreal.WaterBodyComponent)
    for comp in comps:
        for prop in MAT_PROPS:
            try:
                mi = comp.get_editor_property(prop)
            except Exception:
                mi = None
            if mi and isinstance(mi, unreal.MaterialInstanceConstant) and mi.get_name() not in done:
                try:
                    recolor(mi)
                    done.add(mi.get_name())
                    log("recoloured %s (%s)" % (mi.get_name(), prop))
                except Exception as e:
                    err("could not set params on %s: %s" % (mi.get_name(), e))

if oceans == 0:
    err("No WaterBodyOcean found - open NaviSense_Monaco and re-run.")
elif not done:
    err("Found the ocean but no MaterialInstanceConstant in its material slots - "
        "make sure MI_NaviSense_Ocean is assigned to Water Material + Water Static Mesh Material.")
else:
    log("DONE - recoloured %d instance(s): %s. Look at the Monaco viewport (Continue past "
        "the KI-014 save nag). Still cyan? the colour is MPC_Water-driven - tell Claude." %
        (len(done), ", ".join(sorted(done))))
