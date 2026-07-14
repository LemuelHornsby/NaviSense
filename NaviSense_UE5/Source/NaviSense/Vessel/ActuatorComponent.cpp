// Copyright NaviSyn Marine Solutions.
#include "Vessel/ActuatorComponent.h"
#include "Vessel/NaviSenseVesselProfile.h"

namespace
{
    // Move 'cur' toward 'tgt' by at most 'maxStep'.
    FORCEINLINE double Slew(double cur, double tgt, double maxStep)
    {
        return cur + FMath::Clamp(tgt - cur, -maxStep, maxStep);
    }
}

UActuatorComponent::UActuatorComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
}

void UActuatorComponent::CommandRudder(double Deg)
{
    const double Limit = Profile ? Profile->RudderMaxDeg : 35.0;
    State.RudderCmdDeg = FMath::Clamp(Deg, -Limit, Limit);
}

void UActuatorComponent::CommandThrottle(double Rpm)
{
    const double Limit = Profile ? Profile->RpmMax : 1800.0;
    const double Clamped = FMath::Clamp(Rpm, -Limit, Limit);
    State.PortRpmCmd = Clamped;
    State.StarboardRpmCmd = Clamped;
}

void UActuatorComponent::CommandBowThruster(double Norm)
{
    State.BowThrusterCmdNorm = FMath::Clamp(Norm, -1.0, 1.0);
}

void UActuatorComponent::SetFromState(const FNaviSenseState& S)
{
    // Pose-receive: plant is authoritative — copy everything through.
    State.PortRpm = S.portRpm;
    State.StarboardRpm = S.starboardRpm;
    State.RudderDeg = S.rudderDeg;
    State.BowThrusterNorm = S.bowThrusterNorm;

    State.PortRpmCmd = S.portRpmCmd;
    State.StarboardRpmCmd = S.starboardRpmCmd;
    State.RudderCmdDeg = S.rudderCmdDeg;
    State.BowThrusterCmdNorm = S.bowThrusterCmdNorm;
}

void UActuatorComponent::TickComponent(float Dt, ELevelTick, FActorComponentTickFunction*)
{
    if (bPlantAuthoritative || !Profile)
    {
        return; // values come from SetFromState() each bridge packet
    }

    // Manual / native mode: integrate actual toward commanded with rate limits.
    State.RudderDeg     = Slew(State.RudderDeg,      State.RudderCmdDeg,      Profile->RudderRateDegPerSec * Dt);
    State.PortRpm       = Slew(State.PortRpm,        State.PortRpmCmd,        Profile->RpmRatePerSec       * Dt);
    State.StarboardRpm  = Slew(State.StarboardRpm,   State.StarboardRpmCmd,   Profile->RpmRatePerSec       * Dt);
    State.BowThrusterNorm = Slew(State.BowThrusterNorm, State.BowThrusterCmdNorm, Profile->ThrusterRatePerSec * Dt);
}
