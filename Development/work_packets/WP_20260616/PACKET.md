# WP-5 · 2026-06-16 · In-engine Tests + Nightly Automation Skeleton (F7, §6)

> **Pre-authored 2026-06-14** during the autonomous multi-packet run. Planned date 16 Jun.

**Theme:** Stand up the verification machine — C++ Automation tests for the coordinate/sign invariants, a pinned Python wire-contract + plant test suite, and a 02:00 nightly pipeline (tests → render → summary).
**D-gate:** the automation backbone behind every later D-gate (regression safety, evidence inputs).
**Estimated human time:** ≤15 minutes (one engine-path edit + run the nightly once).

---

## What was written

| File | Purpose |
|------|---------|
| `Source/NaviSense/Tests/NaviSenseCoordsTests.cpp` | C++ Automation tests `NaviSense.Coords.RoundTrip` + `NaviSense.Coords.YawSign` — lock the axis map, m↔cm, yaw normalisation, and the +r⇒starboard sign (Risk R3). Auto-compiled by UBT; gated by `WITH_DEV_AUTOMATION_TESTS`. |
| `Development/bridge_harness/tests/test_plant_contract.py` | pytest: plant sign convention (incl. **+rudder⇒starboard**, the G7 Python half), straight-line stability, controller behaviour, the **v1.1 wire-contract key set**, and a **golden-file** packet pin. |
| `Development/bridge_harness/tests/golden_state_v1.json` | Pinned v1.1 packet — drift in the wire contract now fails a test. |
| `Development/automation/{automation_config,nightly_tests,nightly_render,nightly_sweep,nightly,register_nightly_tasks}.ps1` + `README.md` | The four-lane nightly (Plan §6.2): Python+UE tests, beauty render, summary sweep; orchestrator; Task Scheduler registrar. |
| `Development/work_packets/WP_20260616/verify_20260616.py` | Auto-checks T1–T4 here; flags the UE-side gate. |

---

## Already verified by the co-dev (automated, here)

```
PASS T1 pytest            : 10 passed (plant sign, contract, golden)
PASS T2 bridge_verifies   : root re-accept + WP-3 + WP-4 clock verifies all rc=0
PASS T3 automation_scripts: all 7 nightly files present
PASS T4 cpp_and_golden    : coords spec + golden present
4/4 → Saved/NaviSense_Reports/wp_20260616_result.json
```

Notable: `test_positive_rudder_turns_starboard` PASSES — the plant produces **+rudder ⇒ bow starboard**, corroborating the *Python half* of WP-2 G7 (the HUD half is still your in-PIE check).

---

## Your in-editor / terminal steps (≤15 minutes)

### Step 1 — Point the automation at your engine (~2 min)
```powershell
setx UE_ROOT "C:\Program Files\Epic Games\UE_5.7"   # or edit automation_config.ps1
```

### Step 2 — Recompile (picks up the new test .cpp) (~4 min)
**Ctrl+Alt+F11** or build in the IDE. The test file compiles into the module under `WITH_DEV_AUTOMATION_TESTS`.

### Step 3 — Run the nightly once = the WP-5 gate (~6 min)
```powershell
cd "D:\Marine Autonomy\NAVISENSE\NaviSense Simulator with Unreal Engine\Development\automation"
.\nightly.ps1
```
**PASS criteria:**
- `nightly\<date>\tests.json` → `results.ue_automation == true` (i.e. `Automation RunTests NaviSense` green), and `results.pytest == true`.
- `nightly\<date>\beauty_monaco.png` exists.
- `nightly\<date>\summary.json` written (this is what the 07:06 session reads).

### Step 4 — Register the schedule (~1 min, elevated, once)
```powershell
powershell -ExecutionPolicy Bypass -File .\register_nightly_tasks.ps1
```

### Step 5 — Confirm
> "WP-5 gate passed — RunTests NaviSense green + nightly PNG."

---

## Acceptance gates

| Gate | Check | Method | Status |
|------|-------|--------|--------|
| T1 | pytest suite green | auto | ✅ PASS |
| T2 | bridge/clock verifies green | auto | ✅ PASS |
| T3 | nightly scripts present | auto | ✅ PASS |
| T4 | C++ spec + golden present | auto | ✅ PASS |
| G_UE | `RunTests NaviSense` green from CLI + one nightly PNG | **MANUAL (PIE/CLI)** | ⏳ Lemuel |

---

## Rollback

Additive only. To revert: delete `Source/NaviSense/Tests/NaviSenseCoordsTests.cpp` (recompile), `Development/automation/`, and `Development/bridge_harness/tests/`. Unregister the task: `Unregister-ScheduledTask -TaskName "NaviSense Nightly" -Confirm:$false`.

## Next packet (WP-6 · Wed 17 Jun)

**Native fallback / manual mode (F4):** Enhanced-Input keyboard throttle/rudder + simple thrust/drag/yaw forces so the sim is drivable with no Python attached ("never demos dead"). Gate: with no listener, vessel drivable in Monaco at stable FPS. Closes Week 1.
