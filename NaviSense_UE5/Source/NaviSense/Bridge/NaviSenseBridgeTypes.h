// Copyright NaviSyn Marine Solutions.
// =====================================================================
// Bridge DTOs — structs matching the NaviSense v1.1 wire contract.
// Field names are IDENTICAL to the JSON keys so FJsonObjectConverter maps
// them with no manual translation. Master Guide: Appendix A.
//
// Wire reference (Documents/BRIDGE_SCHEMA.md):
//   Python -> Sim : navisense.state.v1  (20-50 Hz)  -> FNaviSenseState
//   Sim -> Python : navisense.sensor.v1 (~5 Hz)      (built as JSON, see bundle)
// =====================================================================
#pragma once

#include "CoreMinimal.h"
#include "Bridge/NaviSenseTrafficTypes.h"
#include "NaviSenseBridgeTypes.generated.h"

/**
 * navisense.state.v1 — authoritative own-ship state from the Python plant.
 * Positions are METRES in Unity's frame; r is RAD/S (note: IMU yaw-rate is deg/s).
 */
USTRUCT(BlueprintType)
struct FNaviSenseState
{
    GENERATED_BODY()

    UPROPERTY() FString schema;
    UPROPERTY() FString runId;
    UPROPERTY() double  t = 0.0;

    // Pose (metres, Unity frame: x=East, y=Up, z=North) + heading (CW from North).
    UPROPERTY() double x = 0.0;
    UPROPERTY() double y = 0.0;
    UPROPERTY() double z = 0.0;
    UPROPERTY() double yawDeg = 0.0;

    // 6-DOF attitude (schema v1 rev 1.2): visual heel/trim proxy from the plant.
    // Defaults 0 => a v1.1 sender (no attitude) renders exactly as before.
    UPROPERTY() double rollDeg = 0.0;    // + = starboard-down (heel to starboard)
    UPROPERTY() double pitchDeg = 0.0;   // + = bow-up (trim)

    // 6-DOF heave (schema v1 rev 1.3): deterministic wave-field vertical bob (m, +up).
    // Default 0 => a v1.2 sender sits exactly at the waterline as before.
    UPROPERTY() double heaveM = 0.0;

    // Body-frame velocities: u surge (fwd), v sway (stbd+), r yaw rate (rad/s).
    UPROPERTY() double u = 0.0;
    UPROPERTY() double v = 0.0;
    UPROPERTY() double r = 0.0;

    // Actual actuator outputs the plant is producing.
    UPROPERTY() double portRpm = 0.0;
    UPROPERTY() double starboardRpm = 0.0;
    UPROPERTY() double rudderDeg = 0.0;          // port-positive
    UPROPERTY() double bowThrusterNorm = 0.0;    // [-1,1], + = bow-to-starboard

    // Most-recent commanded values (for logging / UI).
    UPROPERTY() double portRpmCmd = 0.0;
    UPROPERTY() double starboardRpmCmd = 0.0;
    UPROPERTY() double rudderCmdDeg = 0.0;
    UPROPERTY() double bowThrusterCmdNorm = 0.0;

    UPROPERTY() FString mode;   // idle | manual | auto | replay

    // Scripted AIS traffic for in-engine rendering (WP-15B). One entry per
    // contact; the pawn drives a mapped Traffic actor with each. TArray (not a
    // scalar) so the B1 parity guard still sees the 22 own-ship keys only.
    UPROPERTY() TArray<FNaviSenseTrafficTarget> traffic;
};
