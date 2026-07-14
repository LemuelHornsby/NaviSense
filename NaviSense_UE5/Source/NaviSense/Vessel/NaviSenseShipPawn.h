// Copyright NaviSyn Marine Solutions.
// =====================================================================
// ANaviSenseShipPawn — the own-ship. Pose-receive mode (parity path) applies
// x,y,yaw from the bridge with smoothing; native-physics/manual modes apply
// forces from the actuator component (offline). Mirrors Unity's
// YachtPoseApplier. Master Guide: Section 7 (and Section 8 for the bridge).
// =====================================================================
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "Bridge/NaviSenseBridgeTypes.h"
#include "NaviSenseShipPawn.generated.h"

class UStaticMeshComponent;
class UActuatorComponent;
class UNaviSenseBridgeComponent;
class USensorBundleComponent;
class UNaviSenseVesselProfile;
class UNaviSenseHydrostaticsComponent;
class USpringArmComponent;
class UCameraComponent;

UENUM(BlueprintType)
enum class ENaviSenseMotionSource : uint8
{
    PoseReceive,    // bridge is authoritative (parity path)
    NativePhysics,  // offline: forces from actuators
    Manual          // offline: keyboard/gamepad -> actuators -> forces
};

UCLASS()
class NAVISENSE_API ANaviSenseShipPawn : public APawn
{
    GENERATED_BODY()

public:
    ANaviSenseShipPawn();

    virtual void BeginPlay() override;
    virtual void Tick(float Dt) override;
    virtual void SetupPlayerInputComponent(UInputComponent* Input) override;

    UPROPERTY(EditAnywhere, Category = "NaviSense")
    ENaviSenseMotionSource MotionSource = ENaviSenseMotionSource::PoseReceive;

    // When true (default), the bridge pose is applied as an OFFSET from the pawn's
    // PLACED transform (captured at BeginPlay), so every run starts and stays where
    // the yacht is positioned in the level instead of snapping to the wire origin.
    // Disable only for absolute-world navigation (waypoint/NMPC to fixed coords). (KI-020)
    UPROPERTY(EditAnywhere, Category = "NaviSense")
    bool bAnchorPoseToSpawn = true;

    // When true (default), the analytic hydrostatics component owns heave/roll/pitch
    // (samples the real water surface; DOLPHIN buoyancy/GM model). Falls back to the
    // wire visual proxy when off or no Config is assigned. (KI-022 hydrostatics port)
    UPROPERTY(EditAnywhere, Category = "NaviSense")
    bool bUseHydrostatics = true;

    UPROPERTY(EditAnywhere, Category = "NaviSense")
    TObjectPtr<UNaviSenseVesselProfile> VesselProfile;

    // ---- Scripted AIS traffic (WP-15B) ----
    // The placed vessels (static-mesh props) that scripted AIS contacts drive,
    // mapped by index to state.v1 traffic[]. Leave empty to auto-resolve at
    // BeginPlay every actor tagged TrafficActorTag (sorted by name = stable slot
    // order). Each is forced Movable so it can be driven.
    UPROPERTY(EditAnywhere, Category = "NaviSense|Traffic")
    TArray<TObjectPtr<AActor>> TrafficActors;

    UPROPERTY(EditAnywhere, Category = "NaviSense|Traffic")
    FName TrafficActorTag = TEXT("NaviSenseTraffic");

    // True (default): anchor traffic to OWN-SHIP's spawn (the AIS world origin)
    // so the encounter geometry matches the deterministic preset; each actor
    // keeps its placed Z (waterline). Off => absolute wire->UE world pose.
    UPROPERTY(EditAnywhere, Category = "NaviSense|Traffic")
    bool bAnchorTrafficToSpawn = true;

    // KI-034: the PLACED pitch/roll of each traffic actor, captured on its first
    // ApplyTraffic. Meshes imported with an axis mismatch are corrected by rotating
    // the placed actor (e.g. roll +90 on a Y-up export); the wire drives YAW only,
    // so that correction must survive every packet. Captured once (not re-read per
    // tick) so rotator->quat round-trips can never wobble or accumulate it.
    // Transient (not a UPROPERTY): rebuilt each PIE session.
    TMap<TWeakObjectPtr<AActor>, FRotator> TrafficPlacedRot;

