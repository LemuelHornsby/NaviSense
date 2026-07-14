// Copyright NaviSyn Marine Solutions.
#include "Vessel/NaviSenseShipPawn.h"
#include "Vessel/ActuatorComponent.h"
#include "Vessel/NaviSenseVesselProfile.h"
#include "Vessel/NaviSenseHydrostaticsComponent.h"
#include "Bridge/NaviSenseBridgeComponent.h"
#include "Sensors/SensorBundleComponent.h"
#include "Core/NaviSenseCoords.h"
#include "Core/NaviSenseSimSubsystem.h"
#include "NaviSense.h"

#include "Components/StaticMeshComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Engine/Engine.h"
#include "Kismet/GameplayStatics.h"

ANaviSenseShipPawn::ANaviSenseShipPawn()
{
    PrimaryActorTick.bCanEverTick = true;

    Hull = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Hull"));
    SetRootComponent(Hull);
    Hull->SetMobility(EComponentMobility::Movable);

    Actuators = CreateDefaultSubobject<UActuatorComponent>(TEXT("Actuators"));
    Bridge    = CreateDefaultSubobject<UNaviSenseBridgeComponent>(TEXT("Bridge"));
    Sensors   = CreateDefaultSubobject<USensorBundleComponent>(TEXT("Sensors"));
    Hydrostatics = CreateDefaultSubobject<UNaviSenseHydrostaticsComponent>(TEXT("Hydrostatics"));
    Bridge->SensorBundle = Sensors;   // auto-wire: sensor packets always carry IMU heading

    SpringArm = CreateDefaultSubobject<USpringArmComponent>(TEXT("SpringArm"));
    SpringArm->SetupAttachment(Hull);
    SpringArm->TargetArmLength = 2500.f;
    SpringArm->SocketOffset = FVector(0.f, 0.f, 800.f);
    SpringArm->bEnableCameraLag = true;

    Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
    Camera->SetupAttachment(SpringArm);
}

void ANaviSenseShipPawn::BeginPlay()
{
    Super::BeginPlay();
    // Capture the placed transform as the run origin (KI-020 spawn anchoring).
    SpawnLocation = GetActorLocation();
    SpawnYawDeg   = GetActorRotation().Yaw;
    // Resolve scripted-traffic actors (WP-15B): if none assigned, gather every
    // actor tagged TrafficActorTag (stable slot order by name); force each Movable.
    if (TrafficActors.Num() == 0 && TrafficActorTag != NAME_None)
    {
        TArray<AActor*> Found;
        UGameplayStatics::GetAllActorsWithTag(this, TrafficActorTag, Found);
        Found.Sort([](const AActor& A, const AActor& B){ return A.GetName().Compare(B.GetName()) < 0; });
        for (AActor* A : Found) { TrafficActors.Add(A); }
    }
    for (const TObjectPtr<AActor>& A : TrafficActors)
    {
        if (A && A->GetRootComponent())
        {
            A->GetRootComponent()->SetMobility(EComponentMobility::Movable);
        }
    }
    ResolveActuatorVizComponents();
}

void ANaviSenseShipPawn::ResolveActuatorVizComponents()
{
    TArray<USceneComponent*> Comps;
    GetComponents<USceneComponent>(Comps);
    for (USceneComponent* C : Comps)
    {
        if (!C) { continue; }
        const FString N = C->GetName().ToLower();
        if (!RudderViz && N.Contains(TEXT("rudder")))
        {
            RudderViz = C; RudderBaseRot = C->GetRelativeRotation();
        }
        else if (N.Contains(TEXT("propeller")) || N.Contains(TEXT("prop")))
        {
            // Twin screws: assign by side keyword; else first generic prop is the
            // single merged-mesh fallback (KI-023, until the FBX is split).
            if (!PortPropViz && (N.Contains(TEXT("port")) || N.Contains(TEXT("_p")) || N.Contains(TEXT("left"))))
            {
                PortPropViz = C; PortPropBaseRot = C->GetRelativeRotation();
            }
            else if (!StbdPropViz && (N.Contains(TEXT("star")) || N.Contains(TEXT("stbd")) || N.Contains(TEXT("_s")) || N.Contains(TEXT("right"))))
            {
                StbdPropViz = C; StbdPropBaseRot = C->GetRelativeRotation();
            }
            else if (!PortPropViz && !StbdPropViz && !LegacyPropViz)
            {
                LegacyPropViz = C; LegacyPropBaseRot = C->GetRelativeRotation();
            }
        }
        else if (!BowThrusterViz && N.Contains(TEXT("bow")))
        {
            BowThrusterViz = C; BowBaseRot = C->GetRelativeRotation();
        }
    }
    UE_LOG(LogNaviSense, Display, TEXT("ActuatorViz resolved: rudder=%s propeller=%s bow=%s"),
        RudderViz ? TEXT("ok") : TEXT("MISSING"),
        (PortPropViz || StbdPropViz) ? TEXT("twin") : (LegacyPropViz ? TEXT("single-merged") : TEXT("MISSING")),
        BowThrusterViz ? TEXT("ok") : TEXT("MISSING"));
}

