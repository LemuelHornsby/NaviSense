// Copyright NaviSyn Marine Solutions.
// =====================================================================
// UNaviSenseVesselProfile — data asset mirroring Unity's hydrostatics +
// actuator-dynamics ScriptableObjects. Drives the ship pawn & actuators.
// Defaults are seeded with the DOLPHIN Explorer Yacht figures. Tune in the
// editor; no recompile needed. Master Guide: Section 3.4.
// =====================================================================
#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "NaviSenseVesselProfile.generated.h"

UCLASS(BlueprintType)
class NAVISENSE_API UNaviSenseVesselProfile : public UPrimaryDataAsset
{
    GENERATED_BODY()

public:
    // ---- Identity / hull -------------------------------------------------
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Vessel")
    FString DisplayName = TEXT("DOLPHIN Explorer Yacht");

    /** Length overall (m) — DOLPHIN ~40 m. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Vessel")
    double LengthOverallM = 40.0;

    /** Height of the hull root above the waterline (cm) used for the visual
        bob in pose-receive mode (so the hull sits ON the water, not in it). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Vessel")
    double FreeboardCm = 150.0;

    // ---- Actuator dynamics (rate limits, manual/native mode) -------------
    /** Rudder slew rate (deg/sec). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Actuators")
    double RudderRateDegPerSec = 8.0;

    /** Max rudder angle magnitude (deg). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Actuators")
    double RudderMaxDeg = 35.0;

    /** Propeller RPM slew rate (rpm/sec). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Actuators")
    double RpmRatePerSec = 300.0;

    /** Max propeller RPM magnitude. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Actuators")
    double RpmMax = 1800.0;

    /** Bow thruster normalised slew rate (units/sec, full range is [-1,1]). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Actuators")
    double ThrusterRatePerSec = 2.0;

    // ---- Pose smoothing --------------------------------------------------
    /** Interpolation speed toward the latest bridge pose target. Higher =
        tracks turns tighter; lower = hides packet jitter. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Motion")
    float PoseLerpSpeed = 12.f;
};
