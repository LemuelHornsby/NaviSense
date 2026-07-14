# WP-20260621 — Runtime sea-state schedule (D3) + named-scenario registry (D6)

**Theme:** let a single continuous run sweep through ≥3 sea states (calm→rough),
recorded in the run log — the "switch at runtime" half of demo gate **D3** — and
name the controller + sea-state combinations so a demo is one `--scenario <name>`
flag — the "scenario selection" half of **D6**.

**Kind:** pure-Python. Rides the EXISTING `heaveM` / `rollDeg` / `pitchDeg` wire
keys. **NO C++, NO DTO / wire / schema change, NO recompile, NO new in-engine
gate.** Same low-risk additive pattern as WP-9 / WP-10 / WP-20260620.

## Why today
- The live blocker (**KI-018** yaw-spin) is fixed-and-authored and waits ONLY on
  Lemuel's recompile + `turning_circle` rerun — nothing the sandbox can clear.
- So this advances the next demo gates that ARE sandbox-completable: **D3** (its
  runtime-switch half was the last ☐ piece — sea-state *logging* already landed in
  WP-9) and **D6** (scenario selection — the evidence-pack generator already landed
  in WP-20260620).
- The runtime sea-state build is also strong **D7** (demo reel) material: the sea
  visibly grows during one unbroken take, no relaunch.

