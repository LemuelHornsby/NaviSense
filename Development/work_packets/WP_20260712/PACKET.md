# WP_20260712 — T+1 slip management: the demo session is now the ONLY item (12 Jul 2026, Sunday)

## Goal
The 11 Jul demo-day target **passed without the live session running** (checked, not assumed:
no PIE run since `unreal-test-run_20260708_195058`, film dir still 0 stills / 0 clips,
Step-0 KI-034 Live Coding recompile still pending). Nothing product-side regressed —
this packet re-proves the whole baseline is STILL green today and re-frames the plan:
**no new code lands until the ONE live session happens.** The 11 Jul run card is
unchanged and remains valid; only its date slipped.

## What this session did (headless, no product change)
- Re-ran the TC-50 baseline gate `python/verify_20260711.py` **on 12 Jul**:
  **PASS 5/5 gates + 3/3 negative controls** (Z0 16/16, stacked link audit, preflight GO,
  run-sheet current, pytest 10/10). Evidence: `Saved/NaviSense_Reports/wp_20260712_result.json`.
  - Session note: first invocation FAILED G5 because the fresh sandbox lacked `pytest`
    (environment, not repo). `pip install pytest` → 10/10 → full PASS. No KI: not a product
    or tooling defect; the gate correctly refused to pass with an unrunnable suite.
- Added a dated slip banner to `PENDING_EDITOR_GATES.md` (all G4 anti-drift markers kept).
- PROGRESS burndown + ledger, Test Log row per the Documentation Update Protocol.

## Changed files
- `Development/work_packets/WP_20260712/PACKET.md` (this file, new)
- `NaviSense_UE5/Saved/NaviSense_Reports/wp_20260712_result.json` (new, evidence)
- `Development/work_packets/PENDING_EDITOR_GATES.md` (slip banner only)
- `Documents/PROGRESS.md`, `Manual and Troubleshooting/05_Test_Log.md` (protocol updates)

## Lemuel's steps (unchanged from the 11 Jul run card — ~45–60 min, first free slot)
Run the ONE live session per `WP_20260711/PACKET.md` / `PENDING_EDITOR_GATES.md`:
1. **Step 0** — Live Coding recompile (Ctrl+Alt+F11) for the KI-034 traffic roll fix.
2. **Step 1** — PIE with `python python_listener.py --target unreal --scenario monaco_capture -v`
   → eye-check G_TRAFFIC_UE orientation, D2 SS5 wave-ride, G_HYDRO/G_PROP.
3. **Step 3** — screen-record the PIE run + stills → `verify_capture_artifacts --film-dir` (D7).
4. **Step 5** — `python run_colregs.py --head-on` (and the other encounters as time allows).
5. **Step 6** — `python python/verify_demo_session.py` → ONE command closes out the session.

## Acceptance gates
- **G1 (done this session):** `verify_20260711.py` PASS 5/5 + 3/3 on 12 Jul → `wp_20260712_result.json`. ✅
- **G2 (Lemuel, live):** `verify_demo_session.py` PASS after the live session → closes D2/D4/D6/D7.

## Rollback
Nothing to roll back — no product code changed. Revert the PENDING_EDITOR_GATES.md banner
line if it ever conflicts with a future refresh.