void ANaviSenseShipPawn::UpdateActuatorVisuals(float Dt)
{
    if (!Actuators) { return; }
    const FActuatorState& St = Actuators->State;

    // Rudder: absolute deflection about its local vertical (yaw), preserving authored base.
    if (RudderViz)
    {
        const double MaxRud = VesselProfile ? VesselProfile->RudderMaxDeg : 35.0;
        const double Ang = RudderVisualSign * FMath::Clamp(St.RudderDeg, -MaxRud, MaxRud);
        RudderViz->SetRelativeRotation(RudderBaseRot);
        RudderViz->AddLocalRotation(FRotator(0.0, Ang, 0.0));
    }

    // Propellers: each spins about its own local shaft axis (roll), per-side RPM,
    // counter-rotating (Unity ActuatorVisualRig parity). KI-023: twin screws if the
    // FBX is split into port/stbd components; else the single merged mesh falls back
    // to one pivot at the average RPM until the split is done.
    auto SpinProp = [&](USceneComponent* P, const FRotator& Base, double& Accum, double Rpm, bool Invert)
    {
        if (!P) { return; }
        const double Sign = (Invert ? -1.0 : 1.0) * PropellerVisualSign;
        Accum = FMath::Fmod(Accum + Sign * (Rpm / 60.0) * 360.0 * Dt, 360.0);
        P->SetRelativeRotation(Base);
        P->AddLocalRotation(FRotator(0.0, 0.0, Accum));
    };
    SpinProp(PortPropViz, PortPropBaseRot, PortPropSpinDeg, St.PortRpm, bInvertPortProp);
    SpinProp(StbdPropViz, StbdPropBaseRot, StbdPropSpinDeg, St.StarboardRpm, bInvertStarboardProp);
    if (LegacyPropViz)
    {
        const double AvgRpm = 0.5 * (St.PortRpm + St.StarboardRpm);
        LegacyPropSpinDeg = FMath::Fmod(LegacyPropSpinDeg + PropellerVisualSign * (AvgRpm / 60.0) * 360.0 * Dt, 360.0);
        LegacyPropViz->SetRelativeRotation(LegacyPropBaseRot);
        LegacyPropViz->AddLocalRotation(FRotator(0.0, 0.0, LegacyPropSpinDeg));
    }

    // Bow thruster: spin proportional to commanded normalised thrust.
    if (BowThrusterViz)
    {
        BowSpinDeg = FMath::Fmod(BowSpinDeg + St.BowThrusterNorm * BowThrusterMaxSpinDegPerSec * Dt, 360.0);
        BowThrusterViz->SetRelativeRotation(BowBaseRot);
        BowThrusterViz->AddLocalRotation(FRotator(0.0, 0.0, BowSpinDeg));
    }
}

