# WP-7 — 6-DOF schema v1.2: heel (roll) + trim (pitch)   ·   2026-06-16

**Theme (F1 part 1):** give the hull *attitude*. The plant stays 3-DOF; the listener
now derives a small, tunable **heel** and **trim** from the vessel's own motion and
ships them in `state.v1` (rev 1.2). Unreal applies them to the pawn so the boat
**leans in turns** and **noses up under acceleration** — the first half of demo gate
**D2** (6-DOF water ride). Heave + water-surface sampling are **F1 part 2** (deferred:
they need a UE water-height source and can't be verified headless).

## Why this packet today
Every prior packet (WP-3…WP-6, SENSOR-1, ACTUATOR-RIG) is auto-verified and waiting on
one in-editor recompile + PIE pass — none have a *failing* gate, so there is nothing to
"fix". The highest-value autonomous work is therefore (a) re-confirm the C++ surface is
still compile-ready (done: `verify_compile_readiness.py` **16/16** against today's disk),
and (b) advance the next backlog item, F1, in its fully head-less-verifiable form.

## Changed files
- **`python/attitude_proxy.py`** (NEW) — pure `attitude_deg(u,v,r,du_dt)` → `(roll_deg, pitch_deg)`.
  Outboard steady-turn heel ∝ `u·r` (clamped 8°); bow-up trim ∝ surge accel (clamped 3°).
- **`python_listener.py`** — imports the proxy; `build_state_packet` computes attitude
  (with a per-plant accel cache) and adds `"rollDeg"`, `"pitchDeg"` **inside** the `state.v1` dict.
- **`NaviSense_UE5/Source/NaviSense/Bridge/NaviSenseBridgeTypes.h`** — `FNaviSenseState`
  gains `double rollDeg`, `double pitchDeg` (default `0.0` ⇒ a v1.1 sender renders identically).
- **`Core/NaviSenseCoords.h`** — `WirePitchToUE`, `WireRollToUE`, `WireAttitudeToUE` —
  the *only* place the attitude sign/axis mapping lives (invariant #1).
- **`Vessel/NaviSenseShipPawn.h/.cpp`** — `TargetPitchDeg/TargetRollDeg`; set in
  `ApplyOwnShipState` via the coords helpers; frozen on stale-hold; lerped beside yaw in Tick
  (zero attitude ⇒ byte-identical to today's behaviour).

## Acceptance gates
| Gate | Type | Status | Evidence |
|---|---|---|---|
| A1–A9 attitude model + wire emission + DTO/wire parity + single-source + backward-compat | auto | ✅ PASS 9/9 | `wp_20260616_schema_v12_result.json` |
| Compile-readiness still green after the C++ edits (Z0 + B1 now 21/21) | auto | ✅ PASS 16/16 | `wp_20260615_compile_audit_result.json` |
| pytest plant/contract suite unbroken by the listener change | auto | ✅ PASS 10/10 | `bridge_harness/tests` |
| **G_UE — hull heels in turns / noses up on accel, no jitter @ stable FPS** | **manual (PIE)** | ☐ pending | Lemuel — folded into PENDING_EDITOR_GATES "Session A" |

## Lemuel's steps (≤ ~8 min, folds into the existing editor pass)
1. **Recompile** (Ctrl+Alt+F11). This now also picks up the two attitude fields + pawn lerp.
   *(NB: the 16-Jun "recompile Succeeded" Test-Log row was pre-authored 15 Jun and is unconfirmed;
   a real recompile is needed regardless to get this change.)*
2. Start the listener (`--controller zigzag10 -v` or `turning_circle`), press **Play**.
3. **Watch the hull in the turns:** it should heel a few degrees and nose up slightly when
   accelerating, smoothly (no jitter). Then **tell Claude: "WP-7 G_UE — heel/trim: pass/fail
   (and which way it leans)."**

## Decisions made autonomously (no user present)
- **Heel direction = OUTBOARD** (leans *away* from the turn), the textbook steady-turn result for
  displacement ships. If you'd prefer the cinematic "inboard lean", it's a one-line sign flip in
  `NaviSenseCoords::WireRollToUE` — call it out and I'll switch it.
- Attitude is a **kinematic visual proxy**, deliberately *not* fed back into the MMG plant — keeps
  maneuvering fidelity (IMO KPIs) untouched while delivering the visual.

## Rollback
- C++: revert the 3 files (the edits are small, additive, and brace-verified) — or set
  `rollDeg/pitchDeg` to 0 on the wire and the hull renders exactly as before.
- Python: delete the `attitude_deg(...)` block + the two dict keys in `build_state_packet`,
  and remove `python/attitude_proxy.py`. No other code depends on it.
