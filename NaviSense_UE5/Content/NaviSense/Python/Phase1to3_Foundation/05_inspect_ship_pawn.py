# =====================================================================
# NaviSense P-A 05 - Inspect the ship pawn & confirm actuator-rig wiring
# =====================================================================
# Run: Tools > Execute Python Script...  (pure introspection - no freeze risk)
# Reports, for each ship pawn in the open level:
#   - whether its class derives from NaviSenseShipPawn (=> Python-driven)
#   - VesselProfile assignment
#   - presence of Bridge / Actuators / Sensors components
#   - every StaticMeshComponent and its assigned mesh (Hull/Rudder/Prop/Bow)
# Paste the Output Log result back to Claude to wire the actuator visual rig.
# =====================================================================
import unreal
TAG = "[NaviSense P-A 05]"
def log(m):  unreal.log(TAG + " " + str(m))
def warn(m): unreal.log_warning(TAG + " " + str(m))
def err(m):  unreal.log_error(TAG + " " + str(m))

def get_actors():
    try:
        return unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    except Exception:
        try:    return unreal.EditorLevelLibrary.get_all_level_actors()
        except Exception: return []

def main():
    ns_type = getattr(unreal, "NaviSenseShipPawn", None)
    actors = get_actors()
    cands = []
    for a in actors:
        try:    cn = a.get_class().get_name()
        except Exception: cn = ""
        is_ns = (ns_type is not None and isinstance(a, ns_type))
        looks = ("ship" in cn.lower()) or ("dolphin" in (a.get_actor_label() or "").lower())
        if is_ns or looks:
            cands.append((a, cn, is_ns))
    if not cands:
        err("No ship pawn found. Place the pawn in NaviSense_Monaco, or open that level.")
        return

    for a, cn, is_ns in cands:
        log("=" * 64)
        try: label = a.get_actor_label()
        except Exception: label = "?"
        log("Actor: %s    Class: %s" % (label, cn))
        log("Derives from NaviSenseShipPawn: %s" % (
            "YES (Python-driven, has bridge/sensors)" if is_ns
            else "NO  <-- WARNING: a plain BP pawn will NOT receive Python state"))
        try:
            vp = a.get_editor_property("VesselProfile")
            log("VesselProfile: %s" % (vp.get_name() if vp else "NONE  <-- assign DA_DOLPHIN_VesselProfile"))
        except Exception as e:
            warn("VesselProfile: not readable (%s)" % e)

        for tname, lbl in [("NaviSenseBridgeComponent", "Bridge"),
                           ("ActuatorComponent", "Actuators"),
                           ("SensorBundleComponent", "Sensors")]:
            t = getattr(unreal, tname, None)
            try:
                comp = a.get_component_by_class(t) if t else None
                log("  %-10s component: %s" % (lbl, "present" if comp else "MISSING"))
            except Exception as e:
                warn("  %s component: probe failed (%s)" % (lbl, e))

        try:    smcs = a.get_components_by_class(unreal.StaticMeshComponent)
        except Exception: smcs = []
        log("  StaticMeshComponents (%d):" % len(smcs))
        names = []
        for sm in smcs:
            try:
                nm = sm.get_name(); names.append(nm.lower())
                try:    mesh = sm.get_editor_property("static_mesh")
                except Exception: mesh = getattr(sm, "static_mesh", None)
                log("    - %-24s mesh=%s" % (nm, mesh.get_name() if mesh else "NONE"))
            except Exception as e:
                warn("    - component read failed (%s)" % e)
        joined = " ".join(names)
        for part in ["hull", "rudder", "prop", "bow"]:
            log("  part by name '%s': %s" % (part, "yes" if part in joined else "NO"))

    log("=" * 64)
    log("Done. Paste this Output Log block to Claude to build the actuator visual rig.")

main()
