# =====================================================================
# NaviSense - Capture demo beauty stills (D6 screenshots / D7 film frames)
# =====================================================================
# Run from:  Tools > Execute Python Script...   (editor Python; KI-013: use a
#            SCRIPT, never the right-click menu)
#
# WHY
#   D6 wants >= 3 in-PIE beauty screenshots and D7 wants establishing frames.
#   Framing + firing HighResShot by hand for every shot is fiddly and easy to
#   forget. This fires a BURST of high-res HighResShot captures on a timer
#   (non-blocking - you keep flying the camera) and writes a capture_manifest.json
#   so the headless gate python/verify_capture_artifacts.py can confirm the shots
#   exist + are full-res, and that the run that produced them is healthy.
#
# HOW TO USE (demo capture, ~2 min)
#   1. Start a run + press Play:  python run_demo.py --scenario monaco_capture
#      (COLREGS traffic) or --scenario rough_turning_circle (SS5 seakeeping).
#   2. With PIE running, Tools > Execute Python Script > THIS FILE.
#   3. It captures SHOTS stills, INTERVAL_S apart, into the project Screenshots
#      dir. Re-frame the camera between shots for variety. Re-run for more.
#   4. Stop the run, then verify headless:
#        python python/verify_capture_artifacts.py --latest
#      (or pass --shots-dir / --run-dir explicitly; --since-epoch <started> uses
#       only this session's stills - the manifest records it).
#
# CONFIG (edit then re-run)
SHOTS = 3                     # stills to take this session (>= the D6 min of 3)
INTERVAL_S = 4.0              # seconds between shots (re-frame the camera between)
RESOLUTION = "3840x2160"      # HighResShot resolution (4K); "1920x1080" for 1080p
HIDE_UI = True               # hide the editor/debug UI in the shot (cleaner frame)
SCENARIO_HINT = ""           # optional label written to the manifest (e.g. monaco_capture)
# =====================================================================
import json
import time

import unreal

TAG = "[NaviSense CAPTURE 08]"
def log(m):  unreal.log(TAG + " " + str(m))
def warn(m): unreal.log_warning(TAG + " " + str(m))
def err(m):  unreal.log_error(TAG + " " + str(m))


def _world():
    """Prefer the PIE/game world (so HighResShot grabs the live run); fall back
    to the editor world so the script still works for static framing tests."""
    try:
        ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        w = ues.get_game_world() if ues else None
        if w:
            return w, "PIE"
    except Exception as e:
        warn("no game world (%s)" % e)
    try:
        return unreal.EditorLevelLibrary.get_editor_world(), "editor"
    except Exception:
        try:
            ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
            return (ues.get_editor_world() if ues else None), "editor"
        except Exception as e:
            err("no world available (%s)" % e)
            return None, "none"


def _shots_dir():
    try:
        d = unreal.Paths.screen_shot_dir()         # .../Saved/Screenshots/
        return unreal.Paths.convert_relative_path_to_full(d)
    except Exception:
        try:
            base = unreal.Paths.project_saved_dir()
            return unreal.Paths.convert_relative_path_to_full(base + "Screenshots/")
        except Exception:
            return "Saved/Screenshots/"


def _reports_dir():
    try:
        base = unreal.Paths.project_saved_dir()
        return unreal.Paths.convert_relative_path_to_full(base + "NaviSense_Reports/")
    except Exception:
        return "NaviSense_UE5/Saved/NaviSense_Reports/"


def _fire(world):
    if HIDE_UI:
        try:
            unreal.SystemLibrary.execute_console_command(world, "ShowFlag.Game 1")
        except Exception:
            pass
    # HighResShot <WxH> renders a high-resolution capture of the active viewport
    # to Saved/Screenshots/<Platform>/ (auto-incrementing HighresScreenshotNNNNN.png).
    unreal.SystemLibrary.execute_console_command(world, "HighResShot " + RESOLUTION)


def _write_manifest(started_epoch, sdir, world_kind, fired):
    path = _reports_dir().rstrip("/") + "/capture_manifest.json"
    session = {
        "started_epoch": started_epoch,
        "started_local": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(started_epoch)),
        "world": world_kind,
        "requested_shots": SHOTS,
        "interval_s": INTERVAL_S,
        "resolution": RESOLUTION,
        "shots_fired": fired,
        "scenario_hint": SCENARIO_HINT,
        "screenshots_dir": sdir,
        "verify_hint": ("python python/verify_capture_artifacts.py --latest "
                        "--since-epoch %d" % int(started_epoch)),
    }
    doc = {"tool": "08_capture_demo_stills", "sessions": []}
    try:
        with open(path, "r") as f:
            existing = json.load(f)
            if isinstance(existing, dict) and isinstance(existing.get("sessions"), list):
                doc = existing
    except Exception:
        pass
    doc["sessions"].append(session)
    doc["latest"] = session
    try:
        with open(path, "w") as f:
            json.dump(doc, f, indent=2)
        log("manifest -> %s" % path)
    except Exception as e:
        warn("could not write manifest (%s)" % e)
    return session


def main():
    world, kind = _world()
    if world is None:
        err("No world; aborting. Open a level (and press Play for a PIE capture).")
        return
    sdir = _shots_dir()
    started = time.time()
    log("Capturing %d shot(s) @ %s, %.1fs apart, into %s (world=%s)."
        % (SHOTS, RESOLUTION, INTERVAL_S, sdir, kind))
    if kind != "PIE":
        warn("No PIE world found - capturing the EDITOR viewport. For the demo "
             "stills, press Play first, then re-run.")

    # Fire shot 0 now; schedule the rest on the slate post-tick (non-blocking, so
    # you can re-frame the camera between captures).
    state = {"fired": 0, "next_due": started}
    _fire(world); state["fired"] = 1; state["next_due"] = started + INTERVAL_S
    log("  shot 1/%d fired." % SHOTS)

    if SHOTS <= 1:
        _write_manifest(started, sdir, kind, state["fired"])
        log("DONE. Verify: python python/verify_capture_artifacts.py --latest "
            "--since-epoch %d" % int(started))
        return

    handle = {"h": None}

    def _tick(delta_seconds):
        if state["fired"] >= SHOTS:
            if handle["h"] is not None:
                try:
                    unreal.unregister_slate_post_tick_callback(handle["h"])
                except Exception:
                    pass
                handle["h"] = None
            _write_manifest(started, sdir, kind, state["fired"])
            log("DONE. %d shot(s) in %s. Verify: python "
                "python/verify_capture_artifacts.py --latest --since-epoch %d"
                % (state["fired"], sdir, int(started)))
            return
        if time.time() >= state["next_due"]:
            _fire(world)
            state["fired"] += 1
            state["next_due"] = time.time() + INTERVAL_S
            log("  shot %d/%d fired." % (state["fired"], SHOTS))

    try:
        handle["h"] = unreal.register_slate_post_tick_callback(_tick)
        log("Scheduled %d more shot(s) on the editor tick - keep PIE running + "
            "re-frame between captures." % (SHOTS - 1))
    except Exception as e:
        # No slate callback available: fire the rest immediately (same frame-ish).
        warn("slate post-tick unavailable (%s); firing remaining shots now." % e)
        while state["fired"] < SHOTS:
            _fire(world); state["fired"] += 1
            log("  shot %d/%d fired (immediate)." % (state["fired"], SHOTS))
        _write_manifest(started, sdir, kind, state["fired"])
        log("DONE (immediate). Verify: python python/verify_capture_artifacts.py "
            "--latest --since-epoch %d" % int(started))


main()