void ANaviSenseShipPawn::ApplyOwnShipState(const FNaviSenseState& S)
{
    // Convert wire (m, Y-up) -> UE (cm, Z-up). Single source of truth (invariant #1).
    const FVector WireCm  = FNaviSenseCoords::WireToUE(S.x, S.y, S.z);
    const double  WireYaw = FNaviSenseCoords::WireYawToUE(S.yawDeg);
    if (bAnchorPoseToSpawn)
    {
        // Anchor to the placed transform: rotate the plant's horizontal displacement
        // into the spawn heading and add it to the spawn location, so every run
        // starts/stays where the yacht is placed (not the wire origin). Z stays as the
        // wire maps it (water level + freeboard + heave applied in Tick), so the hull
        // always rides the surface regardless of the placed Z. (KI-020)
        const FRotator SpawnRot(0.0, SpawnYawDeg, 0.0);
        const FVector  Horiz = SpawnRot.RotateVector(FVector(WireCm.X, WireCm.Y, 0.0));
        TargetLocation = FVector(SpawnLocation.X + Horiz.X, SpawnLocation.Y + Horiz.Y, WireCm.Z);
        TargetYawDeg   = FNaviSenseCoords::WireYawToUE(SpawnYawDeg + WireYaw);
    }
    else
    {
        TargetLocation = WireCm;
        TargetYawDeg   = WireYaw;
    }
    TargetPitchDeg   = FNaviSenseCoords::WirePitchToUE(S.pitchDeg);
    TargetRollDeg    = FNaviSenseCoords::WireRollToUE(S.rollDeg);
    TargetHeaveCm    = FNaviSenseCoords::WireHeaveToUE(S.heaveM);
    BodyVelCmPerSec  = FVector(S.u, S.v, 0.0) * FNaviSenseCoords::M_TO_CM;
    YawRateDeg       = FNaviSenseCoords::YawRateRadToDeg(S.r);
    bHasTarget       = true;
    bBridgeStale     = false;   // fresh data — resume normal pose tracking

    if (Actuators)
    {
        Actuators->SetFromState(S);   // push actual + commanded for rig + HUD
    }
    LastPlantMode = S.mode;   // dashboard maneuver panel (WP_20260701)
}

void ANaviSenseShipPawn::ApplyTraffic(const TArray<FNaviSenseTrafficTarget>& Targets)
{
    LastTraffic = Targets;   // keep the full contact list for the AIS sensor feed
    const int32 N = FMath::Min(Targets.Num(), TrafficActors.Num());
    for (int32 i = 0; i < N; ++i)
    {
        AActor* Actor = TrafficActors[i];
        if (!Actor) { continue; }
        const FNaviSenseTrafficTarget& T = Targets[i];
        // Same wire->UE conversion as own-ship (invariant #1).
        const FVector WireCm  = FNaviSenseCoords::WireToUE(T.x, T.y, T.z);
        const double  WireYaw = FNaviSenseCoords::WireYawToUE(T.yawDeg);
        FVector NewLoc;
        double  NewYaw;
        if (bAnchorTrafficToSpawn)
        {
            // Anchor to OWN-SHIP's spawn (the AIS origin), exactly like own-ship,
            // so the relative encounter geometry matches the scripted preset.
            const FRotator SpawnRot(0.0, SpawnYawDeg, 0.0);
            const FVector  Horiz = SpawnRot.RotateVector(FVector(WireCm.X, WireCm.Y, 0.0));
            NewLoc = FVector(SpawnLocation.X + Horiz.X, SpawnLocation.Y + Horiz.Y, 0.0);
            NewYaw = FNaviSenseCoords::WireYawToUE(SpawnYawDeg + WireYaw);
        }
        else
        {
            NewLoc = FVector(WireCm.X, WireCm.Y, 0.0);
            NewYaw = WireYaw;
        }
        // Keep the actor's PLACED Z (visual waterline the user set): these are
        // static props without hydrostatics, so we drive horizontal pose + heading.
        NewLoc.Z = Actor->GetActorLocation().Z;
        if (Actor->GetRootComponent()
            && Actor->GetRootComponent()->Mobility != EComponentMobility::Movable)
        {
            Actor->GetRootComponent()->SetMobility(EComponentMobility::Movable);
        }
        // KI-034: drive YAW only -- preserve the actor's PLACED pitch/roll (the
        // user's mesh-import axis correction, e.g. the 90-deg roll fix on the
        // excursion_vessel / Yacht_with_interior FBX). Captured once per actor.
        const FRotator* Placed = TrafficPlacedRot.Find(Actor);
        if (!Placed)
        {
            Placed = &TrafficPlacedRot.Add(Actor, Actor->GetActorRotation());
        }
        Actor->SetActorLocationAndRotation(NewLoc, FRotator(Placed->Pitch, NewYaw, Placed->Roll));
    }
}

