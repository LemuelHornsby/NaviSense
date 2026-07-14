// Copyright NaviSyn Marine Solutions.
// =====================================================================
// USensorBundleComponent — aggregates enabled sensors into the sensors{}
// block of navisense.sensor.v1. Phase 6 adds the real GPS/IMU/AIS/Camera/
// Radar/LiDAR/Sonar components; this Phase-1 stub emits a valid minimal
// block (time + zeroed gps/imu) so the bridge round-trips end-to-end now.
// Master Guide: Section 9.8.
// =====================================================================
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Dom/JsonObject.h"
#include "SensorBundleComponent.generated.h"

class UNaviSenseSimSubsystem;

UCLASS(ClassGroup = NaviSense, meta = (BlueprintSpawnableComponent))
class NAVISENSE_API USensorBundleComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    USensorBundleComponent();

    virtual void BeginPlay() override;

    /** Build the 'sensors' JSON block. Phase 6 will iterate real sub-sensors. */
    TSharedRef<FJsonObject> BuildSensorsJson();

    /** Emit a placeholder gps/imu block so Python sees a well-formed packet. */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Sensors")
    bool bEmitPlaceholderUntilPhase6 = true;

    /** Optional sensor noise (0 = perfect sensor). */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Sensors")
    float GpsPositionNoiseM = 0.f;

    UPROPERTY(EditAnywhere, Category = "NaviSense|Sensors")
    float ImuYawRateNoiseDegPerSec = 0.f;

    // ---- Camera (WP-14, still-frame metadata sensor) ----
    // Emits sensor.v1 camera{} capture metadata (pose/FOV/resolution + a
    // deterministic frameRef) matching the HighResShot stills the WP-20260630
    // 08_capture_demo_stills.py burst writes. NOT a live in-band pixel feed
    // (KI-026 honesty): the pixels come from the separate HighResShot capture.
    UPROPERTY(EditAnywhere, Category = "NaviSense|Sensors|Camera")
    bool bEmitCamera = true;

    /** Camera horizontal field of view, degrees (matches the chase-cam rig). */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Sensors|Camera")
    float CameraFovDeg = 90.f;

    /** Still-capture output resolution (HighResShot 4K default). */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Sensors|Camera")
    int32 CameraResX = 3840;

    UPROPERTY(EditAnywhere, Category = "NaviSense|Sensors|Camera")
    int32 CameraResY = 2160;

    /** Still-frame filename prefix (matches HighResShot Screenshots naming). */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Sensors|Camera")
    FString CameraFramePrefix = TEXT("NaviSense_");


    // ---- Radar (WP-20260702, Sensor Suite Roadmap Pt 1) ----
    // Emits sensor.v1 radar{maxRangeM,sweepDeg,contacts[]} -- ANONYMOUS blips
    // (range/bearing/radial-speed/closing) for scripted contacts within range.
    // HONESTY (KI-027): a GEOMETRIC radar model derived from the known contact
    // set, NOT an EM-propagation/RCS radar simulation (no clutter/false alarms).
    UPROPERTY(EditAnywhere, Category = "NaviSense|Sensors|Radar")
    bool bEmitRadar = true;

    /** Max radar detection range, metres (default 12 NM). Contacts beyond are not reported. */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Sensors|Radar")
    float RadarMaxRangeM = 22224.f;

private:
    UPROPERTY() TObjectPtr<UNaviSenseSimSubsystem> Sim = nullptr;

    // Acceleration is finite-differenced across BuildSensorsJson() calls.
    FVector PrevBodyVelMPS = FVector::ZeroVector;
    double  PrevSampleTime = -1.0;

    // Monotonic still-frame index for the camera sensor's deterministic frameRef.
    int32   CameraFrameIndex = 0;
};
