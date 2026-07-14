# WP-20260709 — single-ship COLREGS with the REAL vessels (T-2)

**Trigger (Lemuel, 8 Jul in-engine run `unreal-test-run_20260708_195058`):**
ships move; `verify_sensor_suite --latest` **PASS 4/4** on the real wire (⇒
**G_AIS_SENSOR_UE / G_RADAR_UE / G_CAMERA_UE CONFIRMED**). But (1) AIS names were
fictional (MERIDIAN/AZURFERRY/SLOWBELLE) not his ships, (2) the two roll-corrected
meshes (`excursion_vessel`, `Yacht_with_interior`) rendered sideways — a black
"fin" — because `ApplyTraffic` hard-set `FRotator(0, yaw, 0)` every packet,
(3) the run didn't depict COLREGS — it was `monaco_capture` (transit/beauty) on
the **stub** plant, not the four single-ship `colregs_*` scenarios.

## Analysis of the 8-Jul run
`monaco_capture`, plant=**stub**, controller=**transit**, 238 s, health gates
6/6 PASS, 386 raw sensor envelopes, 3 mmsi. Own-ship never maneuvers in this
scenario by design ⇒ no COLREGS behavior to see. The COLREGS path is the four
`colregs_*` scenarios (WP-20260703), one ship at a time via the editor picker.

## Changed files
- `NaviSense_UE5/Source/NaviSense/Vessel/NaviSenseShipPawn.h/.cpp` — **KI-034 fix**:
  `TrafficPlacedRot` captures each traffic actor's PLACED pitch/roll once (first
  apply); `ApplyTraffic` composes `FRotator(placedPitch, wireYaw, placedRoll)` —
  yaw-only drive, the mesh-import roll correction survives. **Needs ONE recompile
  (Live Coding OK).** Z0 16/16 + stacked link audit 5/5 re-verified.
- `python/ais_traffic.py` — rendered presets renamed to the EXACT Outliner labels,
  matched to the slot each preset drives: `head_on_avoid`→`Yacht_with_interior`,
  `crossing_avoid`/`overtaking_avoid`→`excursion_vessel`, `crossing_standon`→
  `marine_rescue_boat`; `monaco_capture` slots = tag-scan order (`excursion_vessel`,
  `marine_rescue_boat`, `Yacht_with_interior`). Naming rule documented; legacy
  analysis-only presets keep fictional names.
- `python/scenarios.py` + `python_listener.py` — a scenario can now REQUIRE a
  plant; the four `colregs_*` carry `plant="mmg"` and the listener resolves it
  when `--plant` is left at default (kills the 28-Jun stub footgun). Explicit
  `--plant` still wins.
- `python/verify_20260629b.py` — follows the rename (5/5+3/3 re-run PASS).
- `Documents/NaviSense_COLREGS_Encounter_Recipe.md` + `PENDING_EDITOR_GATES.md`
  — updated (Step 0 re-opened for the ONE recompile; sensor gates marked
  CONFIRMED; G_TRAFFIC_UE ◐ pending the orientation re-check).

## Acceptance gates — `python/verify_20260709.py` **5/5 + 3/3 PASS** (9 Jul)
G1 cpp-fix (+Z0 16/16) · G2 real-names (4 encounters + monaco slots == picker
labels) · G3 scenario-plant · G4 e2e headless `colregs_head_on` **COMPLIANT**
(`Yacht_with_interior`, give-way, +29° starboard, 238 m miss, health 7/7) ·
G5 regression (verify_20260629b + link audit). Neg: pre-fix rotation caught ·
fictional name caught · unverifiable run caught.

## Lemuel's steps (~15 min total)
1. **Recompile once:** editor open → **Ctrl+Alt+F11** (Live Coding). (Full Build
   if anything looks stale.)
2. Per encounter (repeat ×4): **Tools → Execute Python Script →
   `Phase5_Systems/10_colregs_encounter.py`** with `ENCOUNTER` = `head_on` /
   `crossing_giveway` / `crossing_standon` / `overtaking` → it hides the other
   two ships + prints/launches the listener command → **Play**. Watch: ONE ship,
   upright (KI-034 check), own-ship alters starboard (or holds, stand-on).
3. After each run: `python python/colregs_score.py --run-dir logs/<run> --ais <preset>`
   (or open the evidence report). Expect **COMPLIANT**.
4. Optional: `python python/verify_sensor_suite.py --latest` — AIS names now show
   your real ships.

## Rollback
Revert `NaviSenseShipPawn.h/.cpp` (restores the yaw-only hard-set), and the
renames in `ais_traffic.py`/`verify_20260629b.py`, `plant=` additions in
`scenarios.py`/`python_listener.py`. All changes are additive/localized.