void ANaviSenseShipPawn::NotifyBridgeStale()
{
    // Snap the interpolation target to where we are right now and zero the
    // motion state, so a missing/late plant stream can never make the pawn
    // coast, overshoot, or drift. It simply holds until fresh state arrives.
    bBridgeStale    = true;
    TargetLocation  = GetActorLocation();
    TargetYawDeg    = GetActorRotation().Yaw;
    TargetPitchDeg  = GetActorRotation().Pitch;
    TargetRollDeg   = GetActorRotation().Roll;
    TargetHeaveCm   = CurrentHeaveCm;   // freeze the bob where it is (no drift)
    BodyVelCmPerSec = FVector::ZeroVector;
    YawRateDeg      = 0.0;
    UE_LOG(LogNaviSense, Warning, TEXT("Bridge stale — pawn holding position."));
}

void ANaviSenseShipPawn::Tick(float Dt)
{
    Super::Tick(Dt);

    // Runtime fallback toggle: tap 'M' to flip Manual <-> PoseReceive so a dead
    // Python bridge never means a dead demo (WP-6, F4).
    if (bAllowManualToggleKey)
    {
        if (APlayerController* PC = Cast<APlayerController>(GetController()))
        {
            const bool bM = PC->IsInputKeyDown(EKeys::M);
            if (bM && !bManualTogglePrev)
            {
                MotionSource = (MotionSource == ENaviSenseMotionSource::Manual)
                    ? ENaviSenseMotionSource::PoseReceive
                    : ENaviSenseMotionSource::Manual;
                if (MotionSource == ENaviSenseMotionSource::Manual)
                {
                    ManualSpeedCmS = BodyVelCmPerSec.X;   // seed from last known: no jolt
                }
                if (GEngine)
                {
                    GEngine->AddOnScreenDebugMessage(7702, 2.5f, FColor::Cyan,
                        FString::Printf(TEXT("NaviSense motion: %s"),
                            MotionSource == ENaviSenseMotionSource::Manual
                                ? TEXT("MANUAL (W/S throttle, A/D rudder)")
                                : TEXT("POSE-RECEIVE (bridge)")));
                }
            }
            bManualTogglePrev = bM;
        }
    }

    if (MotionSource == ENaviSenseMotionSource::PoseReceive && bHasTarget)
    {
        const float Lerp = VesselProfile ? VesselProfile->PoseLerpSpeed : 12.f;

        // Smooth XY toward the bridge target; ride the wave-driven heave on Z
        // (schema v1.3). Sampling the *rendered* UE water surface is F1 pt3.
        // Master Guide Section 7.3.
        FVector Loc = FMath::VInterpTo(GetActorLocation(), TargetLocation, Dt, Lerp);
        CurrentHeaveCm = FMath::FInterpTo(CurrentHeaveCm, TargetHeaveCm, Dt, Lerp);
        // Vertical float height. When anchoring to the placed transform (KI-020), ride at
        // the PLACED waterline (SpawnLocation.Z) so the hull floats wherever the yacht is
        // positioned on the water -- independent of the world-origin water level / Cesium
        // georeference. KI-022: the hull was pinned to FreeboardCm above world Z=0, so it
        // hovered once moved to open water whose surface is not at Z=0. Heave bobs on top.
        // Per-wave ride on the *rendered* water mesh is still F1 pt3 (needs the Water module).
        const double FloatBaseZ = bAnchorPoseToSpawn
            ? SpawnLocation.Z
            : TargetLocation.Z + (VesselProfile ? VesselProfile->FreeboardCm : 150.0);
        Loc.Z = FloatBaseZ + CurrentHeaveCm;

        // 6-DOF heave/attitude SOURCE. When the analytic hydrostatics is active
        // (KI-022 port) it OWNS heave (world Z) + roll + pitch: it samples the rendered
        // water surface along hull strips and integrates the buoyancy/GM damped
        // oscillators from the DOLPHIN data, so the hull settles at the REAL waterline
        // and rides waves. Python still owns X/Y/yaw. Otherwise we fall back to the
        // visual proxy (wire rollDeg/pitchDeg/heaveM + placed-waterline Z above).
        double UsePitchDeg = TargetPitchDeg;
        double UseRollDeg  = TargetRollDeg;
        if (bUseHydrostatics && Hydrostatics && Hydrostatics->IsReady())
        {
            Hydrostatics->Step(Dt, FVector(Loc.X, Loc.Y, Loc.Z), TargetYawDeg);
            Loc.Z      = Hydrostatics->GetHeaveZCm();
            UsePitchDeg = Hydrostatics->GetPitchDeg();
            UseRollDeg  = Hydrostatics->GetRollDeg();
        }

        // SHORTEST-ANGLE rotation smoothing. FMath::FInterpTo on a raw Yaw scalar
        // spins the long way once heading passes +/-180 deg: the actor yaw is
        // normalized to [-180,180] but WireYawToUE returns [0,360), so past 180 deg
        // FInterpTo chases a ~360 deg gap that normalization keeps reopening and the
        // hull spins on the spot for the rest of any turn that accumulates >180 deg
        // of heading (e.g. a turning circle). RInterpTo builds a NORMALIZED delta
        // rotator, so each axis takes the short path. The wire->UE sign/axis mapping
        // still lives only in NaviSenseCoords (invariant #1). (KI-018)
        const FRotator TargetRot(UsePitchDeg, TargetYawDeg, UseRollDeg);  // (Pitch,Yaw,Roll)
        const FRotator Rot = FMath::RInterpTo(GetActorRotation(), TargetRot, Dt, Lerp);

        SetActorLocationAndRotation(Loc, Rot);
    }
    else if (MotionSource == ENaviSenseMotionSource::Manual)
    {
        UpdateManual(Dt);   // keyboard-driven kinematic fallback
    }

    UpdateActuatorVisuals(Dt);
    UpdateManeuverTelemetry();   // dashboard maneuver panel rolling proxies (WP_20260701)
}

