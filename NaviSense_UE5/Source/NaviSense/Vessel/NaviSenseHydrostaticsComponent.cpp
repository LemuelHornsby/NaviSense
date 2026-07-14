// Copyright NaviSyn Marine Solutions.
#include "Vessel/NaviSenseHydrostaticsComponent.h"
#include "Vessel/NaviSenseHydrostaticsConfig.h"
#include "WaterBodyComponent.h"
#include "WaterBodyActor.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"

UNaviSenseHydrostaticsComponent::UNaviSenseHydrostaticsComponent()
{
    PrimaryComponentTick.bCanEverTick = false;  // driven by the pawn's Tick via Step()
}

void UNaviSenseHydrostaticsComponent::BeginPlay()
{
    Super::BeginPlay();
    CachedWaterBody = ResolveWaterBody();
}

UWaterBodyComponent* UNaviSenseHydrostaticsComponent::ResolveWaterBody()
{
    if (WaterBodyActor)
    {
        if (AWaterBody* WB = Cast<AWaterBody>(WaterBodyActor))
        {
            return WB->GetWaterBodyComponent();
        }
        return WaterBodyActor->FindComponentByClass<UWaterBodyComponent>();
    }
    if (UWorld* W = GetWorld())
    {
        for (TActorIterator<AWaterBody> It(W); It; ++It)
        {
            if (UWaterBodyComponent* C = It->GetWaterBodyComponent())
            {
                return C;
            }
        }
    }
    return nullptr;
}

double UNaviSenseHydrostaticsComponent::SampleWaterHeightCm(const FVector& WorldLoc) const
{
    if (CachedWaterBody)
    {
        // UE 5.7 Water API: Try* variant (non-deprecated) returns success + handles
        // the query-failed case gracefully (we fall back to the flat sea level).
        const EWaterBodyQueryFlags Flags =
            EWaterBodyQueryFlags::ComputeLocation | EWaterBodyQueryFlags::IncludeWaves;
        // UE 5.7: TryQuery* RETURNS a TValueOrError (not a bool+out-param); the
        // optional 3rd arg is a known query Z, which we don't have -> pass empty.
        const TValueOrError<FWaterBodyQueryResult, EWaterBodyQueryError> Res =
            CachedWaterBody->TryQueryWaterInfoClosestToWorldLocation(WorldLoc, Flags, TOptional<float>());
        if (Res.HasValue())
        {
            return Res.GetValue().GetWaterSurfaceLocation().Z;
        }
    }
    return DefaultSeaLevelCm;
}

