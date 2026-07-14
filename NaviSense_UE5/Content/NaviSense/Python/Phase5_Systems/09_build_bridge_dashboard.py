# =====================================================================
# NaviSense - Bridge Dashboard build helper (WP-UI-DASHBOARD / WP_20260701)
# =====================================================================
# Run from:  Tools > Execute Python Script...   (editor Python; KI-013: use a
#            SCRIPT, never the right-click "New Editor Utility Widget" menu,
#            which is the one known to crash this editor build).
#
# WHY
#   Lemuel asked for a full-screen, INTERACTIVE bridge dashboard (navy theme,
#   4 panels: actuators / sensors / maneuver+IMO KPIs / sea-state+AIS) whose
#   helm/throttle/thruster controls drive the ship. UMG widget graphs (the
#   actual button/slider wiring) are not reliably buildable from Python in
#   this engine build -- so this script does the part Python CAN do safely:
#     1. Prints the exact navy theme palette (single source -- see
#        NAVY_THEME below; verify_20260701.py parity-checks these hex values
#        against Documents/NaviSense_BridgeDashboard_Recipe.md so the doc and
#        the script can never silently drift apart).
#     2. Attempts to create the WBP_BridgeDashboard WidgetBlueprint asset
#        stub under Content/NaviSense/UI/ (best-effort -- WidgetBlueprintFactory
#        availability varies by engine build; failure is non-fatal, the asset
#        can be created by hand in 30s via Content Browser > Add > User
#        Interface > Widget Blueprint if this doesn't work).
#     3. Prints the exact getter/setter names (from ANaviSenseShipPawn) the
#        widget should bind to, and the manual UMG steps -- see the Recipe doc
#        for the full walkthrough (this is a build HELPER, not a full builder).
#
# HOW TO USE
#   1. Tools > Execute Python Script > THIS FILE.
#   2. Open (or hand-create) WBP_BridgeDashboard, follow
#      Documents/NaviSense_BridgeDashboard_Recipe.md to lay out the four
#      panels + bind the getters + wire the helm/throttle/thruster widgets to
#      SetHelm/SetThrottle/SetBowThruster.
#   3. Add the widget to a HUD/PlayerController Event BeginPlay ("Create
#      Widget" -> "Add to Viewport"), toggle visibility on a key (Tab/B).
#   4. Rebuild C++ first (UMG/Slate/SlateCore just enabled in Build.cs) --
#      this script does not itself require the rebuild, but the widget's
#      getter/setter bindings will not resolve in the graph until it lands.
# =====================================================================
import unreal

TAG = "[NaviSense DASHBOARD 09]"
def log(m):  unreal.log(TAG + " " + str(m))
def warn(m): unreal.log_warning(TAG + " " + str(m))
def err(m):  unreal.log_error(TAG + " " + str(m))

# ---------------------------------------------------------------------
# Navy marine-bridge theme palette. SINGLE SOURCE with the recipe doc --
# verify_20260701.py extracts both copies and asserts they match, exactly
# like WP-20260628's wake-curve C++/Python parity gate.
# ---------------------------------------------------------------------
NAVY_THEME = {
    "background": "#0B1F33",   # full-screen dashboard backdrop
    "panel":      "#132A45",   # the four panel cards
    "accent_ok":     "#2ECC71",   # green  -- nominal / compliant / healthy
    "accent_caution": "#F5A623",  # amber  -- caution / degraded / stale
    "accent_alarm":  "#E74C3C",   # red    -- alarm / non-compliant / fault
    "text":       "#FFFFFF",   # primary text
}

WIDGET_PACKAGE_PATH = "/Game/NaviSense/UI"
WIDGET_ASSET_NAME = "WBP_BridgeDashboard"

# Dashboard getters/setters on ANaviSenseShipPawn the widget binds to, grouped
# by panel (mirrors Documents/NaviSense_BridgeDashboard_Recipe.md exactly).
PANEL_BINDINGS = {
    "Actuators":  ["GetRudderDeg", "GetPortRpm", "GetStarboardRpm", "GetBowThrusterNorm"],
    "Sensors":    ["GetHeadingDeg", "GetSpeedOverGroundMS", "GetYawRateDashDegPerSec",
                   "GetRollDeg", "GetPitchDeg", "GetHeaveM", "GetLatDeg", "GetLonDeg"],
    "Maneuver+IMO KPIs": ["GetMotionModeLabel", "GetPlantMode", "GetRollingAdvanceM",
                          "GetPeakHeadingDeviationDeg"],
    "SeaState+AIS/COLREGS": ["GetTrafficContactCount", "GetNearestTrafficRangeM",
                             "GetNearestTrafficName"],
}
CONTROL_ENTRY_POINTS = ["SetHelm(float)", "SetThrottle(float)", "SetBowThruster(float)",
                        "IsDashboardControlActive()"]


def _try_create_widget_bp():
    """Best-effort WidgetBlueprint asset stub. Non-fatal on any failure --
    this is a convenience, not the gate (the acceptance gate is headless
    data/control layer + Z0; the in-engine widget is Lemuel's G_DASHBOARD_UE)."""
    try:
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        existing = unreal.EditorAssetLibrary.does_asset_exist(
            WIDGET_PACKAGE_PATH + "/" + WIDGET_ASSET_NAME)
        if existing:
            log("%s already exists -- leaving it alone." % WIDGET_ASSET_NAME)
            return True
        factory = unreal.WidgetBlueprintFactory()
        try:
            factory.set_editor_property("parent_class", unreal.UserWidget)
        except Exception:
            pass
        new_asset = asset_tools.create_asset(
            WIDGET_ASSET_NAME, WIDGET_PACKAGE_PATH, unreal.WidgetBlueprint, factory)
        if new_asset:
            unreal.EditorAssetLibrary.save_loaded_asset(new_asset)
            log("created %s/%s (empty -- lay out the 4 panels by hand per the Recipe doc)."
                % (WIDGET_PACKAGE_PATH, WIDGET_ASSET_NAME))
            return True
        warn("create_asset returned None for %s -- create it by hand (Content Browser > "
             "Add > User Interface > Widget Blueprint)." % WIDGET_ASSET_NAME)
        return False
    except Exception as e:
        warn("WidgetBlueprintFactory unavailable this engine build (%s) -- create "
             "%s by hand (Content Browser > Add > User Interface > Widget Blueprint), "
             "parent class UserWidget." % (e, WIDGET_ASSET_NAME))
        return False


def main():
    log("Navy theme palette (single source -- must match the Recipe doc):")
    for k, v in NAVY_THEME.items():
        log("  %-16s %s" % (k, v))

    log("Attempting WBP_BridgeDashboard asset stub...")
    _try_create_widget_bp()

    log("Panel bindings (bind each UMG text/gauge to the matching getter):")
    for panel, getters in PANEL_BINDINGS.items():
        log("  [%s]" % panel)
        for g in getters:
            log("    - %s" % g)
    log("Control entry points (wire helm/throttle/thruster widgets to these):")
    for c in CONTROL_ENTRY_POINTS:
        log("    - %s" % c)

    log("DONE. Full manual UMG layout + binding + control-wiring steps: "
        "Documents/NaviSense_BridgeDashboard_Recipe.md")


main()
