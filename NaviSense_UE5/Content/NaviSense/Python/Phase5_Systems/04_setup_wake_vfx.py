# =====================================================================
# NaviSense - Attach + configure the speed-driven wake VFX (D5 / WP-16)
# =====================================================================
# Run from:  Tools > Execute Python Script...   (editor Python)
#
# WHY
#   The hull is kinematically posed (no fluid sim), so the wake is *driven*
#   by the own-ship speed: a Niagara system reads 0..1 user params
#   (WakeIntensity / Spray) and scales bow wave / stern wash / spray.
#   The curve lives in C++ (ANaviSenseShipPawn::GetWakeIntensity01 /
#   GetWakeSpray01) and python/wake_model.py (single source, gate-checked).
#
# WHAT THIS DOES (idempotent, best-effort - the recipe is authoritative)
#   1. Finds the placed yacht pawn in the open level.
#   2. Adds a NiagaraComponent named "WakeViz" at the stern, at the waterline.
#   3. If /Game/NaviSense/Niagara/NS_Wake exists, assigns it.
#   4. Seeds the Niagara user floats from the pawn's wake UPROPERTYs.
#   5. Prints the remaining manual steps (build NS_Wake / bind live intensity).
#
# AFTER
#   See Documents/NaviSense_Wake_VFX_Recipe.md for the NS_Wake emitter build
#   and the live-intensity binding (primary: BlueprintPure getters after the
#   recompile; fallback: BP position-delta, no recompile).
# =====================================================================
import unreal

TAG = "[NaviSense WAKE 04]"
def log(m):  unreal.log(TAG + " " + str(m))
def warn(m): unreal.log_warning(TAG + " " + str(m))
def err(m):  unreal.log_error(TAG + " " + str(m))

WAKE_SYS_PATH = "/Game/NaviSense/Niagara/NS_Wake"   # build per the recipe if missing
COMP_NAME = "WakeViz"
# Stern of a ~40 m hull, at the waterline relative to the actor root.
# (Actor root rides ~FreeboardCm above the water; tune Z so spawns sit on the sea.)
STERN_OFFSET = unreal.Vector(-1800.0, 0.0, -150.0)


def find_yacht():
    """Return the placed NaviSense ship pawn (C++ base or BP-derived), or None."""
    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
    except Exception as e:                       # newer API path
        warn("EditorLevelLibrary unavailable (%s); trying EditorActorSubsystem" % e)
        sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        actors = sub.get_all_level_actors() if sub else []
    base = None
    for a in actors:
        if not a:
            continue
        try:
            if isinstance(a, unreal.NaviSenseShipPawn):
                base = a
                cls = a.get_class().get_name()
                if cls != "NaviSenseShipPawn":   # prefer the BP-derived instance
                    return a
        except Exception:
            pass
    return base


def existing_wake(actor):
    for c in actor.get_components_by_class(unreal.NiagaraComponent):
        nm = c.get_name().lower()
        try:
            tags = [str(t).lower() for t in (c.get_editor_property("component_tags") or [])]
        except Exception:
            tags = []
        if "wakeviz" in nm or "wakeviz" in tags:
            return c
    return None


def main():
    yacht = find_yacht()
    if not yacht:
        err("No NaviSense ship pawn found in the open level. Open NaviSense_Monaco and re-run.")
        return
    log("Yacht: %s (%s)" % (yacht.get_actor_label(), yacht.get_class().get_name()))

    comp = existing_wake(yacht)
    if not comp:
        err("No 'WakeViz' Niagara component on the yacht. This build's Python cannot add it; "
            "add it BY HAND in BP_ShipPawn_Yacht (Components > Add > Niagara Particle System "
            "Component, rename WakeViz), Compile+Save, then re-run this script to assign NS_Wake. "
            "See Documents/NaviSense_Wake_VFX_Recipe.md.")
        return
    log("WakeViz found - configuring.")

    if comp:
        try:
            comp.set_relative_location(STERN_OFFSET, False, False)
            log("Placed WakeViz at stern offset %s." % STERN_OFFSET)
        except Exception as e:
            warn("Could not set relative location (%s)." % e)

        # Assign NS_Wake if it has been built.
        if unreal.EditorAssetLibrary.does_asset_exist(WAKE_SYS_PATH):
            try:
                sysasset = unreal.load_asset(WAKE_SYS_PATH)
                comp.set_asset(sysasset)
                log("Assigned Niagara system %s." % WAKE_SYS_PATH)
            except Exception as e:
                warn("Found NS_Wake but could not assign it (%s)." % e)
        else:
            warn("NS_Wake not found at %s - build it per Documents/NaviSense_Wake_VFX_Recipe.md, "
                 "then re-run this script." % WAKE_SYS_PATH)

        # Seed user floats from the pawn defaults (so the Niagara curve matches C++).
        for prop, var in (("WakeFullSpeedMS", "WakeFullSpeedMS"),
                          ("WakeSprayOnsetMS", "WakeSprayOnsetMS"),
                          ("WakeMinSpeedMS", "WakeMinSpeedMS")):
            try:
                val = float(yacht.get_editor_property(prop))
                comp.set_niagara_variable_float("User." + var, val)
                log("  User.%s = %.3f" % (var, val))
            except Exception:
                pass   # only applies once NS_Wake declares the user params

    log("Saving level...")
    try:
        unreal.EditorLevelLibrary.save_current_level()
    except Exception:
        sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if sub:
            sub.save_current_level()

    log("DONE. Next: build/refine NS_Wake + bind live WakeIntensity/Spray "
        "(recipe). Acceptance G_WAKE_UE: wake scales with speed, spray ~>15 kn, "
        "none when moored.")


main()
