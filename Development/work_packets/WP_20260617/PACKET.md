# WP-6 · 2026-06-17 · Native Fallback / Manual Mode (F4) — Week 1 close

> **Pre-authored 2026-06-14** during the autonomous multi-packet run. Planned date 17 Jun.

**Theme:** Make the sim drivable with **no Python attached** — a simple keyboard-driven kinematic fallback so a dead bridge never means a dead demo.
**D-gate:** de-risks every live demo (D1–D8 insurance).
**Estimated human time:** ≤12 minutes (recompile + drive a lap).

---

## What was written

| File | Change |
|------|--------|
| `Source/NaviSense/Vessel/NaviSenseShipPawn.h/.cpp` | New **Manual** motion source: `UpdateManual()` polls W/S (throttle) + A/D (rudder) **directly off the possessing PlayerController** (asset-free — no Input Mapping Context or config to set up). First-order surge toward a cruise speed (drag built in), speed-scaled yaw ("yaw needs way"), holds at the waterline, and feeds the existing actuator-viz rig + sensor kinematics. Tap **`M`** to toggle Manual ⇄ PoseReceive live. Tunables under `NaviSense\|Manual`. |
| `Development/work_packets/WP_20260617/verify_20260617.py` | Mirrors `UpdateManual` and checks the model (throttle→cruise, yaw-needs-way, rudder sign, astern). |

**Design choice:** keys are *polled*, not bound through Enhanced Input, so this works the instant the pawn is possessed (Auto Possess P0 from WP-2) with zero asset/config setup. A proper Enhanced Input mapping context is a later nicety (WP-12), not needed to "never demo dead".

---

## Already verified by the co-dev (manual model, automated)

```
PASS M1 throttle_to_cruise : full throttle -> speed reaches cruise (600 cm/s)
PASS M2 yaw_needs_way       : full rudder at zero speed -> |dyaw| 0.000 deg
PASS M3 rudder_sign         : +rud -> +55.4 deg (starboard), -rud -> -55.4 deg (port)
PASS M4 astern              : reverse throttle -> sternway
PASS M5 pawn_files_exist
5/5 → Saved/NaviSense_Reports/wp_20260617_result.json
```

---

## Your in-editor steps (≤12 minutes)

### Step 1 — Recompile (~4 min)
**Ctrl+Alt+F11** or build. Only the pawn changed.

### Step 2 — Drive with no Python = Gate G_UE (~6 min)
Open `NaviSense_Monaco`. **Do not** start any listener. Either set the pawn's **MotionSource = Manual** in the Details panel, or just press **Play** and tap **`M`**.
Drive: **W/S** = throttle ahead/astern, **A/D** = rudder stbd/port (turning needs way). Watch the on-screen "MANUAL" banner and the rudder/propeller visuals respond.

**PASS criterion (G_UE):** with no Python running, the vessel is drivable around Port Hercule at **stable FPS** (no hitching, no fall-through). Tapping `M` returns to bridge mode.

### Step 3 — Confirm + Week-1 retro
> "WP-6 G_UE passed — drivable with no Python."
This closes **Week 1**. (PROGRESS.md already carries the Week-1 retro line from the 14 Jun run.)

---

## Acceptance gates

| Gate | Check | Method | Status |
|------|-------|--------|--------|
| M1–M4 | Manual kinematic model correct | auto (mirror) | ✅ PASS |
| M5 | Pawn source present | auto | ✅ PASS |
| G_UE | Drivable with no Python at stable FPS | **MANUAL (PIE)** | ⏳ Lemuel |

---

## Rollback

Additive. To revert: in `NaviSenseShipPawn.cpp/.h` remove the `UpdateManual` method, the `Manual` branch + `M`-toggle in `Tick`, and the `NaviSense|Manual` properties; or `git checkout -- NaviSense_UE5/Source/NaviSense/Vessel/NaviSenseShipPawn.*`. PoseReceive behaviour is untouched.

## Next (Week 2 · 18 Jun onward) — per Execution Plan §4

WP-7/8 **bridge schema v1.2** (roll/pitch/heave) → WP-9 MMG roll → WP-10 water sampling → WP-11 sea-state presets → WP-12 camera modes + Enhanced Input. (6-DOF water ride = demo gate D2.)
