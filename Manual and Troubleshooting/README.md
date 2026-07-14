# NaviSense — Manual, Troubleshooting & QA

Owner: Lemuel · NaviSyn Marine Solutions · Engine: Unreal Engine 5.7
Purpose: the single place that documents **how to run, maintain, test, and quality-assure** the
NaviSense Simulator, and how to track development as it matures toward the flagship release.

This folder complements (does not replace):
- `../Documents/PROGRESS.md` — the per-day development ledger and demo-gate burndown.
- `../CLAUDE.md` — the engineering working agreement and invariants.
- `../Documents/NaviSense_UE5_Master_Execution_Plan.md` — the build roadmap (gates D1–D8).

## Contents

| File | Use it when you want to… |
|---|---|
| `00_Operations_Manual.md` | Install, run the closed loop, pick a controller, read the HUD/logs. The day-to-day run book. |
| `01_Troubleshooting_Guide.md` | Something failed or behaves wrong — find symptom → cause → fix. |
| `02_Maintenance_Guide.md` | Keep the project healthy: backups/git, dependencies, logs/caches, automation, doc upkeep. |
| `03_QA_Test_Plan.md` | Verify a build is correct before a demo/release — test catalog, acceptance gates, sign-off. |
| `04_Known_Issues_Register.md` | Check/record a known bug or limitation (KI-IDs), status, root cause, workaround. |
| `05_Test_Log.md` | Record every QA/test run (the running QA evidence trail). |
| `Templates/` | Reusable templates: bug report, test case, QA sign-off, release checklist. |

## How this folder is used in the dev loop

1. **Build** a Work Packet (daily). 2. **Run** it using `00_Operations_Manual`.
3. If it breaks, consult `01_Troubleshooting`; if it's new, log it in `04_Known_Issues`.
4. **Test** against `03_QA_Test_Plan`; record the run in `05_Test_Log`.
5. Before any demo/release, complete `Templates/release_checklist.md`.

## Document conventions

- **Status tags:** `OPEN` · `IN PROGRESS` · `RESOLVED` · `WONTFIX` · `MONITOR`.
- **Severity:** `S1 Blocker` (no demo possible) · `S2 Major` (core feature broken) · `S3 Minor` (workaround exists) · `S4 Cosmetic`.
- **IDs:** Known issues `KI-NNN`; test cases `TC-NNN`; demo gates `D1`–`D8` (Master Execution Plan).
- **Dates:** ISO-ish, day-month-year. Always date entries.
- Keep these docs in Markdown (living, diff-able). Export to PDF only for external sharing.

*Maintained alongside the codebase. Last reviewed: 14 June 2026.*
