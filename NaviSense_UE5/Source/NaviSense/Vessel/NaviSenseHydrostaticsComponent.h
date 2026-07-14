// Copyright NaviSyn Marine Solutions.
// =====================================================================
// UNaviSenseHydrostaticsComponent — analytic (kinematic) port of the Unity
// HydrostaticsController. Python (MMG plant) owns X/Y/yaw; this component
// owns heave (world Z), roll and pitch. Each tick it samples the rendered
// water surface along hull strips (mean -> heave target, least-squares
// slopes -> pitch/roll targets) and integrates three damped oscillators
// using the design stiffness/inertia/damping from UNaviSenseHydrostaticsConfig.
// No Chaos physics body: the math is integrated here (semi-implicit Euler),
// so the hull settles at the real waterline by buoyancy equilibrium and
// rides waves realistically, while the pawn stays kinematic.
//
// Mirrors: NaviSense Simulator/Assets/Scripts/Hydrostatics/HydrostaticsController.cs
// Coordinate frame (UE, per NaviSenseCoords.h): X=North/forward, Y=East/starboard,
// Z=Up. Pitch + = bow up; Roll + = starboard down (matches WirePitch/RollToUE).
// =====================================================================
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "NaviSenseHydrostaticsComponent.generated.h"

class UNaviSenseHydrostaticsConfig;
class UWaterBodyComponent;

UCLASS(ClassGroup=(NaviSense), meta=(BlueprintSpawnableComponent))
class NAVISENSE_API UNaviSenseHydrostaticsComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UNaviSenseHydrostaticsComponent();

    /** Per-vessel naval-architecture data (DOLPHIN by default). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Hydrostatics")
    TObjectPtr<UNaviSenseHydrostaticsConfig> Config;

    /** Optional explicit water body actor; if null, the first AWaterBody found is used. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Hydrostatics")
    TObjectPtr<AActor> WaterBodyActor;

    /** Flat-sea fallback (UE world Z, cm) when no water body is resolved. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Hydrostatics")
    double DefaultSeaLevelCm = 0.0;

    /** Signed offset (cm) between the hull-root origin and the design waterline.
        Tune so the painted waterline sits at the sea surface (≈ freeboard above
        the sampled surface, minus any keel-origin offset). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Hydrostatics")
    double WaterlineOffsetCm = 0.0;

    // --- Sampling geometry (mirror the Unity controller) ---
    UPROPERTY(EditAnywhere, Category="Hydrostatics|Sampling", meta=(ClampMin="3",ClampMax="41")) int32 LongitudinalSamples = 15;
    UPROPERTY(EditAnywhere, Category="Hydrostatics|Sampling", meta=(ClampMin="3",ClampMax="15")) int32 TransverseSamples = 5;
    UPROPERTY(EditAnywhere, Category="Hydrostatics|Sampling", meta=(ClampMin="0.5",ClampMax="1.0")) double LongitudinalSampleSpan = 0.95;
    UPROPERTY(EditAnywhere, Category="Hydrostatics|Sampling", meta=(ClampMin="0.5",ClampMax="1.0")) double TransverseSampleSpan = 0.95;

    // --- Wave-excitation tuning ---
    UPROPERTY(EditAnywhere, Category="Hydrostatics|Tuning", meta=(ClampMin="0.1",ClampMax="1.5")) double WaveResponseScale = 1.0;
    UPROPERTY(EditAnywhere, Category="Hydrostatics|Tuning", meta=(ClampMin="1.0",ClampMax="15.0")) double MaxWavePitchDeg = 5.0;
    UPROPERTY(EditAnywhere, Category="Hydrostatics|Tuning", meta=(ClampMin="1.0",ClampMax="25.0")) double MaxWaveRollDeg = 10.0;
    UPROPERTY(EditAnywhere, Category="Hydrostatics|Tuning") bool bApplyDesignTrim = true;

    // --- Safety rate clamps (deg/s) ---
    UPROPERTY(EditAnywhere, Category="Hydrostatics|Limits") double RollRateLimitDps = 120.0;
    UPROPERTY(EditAnywhere, Category="Hydrostatics|Limits") double PitchRateLimitDps = 60.0;

    /** Advance the integrator by Dt. HullWorldLocationCm is where the hull is
        horizontally (Python-owned X/Y) at the current Z; YawDeg is the hull heading.
        Returns false (and does nothing) if Config is unset. */
    bool Step(double Dt, const FVector& HullWorldLocationCm, double YawDeg);

    UFUNCTION(BlueprintPure, Category="Hydrostatics") double GetHeaveZCm() const { return HeaveZCm; }
    UFUNCTION(BlueprintPure, Category="Hydrostatics") double GetRollDeg() const  { return RollDeg; }
    UFUNCTION(BlueprintPure, Category="Hydrostatics") double GetPitchDeg() const { return PitchDeg; }
    UFUNCTION(BlueprintPure, Category="Hydrostatics") bool IsReady() const { return Config != nullptr; }

    /** Re-seed at equilibrium on the next Step (call when a run restarts). */
    void ResetState() { bInit = false; }

protected:
    virtual void BeginPlay() override;

private:
    /** Surface Z (cm, UE world) at a world location. Isolated so the exact UE
        Water API is in ONE place (verify on first compile). Falls back to flat. */
    double SampleWaterHeightCm(const FVector& WorldLoc) const;
    UWaterBodyComponent* ResolveWaterBody();

    UPROPERTY(Transient) TObjectPtr<UWaterBodyComponent> CachedWaterBody = nullptr;

    // Integrator state — SI (metres, radians).
    double HeaveYM = 0.0, HeaveVelMps = 0.0;
    double PitchRad = 0.0, PitchRateRps = 0.0;
    double RollRad = 0.0,  RollRateRps = 0.0;
    bool   bInit = false;

    // Outputs — UE units.
    double HeaveZCm = 0.0, RollDeg = 0.0, PitchDeg = 0.0;
};
