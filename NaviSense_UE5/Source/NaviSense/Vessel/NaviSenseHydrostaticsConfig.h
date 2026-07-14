// Copyright NaviSyn Marine Solutions.
// =====================================================================
// UNaviSenseHydrostaticsConfig — data asset porting the Unity
// HydrostaticsConfig (ScriptableObject). Holds the per-vessel naval-
// architecture inputs and exposes the derived restoring/period/damping
// quantities used by UNaviSenseHydrostaticsComponent. Defaults = DOLPHIN
// Explorer Yacht (Group 4, Ship Design 2025). All inputs are SI
// (metres, tonnes->kg, seconds). Tune in the editor; no recompile.
// Mirrors NaviSense Simulator/Assets/Scripts/Hydrostatics/HydrostaticsConfig.cs
// =====================================================================
#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "NaviSenseHydrostaticsConfig.generated.h"

UCLASS(BlueprintType)
class NAVISENSE_API UNaviSenseHydrostaticsConfig : public UPrimaryDataAsset
{
    GENERATED_BODY()

public:
    // ---- Main dimensions (m) --------------------------------------------
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Main") double LOA = 40.0;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Main") double Lwl = 38.0;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Main") double B = 8.11;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Main") double T = 2.177;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Main") double Freeboard = 1.80;

    // ---- Mass and centres -----------------------------------------------
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Mass") double DisplacementTonnes = 366.0;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Mass") double VCG = 3.50;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Mass") double LCG = 18.0;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Mass") double DesignTrimDegByStern = 1.08;

    // ---- Waterplane ------------------------------------------------------
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Waterplane") double LCF = 17.594;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Waterplane") double TPc = 2.641;  // t/cm
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Waterplane") double Cwp = 0.799;

    // ---- Stability (metacentric heights, m) -----------------------------
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Stability") double GMt = 1.044;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Stability") double GMl = 68.154;

    // ---- Inertia (radii of gyration, fractions) -------------------------
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Inertia", meta=(ClampMin="0.25",ClampMax="0.50")) double RollRadiusOfGyrationFrac = 0.38;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Inertia", meta=(ClampMin="0.20",ClampMax="0.30")) double PitchRadiusOfGyrationFrac = 0.25;

    // ---- Added mass / inertia (fractions) -------------------------------
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="AddedMass", meta=(ClampMin="0.2",ClampMax="1.0")) double HeaveAddedMassFrac = 0.50;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="AddedMass", meta=(ClampMin="0.1",ClampMax="0.5")) double RollAddedInertiaFrac = 0.20;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="AddedMass", meta=(ClampMin="0.1",ClampMax="0.5")) double PitchAddedInertiaFrac = 0.25;

    // ---- Damping ratios (fraction of critical) --------------------------
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Damping", meta=(ClampMin="0.05",ClampMax="1.0")) double HeaveDampingRatio = 0.30;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Damping", meta=(ClampMin="0.02",ClampMax="0.50")) double RollDampingRatio = 0.10;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Damping", meta=(ClampMin="0.05",ClampMax="1.0")) double PitchDampingRatio = 0.30;

    // ---- Environment ----------------------------------------------------
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Environment") double WaterDensity = 1025.0;  // kg/m^3
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Environment") double Gravity = 9.81;          // m/s^2

    // ===== Derived quantities (match HydrostaticsConfig.cs) ==============
    /** Structural mass (kg). */
    UFUNCTION(BlueprintPure, Category="Derived") double Mass() const { return DisplacementTonnes * 1000.0; }

    /** Waterplane area (m^2): from TPc if available, else Cwp*Lwl*B. */
    UFUNCTION(BlueprintPure, Category="Derived") double Awp() const
    {
        if (TPc > 1e-6) { return TPc * 1000.0 / WaterDensity * 100.0; }  // (t/cm)->kg/m->m^2
        return Cwp * Lwl * B;
    }

    UFUNCTION(BlueprintPure, Category="Derived") double HeaveStiffness() const { return WaterDensity * Gravity * Awp(); }
    UFUNCTION(BlueprintPure, Category="Derived") double EffectiveHeaveMass() const { return Mass() * (1.0 + HeaveAddedMassFrac); }

    UFUNCTION(BlueprintPure, Category="Derived") double RollInertia() const
    {
        const double k = RollRadiusOfGyrationFrac * B; return Mass() * k * k;
    }
    UFUNCTION(BlueprintPure, Category="Derived") double EffectiveRollInertia() const { return RollInertia() * (1.0 + RollAddedInertiaFrac); }

    UFUNCTION(BlueprintPure, Category="Derived") double PitchInertia() const
    {
        const double k = PitchRadiusOfGyrationFrac * LOA; return Mass() * k * k;
    }
    UFUNCTION(BlueprintPure, Category="Derived") double EffectivePitchInertia() const { return PitchInertia() * (1.0 + PitchAddedInertiaFrac); }

    UFUNCTION(BlueprintPure, Category="Derived") double RollStiffness() const { return Mass() * Gravity * GMt; }
    UFUNCTION(BlueprintPure, Category="Derived") double PitchStiffness() const { return Mass() * Gravity * GMl; }

    UFUNCTION(BlueprintPure, Category="Derived") double HeaveNaturalPeriod() const
    { return 2.0 * PI * FMath::Sqrt(EffectiveHeaveMass() / FMath::Max(HeaveStiffness(), 1e-6)); }
    UFUNCTION(BlueprintPure, Category="Derived") double RollNaturalPeriod() const
    { return 2.0 * PI * FMath::Sqrt(EffectiveRollInertia() / FMath::Max(RollStiffness(), 1e-6)); }
    UFUNCTION(BlueprintPure, Category="Derived") double PitchNaturalPeriod() const
    { return 2.0 * PI * FMath::Sqrt(EffectivePitchInertia() / FMath::Max(PitchStiffness(), 1e-6)); }

    UFUNCTION(BlueprintPure, Category="Derived") double HeaveDampingCoef() const
    { return 2.0 * HeaveDampingRatio * FMath::Sqrt(HeaveStiffness() * EffectiveHeaveMass()); }
    UFUNCTION(BlueprintPure, Category="Derived") double RollDampingCoef() const
    { return 2.0 * RollDampingRatio * FMath::Sqrt(RollStiffness() * EffectiveRollInertia()); }
    UFUNCTION(BlueprintPure, Category="Derived") double PitchDampingCoef() const
    { return 2.0 * PitchDampingRatio * FMath::Sqrt(PitchStiffness() * EffectivePitchInertia()); }
};
