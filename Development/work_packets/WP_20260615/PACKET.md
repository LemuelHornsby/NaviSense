# WP-4 · 2026-06-15 · Deterministic Sim Clock + Run Lifecycle (F5)

> **Pre-authored 2026-06-14** during the autonomous multi-packet run. Planned date 15 Jun.

**Theme:** Replace the wall-clock sim time with a pause-aware, tick-accumulated, fixed-step clock, and add a run start/stop lifecycle so UE and Python share one `t`-origin per run.
**D-gate:** foundation for D6 (evidence pack `t`) and W7 deterministic replay.
**Estimated human time:** ≤15 minutes (recompile + one PIE pause test).

---

## What was written (all files ready in the repo)

| File | Change |
|------|--------|
| `Source/NaviSense/Core/NaviSenseSimSubsystem.h/.cpp` | Now a `FTickableGameObject`. `GetSimTime()` returns a **continuous, pause-aware** accumulated sim time (`IsTickableWhenPaused()==false` ⇒ a PIE pause freezes `t`). A **fixed-step accumulator** advances an integer `StepCount` in `FixedStepSeconds` (default 1/120) steps — the deterministic spine replay (W7) needs. New run lifecycle: `StartRun(RunId)` resets the clock + stamps the id; `StopRun()` freezes it; `IsRunActive()`, `GetStepCount()`, `GetFixedStepSeconds()`. The geo-origin fields (`RefLatDeg/RefLonDeg`) are preserved. |
| `Source/NaviSense/Bridge/NaviSenseBridgeComponent.cpp` | On the **first state of a run** the bridge calls `Sim->StartRun(State.runId)` — adopting Python's RunId and zeroing the UE clock so both ends share a `t`-origin. `Sim->StopRun()` on drop and on `Disconnect()` (so each reconnect is a fresh run, matching the listener's fresh-run-per-connection). |
| `Development/work_packets/WP_20260615/verify_20260615.py` | Mirrors the exact C++ accumulator and proves the algorithm: pause-aware drift, fixed-step counter, both-ends-same-`t`. |

---

## Already verified by the co-dev (clock algorithm, automated)

`verify_20260615.py` (mirror of `UNaviSenseSimSubsystem::Tick`):

```
PASS C1 pause_aware_drift   : 5 s pause not counted; sim t == ticked seconds (drift 0.0000 ms < 1 ms)
PASS C2 fixed_step_count    : StepCount 600 == floor(t/step)
PASS C3 both_ends_same_t    : UE t == Python K*dt (drift 0.0000 ms < 1 ms)
3/3 automated checks PASS  → Saved/NaviSense_Reports/wp_20260615_result.json
```

The one remaining gate is the in-engine pause test.

---

## Your in-editor steps (≤15 minutes)

### Step 1 — Recompile C++ (~4 min)
**Ctrl+Alt+F11** (Live Coding) or build in the IDE. Only `Core/NaviSenseSimSubsystem` + one bridge hook changed. *(If Live Coding refuses because a class layout changed — it added a base class — do a full editor restart + Build.)*

### Step 2 — Run + the pause test = Gate C4 (~8 min)
Start the canonical listener and Play (as in WP-3):
```
cd "D:\Marine Autonomy\NAVISENSE"
python python_listener.py --target unreal --controller zigzag10 -v
```
With the run live, in PIE press **Pause** (default `Pause` key / the editor Pause button), wait **5 s**, then **Resume**, then **Stop**.

**PASS criterion (C4):** the UE sim `t` (sensor packet `t`, or `stat`/HUD) must match Python's `t` within **< 1 ms** — i.e. the 5 s pause added nothing. If UE `t` is ~5 s ahead of Python after the pause, the clock is still counting wall-clock → fail (re-check `IsTickableWhenPaused`).

### Step 3 — Confirm
> "WP-4 C4 passed — clock holds across pause."  → next session closes WP-4.

---

## Acceptance gates

| Gate | Check | Method | Status |
|------|-------|--------|--------|
| C1 | Pause-aware: 5 s pause not counted, drift < 1 ms | auto (mirror) | ✅ PASS |
| C2 | `StepCount == floor(t/fixedStep)` | auto | ✅ PASS |
| C3 | UE `t` matches Python tick model < 1 ms | auto | ✅ PASS |
| C4 | In-PIE 5 s pause ⇒ `t` drift < 1 ms vs Python | **MANUAL (PIE)** | ⏳ Lemuel |

---

## Rollback

Changes are isolated to `Core/NaviSenseSimSubsystem.*` and two bridge hooks:
```
git checkout -- NaviSense_UE5/Source/NaviSense/Core/NaviSenseSimSubsystem.h \
                NaviSense_UE5/Source/NaviSense/Core/NaviSenseSimSubsystem.cpp \
                NaviSense_UE5/Source/NaviSense/Bridge/NaviSenseBridgeComponent.cpp
```
Then recompile. Note: reverting the bridge file also drops the WP-4 StartRun/StopRun hooks but keeps WP-3 (they are additive lines).

> ⚠️ **Risk note:** `UNaviSenseSimSubsystem` gained a second base class (`FTickableGameObject`). Live Coding sometimes can't hot-reload a changed class hierarchy — if the editor behaves oddly after Step 1, close it and do a clean Build once.

## Next packet (WP-5 · Tue 16 Jun)

**In-engine tests + nightly automation skeleton (F7, §6):** C++ Automation Specs (coords round-trip + sign convention), JSON contract golden-file test, `pytest` for the plant/controllers, `Development/automation/` nightly PowerShell scripts. Gate: `RunTests NaviSense` green from the CLI; one nightly PNG lands in `Saved/NaviSense_Reports/nightly/`.
