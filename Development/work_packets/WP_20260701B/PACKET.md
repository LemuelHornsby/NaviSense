# WP-20260701B — AIS → `sensor.v1` feed (own-ship AIS receiver; closes a concrete D4 gap)

**Date:** 2026-07-01 (Tue) · **Author:** Claude (Opus 4.8) · **Type:** additive C++ (+ reusable
Python mirror + verify) · **Demo gate:** **D4** (real sensors — the AIS-on-`sensor.v1` half) ·
**Verdict (headless):** `verify_20260701b.py` **5/5 gates + 3/3 controls = PASS**. **Rides the same
C++ rebuild already pending for the dashboard (WP-20260701) — no extra rebuild.**

## Why
GPS/IMU are validated and scripted AIS is rendered in-engine (WP-15B) + fully analysed
(CPA/TCPA/COLREGS). But the own-ship's **`sensor.v1 ais.targets[]`** block in
`USensorBundleComponent::BuildSensorsJson()` was still **hardcoded to an empty array** — the
receiver never reported the contacts it can plainly see. This is the small, concrete, headless-
buildable D4 gap the 1-Jul directive (§4 item 2) flagged. This packet wires it.

## What changed (all in the WORKSPACE; additive, needs the pending rebuild)
- **C++ — `Vessel/NaviSenseShipPawn.h/.cpp`:** the pawn now **retains** the last applied contact
  list (`TArray<FNaviSenseTrafficTarget> LastTraffic;`, set at the top of `ApplyTraffic`) and
  exposes `GetTrafficTargets()`. (Previously the target data was consumed to drive the actors and
  discarded; only actor transforms remained, which lack mmsi/cog/sog.)
- **C++ — `Sensors/SensorBundleComponent.cpp`:** `BuildSensorsJson()`'s AIS block now emits one
  `ais.targets[]` record per contact from `Pawn->GetTrafficTargets()`:
  `{mmsi, name, rangeM, trueBearingDeg, relBearingDeg, cogDeg, sogKn, latDeg, lonDeg}`. Range +
  true/relative bearing are computed from own-ship's wire pose (`x=East, z=North`) and heading;
  lat/lon reuse the **same geo origin the GPS block already uses** (RefLat/Lon 43.7350/7.4250).
  Empty contact list ⇒ `[]` (byte-identical to before — full back-compat). **No new DTO/USTRUCT**
  (sensor.v1 is built as raw JSON), so **B1 wire-parity + Z0 stay 16/16**; invariants intact
  (coord math via `NaviSenseCoords` frame semantics; the RX thread is untouched).
- **Python — `python/ais_sensor.py` (NEW, reusable, stdlib-only):** the receiver-feed builder —
  `build_ais_targets(own_e, own_n, own_heading, wire_targets)` — an **independent** reimplementation
  of the same geometry, so a future sensor.v1 AIS consumer/fuser/dashboard can use it and the verify
  can prove the C++ math is correct.
- **Python — `python/verify_20260701b.py` (NEW):** 5 gates + 3 controls (below).

## Acceptance gates — `python python/verify_20260701b.py` → **5/5 + 3/3 PASS** (done, headless)
- **G1** the C++ is wired: the pawn retains `LastTraffic`/`GetTrafficTargets`, and the SBC emits
  `ais.targets` **from** it (not the old empty array) with all 9 keys.
- **G2** geometry parity — the independent Python mirror matches the canonical `ais_traffic`
  geometry (`range_bearing` / `relative_bearing`) across 48 contact-instants (2 presets × 3 own
  headings × 4 times) to **0.00e+00** on the same wire inputs.
- **G3** schema / back-compat / identity — right keys+types, `mmsi == contact id`, geo-origin
  lat/lon, and **no traffic ⇒ `[]`**.
- **G4** determinism — bit-identical replay.
- **G5** regression — **Z0 16/16**, and the dashboard (`verify_20260701`) + traffic-render
  (`verify_20260629b`) gates **still PASS** (additive to both).
- **N1** the old hardcoded-empty block is detected as "not wired" · **N2** a swapped wire→receiver
  frame is caught (87° bearing error) · **N3** the feed tracks identity/course (id/cog changes
  reflected — not a stub).

## Your steps (≤ 5 min, folds into the dashboard rebuild)
1. **Rebuild C++** (the same full Build you already need for `WBP_BridgeDashboard` — this packet adds
   no separate rebuild).
2. Run any traffic scenario: `python run_demo.py --scenario monaco_capture`, press **Play**.
3. **G_AIS_SENSOR_UE (in-engine gate):** in `logs/<run>/sensor.csv` (or the live wire), the
   `sensor.v1 ais.targets[]` block now carries the **3 contacts** with mmsi/name/range/bearing/cog/sog
   (was empty). Optional: the dashboard's Sea-state/AIS panel can read them.

## Rollback
Revert `NaviSenseShipPawn.h/.cpp` + `SensorBundleComponent.cpp` (restore the empty-array AIS block);
delete `python/ais_sensor.py`, `python/verify_20260701b.py`. Fully additive — old runs, the wire
schema, and the render path are unaffected.

## Honesty (KI-019 / KI-009 family)
The feed is the own-ship's **AIS receiver view of scripted, deterministic contacts** — not a live
AIS receiver, not autonomy. `rangeM`/`bearing` are receiver geometry, **not** the post-run
CPA/TCPA/COLREGS verdict (`python/colregs_score.py`). `latDeg/lonDeg` use the flat-earth geo origin
(a live `CesiumGeoreference` is the separate D4 item). Radar/LiDAR/Sonar remain out of D4 scope.