    // ---- Components ----
    UPROPERTY(VisibleAnywhere, Category = "NaviSense") TObjectPtr<UStaticMeshComponent> Hull;
    UPROPERTY(VisibleAnywhere, Category = "NaviSense") TObjectPtr<UActuatorComponent> Actuators;
    UPROPERTY(VisibleAnywhere, Category = "NaviSense") TObjectPtr<UNaviSenseBridgeComponent> Bridge;
    UPROPERTY(VisibleAnywhere, Category = "NaviSense") TObjectPtr<USensorBundleComponent> Sensors;
    UPROPERTY(VisibleAnywhere, Category = "NaviSense") TObjectPtr<UNaviSenseHydrostaticsComponent> Hydrostatics;
    UPROPERTY(VisibleAnywhere, Category = "NaviSense") TObjectPtr<USpringArmComponent> SpringArm;
    UPROPERTY(VisibleAnywhere, Category = "NaviSense") TObjectPtr<UCameraComponent> Camera;

    /** Called by the bridge when a state.v1 packet arrives (GAME THREAD only). */
    void ApplyOwnShipState(const FNaviSenseState& S);

    /** Drive the placed Traffic actors from a state.v1 traffic[] (GAME THREAD). */
    void ApplyTraffic(const TArray<FNaviSenseTrafficTarget>& Targets);

    // ---- True own-ship kinematics for sensor models + VFX (game thread) ----
    // BlueprintPure so the wake/HUD can read live kinematics with no C++ glue.
    /** Body-frame velocity cm/s (x=surge, y=sway). */
    UFUNCTION(BlueprintPure, Category = "NaviSense|Kinematics")
    FVector GetBodyVelocityCmPerSec() const { return BodyVelCmPerSec; }
    /** Yaw rate, deg/s. */
    UFUNCTION(BlueprintPure, Category = "NaviSense|Kinematics")
    double GetYawRateDegPerSec() const { return YawRateDeg; }
    /** Horizontal speed over ground, m/s. */
    UFUNCTION(BlueprintPure, Category = "NaviSense|Kinematics")
    double GetSpeedMetersPerSec() const { return BodyVelCmPerSec.Size2D() * 0.01; }

    // ---- Wake / spray VFX feed (D5 / WP-16): speed-driven, data-driven --------
    // A Niagara wake system reads these 0..1 scalars as user parameters so the
    // bow wave / stern wash / spray scale with speed. The curve is single-sourced
    // with python/wake_model.py (verify_20260628.py asserts the constants match).
    /** Speed (m/s) at which the wake reaches full intensity (~design top speed, ~20 kn). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "NaviSense|VFX")
    float WakeFullSpeedMS = 10.3f;
    /** Speed (m/s) above which spray / whitewater bursts switch on (~hull speed, ~15 kn). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "NaviSense|VFX")
    float WakeSprayOnsetMS = 7.7f;
    /** Dead-band (m/s): below this the wake is off (moored / drifting). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "NaviSense|VFX")
    float WakeMinSpeedMS = 0.3f;
    /** 0..1 wake intensity from current speed (single source for Niagara/BP). */
    UFUNCTION(BlueprintPure, Category = "NaviSense|VFX")
    float GetWakeIntensity01() const;
    /** 0..1 spray intensity (0 below the spray-onset speed). */
    UFUNCTION(BlueprintPure, Category = "NaviSense|VFX")
    float GetWakeSpray01() const;

    // ---- Actuator visual rig (drives BP part meshes from FActuatorState) ----
    /** Flip if the rudder deflects the wrong way visually. */
    UPROPERTY(EditAnywhere, Category = "NaviSense|ActuatorViz") float RudderVisualSign = 1.f;
    /** Flip if the propeller spins backwards visually. */
    UPROPERTY(EditAnywhere, Category = "NaviSense|ActuatorViz") float PropellerVisualSign = 1.f;
    UPROPERTY(EditAnywhere, Category = "NaviSense|ActuatorViz") bool bInvertPortProp = false;
    UPROPERTY(EditAnywhere, Category = "NaviSense|ActuatorViz") bool bInvertStarboardProp = true;  // twin screws counter-rotate
    /** Bow-thruster visual spin rate at full command (deg/s). */
    UPROPERTY(EditAnywhere, Category = "NaviSense|ActuatorViz") float BowThrusterMaxSpinDegPerSec = 720.f;