void ANaviSenseShipPawn::UpdateManual(float Dt)
{
    // Poll keys straight off the possessing controller — no Input assets needed.
    // The bridge-dashboard widget (WP_20260701) takes over these targets once
    // it has issued its first Set* call, so helm/throttle/thruster from the UI
    // drive the ship exactly as W/S/A/D do (same [-1,1] range, same slew).
    float ThrTarget = 0.f, RudTarget = 0.f;
    if (bDashboardControlActive)
    {
        ThrTarget = DashboardThrottleCmd;
        RudTarget = DashboardRudderCmd;
    }
    else if (APlayerController* PC = Cast<APlayerController>(GetController()))
    {
        if (PC->IsInputKeyDown(EKeys::W) || PC->IsInputKeyDown(EKeys::Up))    { ThrTarget += 1.f; }
        if (PC->IsInputKeyDown(EKeys::S) || PC->IsInputKeyDown(EKeys::Down))  { ThrTarget -= 1.f; }
        if (PC->IsInputKeyDown(EKeys::D) || PC->IsInputKeyDown(EKeys::Right)) { RudTarget += 1.f; }
        if (PC->IsInputKeyDown(EKeys::A) || PC->IsInputKeyDown(EKeys::Left))  { RudTarget -= 1.f; }
    }

    // Slew inputs, then a first-order surge toward throttle*cruise (drag built in).
    ManualThrottle = FMath::FInterpTo(ManualThrottle, ThrTarget, Dt, ManualInputSlew);
    ManualRudder   = FMath::FInterpTo(ManualRudder,   RudTarget, Dt, ManualInputSlew);
    const float TargetSpeed = ManualThrottle * ManualCruiseSpeedCmS;
    ManualSpeedCmS = FMath::FInterpTo(ManualSpeedCmS, TargetSpeed, Dt, ManualAccel);

    // Yaw needs way: scale max yaw rate by current speed fraction.
    const float SpeedFrac = (ManualCruiseSpeedCmS > 1.f)
        ? FMath::Clamp(FMath::Abs(ManualSpeedCmS) / ManualCruiseSpeedCmS, 0.f, 1.f) : 0.f;
    // Bow thruster: works at ANY speed (real thrusters are most useful at zero
    // way, unlike the rudder which needs SpeedFrac). Additive yaw term.
    const float ThrusterYawRate = bDashboardControlActive
        ? DashboardBowThrusterCmd * BowThrusterMaxYawRateDeg : 0.f;
    const float YawRate = ManualRudder * ManualMaxYawRateDeg * SpeedFrac + ThrusterYawRate;   // deg/s

    FRotator Rot = GetActorRotation();
    Rot.Yaw += YawRate * Dt;

    // Advance along facing (UE +X = heading 0 = North), hold at the waterline.
    const FVector Fwd = FRotationMatrix(FRotator(0.f, Rot.Yaw, 0.f)).GetUnitAxis(EAxis::X);
    FVector Loc = GetActorLocation() + Fwd * (ManualSpeedCmS * Dt);
    Loc.Z = (VesselProfile ? VesselProfile->FreeboardCm : 150.0);
    SetActorLocationAndRotation(Loc, Rot);

    // Publish kinematics for sensors/VFX and feed the actuator-viz rig.
    BodyVelCmPerSec = FVector(ManualSpeedCmS, 0.f, 0.f);
    YawRateDeg      = YawRate;
    if (Actuators)
    {
        FNaviSenseState S;
        S.u            = ManualSpeedCmS * 0.01;   // m/s
        S.r            = FMath::DegreesToRadians(YawRate);
        S.rudderDeg    = ManualRudder * (VesselProfile ? VesselProfile->RudderMaxDeg : 35.0);
        S.portRpm      = ManualThrottle * 900.0;
        S.starboardRpm = S.portRpm;
        S.bowThrusterNorm = bDashboardControlActive ? DashboardBowThrusterCmd : 0.0;
        Actuators->SetFromState(S);
    }
}

