# NaviSense Bridge Protocol & Schema Specification (external-facing)

**Version 0.1 (draft) · 14 July 2026.** This is the versioned public contract for anything that talks to NaviSense. Source of truth until the core/view split lands: `NaviSense_UE5/Source/NaviSense/Bridge/NaviSenseBridgeTypes.h` and `python_listener.py`. On discrepancy, code wins and this spec gets a patch + changelog entry. Planned: generate JSON Schema files from this spec and validate in CI.

## 1. Transport

Newline-delimited JSON (NDJSON), UTF-8, over TCP; default port **5005** (`PROBE_5005.bat` probes it). Two message families, one per direction: `navisense.state.v1` (Python plant → renderer/clients) and `navisense.sensor.v1` (renderer → Python/clients). Every message carries `schema` (string) and `runId`.

## 2. `navisense.state.v1` (plant truth)

| Field | Type | Units / convention |
|---|---|---|
| schema, runId | string | — |
| t | double | plant sim-time, s (canonical run clock `t_mono` in logs) |
| x, y, z | double | position, m (see coordinate note) |
| yawDeg | double | heading, deg (sign convention centralized in `NaviSenseCoords.h::WireYawToUE` — fix signs ONLY there) |
| rollDeg | double | + = starboard-down (heel to starboard) |
| pitchDeg | double | + = bow-up (trim) |
| heaveM | double | m |
| u, v, r | double | surge m/s, sway m/s, yaw rate |
| portRpm, starboardRpm | double | achieved propeller rpm |
| rudderDeg | double | achieved, **port-positive** |
| bowThrusterNorm | double | achieved, [-1, 1], + = bow-to-starboard |
| portRpmCmd, starboardRpmCmd, rudderCmdDeg, bowThrusterCmdNorm | double | commanded values (kept distinct from achieved — required for unbiased system ID) |
| mode | string | idle · manual · auto · replay |

## 3. `navisense.sensor.v1` (sensor echo)

Envelope per tick with sensor blocks (authoritative field lists in `python/…_sensor.py` modules): `gps` (lat/lon from WGS84 geo-origin), `imu`, `ais.targets[]` (mmsi, cog, sog, position…), `radar.contacts[]` (anonymous blips: range/bearing…), `camera` {fovDeg, resX, resY, headingDeg, frameIndex, frameRef, pose} where `frameRef` names on-disk HighResShot stills.

**Clock warning (KI-024, resolved by convention):** sensor-side `t` is the UE engine clock and may diverge from plant `t` under FPS load; **join streams on `wall_time` / canonical `t_mono`**, never on raw `t` equality.

## 4. Run artifacts (on-disk contract)

`logs/<run>/`: `state.csv` (plant truth), sensor log, `manifest.json` (integrity: sizes, hashes, completeness — packs refuse partial views), `runs.csv` registry row, `evidence_pack/` (KPIs, COLREGS scoring, HTML report, regulatory mapping + requirements trace + uncertainty statement per Evidence_Pack_Templates.md).

## 5. Versioning & stability policy

Schema names carry the major version (`*.v1`). Additive fields = minor, non-breaking (consumers must ignore unknown fields). Renames/removals/semantic changes = new major (`*.v2`) with one overlapping deprecation release. Every change lands in CHANGELOG.md + this spec. Sign conventions are API: changing one is a major version even if the field name survives.

## 6. Conformance

A third-party client is conformant if it: parses NDJSON tolerantly (ignores unknown fields), respects the clock-join rule (§3), treats commanded vs achieved actuation as distinct, and never writes into `logs/<run>/` except via the provided runner. Conformance test vectors: TODO — export golden NDJSON samples from a reference run into `Development/bridge_harness/vectors/` and reference them here.

## Revision log

| Ver | Date | Change |
|---|---|---|
| 0.1 | 2026-07-14 | Initial spec extracted from BridgeTypes.h + listener; port/clock/versioning policies declared |
