# =====================================================================
# NaviSense - Wire the 3 placed Traffic ships for COLREGS scenarios (WP-15B)
# =====================================================================
# Run from:  Tools > Execute Python Script...   (editor Python; KI-013: use a
#            SCRIPT, never the right-click menu)
#
# WHY
#   The COLREGS evidence pack (AIS / CPA-TCPA / conformance) was validated only
#   against SCRIPTED targets - no ships were on screen. This wires the vessels
#   you placed under the "Traffic" folder so the listener drives them over the
#   wire (state.v1 traffic[]) from the SAME deterministic preset the pack scores.
#   The rendered ships then match the analysis exactly -> capture is honest.
#
# WHAT THIS DOES (idempotent, best-effort)
#   1. Finds the placed Traffic actors (folder "Traffic", else label match, else
#      the TRAFFIC_LABELS override below).
#   2. Forces each one's root component MOVABLE (static-mesh props can't be driven
#      otherwise) and tags it "NaviSenseTraffic".
#   3. Finds the own-ship pawn and assigns its TrafficActors array (sorted by
#      label = stable slot order) + bAnchorTrafficToSpawn = True.
#   4. Saves the level.
#
# SLOT MAPPING  (state.v1 traffic[] index -> TrafficActors[] index, by sorted label)
#   The "monaco_capture" preset emits targets in this order:
#       slot 0 = SLOWBELLE (overtaking, slow, close ahead)
#       slot 1 = AZURFERRY (crossing from starboard bow)
#       slot 2 = MERIDIAN  (head-on, inbound)
#   The 3 actors are assigned slot 0/1/2 by sorted label. Rename your actors
#   (e.g. Traffic_0_SLOWBELLE / Traffic_1_AZURFERRY / Traffic_2_MERIDIAN) to pick
#   which prop is which contact. Mapping is cosmetic if the props look alike.
#
# AFTER
#   Rebuild C++ (this packet adds FNaviSenseState.traffic + ApplyTraffic), then
#   run:  python run_demo.py --scenario monaco_capture   (or python_listener.py
#   --scenario monaco_capture) and Play. Acceptance G_TRAFFIC_UE: the 3 ships
#   move along the encounter; own-ship meets/crosses/overtakes them.
# =====================================================================
import unreal

TAG = "[NaviSense TRAFFIC 07]"
def log(m):  unreal.log(TAG + " " + str(m))
def warn(m): unreal.log_warning(TAG + " " + str(m))
def err(m):  unreal.log_error(TAG + " " + str(m))

TRAFFIC_TAG = "NaviSenseTraffic"
FOLDER_HINT = "traffic"                 # outliner folder substring (case-insensitive)
# Optional hard override: exact actor labels, in the slot order you want.
TRAFFIC_LABELS = []                     # e.g. ["Traffic_0", "Traffic_1", "Traffic_2"]


def all_actors():
    try:
        return unreal.EditorLevelLibrary.get_all_level_actors()
    except Exception as e:
        warn("EditorLevelLibrary unavailable (%s); using EditorActorSubsystem" % e)
        sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        return sub.get_all_level_actors() if sub else []


def find_yacht(actors):
    base = None
    for a in actors:
        if not a:
            continue
        try:
            if isinstance(a, unreal.NaviSenseShipPawn):
                base = a
                if a.get_class().get_name() != "NaviSenseShipPawn":
                    return a                      # prefer the BP-derived instance
        except Exception:
            pass
    return base


def find_traffic(actors, yacht):
    # 1) explicit override
    if TRAFFIC_LABELS:
        by_label = {a.get_actor_label(): a for a in actors if a}
        picked = [by_label[l] for l in TRAFFIC_LABELS if l in by_label]
        if picked:
            return picked
        warn("TRAFFIC_LABELS set but none matched; falling back to folder/label scan.")
    # 2) by outliner folder
    found = []
    for a in actors:
        if not a or a is yacht:
            continue
        try:
            fp = str(a.get_folder_path() or "").lower()
        except Exception:
            fp = ""
        if FOLDER_HINT in fp:
            found.append(a)
    # 3) fallback by label
    if not found:
        for a in actors:
            if not a or a is yacht:
                continue
            lbl = a.get_actor_label().lower()
            if any(k in lbl for k in ("traffic", "vessel", "ship", "boat", "ferry", "cargo")):
                found.append(a)
    # stable slot order by label
    found.sort(key=lambda a: a.get_actor_label())
    return found


def main():
    actors = all_actors()
    if not actors:
        err("No level actors. Open NaviSense_Monaco and re-run.")
        return
    yacht = find_yacht(actors)
    if not yacht:
        err("No NaviSense ship pawn (own-ship) found. Open NaviSense_Monaco and re-run.")
        return
    log("Own-ship: %s (%s)" % (yacht.get_actor_label(), yacht.get_class().get_name()))

    traffic = find_traffic(actors, yacht)
    if not traffic:
        err("No Traffic actors found. Put your 3 ships under an outliner folder named "
            "'Traffic', or set TRAFFIC_LABELS at the top of this script, then re-run.")
        return
    log("Found %d Traffic actor(s):" % len(traffic))

    for i, a in enumerate(traffic):
        # MOVABLE root (static-mesh props are Static by default and can't be driven)
        try:
            root = a.get_editor_property("root_component")
            if root:
                root.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        except Exception as e:
            warn("  [%d] %s: could not set Movable (%s)" % (i, a.get_actor_label(), e))
        # tag NaviSenseTraffic (so the pawn can auto-resolve even without the array)
        try:
            tags = [str(t) for t in (a.tags or [])]
            if TRAFFIC_TAG not in tags:
                tags.append(TRAFFIC_TAG)
                a.set_editor_property("tags", [unreal.Name(t) for t in tags])
        except Exception as e:
            warn("  [%d] %s: could not tag (%s)" % (i, a.get_actor_label(), e))
        log("  slot %d -> %s  (Movable + tagged)" % (i, a.get_actor_label()))

    # Assign the array on the own-ship pawn + anchor traffic to its spawn.
    try:
        yacht.set_editor_property("TrafficActors", traffic)
        yacht.set_editor_property("bAnchorTrafficToSpawn", True)
        log("Assigned TrafficActors[%d] + bAnchorTrafficToSpawn=True on the pawn." % len(traffic))
    except Exception as e:
        warn("Could not set TrafficActors on the pawn (%s). The pawn will still "
             "auto-resolve by the '%s' tag at BeginPlay." % (e, TRAFFIC_TAG))

    log("Saving level...")
    try:
        unreal.EditorLevelLibrary.save_current_level()
    except Exception:
        sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if sub:
            sub.save_current_level()

    log("DONE. Slot order (state.v1 traffic[] -> actor): 0=SLOWBELLE 1=AZURFERRY "
        "2=MERIDIAN. Rebuild C++, then: python run_demo.py --scenario monaco_capture "
        "and Play. G_TRAFFIC_UE: the 3 ships move along the encounter.")


main()
