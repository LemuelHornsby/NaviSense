# WP-20260620 — Run-log health gate + D6 IMO-KPI evidence pack

**Theme:** turn subjective "watch the run" eye-checks into an objective, reusable
machine gate, and stand up the **D6 evidence pack** (consolidated IMO maneuvering
KPIs) so every demo run produces a demo-ready bundle.

**Kind:** pure-Python, **read-only over `logs/`**. NO C++, NO DTO/wire change,
**NO recompile, NO new in-engine gate.** Same low-risk pattern as WP-9/WP-10.

## Why today
- The live blocker (**KI-018** yaw-spin) is fixed-and-authored, waiting on Lemuel's
  recompile + `turning_circle` rerun. The logged **plant** is healthy — the spin is
  *pawn-side visual smoothing* — so its close-out stays an in-engine eye-check. This
  packet adds the **log-side corroboration** (K5/K7) and the tooling that will turn
  the post-fix rerun into the **D1 sign-confirm** + **D6** artifacts automatically.
- D6 (scenario + evidence pack) was un-started (☐). The IMO KPIs it produces are
  exactly what the GTM messaging is now allowed to claim ("MMG standard method
  producing IMO KPIs now" — see KI-019 guardrail).

## New files
- `python/verify_run_kinematics.py` — objective kinematic-health / acceptance gate
  over `logs/<run>/state.csv`. Checks **K1** time monotonic, **K2** finite,
  **K3** yaw-rate bounded, **K4** speed bounded, **K5** not-spinning-on-spot
  (effective turn radius = path / cumulative heading), **K6** heading monotonic
  (turning_circle only), **K7** wire-yaw continuity through the ±180° KI-018
  trigger zone, **K8** actuator tracking. Emits a JSON verdict + a `ki018_corroboration`
  block. Exit 0/1 so it can gate the nightly.
- `python/build_evidence_pack.py` — orchestrates the existing analysers
  (`analyse_turning_circle`, `analyse_zigzag`, `analyse_actuators`) + the health
  gate into `logs/<run>/evidence_pack/`: `kpis.json` (machine), `EVIDENCE.md`
  (demo), and the trajectory/heading/actuator PNGs. Auto-selects turning-circle vs
  zig-zag KPIs by controller. Read-only over the source log.
- `Development/work_packets/WP_20260620/verify_20260620.py` — the auto-verify
  harness (synthetic good/spin/NaN/oscillation fixtures + real-log + pack gates).

## Generated artifact (sample, committed)
- `logs/unreal-test-run_20260618_201335/evidence_pack/` — built from the 18-Jun
  turning_circle run: health **8/8 PASS**; **Advance 155.3 m (A/Lpp 4.09, IMO PASS)**,
  **Tactical diameter 158.2 m (DT/Lpp 4.16, IMO PASS)**; trajectory + actuator plots.
  *(This is a pre-fix run — visual spin present in-engine — so it demonstrates the
  tooling; the definitive D1/D6 pack comes from Lemuel's post-recompile rerun.)*

## Auto gates — ALL GREEN (sandbox, headless)
`python3 Development/work_packets/WP_20260620/verify_20260620.py` → **8/8**:
- **V1** real 18-Jun log → 8/8 health PASS; KI-018 log-side: entered-180°-zone=True,
  plant continuous=True, effective radius **89.3 m** (translating, not pirouetting).
- **V2** clean synthetic turn → PASS.
- **V3** pirouette (heading sweeps, position frozen) → **K5 FAIL** (spin caught).
- **V4** NaN + per-tick heading jump → **K2 & K3 FAIL** (finite/bounded caught).
- **V5** wobbling "turning_circle" → **K6 FAIL** (oscillation caught).
- **V6** pack on real log → turning-circle IMO KPIs + health verdict + EVIDENCE.md.
- **V7** pack on synthetic zig-zag → overshoots ≈3° + IMO 1st/2nd verdicts.
- **V8** pack build leaves `state.csv` byte-identical (read-only proof).

**Regression on current disk (unchanged):** compile-readiness `Z0` **16/16**,
schema-v13 **12/12**, WP-9 **9/9**, canonical re-accept **5/5**, pytest plant/contract **10/10**.

## Lemuel — in-editor / terminal steps (≤20 min, after the pending recompile)
1. **Recompile** (Ctrl+Alt+F11) — already required for the KI-018 fix.
2. Start the listener + **Play**, run `turning_circle` to completion past 180°
   (the existing G7/G_UE7 Session-A gate). Stop.
3. Terminal (closes the loop into D1 + D6):
   ```
   cd "D:\Marine Autonomy\NAVISENSE\NaviSense Simulator with Unreal Engine"
   python python\verify_run_kinematics.py                 # pre-flight: expect 8/8 PASS, K6 PASS
   python python\build_evidence_pack.py                   # writes logs\<run>\evidence_pack\
   ```
4. (Optional) run `zigzag10`, then `python python\build_evidence_pack.py` again.

## Human acceptance gate (closes D1 sign-confirm; advances D6)
On the **post-recompile** turning_circle run: `verify_run_kinematics.py` reports
**K6 PASS** (heading turns one way, no spin) AND the in-engine view shows a steady
continuous circle past 180° (the KI-018 eye-check). The evidence pack's
`EVIDENCE.md` then is the D1/D6 artifact (IMO turning KPIs + health verdict).

> Tell Claude: **"WP-20260620: post-fix turning_circle health = N/8, K6 pass/fail; pack built y/n."**

## Rollback
Pure-additive — no existing file was modified. To revert: delete
`python/verify_run_kinematics.py`, `python/build_evidence_pack.py`,
`Development/work_packets/WP_20260620/`, and any `logs/<run>/evidence_pack/` dirs.

## Docs updated this session (Documentation Update Protocol)
PROGRESS.md ledger + D6 burndown; 05_Test_Log (TC-17/TC-18 sandbox rows);
03_QA_Test_Plan (TC-17 health gate, TC-18 evidence pack); 00_Operations_Manual
(two new analysis commands); 04_Known_Issues_Register (KI-018 log-side
corroboration note — stays IN PROGRESS until the in-engine rerun).