void ANaviSenseShipPawn::SetupPlayerInputComponent(UInputComponent* Input)
{
    Super::SetupPlayerInputComponent(Input);
    // Enhanced Input bindings (throttle/rudder/bow/camera) are wired in Phase 4
    // / Phase 10. Left intentionally empty here so the class compiles standalone.
}

// ---- Wake / spray VFX feed (D5 / WP-16) ---------------------------------
// 0..1 scalars mirrored EXACTLY by python/wake_model.py (intensity01 / spray01);
// verify_20260628.py asserts the WakeFullSpeedMS/WakeSprayOnsetMS/WakeMinSpeedMS
// defaults here equal the Python constants so the rendered curve is the gated one.
float ANaviSenseShipPawn::GetWakeIntensity01() const
{
    const float V  = (float)GetSpeedMetersPerSec();
    const float Lo = WakeMinSpeedMS;
    const float Hi = FMath::Max(WakeFullSpeedMS, Lo + 0.001f);
    if (V <= Lo) { return 0.f; }
    return FMath::Clamp((V - Lo) / (Hi - Lo), 0.f, 1.f);
}

float ANaviSenseShipPawn::GetWakeSpray01() const
{
    const float V  = (float)GetSpeedMetersPerSec();
    const float Lo = WakeSprayOnsetMS;
    const float Hi = FMath::Max(WakeFullSpeedMS, Lo + 0.001f);
    if (V <= Lo) { return 0.f; }
    return FMath::Clamp((V - Lo) / (Hi - Lo), 0.f, 1.f);
}

// ---- Bridge Dashboard data + control layer (WP-UI-DASHBOARD / WP_20260701) --
// Getters read existing game-thread state (Actuators->State, actor transform,
// TrafficActors); no new fields on the wire DTO (invariant #3 stays 22/22).
double ANaviSenseShipPawn::GetRudderDeg() const
{
    return Actuators ? Actuators->State.RudderDeg : 0.0;
}

double ANaviSenseShipPawn::GetPortRpm() const
{
    return Actuators ? Actuators->State.PortRpm : 0.0;
}

double ANaviSenseShipPawn::GetStarboardRpm() const
{
    return Actuators ? Actuators->State.StarboardRpm : 0.0;
}

double ANaviSenseShipPawn::GetBowThrusterNorm() const
{
    return Actuators ? Actuators->State.BowThrusterNorm : 0.0;
}

double ANaviSenseShipPawn::GetHeadingDeg() const
{
    return FNaviSenseCoords::UEYawToWire(GetActorRotation().Yaw);
}

double ANaviSenseShipPawn::GetHeaveM() const
{
    return CurrentHeaveCm * FNaviSenseCoords::CM_TO_M;
}

// Same flat-earth projection SensorBundleComponent::BuildSensorsJson applies to
// the plant's GPS block (SensorBundleComponent.cpp is untouched this packet;
// verify_20260701.py parity-checks the shared 111320.0 constant).
double ANaviSenseShipPawn::GetLatDeg() const
{
    const UNaviSenseSimSubsystem* Sim = GetGameInstance()
        ? GetGameInstance()->GetSubsystem<UNaviSenseSimSubsystem>() : nullptr;
    const double Lat0 = Sim ? Sim->RefLatDeg : 43.7350;
    const FVector Wire = FNaviSenseCoords::UEToWire(GetActorLocation());
    return FNaviSenseCoords::NorthMToLatDeg(Wire.Z, Lat0);
}