bool UNaviSenseHydrostaticsComponent::Step(double Dt, const FVector& HullWorldLocationCm, double YawDeg)
{
    if (!Config || Dt <= 0.0)
    {
        return false;
    }

    const double M_TO_CM = 100.0;
    const double CM_TO_M = 0.01;
    const FRotator YawRot(0.0, YawDeg, 0.0);

    // --- Longitudinal strips: heave mean + pitch slope (UE +X = forward) ---
    const int32 nLong = FMath::Clamp(LongitudinalSamples, 3, 41);
    const double halfSpanFwdCm = 0.5 * LongitudinalSampleSpan * Config->Lwl * M_TO_CM;
    double sumH = 0.0, sumArmH = 0.0, sumArmSq = 0.0;
    for (int32 i = 0; i < nLong; ++i)
    {
        const double t = (nLong <= 1) ? 0.0 : ((double)i / (nLong - 1)) * 2.0 - 1.0;
        const double armCm = t * halfSpanFwdCm;
        const FVector world = HullWorldLocationCm + YawRot.RotateVector(FVector(armCm, 0.0, 0.0));
        const double hCm = SampleWaterHeightCm(world);
        sumH += hCm;
        sumArmH += armCm * hCm;
        sumArmSq += armCm * armCm;
    }
    const double waveMeanCm = sumH / nLong;
    const double slopeLong = (sumArmSq > 1e-6) ? (sumArmH / sumArmSq) : 0.0;
    double pitchWaveRad = FMath::Atan(slopeLong);   // + = bow up

    // --- Transverse strips: roll slope (UE +Y = starboard) ---
    const int32 nTrans = FMath::Clamp(TransverseSamples, 3, 15);
    const double halfSpanStbdCm = 0.5 * TransverseSampleSpan * Config->B * M_TO_CM;
    double sumArmHt = 0.0, sumArmSqt = 0.0;
    for (int32 i = 0; i < nTrans; ++i)
    {
        const double t = (nTrans <= 1) ? 0.0 : ((double)i / (nTrans - 1)) * 2.0 - 1.0;
        const double armCm = t * halfSpanStbdCm;
        const FVector world = HullWorldLocationCm + YawRot.RotateVector(FVector(0.0, armCm, 0.0));
        const double hCm = SampleWaterHeightCm(world);
        sumArmHt += armCm * hCm;
        sumArmSqt += armCm * armCm;
    }
    const double slopeTrans = (sumArmSqt > 1e-6) ? (sumArmHt / sumArmSqt) : 0.0;
    double rollWaveRad = -FMath::Atan(slopeTrans);  // + = starboard down

    // Tuning + clamps.
    pitchWaveRad = FMath::Clamp(pitchWaveRad * WaveResponseScale,
                                -FMath::DegreesToRadians(MaxWavePitchDeg),
                                 FMath::DegreesToRadians(MaxWavePitchDeg));
    rollWaveRad = FMath::Clamp(rollWaveRad * WaveResponseScale,
                               -FMath::DegreesToRadians(MaxWaveRollDeg),
                                FMath::DegreesToRadians(MaxWaveRollDeg));

    const double eqM = waveMeanCm * CM_TO_M + WaterlineOffsetCm * CM_TO_M;
    const double designTrimRad = bApplyDesignTrim ? FMath::DegreesToRadians(Config->DesignTrimDegByStern) : 0.0;
    const double pitchTargetRad = designTrimRad + pitchWaveRad;
    const double rollTargetRad = rollWaveRad;

    // Seed at equilibrium on the first call (no startup jolt).
    if (!bInit)
    {
        bInit = true;
        HeaveYM = eqM;          HeaveVelMps = 0.0;
        PitchRad = pitchTargetRad; PitchRateRps = 0.0;
        RollRad = rollTargetRad;   RollRateRps = 0.0;
    }

    // Heave: m_eff*a = -k*(y-eq) - b*v
    {
        const double k = Config->HeaveStiffness();
        const double b = Config->HeaveDampingCoef();
        const double m = FMath::Max(Config->EffectiveHeaveMass(), 1.0);
        const double a = (-k * (HeaveYM - eqM) - b * HeaveVelMps) / m;
        HeaveVelMps += a * Dt;
        HeaveYM += HeaveVelMps * Dt;
    }
    // Pitch: I_eff*a = -k*sin(th-target) - b*w
    {
        const double k = Config->PitchStiffness();
        const double b = Config->PitchDampingCoef();
        const double I = FMath::Max(Config->EffectivePitchInertia(), 1.0);
        const double a = (-k * FMath::Sin(PitchRad - pitchTargetRad) - b * PitchRateRps) / I;
        PitchRateRps += a * Dt;
        const double cap = FMath::DegreesToRadians(PitchRateLimitDps);
        PitchRateRps = FMath::Clamp(PitchRateRps, -cap, cap);
        PitchRad += PitchRateRps * Dt;
    }
    // Roll: I_eff*a = -k*sin(phi-target) - b*w
    {
        const double k = Config->RollStiffness();
        const double b = Config->RollDampingCoef();
        const double I = FMath::Max(Config->EffectiveRollInertia(), 1.0);
        const double a = (-k * FMath::Sin(RollRad - rollTargetRad) - b * RollRateRps) / I;
        RollRateRps += a * Dt;
        const double cap = FMath::DegreesToRadians(RollRateLimitDps);
        RollRateRps = FMath::Clamp(RollRateRps, -cap, cap);
        RollRad += RollRateRps * Dt;
    }

    HeaveZCm = HeaveYM * M_TO_CM;
    PitchDeg = FMath::RadiansToDegrees(PitchRad);
    RollDeg = FMath::RadiansToDegrees(RollRad);
    return true;
}