    // ---- Manual / native fallback (WP-6, F4): drivable with NO Python ----
    // Not physical truth — just "the sim never demos dead". Asset-free: keys are
    // polled from the possessing PlayerController, so no Input assets/config needed.
    /** Forward cruise speed at full throttle (cm/s). ~8 kn ≈ 412 cm/s. */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Manual") float ManualCruiseSpeedCmS = 600.f;
    /** Surge response toward target speed (1/s) — also acts as drag. */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Manual") float ManualAccel = 0.6f;
    /** Max yaw rate at cruise + full rudder (deg/s); scales with speed (needs way). */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Manual") float ManualMaxYawRateDeg = 12.f;
    /** Throttle/rudder slew toward key input (per s). */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Manual") float ManualInputSlew = 2.5f;
    /** Allow the 'M' key to toggle Manual <-> PoseReceive at runtime. */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Manual") bool bAllowManualToggleKey = true;

    /** Called by the bridge when state.v1 has gone stale (link down/slow).
     *  Freezes the pawn at its last good pose so it never drifts on missing data. */
    void NotifyBridgeStale();

    /** True while the bridge link is stale and the pawn is holding position. */
    UFUNCTION(BlueprintPure, Category = "NaviSense")
    bool IsBridgeStale() const { return bBridgeStale; }

    // =====================================================================
    // Bridge Dashboard data + control layer (WP-UI-DASHBOARD / WP_20260701).
    // WBP_BridgeDashboard (full-screen UMG, navy theme) binds to the
    // BlueprintPure getters below (read-only telemetry, four panels:
    // actuators / sensors / maneuver+IMO KPIs / sea-state+AIS) and drives the
    // ship through the Set* control entry points, which route into the
    // EXISTING manual-drive path (UpdateManual) -- no new physics model, no
    // DTO/schema change (invariant #3: FNaviSenseState keeps its 22 wire keys).
    // Does not touch the bridge/RX thread (invariant #2); no coordinate/sign
    // work outside NaviSenseCoords.h (invariant #1).
    // Honesty (KI-019 family): the live maneuver/IMO readout here is a ROLLING
    // KINEMATIC PROXY, not the post-run CFD-validated evidence-pack numbers
    // (build_evidence_pack.py); AIS range is geometry only, not the logged
    // CPA/TCPA/COLREGS verdict (python/colregs_score.py); wake/attitude remain
    // visual proxies. The widget must label these, not present them as
    // validated results.
    // =====================================================================

    // ---- Actuators panel ------------------------------------------------
    /** Rudder angle, degrees, port-positive (mirrors FActuatorState.RudderDeg). */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    double GetRudderDeg() const;
    /** Port shaft RPM. */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    double GetPortRpm() const;
    /** Starboard shaft RPM. */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    double GetStarboardRpm() const;
    /** Bow-thruster command, [-1,1], + = bow-to-starboard. */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    double GetBowThrusterNorm() const;

    // ---- Sensors panel ---------------------------------------------------
    /** Compass heading, degrees [0,360) CW from North (wire convention). */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    double GetHeadingDeg() const;
    /** Speed-over-ground, m/s (dashboard-facing alias of GetSpeedMetersPerSec). */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    double GetSpeedOverGroundMS() const { return GetSpeedMetersPerSec(); }
    /** Yaw rate, deg/s (dashboard-facing alias of GetYawRateDegPerSec). */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    double GetYawRateDashDegPerSec() const { return GetYawRateDegPerSec(); }
    /** Roll (heel), degrees, + = starboard-down: attitude actually rendered this tick. */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    double GetRollDeg() const { return GetActorRotation().Roll; }
    /** Pitch (trim), degrees, + = bow-up: attitude actually rendered this tick. */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    double GetPitchDeg() const { return GetActorRotation().Pitch; }
    /** Heave, metres, +up: the smoothed vertical bob actually applied this tick. */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    double GetHeaveM() const;
    /** Synthetic GPS latitude, degrees (same geo-origin projection as SensorBundleComponent). */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    double GetLatDeg() const;
    /** Synthetic GPS longitude, degrees. */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    double GetLonDeg() const;

