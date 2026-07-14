# =====================================================================
# NaviSense - COLREGS encounter picker (WP-20260703)
# =====================================================================
# Run from:  Tools > Execute Python Script...   (editor Python; KI-013: use a
#            SCRIPT, never the right-click menu). Best bound to a 4-button
#            Editor Utility Widget (see Documents/NaviSense_COLREGS_Encounter_Recipe.md).
#
# SINCE WP-20260709C this script's DEFAULT action is the ONE-TIME
# setup_scenery_target(): assign marine_rescue_boat as TrafficActors[0], hide
# nothing, save the level -- then every run is started from a TERMINAL with
# run_colregs.py (scenario chosen in code: --head-on etc.). pick()/reset_all()
# remain for the hide-others flow and for restoring 3-ship scenes.
#
# WHAT pick() DOES (per chosen encounter, idempotent, best-effort)
#   1. Picks ONE target ship (mapping below) as THE COLREGS target; HIDES the
#      other two Traffic ships (SetActorHiddenInGame) so the scene shows a single,
#      unambiguous encounter.
#   2. Forces the chosen ship MOVABLE + assigns it as the own-ship pawn's
#      TrafficActors[0] (+ bAnchorTrafficToSpawn=True) so ApplyTraffic drives it
#      from the wire (state.v1 traffic[]).
#   3. Prints the exact listener command (and tries to launch it in a new console).
#      Then you press PLAY. Own-ship runs its SCRIPTED avoidance (give-way) or HOLD
#      (stand-on); after the run the evidence pack scores COLREGS conformance.
#
# HOW TO CHOOSE
#   Set ENCOUNTER below to one of: head_on | crossing_giveway | crossing_standon
#   | overtaking   (or call pick("<encounter>") from an EUW button).
# =====================================================================
import unreal, os

TAG = "[NaviSense COLREGS 10]"
def log(m):  unreal.log(TAG + " " + str(m))
def warn(m): unreal.log_warning(TAG + " " + str(m))
def err(m):  unreal.log_error(TAG + " " + str(m))

# ---- CHOOSE THE ENCOUNTER HERE (or call pick(...) from an EUW button) --------
ENCOUNTER = "head_on"

# ---- THE TARGET SHIP (WP-20260709B: ONE default for ALL encounters) ----------
# marine_rescue_boat is the default: it imported world-aligned (no roll
# correction needed). To use another ship for a run, EITHER edit this ONE
# variable OR call pick("<encounter>", ship="<label substring>") from the
# editor Python console. The choice flows everywhere automatically: the picker
# assigns the actor AND passes --target-name to the listener, so the wire /
# logs / evidence always name the ship actually driven.
TARGET_SHIP = "marine_rescue_boat"

# encounter -> listener scenario. The target ship is TARGET_SHIP for all four
# (override per call via pick(..., ship=...)). Only ONE ship is active per run;
# the other two are hidden.
ENCOUNTERS = {
    "head_on":          "colregs_head_on",
    "crossing_giveway": "colregs_crossing_giveway",
    "crossing_standon": "colregs_crossing_standon",
    "overtaking":       "colregs_overtaking",
}
FOLDER_HINT = "traffic"
TRAFFIC_TAG = "NaviSenseTraffic"


def _all_actors():
    try:
        return unreal.EditorLevelLibrary.get_all_level_actors()
    except Exception:
        sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        return sub.get_all_level_actors() if sub else []


def _find_yacht(actors):
    base = None
    for a in actors:
        try:
            if isinstance(a, unreal.NaviSenseShipPawn):
                base = a
                if a.get_class().get_name() != "NaviSenseShipPawn":
                    return a
        except Exception:
            pass
    return base


def _traffic_actors(actors, yacht):
    found = []
    for a in actors:
        if not a or a is yacht:
            continue
        try:
            fp = str(a.get_folder_path() or "").lower()
        except Exception:
            fp = ""
        lbl = a.get_actor_label().lower()
        if FOLDER_HINT in fp or any(k in lbl for k in
                                    ("traffic", "vessel", "ship", "boat", "ferry", "rescue", "yacht_with")):
            found.append(a)
    found.sort(key=lambda a: a.get_actor_label())
    return found


def _workspace_root():
    # workspace root = five levels up from this script
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))


