# WP-3 · 2026-06-14 · Bridge Robustness (F3)

**Theme:** Make the Python⇄Unreal bridge survive drops — auto-reconnect, stale-state hold, and a non-blocking send that never hitches the frame.
**D-gate:** hardens D1 (the closed loop must not die when the listener blips).
**Estimated human time:** ≤20 minutes (recompile + one PIE kill/restart test).

---

## What was written (all files ready in the repo)

| File | Change |
|------|--------|
| `Source/NaviSense/Bridge/BridgeSocketRunnable.h/.cpp` | RX thread now detects a dropped link (peer FIN / socket error) via `Wait(WaitForRead, 100ms)` + `Recv==0`, and raises a thread-safe flag. **Still touches zero UObjects** — threading rule (R2) intact. |
| `Source/NaviSense/Bridge/NaviSenseBridgeComponent.h/.cpp` | Exponential-backoff (re)connect 0.5→8 s (also retries the *initial* connect, so PIE order no longer matters); stale-state failsafe (>`StaleStateTimeoutSec`, default 1 s); **non-blocking queued send** (`PumpTx`) so the socket syscall can never stall the game thread; `OnConnectionChanged` BlueprintAssignable delegate + `ENaviSenseBridgeState` enum + on-screen status banner. TX/queue wrapped in `TRACE_CPUPROFILER_EVENT_SCOPE` for Insights. |
| `Source/NaviSense/Vessel/NaviSenseShipPawn.h/.cpp` | `NotifyBridgeStale()` — freezes the pawn at its last good pose (zeros vel/yaw-rate) when state goes stale; auto-resumes on the next fresh packet. `IsBridgeStale()` BlueprintPure for HUD. |
| `Development/bridge_harness/python_listener.py` | Listener now **re-accepts** clients after a drop (outer accept loop, 1 s poll so Ctrl-C stays snappy); a **fresh plant+controller per connection** (clean, repeatable run each PIE session); `--once` flag keeps the old single-client CI behaviour. |
| `Development/work_packets/WP_20260614/verify_20260614.py` | Standalone (no-UE) harness: spawns the listener, streams, hard-drops the client, reconnects, drops again, reconnects — asserts re-accept + resume + fresh-run. Writes `Saved/NaviSense_Reports/wp_20260614_result.json`. |

**Design note (authority split, per Plan §7):** the stale failsafe *holds* — it never extrapolates. A missing plant stream can never make the hull coast, overshoot, or drift; it parks at the last truth until real data resumes. This keeps "plant truth vs cosmetic motion" honest.

---

## Already verified by the co-dev (automated, Python/transport half)

`verify_20260614.py` was run in the sandbox against a byte-identical copy of the listener:

```
PASS P1 initial_stream         : 5 state.v1 packets on first connect
PASS P2 reaccept_after_drop    : re-accepted + streamed after a hard drop (no relaunch)
PASS P3 second_reconnect       : second drop+reconnect also recovered (durable loop)
PASS P4 fresh_run_per_connection: first packet t=0.000s after reconnect
4/4 automated gates PASS  → Saved/NaviSense_Reports/wp_20260614_result.json
```

So the transport/Python half is **green**. What remains are the two UE-side gates that need the editor.

**Also verified (added in the 14 Jun autonomous run):** the WP-3 re-accept robustness was propagated into the **canonical root `python_listener.py`** (the real run path; bridge_harness is the CI mirror). `Development/bridge_harness/verify_root_reaccept.py` → 4/4 PASS → `Saved/NaviSense_Reports/root_listener_reaccept_result.json`.

---

## Your in-editor steps (≤20 minutes)

> **Prerequisite:** `NaviSense_Monaco` open, pawn placed (from WP-2).

### Step 1 — Recompile C++ (~4 min)
Live Coding: **Ctrl+Alt+F11** in the editor (or build `NaviSense_UE5` in your IDE). Watch for a clean build in the Output Log. *(This packet touches only `Source/NaviSense/Bridge` + `Vessel` — no new modules, no .uproject change.)*

