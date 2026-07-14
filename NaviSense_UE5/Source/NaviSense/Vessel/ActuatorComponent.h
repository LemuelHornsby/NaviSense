// Copyright NaviSyn Marine Solutions.
// =====================================================================
// UActuatorComponent — holds actual + commanded rudder/RPM/thruster with
// rate limiting. In pose-receive mode the plant is authoritative (copy
// through). In manual/native mode it integrates toward commanded targets.
// Mirrors Unity's ActuatorController + per-actuator models.
// Master Guide: Section 7.4.
// =====================================================================
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Bridge/NaviSenseBridgeTypes.h"
#include "ActuatorComponent.generated.h"

class UNaviSenseVesselProfile;

USTRUCT(BlueprintType)
struct FActuatorState
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Actuators") double PortRpm = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Actuators") double StarboardRpm = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Actuators") double RudderDeg = 0.0;        // port-positive
    UPROPERTY(BlueprintReadOnly, Category = "Actuators") double BowThrusterNorm = 0.0;  // [-1,1]

    UPROPERTY(BlueprintReadOnly, Category = "Actuators") double PortRpmCmd = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Actuators") double StarboardRpmCmd = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Actuators") double RudderCmdDeg = 0.0;
    UPROPERTY(BlueprintReadOnly, Category = "Actuators") double BowThrusterCmdNorm = 0.0;
};

UCLASS(ClassGroup = NaviSense, meta = (BlueprintSpawnableComponent))
class NAVISENSE_API UActuatorComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UActuatorComponent();

    virtual void TickComponent(float Dt, ELevelTick, FActorComponentTickFunction*) override;

    UPROPERTY(EditAnywhere, Category = "Actuators")
    TObjectPtr<UNaviSenseVesselProfile> Profile;

    UPROPERTY(BlueprintReadOnly, Category = "Actuators")
    FActuatorState State;

    /** True when the plant (bridge) owns actuator values; false for manual/native. */
    UPROPERTY(EditAnywhere, Category = "Actuators")
    bool bPlantAuthoritative = true;

    // Manual / autopilot command entry (clamped + rate-limited in Tick).
    UFUNCTION(BlueprintCallable, Category = "Actuators") void CommandRudder(double Deg);
    UFUNCTION(BlueprintCallable, Category = "Actuators") void CommandThrottle(double Rpm);
    UFUNCTION(BlueprintCallable, Category = "Actuators") void CommandBowThruster(double Norm);

    /** Bridge fills both actual + commanded straight from the plant. */
    void SetFromState(const FNaviSenseState& S);
};