def pick(encounter, ship=None):
    """Set up ONE COLREGS encounter. ship=None -> TARGET_SHIP (marine_rescue_boat);
    pass ship="Yacht_with_interior" (label substring) to swap for this run."""
    encounter = (encounter or "").strip()
    if encounter not in ENCOUNTERS:
        err("Unknown encounter '%s'. Use one of: %s" % (encounter, ", ".join(ENCOUNTERS)))
        return
    scenario = ENCOUNTERS[encounter]
    target_hint = (ship or TARGET_SHIP).strip()
    actors = _all_actors()
    yacht = _find_yacht(actors)
    if not yacht:
        err("No NaviSense own-ship pawn found. Open NaviSense_Monaco and re-run.")
        return
    traffic = _traffic_actors(actors, yacht)
    if not traffic:
        err("No Traffic ships found. Put them under an Outliner folder named 'Traffic'.")
        return

    # choose the target by label substring; fall back to the first ship
    target = next((a for a in traffic if target_hint.lower() in a.get_actor_label().lower()), None)
    if target is None:
        target = traffic[0]
        warn("Target label '%s' not found; using '%s'." % (target_hint, target.get_actor_label()))

    # 1) hide the others, show + prep the target
    for a in traffic:
        is_target = (a is target)
        try:
            a.set_actor_hidden_in_game(not is_target)
            # also hide in the editor viewport for a clean pre-Play scene
            a.set_editor_property("is_temporarily_hidden_in_editor", not is_target)
        except Exception as e:
            warn("  visibility on %s: %s" % (a.get_actor_label(), e))
        if is_target:
            try:
                root = a.get_editor_property("root_component")
                if root:
                    root.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
                tags = [str(t) for t in (a.tags or [])]
                if TRAFFIC_TAG not in tags:
                    a.set_editor_property("tags", [unreal.Name(t) for t in tags + [TRAFFIC_TAG]])
            except Exception as e:
                warn("  prep target: %s" % e)

    # 2) assign the single target as TrafficActors[0]
    try:
        yacht.set_editor_property("TrafficActors", [target])
        yacht.set_editor_property("bAnchorTrafficToSpawn", True)
    except Exception as e:
        warn("Could not assign TrafficActors (%s); the pawn will auto-resolve by tag." % e)

    log("Encounter '%s' -> scenario '%s'; target = %s (others hidden)."
        % (encounter, scenario, target.get_actor_label()))

    # 3) print the TERMINAL command (KI-036: never launch a child process from
    #    editor Python -- the interpreter binary here IS the Unreal editor, so
    #    the old auto-launch opened a new blank editor window. Day-to-day runs
    #    use run_colregs.py from a real terminal.)
    target_label = target.get_actor_label()
    ws = _workspace_root()
    flag = "--" + [k for k, v in ENCOUNTERS.items() if v == scenario][0].replace("_", "-")
    ship_arg = "" if target_label == TARGET_SHIP else ' --ship "%s"' % target_label
    log('Scene ready. Run this in a TERMINAL, then press PLAY:\n'
        '  cd "%s"\n  python run_colregs.py %s%s' % (ws, flag, ship_arg))
    log("After the run, the evidence pack scores COLREGS conformance "
        "(logs/<run>/evidence_pack/evidence_report.html).")


def setup_scenery_target(ship=None):
    """ONE-TIME setup for the terminal workflow (WP-20260709C, scenery mode):
    assign the default target (marine_rescue_boat) as TrafficActors[0] WITHOUT
    hiding the other ships -- they stay visible as static scenery. After this,
    every scenario is chosen purely in the terminal (run_colregs.py)."""
    target_hint = (ship or TARGET_SHIP).strip()
    actors = _all_actors()
    yacht = _find_yacht(actors)
    if not yacht:
        err("No NaviSense own-ship pawn found. Open NaviSense_Monaco and re-run.")
        return
    traffic = _traffic_actors(actors, yacht)
    target = next((a for a in traffic if target_hint.lower() in a.get_actor_label().lower()), None)
    if target is None:
        err("No Traffic ship matches '%s'." % target_hint)
        return
    try:
        root = target.get_editor_property("root_component")
        if root:
            root.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        tags = [str(t) for t in (target.tags or [])]
        if TRAFFIC_TAG not in tags:
            target.set_editor_property("tags", [unreal.Name(t) for t in tags + [TRAFFIC_TAG]])
        target.set_actor_hidden_in_game(False)
        target.set_editor_property("is_temporarily_hidden_in_editor", False)
        yacht.set_editor_property("TrafficActors", [target])
        yacht.set_editor_property("bAnchorTrafficToSpawn", True)
    except Exception as e:
        err("setup failed: %s" % e)
        return
    log("setup_scenery_target: TrafficActors[0] = %s (others visible as scenery). "
        "SAVE THE LEVEL. From now on run scenarios from the terminal: "
        "python run_colregs.py --head-on | --crossing-giveway | --crossing-standon | --overtaking"
        % target.get_actor_label())


def reset_all():
    """Undo a picker session for 3-ship runs (monaco_capture / harbor_traffic):
    un-hide all Traffic ships, tag them, and CLEAR the pawn's TrafficActors so
    BeginPlay re-scans by tag (stable name order). Run this before any
    multi-ship scenario after using pick()."""
    actors = _all_actors()
    yacht = _find_yacht(actors)
    if not yacht:
        err("No NaviSense own-ship pawn found.")
        return
    traffic = _traffic_actors(actors, yacht)
    for a in traffic:
        try:
            a.set_actor_hidden_in_game(False)
            a.set_editor_property("is_temporarily_hidden_in_editor", False)
            tags = [str(t) for t in (a.tags or [])]
            if TRAFFIC_TAG not in tags:
                a.set_editor_property("tags", [unreal.Name(t) for t in tags + [TRAFFIC_TAG]])
            root = a.get_editor_property("root_component")
            if root:
                root.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        except Exception as e:
            warn("  reset %s: %s" % (a.get_actor_label(), e))
    try:
        yacht.set_editor_property("TrafficActors", [])
    except Exception as e:
        warn("Could not clear TrafficActors: %s" % e)
    log("reset_all: %d Traffic ships visible + tagged; TrafficActors cleared "
        "(BeginPlay re-scans by tag). Ready for monaco_capture / harbor_traffic." % len(traffic))


# EUW button helpers
def head_on():          pick("head_on")
def crossing_giveway(): pick("crossing_giveway")
def crossing_standon(): pick("crossing_standon")
def overtaking():       pick("overtaking")

if __name__ == "__main__":
    # WP-20260709C default: ONE-TIME scenery setup (assign the rescue boat as
    # the driven slot, hide nothing). Day-to-day scenario choice lives in the
    # terminal: python run_colregs.py --head-on | --crossing-giveway |
    # --crossing-standon | --overtaking.
    # For the old hide-the-others flow, change this line to: pick(ENCOUNTER)
    setup_scenery_target()
