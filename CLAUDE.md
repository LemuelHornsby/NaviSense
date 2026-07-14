# NaviSense UE5 — working agreement (read first)

**This folder is the canonical NaviSense Unreal workspace. All future additions and
modifications happen HERE.** The old `D:\Marine Autonomy\NAVISENSE` root (Unity project +
original python stack) is a **backup** — never depend on it or edit it.

## Canonical entry points
- Run listener: `python_listener.py` at THIS workspace root (full features; `-v`/`--verbose`).
- Plant/control code: `python/` (here, not the old root).
- MMG dynamics: `Maneuvering/maniobrabilidad/mmg/`.
- UE C++: `NaviSense_UE5/Source/NaviSense/`.
- `Development/bridge_harness/` is OFFLINE TEST tooling only — not the run listener.

## Invariants (do not violate)
1. Coordinate / yaw-sign conversions live ONLY in `Source/NaviSense/Core/NaviSenseCoords.h`.
2. The socket RX thread never touches UObjects (SPSC queue hand-off to the game thread).
3. Bridge DTO field names match the JSON wire keys exactly.
4. Vessel tuning via the `UNaviSenseVesselProfile` data asset (no recompiles to tune).
5. Scenario controllers are fed the plant's authoritative yaw (so they never stall on a
   missing sensor echo). Keep that behavior.

## Tooling gotcha (important)
The `D:` drive truncates file-tool (editor Edit/Write) writes mid-file — **any size, not just large
files** (17 Jun: even a 2.3 KB header was cut). Make **all** D: changes via the shell (heredoc / `cp` /
python), never the editor tool, then verify (line count + brace/parse). Do not trust a silent save.
Guard C++ with `verify_compile_readiness.py` `Z0` before claiming any packet green.

## Known follow-ups (tracked)
- ~~Port the WP-3 listener auto-reaccept into the canonical `python_listener.py`.~~ **DONE 19 Jun (WP-10, KI-017):** `run()` binds/listens once then re-accepts a fresh run each reconnect; `--once` keeps single-shot CI. Verified headless 5/5 (`verify_canonical_reaccept.py`).
- Commit `Content/` via Git LFS (first scoped commit intentionally excluded it).
- 6-DOF schema: heel/trim v1.2 (WP-7) + heave v1.3 (WP-8) DONE on the wire + pawn; remaining is
  sampling the *rendered* UE water surface so the hull rides the actual water mesh (F1 pt3, engine-side).

## Documentation Update Protocol (Definition of Done for docs)

**A change is not "done" until the docs it affects are updated in the same session.** Every Work Packet
and every fix must satisfy this. The daily session checks PROGRESS, Test Log, and Known Issues on every run.

Canonical living docs:
- `Documents/PROGRESS.md` — dev ledger + demo-gate (D1–D8) burndown + weekly metrics
- `Manual and Troubleshooting/04_Known_Issues_Register.md` — `KI-NNN` bug/limitation register
- `Manual and Troubleshooting/05_Test_Log.md` — test-run evidence log
- `Manual and Troubleshooting/01_Troubleshooting_Guide.md` — user-facing symptom→fix
- `Manual and Troubleshooting/00_Operations_Manual.md` — run book (commands/flags/controls)
- `Manual and Troubleshooting/03_QA_Test_Plan.md` — test catalog (`TC-NNN`) + gates
- Status banners atop `Documents/NaviSense_UE5_COMPONENT_GUIDE.md`, `NaviSense_UE5_Analytical_Review.md`, `NaviSense_UE5_Master_Execution_Plan.md`
- `Documents/PIPELINE.md` — GTM pipeline (Friday session)

When X happens → update Y:

| Event | Docs to update |
|---|---|
| Work packet completed (any code/script/config change) | `PROGRESS.md` ledger line (always) |
| …changed a run command / flag / controller / control | `00_Operations_Manual.md` (+ wire-contract note if protocol changed) |
| …changed config / deps / automation / engine-plugin | `02_Maintenance_Guide.md` |
| A test or `verify_*.py` was run | `05_Test_Log.md` row (date, build, TC-ID, PASS/FAIL, evidence, tester) |
| A bug/defect found | new `KI-NNN` in `04_Known_Issues_Register.md` (OPEN, severity, root cause) + `05_Test_Log` FAIL + (if user-facing) `01_Troubleshooting_Guide` entry |
| A bug fixed | `KI-NNN` → RESOLVED (date+fix) + `05_Test_Log` PASS + `PROGRESS.md` line |
| A demo gate (D1–D8) status changes | `PROGRESS.md` burndown + the affected doc's status banner (same day) |
| New feature / sensor / scenario | `00_Operations_Manual` + new `TC-NNN` in `03_QA_Test_Plan` + `KI` if it adds a limitation |
| Architecture / invariant / entry-point change | the affected doc's status banner + this `CLAUDE.md` |
| Release / demo | `Manual and Troubleshooting/Templates/release_checklist.md` + QA sign-off + git tag (BLOCKED until regression green) |

**Definition of Done:** a Work Packet is closed only when (1) its acceptance gates pass AND (2) every doc
this matrix points to for the change has been updated the same session. Update via the shell + verify
(the D: large-write caveat). New IDs are sequential: `KI-NNN`, `TC-NNN`.
