# WP-20260629B — Real Traffic ships for COLREGS scenarios (WP-15B)

**Date:** 2026-06-29 (Mon) · **Author:** Claude (w/ Lemuel decisions) · **Type:** wire-driven
in-engine rendering — **C++ DTO + pawn + listener + new preset/scenario + editor script** ·
**Needs a C++ rebuild.** · **Demo gates:** D4 (real sensors/traffic) + unblocks D7 (a COLREGS film).
· **Verdict (headless):** `verify_20260629b.py` **5/5 gates + 3/3 controls = PASS**.

## Why
The COLREGS evidence layer (AIS / CPA-TCPA / conformance) was validated only against **scripted**
targets — **no ships on screen**. You placed 3 vessels under a *Traffic* folder. This packet drives
those ships from the listener over the wire using the **same deterministic preset the evidence pack
scores**, so what's captured == what's scored (no drift, replayable). Decisions you made: Python
drives over the wire · custom 3-ship encounter · rebuild OK · the 3 are static-mesh props.

## What changed (all in the WORKSPACE)
- **C++ (rebuild required):**
  - `Source/NaviSense/Bridge/NaviSenseTrafficTypes.h` — **NEW** `FNaviSenseTrafficTarget`
    {id,name,x,y,z,yawDeg,sogKn,cogDeg} (own header so the B1 wire-parity guard still sees the 22
    own-ship keys only).
  - `NaviSenseBridgeTypes.h` — `FNaviSenseState` gains `TArray<FNaviSenseTrafficTarget> traffic`
    (optional/additive; absent ⇒ identical to before; **no schema-string bump**, like env/attitude).
  - `Vessel/NaviSenseShipPawn.h/.cpp` — `ApplyTraffic()` drives each mapped actor with the SAME
    `NaviSenseCoords` conversion + **own-ship spawn anchor** (invariant #1), keeping the actor's
    placed Z (waterline) and forcing it Movable; `TrafficActors[]` (+ auto-resolve by tag
    `NaviSenseTraffic`, sorted by name) + `bAnchorTrafficToSpawn`.
  - `Bridge/NaviSenseBridgeComponent.cpp` — `ApplyState()` also calls `Pawn->ApplyTraffic(State.traffic)`
    (game thread; RX thread still touches no UObjects, invariant #2).
- **Python (no rebuild):**
  - `python/ais_traffic.py` — `wire_targets(field,t)` (per-tick wire poses) + **new `monaco_capture`**
    3-ship preset.
  - `python_listener.py` — builds the `AISTrafficField` once at run start (own-ship origin) and emits
    a per-tick `traffic[]` for any `--ais`/scenario; `build_state_packet(..., traffic=)`.
  - `python/scenarios.py` — new **`monaco_capture`** scenario (controller `transit`, SS2, ais=monaco_capture).
- **Editor (run once, in-engine):** `Content/NaviSense/Python/Phase5_Systems/07_setup_traffic_ships.py`
  — finds the 3 Traffic actors, forces Movable + tags them, assigns the pawn's `TrafficActors`, saves.
- **Verify:** `python/verify_20260629b.py` (5 gates + 3 controls).

## Proposed encounter geometry — `monaco_capture` (CONFIRM / TWEAK)
Own-ship transits ~north into three staggered, simultaneous COLREGS encounters; own-ship is give-way
to all three. Tune the four numbers per row in `python/ais_traffic.py → _PRESETS["monaco_capture"]`
(relative to own-ship's start; the rendered ships AND the scored encounter both follow it):

| Ship | Encounter (Rule) | ahead_m | starboard_m | rel_course° | speed (kn) |
|---|---|---|---|---|---|
| SLOWBELLE | overtaking (13) | 450 | +15 | 0 | 3.5 |
| AZURFERRY | crossing from stbd (15) | 950 | +750 | 255 | 12.6 |
| MERIDIAN | head-on (14) | 1550 | −30 | 180 | 11.7 |

## Acceptance gates — `python python/verify_20260629b.py` → **5/5 + 3/3 PASS**
- **G1** the listener emits `state.v1 traffic[]` (3 entries, correct keys); no-traffic packet omits it.
- **G2 (capture-correctness)** replicating the C++ anchor math, each rendered target lands **exactly
  `ahead_m` ahead + `starboard_m` to starboard** of own-ship for an arbitrary spawn pose (max error
  **0.000 cm**, spawn-invariant) ⇒ what's captured == what's scored.
- **G3** `monaco_capture` is COLREGS-valid: overtaking + crossing + head_on, own-ship give-way to all
  (held-course ⇒ scored non_compliant, the honest baseline).
- **G4** determinism — wire poses replay bit-for-bit.
- **G5 (e2e)** the REAL listener with `--scenario monaco_capture` emits **55 packets × 3 moving
  targets** (subprocess + socket sniff).
- **N1** unknown preset rejected · **N2** a wrong wire→UE frame is caught by G2 (223 446 cm error) ·
  **N3** the render tracks the scripted course (flip COG ⇒ 720 m divergence).

## Regression (current disk, headless) — all green
Z0 **16/16** (B1 still 22/22, coords single-source + RX-no-UObjects intact); `verify_20260624` AIS
**6/6+3/3**; `verify_20260627` COLREGS **6/6+3/3**; `verify_20260629` clock **6/6+3/3**;
`run_demo --selftest --scenario monaco_capture` → **DEMO COMPLETE, health 6/6**, evidence pack carries
3 targets + COLREGS conformance.

## Your steps (≤ 20 min)
1. **Confirm/tweak** the geometry table above (edit the preset rows if you want a different framing).
2. **Rebuild C++** (full Build, editor closed — this adds the traffic DTO + ApplyTraffic).
3. Open `NaviSense_Monaco`, **Tools → Execute Python Script → `07_setup_traffic_ships.py`** (sets the
   3 props Movable + tags + assigns them to the yacht; save). *(If your ships aren't in a "Traffic"
   folder, set `TRAFFIC_LABELS` at the top of the script.)*
4. Run `python run_demo.py --scenario monaco_capture` (or `python python_listener.py --scenario
   monaco_capture --target unreal`), press **Play**, frame the shot by placing own-ship + camera.
5. **G_TRAFFIC_UE (capture gate):** the 3 ships move along the encounter — own-ship overtakes
   SLOWBELLE, gives way to AZURFERRY crossing from starboard, and meets MERIDIAN head-on.

## Rollback
`git checkout -- Source/NaviSense/Bridge/NaviSenseBridgeTypes.h Source/NaviSense/Vessel/NaviSenseShipPawn.h
Source/NaviSense/Vessel/NaviSenseShipPawn.cpp Source/NaviSense/Bridge/NaviSenseBridgeComponent.cpp
python_listener.py python/ais_traffic.py python/scenarios.py` ; delete
`Source/NaviSense/Bridge/NaviSenseTrafficTypes.h`, `python/verify_20260629b.py`,
`Content/NaviSense/Python/Phase5_Systems/07_setup_traffic_ships.py`, rebuild. Additive throughout:
old runs/scenarios and a no-traffic wire are unaffected.

## Honesty (KI-019 / KI-009 family)
The 3 ships are **visual props driven by a deterministic scripted preset** — not a live AIS receiver
and not autonomous traffic. Own-ship runs a FIXED controller, so a straight transit is correctly
scored **non-compliant** to the give-way duties (the avoidance controller is the W5-6 roadmap). Say
"scripted COLREGS scenario with rendered traffic," never "autonomous COLREGS avoidance."
