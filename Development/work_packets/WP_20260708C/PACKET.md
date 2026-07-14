# WP-20260708C — sensor.v1 raw evidence sink + objective sensor-suite gate (T-3)

**Goal.** The Step-1 in-engine sensor gates (`G_AIS_SENSOR_UE`, `G_RADAR_UE`,
`G_CAMERA_UE`) were **console eye-checks only**: `sensor.csv` flattens the wire to
GPS/IMU scalars + an `ais_target_count`, so the rich `sensor.v1` blocks
(`ais.targets[]`, `radar.contacts[]`, `camera{}`) left **no on-disk evidence**.
At T-3 that means the ONE PIE session would close three gates on "I saw it in the
console" with nothing verifiable afterwards. This packet (1) persists a sampled
raw copy of every `sensor.v1` packet and (2) gates the three blocks objectively.

**No C++ / wire / DTO / schema / product-behavior change. NO rebuild** — Z0
untouched; pure-Python, additive. The RX hot path gains one sampled, exception-
swallowed JSONL write (same thread that already writes the CSV row).

## Changed files
- `python/run_logger.py` — **edited (additive)**: new `sensor_raw.jsonl` sink per
  run (envelope `{wall_time, t_mono, msg}` — wire packet byte-intact). Sampling:
  every packet for the first 300 rows, then 1-in-10 (~6 Hz @ 60 fps ⇒ a few MB
  per 10-min run). Best-effort open + write (can never break the bridge loop);
  manifest gains `sensorRawLines`; file closed in `finalise()`.
- `python/verify_sensor_suite.py` — **new**: objective gate over a real run's
  `sensor_raw.jsonl`. R0 raw-present · R1 = `G_AIS_SENSOR_UE` (9 wire keys per
  target, sane bearings, ranges TRACK over time) · R2 = `G_RADAR_UE` (blips
  anonymous — mmsi/name must NOT leak; 5 contact keys; all ≤ `maxRangeM`) ·
  R3 = `G_CAMERA_UE` (7 keys incl. `pose{x,y,z}`; `frameIndex` monotonic;
  `frameRef` a `.png` still name). `--latest` skips `_`-prefixed dirs;
  `--require ais,radar[,camera]` tailors non-traffic runs. Writes
  `Saved/NaviSense_Reports/sensor_suite_result.json`, exit 0/1.
- `python/verify_20260708c.py` — **new**: packet gate (see below).
- `Development/work_packets/PENDING_EDITOR_GATES.md` — Step 1 now ends with the
  one-command objective confirm (replaces "read the -v console" for 3 of 4 gates).

## Acceptance gates — ALL PASSED headless 8 Jul (autonomous session)
`python python/verify_20260708c.py` → `wp_20260708c_result.json` **4/4 + 3/3**:
- **G1 raw-sink** — real `RunLogger` fed 350 synthetic packets (built with the
  same `ais_sensor`/`radar_sensor`/`camera_sensor` mirrors the C++ is
  parity-verified against) → exactly 305 sampled envelopes, all parseable,
  manifest `sensorRawLines=305`. PASS
- **G2 suite-pass** — `verify_sensor_suite --run <fixture>` 4/4. PASS
- **G3 back-compat** — `sensor.csv` unchanged: same 16-column header, 350 rows. PASS
- **G4 regression** — `preflight_demo --report-only` rc=0 **GO**;
  `wp_20260708b_result.json` still `pass=true`. PASS
- **N1/N2/N3** — stripped AIS / identity-leaking radar blip / missing camera
  block each FAIL the right gate (R1/R2/R3), exit 1. PASS

## Lemuel's steps (≤ 5 min, folds INTO the already-planned PIE session)
Nothing new to set up. In the Step-1 `monaco_capture` PIE run (see
`PENDING_EDITOR_GATES.md`), after you stop the run, add ONE command:
```
python python/verify_sensor_suite.py --latest
```
PASS ⇒ `G_AIS_SENSOR_UE` + `G_RADAR_UE` + `G_CAMERA_UE` are closed with on-disk
evidence (`sensor_suite_result.json` + the run's `sensor_raw.jsonl`).
`G_TRAFFIC_UE` (ships visibly moving) stays an eye-check. If the run has no
traffic scenario, use `--require camera` (AIS/radar have nothing to see).

## Rollback
`git checkout -- python/run_logger.py` (or delete the try-block additions);
delete `python/verify_sensor_suite.py`, `python/verify_20260708c.py`,
`Development/work_packets/WP_20260708C/`. `sensor_raw.jsonl` files are inert
per-run artifacts; removing the sink simply stops producing them.
