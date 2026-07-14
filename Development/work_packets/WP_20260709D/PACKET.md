# WP-20260709D — ONE-command demo-session closeout (T-2)

**Goal:** the 11 Jul live PIE/capture session ends with a single terminal command
instead of four. `python/verify_demo_session.py` (NEW) runs the three existing
gated tools as subprocesses — `verify_sensor_suite --latest` (G_AIS/G_RADAR/
G_CAMERA, D4), `verify_capture_artifacts --latest [--film-dir]` (G_CAPTURE_UE
D6 + G_FILM_UE D7), `verify_colregs --matrix` (G_COLREGS_UE) — and rolls them
into `Saved/NaviSense_Reports/demo_session_result.json` with `gates_closed` /
`gates_failed` and the two remaining EYE-CHECKS listed honestly (G_TRAFFIC_UE
orientation post-KI-034 + D2 SS5 wave-ride). Exit 0 iff every non-skipped
section passes; a sub-tool FAIL can never be masked.

Also refreshed `PENDING_EDITOR_GATES.md`: the G_TRAFFIC_UE row still told you to
look for SLOWBELLE/AZURFERRY/MERIDIAN — fictional names removed 9 Jul (KI-035);
now names the real Outliner labels, and NEW Step 5 (COLREGS live matrix via
`run_colregs.py`) + Step 6 (this closeout) are folded into the ONE-session plan.

## Changed files
- `python/verify_demo_session.py` — NEW (131 lines, stdlib only)
- `python/verify_20260709d.py` — NEW acceptance gates
- `Development/work_packets/PENDING_EDITOR_GATES.md` — stale names fixed; Steps 5+6 added

## Acceptance — `python python/verify_20260709d.py` **4/4 + 3/3 PASS** (9 Jul)
G1 tool-parses (compile + --help documents sections/flags) ·
G2 partial-pass (`--skip sensors,capture` → rc 0, colregs PASS, skips recorded) ·
G3 fail-propagates (empty tmp `--film-dir` → rc 1, G_FILM_UE+G_CAPTURE_UE in
`gates_failed`) · G4 regression (verify_20260709c rc 0).
Neg: all-skip rejected rc 2 · unknown skip token rejected rc 2 ·
nonexistent film dir rejected rc 2.
Evidence: `Saved/NaviSense_Reports/wp_20260709d_result.json`.

## Lemuel — nothing new to do before the session (0 min today)
This packet only changes how the live session ENDS. The session plan is
`PENDING_EDITOR_GATES.md` Steps 0–6; the last command of the day is now:
```
cd "D:\Marine Autonomy\NAVISENSE\NaviSense Simulator with Unreal Engine"
python python/verify_demo_session.py --film-dir "%USERPROFILE%\Videos\Captures"
```
SESSION PASS ⇒ D4 evidence + D6 stills + D7 film + COLREGS matrix all on disk.

## Rollback
Delete `python/verify_demo_session.py` + `python/verify_20260709d.py`; restore
the previous `PENDING_EDITOR_GATES.md` from git.
