# WP-SENSOR-1 · 2026-06-14 · Real GPS + IMU (sensor suite, part 1)

**Theme:** Turn the placeholder sensor block into real readings — true lat/lon, speed-over-ground,
yaw-rate, and acceleration — so `navisense.sensor.v1` carries usable perception data.
**D-gate:** advances **D4** (real sensors on the wire).
**Estimated human time:** ≤10 minutes (recompile + one run + glance at the log).

## What was written (C++, all in NaviSense_UE5/Source/NaviSense)
| File | Change |
|------|--------|
| `Sensors/SensorBundleComponent.cpp/.h` | Real GPS (worldPosition + speed + **lat/lon via geo-origin** + hasFix) and IMU (heading + **real yaw-rate** + **finite-difference acceleration**). Optional noise fields. |
| `Vessel/NaviSenseShipPawn.h` | Public accessors: `GetBodyVelocityCmPerSec`, `GetYawRateDegPerSec`, `GetSpeedMetersPerSec` (true own-ship kinematics for the sensor model). |
| `Core/NaviSenseSimSubsystem.h` | `RefLatDeg`/`RefLonDeg` geo-origin (default Monaco / Port Hercule 43.7350 N, 7.4250 E). |

**Design:** GPS lat/lon comes from a local-ENU geo-origin (no hard Cesium dependency — robust against the
current Cesium tileset load error, KI-014). Sensors read the pawn's true kinematics and add optional noise —
the correct sensor-model shape. AIS stays empty until traffic exists (next packets).

## Your in-editor steps (≤10 min)
1. **Recompile** — Ctrl+Alt+F11 (Live Coding). If it balks at the header changes, do a full VS rebuild
   (Development Editor / Win64). Watch for `Result: Succeeded`.
2. **Run** a maneuver so the values move:
   ```
   python python_listener.py --plant mmg --controller turning_circle --target unreal --verbose
   ```
   Press Play; wait past the 60 s approach so the ship turns.
3. **Verify** the log (after stopping):
   ```
   python Development\work_packets\WP_20260614_SENSORS\verify_sensors.py
   ```
   Expect `WP-SENSOR-1: PASS` — lat≈43.73, lon≈7.42, speed>0, yaw-rate non-zero during the turn.
4. Tell Claude: **"WP-SENSOR-1 passed"** → it closes the packet and starts WP-SENSOR-2 (camera capture).

## Acceptance gates
| Gate | Check | Method |
|------|-------|--------|
| S1 | `gps_latDeg`≈43.7, `gps_lonDeg`≈7.4 in sensor.csv | auto (verify_sensors.py) |
| S2 | `gps_speed` > 0 during the run | auto |
| S3 | `imu_yawRateDegPerSec` non-zero during the turn | auto |
| S4 | builds clean; closed loop still runs | manual (PIE) |

## Rollback
All changes are additive. To revert: `git checkout -- NaviSense_UE5/Source/NaviSense/Sensors NaviSense_UE5/Source/NaviSense/Vessel/NaviSenseShipPawn.h NaviSense_UE5/Source/NaviSense/Core/NaviSenseSimSubsystem.h` then recompile. The placeholder behaviour returns.

## Next packets (sensor + actuator suite)
- **WP-SENSOR-2** Camera (SceneCapture2D → JPEG + manifest) — D4.
- **WP-SENSOR-3** AIS — needs a traffic vessel first (depends on the traffic packet).
- **WP-SENSOR-4..6** Radar / LiDAR / Sonar (heavier; Phase C).
- **WP-ACTUATOR-RIG** — BLOCKED: needs the hull split into Hull/Rudder/Propeller_Port/Propeller_Stbd/BowThruster
  per `Documents/Yacht_Rhino_Part_Isolation_Guide.md`. Until then the actuator *data* is live but nothing
  visually moves. See the brief.