### Step 2 — Connect-order no longer matters (~2 min)
Press **Play** with **no** listener running. You should see the on-screen banner **"NaviSense bridge: RECONNECTING…"** (not a dead socket). Now start the **canonical** listener (the workspace-root one — it now has the same re-accept robustness):
```
cd "D:\Marine Autonomy\NAVISENSE"          # project root = canonical run listener
python python_listener.py --target unreal --controller zigzag10 -v
```
Within ≤8 s the banner flips to **"CONNECTED"** and the pawn starts moving ahead. ✅
*(`zigzag10` lets you also do the carried-over WP-2 G7 sign test in this same session. `Development/bridge_harness/python_listener.py` is the offline CI copy only — don't use it for live runs.)*

### Step 3 — The drop/restart test = Gate G4 (~6 min)
With it running and connected, **Ctrl-C the listener**. Watch:
- within ~1 s: banner **"STALE — holding position"**, pawn **freezes** (no drift).

Restart the listener (same command). Watch:
- banner returns to **"CONNECTED"**, pawn **resumes** moving. ✅ **G4 PASS** if hold→reconnect→resume all happen with no crash.

### Step 4 — Hitch trace = Gate G5 (~5 min, optional but recommended)
Launch with a CPU trace (or just watch `stat unit` for spikes):
```
UnrealEditor.exe <project> NaviSense_Monaco -game -trace=cpu -statnamedevents
```
Run ~60 s, then open the trace in **Unreal Insights**. Filter the game thread for `NaviSenseBridge_PumpTx` / `NaviSenseBridge_QueueSensorPacket`. ✅ **G5 PASS** if no occurrence exceeds 5 ms (expected: microseconds — the send is non-blocking).

### Step 5 — Regenerate the result file on your machine (~1 min)
```
python Development/work_packets/WP_20260614/verify_20260614.py
```
Confirms P1–P4 on real hardware and rewrites `wp_20260614_result.json`.

### Step 6 — Tell Claude to close WP-3
> "WP-3 G4 + G5 passed."  → next session marks WP-3 closed and builds WP-4.

---

## Acceptance gates

| Gate | Check | Method | Status |
|------|-------|--------|--------|
| P1 | Listener streams state.v1 on connect | auto (verify) | ✅ PASS |
| P2 | Re-accepts a new client after a hard drop, no relaunch | auto | ✅ PASS |
| P3 | A second drop+reconnect also recovers | auto | ✅ PASS |
| P4 | Fresh run per connection (first t≈0) | auto | ✅ PASS |
| G4 | Kill/restart listener mid-Play ⇒ pawn holds, UE auto-reconnects, resumes | **MANUAL (PIE)** | ⏳ Lemuel |
| G5 | Zero game-thread hitches >5 ms from Send (Insights) | **MANUAL (PIE)** | ⏳ Lemuel |

WP-3 **closes** when G4 + G5 are confirmed. (P1–P4 already green.)

---

## Rollback

All changes are additive and isolated to `Source/NaviSense/Bridge`, one method on the pawn, and the harness listener. To revert:
```
git checkout -- NaviSense_UE5/Source/NaviSense/Bridge \
                NaviSense_UE5/Source/NaviSense/Vessel/NaviSenseShipPawn.h \
                NaviSense_UE5/Source/NaviSense/Vessel/NaviSenseShipPawn.cpp \
                "Development/bridge_harness/python_listener.py"
```
Then recompile. The WP-2 behaviour (single connect, blocking send) returns. No data assets, levels, or .uproject were touched.

> ⚠️ **Tooling note for Claude/next session:** the sandbox bash *mount* served a stale, size-capped copy of `python_listener.py` after the file-tool overwrite (read-cache pinned at the original 15801 bytes). The Read tool and the real D: file are correct and complete. If a future edit to a large existing file "won't compile in bash but looks right in Read", suspect the mount cache — verify against a `/tmp` copy rather than re-editing.

---

## Carry-over (not part of WP-3)

- **WP-2 G7 (sign test)** is still open and is human-only: run `--controller zigzag10`, press Play, confirm **+10° rudder ⇒ bow swings starboard** in HUD + Python log. If wrong, fix **only** in `Core/NaviSenseCoords.h::WireYawToUE`. Then: "WP-2 G7 passed." Tip: you can do G7 and WP-3 G4 in the same PIE session.

## Next packet (WP-4 · Mon 15 Jun)

**Deterministic sim clock + run lifecycle (F5):** tick-accumulated, pause-aware sim clock in `UNaviSenseSimSubsystem` (fixed-step accumulator), run start/stop API stamped by `RunId`, both ends log the same `t`. Gate: PIE pause 5 s ⇒ `t` drift < 1 ms vs Python tick count. (Monday = also the §9 weekly metrics in PROGRESS.md.)