    // ---- Maneuver + IMO KPIs panel ---------------------------------------
    /** "Pose-Receive (Bridge)" | "Manual" | "Native Physics" -- current motion source label. */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    FString GetMotionModeLabel() const;
    /** Plant-reported run mode (idle|manual|auto|replay), last state.v1 'mode'. */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    FString GetPlantMode() const { return LastPlantMode; }
    /** Rolling net forward distance since BeginPlay, metres -- LIVE PROXY ONLY.
     *  The validated IMO advance/tactical-diameter/overshoot KPIs are computed
     *  post-run by build_evidence_pack.py (KI-019: do not conflate the two). */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    double GetRollingAdvanceM() const { return RollingAdvanceM; }
    /** Peak |heading deviation| from the BeginPlay heading, degrees -- live overshoot proxy. */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    double GetPeakHeadingDeviationDeg() const { return PeakHeadingDeviationDeg; }

    // ---- Sea state + AIS/COLREGS panel -----------------------------------
    /** Number of scripted traffic contacts currently rendered. */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    int32 GetTrafficContactCount() const { return TrafficActors.Num(); }
    /** Range to the nearest rendered traffic contact, metres (-1 if none). Geometry
     *  only -- NOT the CPA/TCPA/COLREGS verdict (python/colregs_score.py, post-run). */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    double GetNearestTrafficRangeM() const;
    /** Name of the nearest rendered traffic contact ("" if none). */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    FString GetNearestTrafficName() const;

    /** The full scripted-traffic contact list last applied over the wire (state.v1
     *  traffic[]). Read by the AIS sensor to emit sensor.v1 ais.targets[] with
     *  mmsi/cog/sog + receiver-computed range/bearing. Empty => no traffic. */
    const TArray<FNaviSenseTrafficTarget>& GetTrafficTargets() const { return LastTraffic; }

    /** KI-040: spawn-anchor accessors. Traffic targets ride the wire in PLANT
     *  frame; the sensors must express own-ship in that same frame by removing
     *  the KI-020 spawn anchor before computing AIS/radar range & bearing. */
    const FVector& GetSpawnLocation() const { return SpawnLocation; }
    double GetSpawnYawDeg() const { return SpawnYawDeg; }

    // ---- Interactive control entry points --------------------------------
    // Route into the EXISTING manual-drive path (UpdateManual): the widget is
    // expected to call these every tick while visible (typical UMG slider
    // binding), same as keyboard polling; values are clamped to the same
    // [-1,1] command range as W/S/A/D so helm/throttle/thruster drive the ship
    // identically either way.
    /** Helm/rudder command, [-1,1], + = starboard. Clamped. Marks dashboard control active. */
    UFUNCTION(BlueprintCallable, Category = "NaviSense|BridgeDashboard")
    void SetHelm(float Rudder01);
    /** Throttle command, [-1,1], + = ahead. Clamped. Marks dashboard control active. */
    UFUNCTION(BlueprintCallable, Category = "NaviSense|BridgeDashboard")
    void SetThrottle(float Throttle01);
    /** Bow-thruster command, [-1,1], + = bow-to-starboard. Clamped. Marks dashboard control active. */
    UFUNCTION(BlueprintCallable, Category = "NaviSense|BridgeDashboard")
    void SetBowThruster(float Norm01);
    /** True once the dashboard widget has issued a Set* call this run (keyboard
     *  W/S/A/D still works independently when this is false). */
    UFUNCTION(BlueprintPure, Category = "NaviSense|BridgeDashboard")
    bool IsDashboardControlActive() const { return bDashboardControlActive; }
    /** Max yaw rate the bow thruster alone can command at zero way (deg/s); adds
     *  to the rudder's speed-scaled yaw rate in UpdateManual. */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Manual") float BowThrusterMaxYawRateDeg = 6.f;

private:
    // Pose interpolation targets (UE units, derived from the wire packet).
    FVector TargetLocation = FVector::ZeroVector;
    double  TargetYawDeg = 0.0;
    double  TargetPitchDeg = 0.0;   // 6-DOF attitude (schema v1.2): trim
    double  TargetRollDeg = 0.0;    // 6-DOF attitude (schema v1.2): heel
    double  TargetHeaveCm = 0.0;    // 6-DOF heave (schema v1.3): wave Z-offset target (cm)
    double  CurrentHeaveCm = 0.0;   // smoothed heave actually applied to Z
    FVector BodyVelCmPerSec = FVector::ZeroVector;   // for wake/VFX (Phase 11)
    double  YawRateDeg = 0.0;
    bool    bHasTarget = false;
    // Placed transform captured at BeginPlay; the run origin when bAnchorPoseToSpawn.
    FVector SpawnLocation = FVector::ZeroVector;
    double  SpawnYawDeg   = 0.0;

