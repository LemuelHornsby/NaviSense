# WP-20260702 — Radar sensor (Sensor Suite Roadmap Pt 1) on `sensor.v1`

**Date:** 2026-07-02 (Thu) · **Author:** Claude (**Opus 4.8**, autonomous daily session)
· **Type:** additive C++ wire block (`SensorBundleComponent`) + reusable stdlib Python mirror
+ verify + §5 design record · **NO DTO/USTRUCT/schema-struct change, NO controller change** ·
**Scope:** **NEW sensor beyond D4** (Radar/LiDAR/Sonar roadmap) — **does NOT move the D4 gate** ·
**Verdict (headless):** `verify_20260702.py` **5/5 gates + 3/3 controls = PASS**, `Z0` 16/16.

## Why (scope + sequencing)
The 1-Jul directive (`NEXT_PACKET_DIRECTIVE.md`) has two tiers: (a) close the last concrete **D4**
sensor item — live `CesiumGeoreference` GPS, which is deferred behind the OPEN S2 **KI-014** Cesium
editor-crash (in-engine risk against the 11-Jul demo, not safely closeable headless); and (b) the
NEW Radar/LiDAR/Sonar sensor suite (§4 items 5–7), each requiring the §5 design decisions **recorded
before any C++**. With the three headless-buildable D4 items already shipped 1 Jul (AIS→`sensor.v1`,
camera, dashboard data layer) and the remaining D4 item blocked on Cesium, the highest-value headless
move today is roadmap item #5 — **Radar** — the natural extension of the already-validated AIS
receiver geometry (a contact list, no new engine feature, no ray traces). Design decisions for all
three roadmap sensors are recorded first in `Documents/NaviSense_Sensor_Suite_Roadmap.md`.

**This is explicitly flagged as new scope:** Radar/LiDAR/Sonar are **not** part of the D4 demo gate
and must not divert effort from D4/the demo. Tracked as a separate "Sensor Suite Roadmap" line in
`PROGRESS.md`, not folded into D4.

## What changed (all in the WORKSPACE; additive, rides the shared pending rebuild)
- **EDIT** `Source/NaviSense/Sensors/SensorBundleComponent.cpp` — new `// ---------- RADAR` block
  before `return Sensors;`, gated on `bEmitRadar`. Emits `sensor.v1 radar{maxRangeM, sweepDeg,
  contacts[]}`; each contact from `Pawn->GetTrafficTargets()` within `RadarMaxRangeM` is an
  **anonymous blip** `{rangeM, trueBearingDeg, relBearingDeg, radialSpeedKn, closing}` — NO identity
  (no mmsi/name). Range + true/relative bearing reuse the AIS block's geometry (own wire pose
  `x=East, z=North`, heading from the IMU block); radial (range-rate) speed is computed from own
  velocity (`SpeedMps` + heading) and target velocity (`sogKn`/`cogDeg`), `closing = radial < 0`
  (+ve = opening). Contacts beyond range are dropped; no traffic ⇒ `contacts: []`.
- **EDIT** `Source/NaviSense/Sensors/SensorBundleComponent.h` — radar UPROPERTYs
  (`bEmitRadar=true`, `RadarMaxRangeM=22224.f` = 12 NM). **No new USTRUCT** (raw JSON like AIS/camera),
  so the B1 top-level wire-parity guard + `Z0` stay 16/16; RX-thread + coord invariants intact.
- **NEW** `python/radar_sensor.py` — reusable, stdlib-only mirror (`radar_contact` / `build_radar`),
  same keys/geometry/defaults, honesty note (KI-027) in the docstring.
- **NEW** `python/verify_20260702.py` — the headless authoring gate (5 gates + 3 controls); writes
  `NaviSense_UE5/Saved/NaviSense_Reports/wp_20260702_result.json`, exits 0 iff PASS.
- **NEW** `Documents/NaviSense_Sensor_Suite_Roadmap.md` — the §5 design record for Radar (realised)
  + LiDAR/Sonar (design recorded, incl. the Sonar seabed-mesh prerequisite), with the scope flag and
  KI-019 honesty discipline.

## Acceptance gates — `python python/verify_20260702.py` → **5/5 + 3/3 PASS** (done, headless)
- **G1** C++ wired: `radar` block gated on `bEmitRadar`, `{maxRangeM,sweepDeg,contacts[]}`, each
  contact with the 5 keys from `GetTrafficTargets()`, a `RangeM > RadarMaxRangeM` drop, header UPROPERTYs.
- **G2** geometry parity: the Python mirror matches canonical `ais_traffic.range_bearing` /
  `relative_bearing` to **0.00e+00** across 48 contact-instants; radial-speed sign agrees (head-on
  closes, receding opens).
- **G3** schema / anonymity / honesty: exact keys+types, **no identity keys** (anonymous blip),
  beyond-range drop, default range matches C++↔mirror, KI-027 honesty label present in both.
- **G4** determinism: bit-identical replay.
- **G5** regression: `Z0` 16/16 + `verify_20260701b` (AIS) + `verify_20260701c` (camera) +
  `verify_20260629b` (traffic) all PASS + the roadmap design doc exists.
- **Controls:** N1 unwired block detected as not wired; N2 beyond-range contact dropped + closing sign
  correct; N3 tracks geometry (own move/turn changes range/bearing; receding target opens).

## Lemuel's steps (≤20 min, in-engine — deferred, rides the shared rebuild)
1. On the next `Build.bat` rebuild (the one already pending for the dashboard/AIS/camera work — **no
   extra rebuild**), open `NaviSense_Monaco`, run a scenario with traffic (e.g. `monaco_capture`).
2. Confirm the `sensor.v1` packets now carry a `radar` block with `contacts[]` blips whose `rangeM`/
   `trueBearingDeg` track the visible traffic ships, and `closing=true` on an approaching target.
   That closes the in-engine gate **G_RADAR_UE**.
3. No new data assets, no controller change, no new flags at runtime (radar is on by default via
   `bEmitRadar`).

## Rollback
Revert the two `SensorBundleComponent.{h,cpp}` edits (delete the `RADAR` block + the two UPROPERTYs)
and remove `python/radar_sensor.py`, `python/verify_20260702.py`,
`Documents/NaviSense_Sensor_Suite_Roadmap.md`. The `radar` block is purely additive and gated on
`bEmitRadar`; with it removed the wire is byte-identical to WP-20260701C. No schema/DTO change to
unwind. Setting `bEmitRadar=false` disables it without a code change.
