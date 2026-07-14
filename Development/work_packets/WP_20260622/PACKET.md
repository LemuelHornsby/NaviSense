# WP-20260622 — Sensor-fidelity gate (D4 / F2)

**Goal:** turn the in-engine sensor bundle from "emits non-zero values" into
"emits values that **provably match the vessel's true motion**." This makes
**D4 (real sensors)** objectively checkable in the nightly instead of by eye, and
gives the first real-data validation of the GPS/IMU against the plant.

**Type:** pure-Python, **read-only** over `logs/`. **NO recompile, NO DTO / wire /
schema change, NO new in-engine gate.** (Folds into the existing automation.)

## Why this packet now
- The 21-Jun `WP-20260621_HYDRO` packet is **green headless (9/9)** but its in-engine
  gates (G_HYDRO float-at-waterline, G_PROP twin-prop) need Lemuel's full rebuild +
  config-asset + Blender split — those can't be advanced from the sandbox today.
- The next open demo gate is **D4 real sensors** (plan §4 WP-13). Lemuel's morning
  run `unreal-test-run_20260622_054815` carries a fresh `sensor.csv`, and the only
  sensor check that existed (`WP_20260614_SENSORS/verify_sensors.py`, S1–S3) just
  asks "are the numbers non-zero and in range" — not whether they're **correct**.

## What shipped
- **NEW `python/verify_sensors_fidelity.py`** — cross-validates `logs/<run>/sensor.csv`
  (the pawn's GPS/IMU) against `logs/<run>/state.csv` (the authoritative plant pose).
  It derives the expected sensor from the plant the same way
  `SensorBundleComponent::BuildSensorsJson` does, so a faithful sensor is a near-affine
  image (slope ≈ 1, corr ≈ 1) of the plant signal. Exit 0/1 for the nightly; `--json`
  writes a verdict; `--selftest` runs negative controls.

### Gates (a run PASSES when all gate-checks pass)
| ID | Check | What it proves |
|---|---|---|
| D1 | timing | sensor `wall_time` strictly increasing & inside the state span |
| D2 | finite_and_fix | all sensor numerics finite; `gps_hasFix` always true |
| D3 | speed_fidelity | `gps_speed` ≈ plant `speed_mag` (slope≈1, corr≥0.97, RMS≤0.30 m/s) |
| D4 | yawrate_fidelity | `imu_yawRate` ≈ plant `r`·180/π (|slope|≈1, corr≥0.90) |
| D5 | heading_fidelity | unwrap(`imu_heading`) ≈ unwrap(plant yaw) (slope≈1) — INFO if turn <5° |
| D6 | position_fidelity | gps pos == plant pos + a constant spawn-anchor offset (robust median residual ≪ path extent) |
| D7 | geo_projection | one Monaco origin reconstructs every lat/lon from (E,N), consistent + sane (~43.7 N, 7.4 E) |
| D8 | accel_sane | IMU accel finite, bounded, and actually computed (non-zero while accelerating) |
| D9 | ais (INFO) | `ais_target_count` (0 until scripted traffic, WP-15) |
| C1 | clock (INFO) | plant-t/wall vs sensor-t/wall ratio — surfaces **KI-024** |

**Key design choice:** the two logs are on **different clocks** — `state.csv` `t` is
the Python plant sim-clock; `sensor.csv` `t` is the UE engine sim-clock. On the
morning run they diverge **3.0× vs 1.0×** (the plant free-ran at high PIE FPS). Both
share `wall_time`, so the gate **joins on `wall_time`, never on `t`**, and flags the
divergence as **KI-024** (data-integrity, S3).

## Verified (sandbox, headless)
Evidence: `NaviSense_UE5/Saved/NaviSense_Reports/wp_20260622_result.json`

- **Fresh run** `unreal-test-run_20260622_054815` (turning_circle, SS0): **8/8 PASS**
  — speed corr 1.0000 (RMS 0.001 m/s), yaw-rate corr 1.0000, position gps=plant+offset
  (−243.4 E, 1738 N) median residual **0.18 m** (p90 0.37 m).
- **Rich run** `unreal-test-run_20260621_163148` (493° turn): **8/8 PASS** — heading
  corr **1.0000 over a 492° sweep**, position median residual **0.43 m** over a 179 m path.
- **Negative controls (teeth)**: constant speed → D3 FAIL; frozen heading → D5 FAIL;
  scrambled lat/lon → D7 FAIL; NaN accel → D2 FAIL; lost fix → D2 FAIL. **all_fired=True.**
- Regression (current disk): `verify_run_kinematics` on the morning run **7/7 PASS**;
  `WP-SENSOR-1` S1–S3 PASS.

## Lemuel — steps (≤5 min; optional — nothing blocks on this)
1. (Optional) After any future PIE run, gate the sensors:
   `python python/verify_sensors_fidelity.py`            (latest run, prints 8/8)
   `python python/verify_sensors_fidelity.py --selftest` (on a turning_circle run, to see the controls fire)
2. (Optional) Add it to the nightly next to `verify_run_kinematics.py` (see Maintenance Guide).

There is **no in-engine gate** in this packet. The HYDRO in-engine steps from
`WP_20260621_HYDRO/PACKET.md` (full rebuild + `DA_DOLPHIN_HydrostaticsConfig` +
WaterlineOffsetCm tune + Blender prop split) remain the real blockers for D2's last half.

## Acceptance gates (this packet)
- **G_SENSOR_AUTO:** `verify_sensors_fidelity.py` returns **8/8 PASS** on a real run and
  **all 5 negative controls fire** on a turning run. ✅ (see result JSON).
- (No human/in-engine gate.)

## Demo-gate impact
- **D4 real sensors: ☐ → ◐** — GPS speed/position, IMU heading/yaw-rate/accel, and the
  WGS84 geo-projection are now **objectively validated against the plant** on real runs.
  Remaining for D4: scripted **AIS traffic** target (WP-15), **camera sensor** (WP-14),
  and routing GPS through the live **CesiumGeoreference** (today it uses the geo-origin).

## Follow-ups opened
- **KI-024 (S3, OPEN):** plant-log `t` (Python sim-clock) and sensor-log `t` (UE
  engine-clock) diverge under high FPS; anyone fusing the two CSVs by `t` gets garbage.
  Mitigation in place: join on `wall_time`. Consider stamping both logs with one clock.
- Once `WP_20260621_HYDRO` lands, feed the **hydrostatics-computed** heave/roll/pitch
  to the sensors/log so logged seakeeping = the physics (then add D2/D3 fidelity checks
  for them too).

## Rollback
Delete `python/verify_sensors_fidelity.py` and this packet dir. Nothing else references
it (no imports into the listener/plant); removing it cannot affect a run.
