# WP-2 · 2026-06-13 · Phase A: Closed Loop

**Theme:** Place `ANaviSenseShipPawn` in Monaco, wire the Python bridge, execute the zig-zag sign test.
**D-gate:** D1 (closed loop live in `NaviSense_Monaco`).
**Estimated human time:** ≤20 minutes.

---

## What was written (all files ready in the repo)

| File | Purpose |
|------|---------|
| `Content/NaviSense/Python/Phase5_Systems/01_place_ship_pawn_monaco.py` | Editor-Python: spawns / moves the ship pawn, assigns DOLPHIN hull mesh + vessel profile, sets Auto Possess P0, hides legacy yacht actors, saves level |
| `Development/bridge_harness/python_listener.py` | Python bridge server: MMG-lite plant + controllers (zigzag10, turning_circle, straight). Speaks the v1.1 wire protocol. Run this BEFORE pressing Play in UE. |
| `Development/work_packets/WP_20260613/verify_20260613.py` | Editor-Python: checks gates G1–G6 automatically, writes `Saved/NaviSense_Reports/wp_20260613_result.json`. G7 (sign test) is marked MANUAL_REQUIRED. |

---

## Your in-editor steps (≤20 minutes)

> **Prerequisites:** NaviSense_Monaco is open in the UE editor.

### Step 1 — Create the vessel profile data asset (if not done already)  (~2 min)

In the UE editor:
```
Tools > Execute Python Script...
→  Content/NaviSense/Python/Phase1to3_Foundation/04_create_vessel_profile.py
```
Check the Output Log for `[NaviSense P-A 04] Created and saved`. If it says "Already exists", skip.

### Step 2 — Place the ship pawn  (~3 min)

```
Tools > Execute Python Script...
→  Content/NaviSense/Python/Phase5_Systems/01_place_ship_pawn_monaco.py
```
Expected output:
```
[NaviSense WP-2] WP-2 placement COMPLETE.
[NaviSense WP-2] Pawn: NaviSenseShipPawn_DOLPHIN  Location: X=20580 Y=-23500 Z=-310
```
Verify visually: the pawn should appear near Port Hercule in the Monaco viewport.

### Step 3 — Quick static smoke test  (~2 min)

Press **Play (PIE)**. The pawn should sit still at the spawn point (no Python running = no motion). Press **Stop**.

### Step 4 — Run the zig-zag sign test (Gate G7)  (~10 min)

Open a terminal in `Development/bridge_harness/`:
```
python python_listener.py --controller zigzag10 --target unreal -v
```
Wait for: `[listener] Waiting for Unreal to connect on 127.0.0.1:5005 ...`

Press **Play (PIE)** in UE. The listener should print:
```
[listener] Unreal connected from ('127.0.0.1', ...)
[tx] t= ...  yaw=...°  rud=+10.0°  r=+...°/s
```

**PASS criterion (Gate G7):**
- When `rud=+10.0°` → `yaw` should be **increasing** (bow swings **starboard**)
- When `rud=-10.0°` → `yaw` should be **decreasing** (bow swings **port**)
- Same sign convention should be visible in UE's HUD log (if wired) or via `stat NaviSense`

If the sign is **wrong** (bow goes the wrong way): do NOT change the controller. Fix it exclusively in `Source/NaviSense/Core/NaviSenseCoords.h` → `WireYawToUE`. This is by design (Master Guide Section 2.3).

Press **Stop** after confirming.

### Step 5 — Run the verify script  (~2 min)

```
Tools > Execute Python Script...
→  Development/work_packets/WP_20260613/verify_20260613.py
```
Expected: `WP-2 Verify complete: 6/6 automated gates PASS`
Report written to: `Saved/NaviSense_Reports/wp_20260613_result.json`

### Step 6 — Confirm G7 and close WP-2

After confirming the sign test in PIE, **tell Claude** (in chat or the next session):
> "WP-2 G7 passed — heading swings correctly."

Claude will then update `PROGRESS.md` to mark WP-2 closed and build WP-3.

---

## Acceptance gates

| Gate | Check | Method |
|------|-------|--------|
| G1 | `ANaviSenseShipPawn` exists in `NaviSense_Monaco` | auto (verify script) |
| G2 | Pawn within 500 cm of spawn (20580, −23500, −310) | auto |
| G3 | Auto Possess = Player 0 | auto |
| G4 | `VesselProfile` = DA_DOLPHIN assigned | auto |
| G5 | Hull `StaticMesh` assigned | auto |
| G6 | No visible legacy yacht/unity actors | auto |
| G7 | +10° rudder → bow swings starboard (sign test) | **MANUAL** — Lemuel confirms in PIE |

WP-2 is **closed** only when all 7 gates pass. G7 requires explicit confirmation.

---

## Rollback

If something breaks or the pawn placement is wrong:
1. In UE Outliner, find `NaviSenseShipPawn_DOLPHIN` → right-click → Delete.
2. Re-run `01_place_ship_pawn_monaco.py` after fixing.
3. The Python listener has no persistent state — just restart it.

No C++ changes were made in this packet. There is nothing to revert in code.

---

## Next packet (WP-3 · Sun 14 Jun)

**Bridge robustness** (F3): reconnect with exponential backoff (0.5→8 s), heartbeat/stale-state failsafe (>1 s without state.v1 → hold position + on-screen warning), send moved off the hot path (queued, non-blocking), connection-state Blueprint event for HUD.
Gate: kill/restart listener mid-Play → pawn freezes gracefully, auto-reconnects, resumes; zero hitches >5 ms from Send (Insights trace).