    // Last scripted-traffic contact list applied by ApplyTraffic; source for the
    // sensor.v1 AIS receiver feed (mmsi/cog/sog + range/bearing).
    TArray<FNaviSenseTrafficTarget> LastTraffic;

    // Actuator-viz part components, resolved by name at BeginPlay (Rudder/propeller/bowthruster).
    UPROPERTY() TObjectPtr<USceneComponent> RudderViz = nullptr;
    // Twin propellers (KI-023): resolved by name (port/stbd). LegacyPropViz is the
    // single merged mesh fallback until the FBX is split into two.
    UPROPERTY() TObjectPtr<USceneComponent> PortPropViz = nullptr;
    UPROPERTY() TObjectPtr<USceneComponent> StbdPropViz = nullptr;
    UPROPERTY() TObjectPtr<USceneComponent> LegacyPropViz = nullptr;
    UPROPERTY() TObjectPtr<USceneComponent> BowThrusterViz = nullptr;
    FRotator RudderBaseRot = FRotator::ZeroRotator;
    FRotator PortPropBaseRot   = FRotator::ZeroRotator;
    FRotator StbdPropBaseRot   = FRotator::ZeroRotator;
    FRotator LegacyPropBaseRot = FRotator::ZeroRotator;
    FRotator BowBaseRot    = FRotator::ZeroRotator;
    double PortPropSpinDeg = 0.0;
    double StbdPropSpinDeg = 0.0;
    double LegacyPropSpinDeg = 0.0;
    double BowSpinDeg  = 0.0;
    void ResolveActuatorVizComponents();
    void UpdateActuatorVisuals(float Dt);
    bool    bBridgeStale = false;   // hold position; cleared by the next fresh state

    // Manual-mode runtime state (WP-6).
    void  UpdateManual(float Dt);
    float ManualThrottle = 0.f;     // [-1,1]
    float ManualRudder   = 0.f;     // [-1,1]
    float ManualSpeedCmS = 0.f;
    bool  bManualTogglePrev = false;

    // Bridge-dashboard control state (WP_20260701): the widget's helm/throttle/
    // thruster commands, consumed by UpdateManual in place of keyboard polling
    // once active.
    void   UpdateManeuverTelemetry();
    bool   bDashboardControlActive = false;
    float  DashboardRudderCmd = 0.f;        // [-1,1]
    float  DashboardThrottleCmd = 0.f;      // [-1,1]
    float  DashboardBowThrusterCmd = 0.f;   // [-1,1]
    FString LastPlantMode = TEXT("idle");   // last state.v1 'mode'
    double RollingAdvanceM = 0.0;           // live proxy, NOT the evidence-pack KPI
    double PeakHeadingDeviationDeg = 0.0;   // live proxy, NOT the evidence-pack KPI
    double InitialHeadingDeg = -1.0;        // sentinel: set on first telemetry update
    FVector LastLocationForAdvance = FVector::ZeroVector;
};
