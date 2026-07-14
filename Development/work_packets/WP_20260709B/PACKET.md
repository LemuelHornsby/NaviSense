# WP-20260709B — rescue-boat default target + independently verifiable COLREGS (T-2)

**Directive (Lemuel):** all COLREGS scenarios default to the **marine_rescue_boat**
(the one ship that imported world-aligned — no roll correction), each scenario
independently runnable + independently verifiable, chosen at run time, with an
easy per-run ship swap. Goal: solid and complete — never revisit.

## Design — one source of truth, one flow
The target ship is decided in ONE place and flows everywhere automatically:

  picker `TARGET_SHIP` (or `pick(enc, ship=...)`) → assigns the actor as
  `TrafficActors[0]` → passes `--target-name <label>` to the listener →
  `make_field()` renames the preset target (+ known ship type) → wire /
  `sensor_raw.jsonl` / evidence all carry the real name → manifest records
  `aisTargetName` → `verify_colregs` checks against it.

Default (no action needed): `marine_rescue_boat` everywhere.

## Changed files
- `python/ais_traffic.py` — the four colregs presets all name
  `DEFAULT_COLREGS_TARGET = "marine_rescue_boat"` (type `rescue`); new
  `make_field(..., target_name=)` override (single-target presets only —
  multi-target raises `ValueError`); `SHIP_TYPES` label→type table.
- `python_listener.py` — new `--target-name LABEL` flag → `make_field` +
  manifest.
- `python/run_logger.py` — manifest gains `aisTargetName` (only when swapped).
- `run_demo.py` — `--target-name` passthrough (headless swap testing).
- `Phase5_Systems/10_colregs_encounter.py` — **refactored**: `TARGET_SHIP`
  single default for ALL encounters; `ENCOUNTERS` maps encounter→scenario only;
  `pick(encounter, ship=None)` per-run override; the printed/launched listener
  command always includes `--target-name <actual actor label>`; new
  **`reset_all()`** un-hides all Traffic ships + clears `TrafficActors` so
  3-ship scenarios (monaco_capture) work again after a picker session.
- `python/verify_colregs.py` — **new, the independent-verification tool**:
  `--latest`/`--run-dir` reads the run's OWN manifest (scenario/preset/
  aisTargetName), gates V1 health + V2 verdict (1 compliant / 0 non-compliant)
  + V3 target identity (cross-checks `sensor_raw.jsonl` wire names on real PIE
  runs); writes ONE result file PER SCENARIO
  (`Saved/NaviSense_Reports/colregs_<scenario>_result.json`); `--matrix` rolls
  the four up into `colregs_matrix_result.json`.
- `python/verify_20260709.py` — G2/G4 revised to the single-default model
  (re-PASS 5/5+3/3).

## Acceptance — `python/verify_20260709b.py` **5/5 + 3/3 PASS** (9 Jul)
G1 default-target · G2 swap-path (rename + picker/listener/manifest plumbing) ·
G3 independent-verify (**4 per-scenario PASS files from 4 distinct headless
runs + matrix PASS 4/4**) · G4 swap-e2e (`--target-name Yacht_with_interior`
recorded in the manifest, verified end-to-end) · G5 regression. Neg: fictional
default caught · multi-target rename rejected · non-colregs run rejected.
Headless matrix evidence (all four ran fresh today, MMG plant, COMPLIANT):
head_on 051539 · crossing_giveway 055053 · crossing_standon 055117 ·
overtaking 055140.

## Lemuel — in-editor procedure (per scenario, ~5 min each)
0. Once: recompile if not yet done today (**Ctrl+Alt+F11** — KI-034 fix).
1. **Choose scenario**: Tools → Execute Python Script →
   `Phase5_Systems/10_colregs_encounter.py` with `ENCOUNTER = "head_on"` (or
   `crossing_giveway` / `crossing_standon` / `overtaking`). The rescue boat is
   picked automatically; the other two ships are hidden; the listener launches
   (or the exact command is printed).
2. Press **Play**. Watch the rescue boat run the encounter; own-ship alters
   starboard (or holds, stand-on).
3. Stop. **Verify independently**: `python python/verify_colregs.py --latest`
   → PASS 3/3 writes that scenario's own result file.
4. After all four: `python python/verify_colregs.py --matrix` → **PASS 4/4** =
   G_COLREGS_UE evidence complete.
- **Swap ship for a run**: edit `TARGET_SHIP` at the top of the picker, or in
  the editor Python console: `pick("head_on", ship="Yacht_with_interior")`.
  Nothing else to change — names/logs/verify follow automatically.
- **Back to 3-ship scenes** (monaco_capture beauty runs): run `reset_all()`
  from the picker (Execute Python Script with the last line changed to
  `reset_all()`, or call it from the console).

## Rollback
Revert the six files above; per-scenario result files are inert artifacts.