double ANaviSenseShipPawn::GetLonDeg() const
{
    const UNaviSenseSimSubsystem* Sim = GetGameInstance()
        ? GetGameInstance()->GetSubsystem<UNaviSenseSimSubsystem>() : nullptr;
    const double Lat0 = Sim ? Sim->RefLatDeg : 43.7350;
    const double Lon0 = Sim ? Sim->RefLonDeg : 7.4250;
    const FVector Wire = FNaviSenseCoords::UEToWire(GetActorLocation());
    return FNaviSenseCoords::EastMToLonDeg(Wire.X, Lat0, Lon0);
}

FString ANaviSenseShipPawn::GetMotionModeLabel() const
{
    switch (MotionSource)
    {
        case ENaviSenseMotionSource::Manual:        return TEXT("Manual");
        case ENaviSenseMotionSource::NativePhysics: return TEXT("Native Physics");
        case ENaviSenseMotionSource::PoseReceive:
        default:                                    return TEXT("Pose-Receive (Bridge)");
    }
}

double ANaviSenseShipPawn::GetNearestTrafficRangeM() const
{
    double Best = -1.0;
    const FVector Here = GetActorLocation();
    for (const TObjectPtr<AActor>& A : TrafficActors)
    {
        if (!A) { continue; }
        const double D = FVector::Dist(Here, A->GetActorLocation()) * FNaviSenseCoords::CM_TO_M;
        if (Best < 0.0 || D < Best) { Best = D; }
    }
    return Best;
}

FString ANaviSenseShipPawn::GetNearestTrafficName() const
{
    double Best = -1.0;
    FString Name;
    const FVector Here = GetActorLocation();
    for (const TObjectPtr<AActor>& A : TrafficActors)
    {
        if (!A) { continue; }
        const double D = FVector::Dist(Here, A->GetActorLocation());
        if (Best < 0.0 || D < Best) { Best = D; Name = A->GetActorNameOrLabel(); }
    }
    return Name;
}

void ANaviSenseShipPawn::SetHelm(float Rudder01)
{
    DashboardRudderCmd = FMath::Clamp(Rudder01, -1.f, 1.f);
    bDashboardControlActive = true;
}

void ANaviSenseShipPawn::SetThrottle(float Throttle01)
{
    DashboardThrottleCmd = FMath::Clamp(Throttle01, -1.f, 1.f);
    bDashboardControlActive = true;
}

void ANaviSenseShipPawn::SetBowThruster(float Norm01)
{
    DashboardBowThrusterCmd = FMath::Clamp(Norm01, -1.f, 1.f);
    bDashboardControlActive = true;
}

void ANaviSenseShipPawn::UpdateManeuverTelemetry()
{
    // Live rolling proxies for the dashboard's maneuver/IMO panel (NOT the
    // validated post-run evidence-pack KPIs -- KI-019). Advance = cumulative
    // displacement projected onto the heading captured the first tick;
    // overshoot proxy = peak |heading deviation| from that same reference.
    const double HeadingNow = FNaviSenseCoords::UEYawToWire(GetActorRotation().Yaw);
    if (InitialHeadingDeg < 0.0)
    {
        InitialHeadingDeg = HeadingNow;
        LastLocationForAdvance = GetActorLocation();
        return;
    }
    const FVector Delta = GetActorLocation() - LastLocationForAdvance;
    const FVector InitialFwd = FRotationMatrix(
        FRotator(0.0, FNaviSenseCoords::WireYawToUE(InitialHeadingDeg), 0.0)).GetUnitAxis(EAxis::X);
    RollingAdvanceM += FVector::DotProduct(Delta, InitialFwd) * FNaviSenseCoords::CM_TO_M;
    LastLocationForAdvance = GetActorLocation();

    const double Dev = FMath::Abs(FMath::FindDeltaAngleDegrees(InitialHeadingDeg, HeadingNow));
    PeakHeadingDeviationDeg = FMath::Max(PeakHeadingDeviationDeg, Dev);
}
