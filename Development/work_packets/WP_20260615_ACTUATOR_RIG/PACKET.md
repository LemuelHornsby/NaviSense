# WP-ACTUATOR-RIG · 2026-06-15 · Actuator visual rig

**Theme:** Drive the BP part meshes (`Rudder`, `propeller`, `bowthruster`) from the live `FActuatorState`
so the rudder deflects, the propeller spins with RPM, and the bow thruster spins — completing the
*visual* half of the actuator suite. **D-gate:** vessel fidelity (Phase B); supports the demo film.
**Estimated human time:** ≤10 min (recompile + one run + eyeball).

## What was written (NaviSense_UE5/Source/NaviSense/Vessel)
| File | Change |
|------|--------|
| `NaviSenseShipPawn.h/.cpp` | `BeginPlay` resolves the part components by name (Rudder/propeller/bow*) and stores their base rotation; `UpdateActuatorVisuals(Dt)` (called each Tick) sets rudder yaw = ±RudderDeg (clamped to profile max), spins the propeller by avg RPM, and spins the bow thruster by commanded thrust — each applied on top of the authored base rotation. Sign flips exposed as `RudderVisualSign` / `PropellerVisualSign`; `BowThrusterMaxSpinDegPerSec`. |

**Matches your BP:** inspection (05_inspect_ship_pawn.py) confirmed `BP_ShipPawn_Yacht` derives from
`NaviSenseShipPawn`, profile `DA_DOLPHIN_VesselProfile`, components `Rudder` / `propeller` / `bowthruster`.

## Your in-editor steps (≤10 min)
1. **Recompile** — Ctrl+Alt+F11 (or full VS rebuild if it balks). On Play, the Output Log should print
   `ActuatorViz resolved: rudder=ok propeller=ok bow=ok`. If any says MISSING, tell me the component name.
2. **Run** a maneuver: `python python_listener.py --plant mmg --controller zigzag10 --target unreal --verbose`
   → Play, wait past the 60 s approach.
3. **Watch** (gate): the **rudder deflects** as the command alternates (and the bow swings the matching way),
   the **propeller spins** while RPM > 0. For the bow thruster, run `--controller turning_circle` or a docking
   scenario that commands it.
4. While you're here, also run `python Development\work_packets\WP_20260614_SENSORS\verify_sensors.py`
   to close **WP-SENSOR-1** in the same session.
5. Tell me: **"rig OK"** (and flag any part that turns the wrong way or about the wrong axis).

## Acceptance gates
| Gate | Check |
|------|-------|
| R1 | `ActuatorViz resolved: rudder=ok propeller=ok bow=ok` in the log |
| R2 | Rudder visibly deflects with the rudder command (correct direction) |
| R3 | Propeller spins while RPM > 0 (correct direction) |
| R4 | Bow thruster spins when commanded; no part detaches/jitters |

## If a part looks wrong
- Wrong **direction**: flip `RudderVisualSign` or `PropellerVisualSign` on the pawn (Details → NaviSense|ActuatorViz). No recompile needed.
- Wrong **axis** (spins about the wrong axis): tell me which part — it's a one-line change (the local rotation axis) and I'll adjust.

## Rollback
Additive. `git checkout -- NaviSense_UE5/Source/NaviSense/Vessel/NaviSenseShipPawn.h NaviSense_UE5/Source/NaviSense/Vessel/NaviSenseShipPawn.cpp` then recompile.

## Next (sensor + actuator suite)
- Confirm WP-SENSOR-1 (GPS/IMU) via verify_sensors.py.
- WP-SENSOR-2 camera capture; then traffic + AIS; then radar/LiDAR/sonar.
- Optional: engine-RPM sound; actuator HUD readout.