## New files
- `python/sea_state.py` (+ `ScheduledSeaState` / `parse_schedule` /
  `make_scheduled_sea_state`): a time-varying sea state built by CROSS-FADING one
  deterministic `WaveField` per distinct sea-state value in the schedule.
  CONTINUOUS in time (no jump → no vertical jitter, satisfies the G_UE8 "smooth"
  eye-check), EXACT at each set-point, deterministic/replayable (every component
  field seeded ONCE; cross-fade weight is a pure function of sim time, so it
  composes with WP-4's deterministic clock). Duck-types `WaveField`, so
  `build_state_packet` / `wave_response` sample it with no other change.
- `python/scenarios.py` (new): a registry of named demo scenarios bundling
  controller + (fixed or scheduled) sea state + wave heading + description.
  `get_scenario` / `list_scenarios` / `format_scenarios`.
- `Development/work_packets/WP_20260621/verify_20260621.py`: 10-gate auto-verify
  with negative controls.

## Changed files (additive, defaulted — zero behaviour change when the flags are unused)
- `python_listener.py`: `--sea-state-schedule "t:ss, …"` (overrides `--sea-state`)
  and `--scenario <name>` (`--scenario list` prints the registry; explicit flags
  still win). When scheduled, attaches a `ScheduledSeaState` instead of a fixed
  `WaveField`, and logs each integer sea-state crossing to `events.csv`.
- `python/run_logger.py`: records `seaStateSchedule` + `scenario` in `manifest.json`
  (conditional keys; absent ⇒ byte-identical manifests; `runs.csv`/`state.csv`
  headers unchanged).
- `python/build_evidence_pack.py`: surfaces the scenario + schedule in `kpis.json`
  meta and `EVIDENCE.md` (read-side only).

## Invariants (CLAUDE.md) — respected
No sign/coordinate change (#1 — signs still single-sourced in `NaviSenseCoords.h`);
no wire key added (#3); controllers still fed plant yaw (#5). The schedule only
makes the sea-state VALUE a function of sim time; the field math and the wire shape
are unchanged. All D: writes via the shell + verified (KI-004).

## Auto gates — ALL GREEN (sandbox, headless): `verify_20260621.py` **10/10**
- **V1** parse rejects 7/7 malformed schedules *(neg. control)*.
- **V2** cross-faded elevation == pure `WaveField` at every set-point *(exactness)*.
- **V3** cross-fade boundary jump **0.0005 m** vs a naive hard-switch **0.218 m**
  *(neg. control: continuity)*.
- **V4** same seed identical / different seed differs *(deterministic + seeded)*.
- **V5** building schedule RMS up 0.16→1.10, easing schedule down 1.07→0.19
  *(neg. control: tracks schedule DIRECTION, not "always grows")*.
- **V6** SS0-only schedule `active=False`, elevation/slope == 0 *(calm back-compat)*.
- **V7** scenario registry valid (7 scenarios, controllers known, unknown rejected).
- **V8** END-TO-END headless listener `--scenario building_sea_transit`: heave grows
  0.07 < 0.49 < 0.77, manifest records schedule + scenario, **6 sea states logged**
  to `events.csv` (D3 ≥3).
- **V9** evidence pack surfaces scenario + schedule, health **PASS**, `state.csv`
  byte-identical *(read-only)*.
- **V10** scheduled `turning_circle` → IMO turning KPIs (advance / tactical
  diameter) **+** schedule line in `EVIDENCE.md` (D6).

**Regression on current disk (unchanged):** WP-20260620 **8/8**, compile-readiness
`Z0` **16/16**, schema-v13 **12/12**, WP-9 **9/9**, canonical re-accept **5/5**,
pytest plant/contract **10/10**.

## Generated artifact (sample, committed)
- `logs/wp21_schedule_demo/wp21smoke_*/` — a real headless `building_sea_transit`
  run: `events.csv` logs SS1→SS6, `manifest.json` records the schedule, and
  `evidence_pack/EVIDENCE.md` shows the scenario + schedule + health (**7/7**).

## Lemuel — in-editor / terminal steps (≤10 min; **NO recompile required by this packet**)
These ride the same pawn that already consumes heave/roll/pitch, so they fold into
the SAME pending Session-A recompile (KI-018) — no extra build.
1. List the menu: `python python_listener.py --scenario list`
2. **D3 runtime build** (one continuous PIE run, then watch the hull):
   ```
   cd "D:\Marine Autonomy\NAVISENSE\NaviSense Simulator with Unreal Engine"
   python python_listener.py --target unreal --scenario building_sea_transit -v
   ```
   Press **Play**; over ~3 min the swell builds SS1→SS6 — hull heave/roll grow
   smoothly with NO relaunch and NO jitter at the transitions.
3. **D6 one-command scenario + evidence**:
   ```
   python python_listener.py --target unreal --scenario imo_turning_circle -v
   # after the run:
   python python\build_evidence_pack.py
   ```

## Human acceptance gate (advances D3 + D6; no recompile)
- **D3:** the `building_sea_transit` PIE run shows the hull's vertical bob + beam
  roll GROW as the sea builds, smoothly across the SS transitions, in one take;
  the run log's `events.csv` lists ≥3 `sea_state_change` rows. *(Headless half
  already PASS — V8.)*
- **D6:** `--scenario imo_turning_circle` then `build_evidence_pack.py` yields an
  `EVIDENCE.md` naming the scenario alongside the IMO turning KPIs. *(Headless half
  PASS — V9/V10.)*

> Tell Claude: **"WP-20260621: building_sea_transit hull builds smoothly y/n; ≥3 sea_state_change rows y/n; scenario evidence pack built y/n."**

## Rollback
Pre-edit copies of the 3 modified files are in
`Development/work_packets/WP_20260621/rollback_originals/*.wp21bak`. To revert:
restore those three, delete the appended `ScheduledSeaState` block in
`python/sea_state.py` (everything below the "rev 1.5" banner), and delete
`python/scenarios.py` + this packet dir + any `logs/*/evidence_pack/`. Pure-additive
otherwise.

## Docs updated this session (Documentation Update Protocol)
PROGRESS.md ledger + D3/D6 burndown; 05_Test_Log (TC-19/TC-20 + regression rows);
03_QA_Test_Plan (TC-19 schedule, TC-20 scenario; D3/D6 gate rows); 00_Operations_Manual
(`--sea-state-schedule` / `--scenario` + recipes); 04_Known_Issues_Register (KI-008
rev 1.5 note + last-updated); status banners (Master Execution Plan, Component Guide).
