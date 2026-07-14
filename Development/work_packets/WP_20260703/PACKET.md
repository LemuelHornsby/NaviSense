# WP-20260703 — Single-target COLREGS encounters + scripted own-ship avoidance

**Date:** 2026-07-03 · **Model:** Opus 4.8 · **Type:** pure-Python + editor-Python + docs.
**NO C++ / wire / DTO / schema change → no rebuild (Z0 stays 16/16).**

## Goal (Lemuel-directed, 3 Jul)
Replace the confusing 3-ships-at-once `monaco_capture` with a clean, intuitive COLREGS
setup: pick ONE encounter; a SINGLE target ship runs the scripted COLREGS scenario
relative to own-ship; own-ship runs its model; the run is scored for compliance.

## What was built
- **Scripted-avoidance own-ship** — `ColregsAvoidController` (`python/scenario_controllers.py`):
  a deterministic, closed-loop heading hold on the plant's authoritative yaw (invariant #5).
  Give-way encounters make an early, bounded **starboard** alteration (ramped setpoint,
  PD-damped) held through CPA, then resume; the stand-on encounter **holds** course/speed
  (Rule 17). Per-encounter tuning in the factory.
- **Four scenarios** (`python/scenarios.py`): `colregs_head_on` (Rule 14), `colregs_crossing_giveway`
  (Rule 15, target from starboard), `colregs_crossing_standon` (Rule 17, target from port),
  `colregs_overtaking` (Rule 13). Each uses a dedicated single-target `*_avoid` AIS preset
  (`python/ais_traffic.py`, new `head_on_avoid`/`crossing_avoid`/`overtaking_avoid`/`crossing_standon`)
  — kept SEPARATE from the transit presets so the existing scenarios + their verifies are unchanged.
- **Running start** — new `--initial-speed` listener flag + `Scenario.initial_speed_mps`; the stand-on
  scenario begins at cruise speed so "keep speed" (Rule 17) is measured on a steady vessel, not a
  0→cruise spin-up.
- **In-editor picker** — `Phase5_Systems/10_colregs_encounter.py`: hides the two unused Traffic
  ships, assigns the chosen one as `TrafficActors[0]`, launches the listener with the scenario.
  4-button Editor Utility Widget recipe in `Documents/NaviSense_COLREGS_Encounter_Recipe.md`.
- **Compliance** — the existing `python/colregs_score.py` + evidence pack score each run.

## Acceptance gates — `python python/verify_20260703.py` → **PASS 5/5 + 3/3**
G1 registry (4 scenarios → avoid controllers + single-target presets; stand-on running start) ·
G2 controller profiles (give-way alter starboard mid-run; stand-on holds 0 rudder) ·
**G3 end-to-end compliance** — all four scored the intended verdict on real `--selftest --plant mmg`
runs: head_on **COMPLIANT** (238 m), crossing give-way **COMPLIANT** (342 m, passed astern),
overtaking **COMPLIANT** (295 m), stand-on **COMPLIANT** (held course+speed, 152 m near-miss) ·
G4 picker (maps 4 encounters → scenario + 1 of 3 ships, hides others) · G5 regression
(Z0 16/16 · verify_20260702b / _701b / _629b green). Controls: N1 held-course head-on → NON_COMPLIANT;
N2 port (wrong-way) crossing → flagged; N3 stand-on early turn → NON_COMPLIANT.

## Lemuel's steps (≤5 min, no rebuild)
1. Ships already under the **Traffic** folder — no setup needed.
2. **Tools → Execute Python Script → `Phase5_Systems/10_colregs_encounter.py`** with `ENCOUNTER`
   set to `head_on` / `crossing_giveway` / `crossing_standon` / `overtaking` (or build the 4-button
   EUW from the recipe). It hides the other two ships + launches the listener.
3. Press **Play**. After the run, open `logs/<run>/evidence_pack/evidence_report.html` → COLREGS
   conformance verdict. In-engine confirm = **G_COLREGS_UE** (one ship moves, own-ship maneuvers,
   verdict shown).

## Honesty (KI-028)
Scripted, deterministic target + a pre-planned own-ship maneuver — demonstrates the encounter
geometry and the conformance METRIC, not autonomous COLREGS decision-making (W5-6 roadmap).

## Rollback
Pure-additive (new controller/presets/scenarios/flag/picker/verify). Revert the edits to
`scenario_controllers.py` / `scenarios.py` / `ais_traffic.py` / `python_listener.py` and delete the
new files. No C++, wire, or asset touched.
