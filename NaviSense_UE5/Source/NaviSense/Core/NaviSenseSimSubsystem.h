// Copyright NaviSyn Marine Solutions.
// =====================================================================
// UNaviSenseSimSubsystem — run lifecycle owner (GameInstance subsystem).
// Holds the authoritative RunId, Mode, geo-origin, and the sim clock the
// bridge 't' field uses. Master Guide: Section 3.3 + Phase 1.
//
// WP-4 (F5): the clock is now a PAUSE-AWARE, TICK-ACCUMULATED, FIXED-STEP
// sim clock (not wall-clock):
//   * FTickableGameObject drives it; IsTickableWhenPaused()==false means a
//     PIE pause freezes sim time (no wall-clock drift across a pause).
//   * A fixed-step accumulator advances an integer StepCount in
//     FixedStepSeconds increments — the deterministic spine that replay (W7)
//     and "both ends log the same t" depend on.
//   * Run lifecycle: StartRun(RunId) resets the clock and stamps the id so
//     UE and Python share one t-origin per run; StopRun() freezes it.
// =====================================================================
#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Tickable.h"
#include "NaviSenseSimSubsystem.generated.h"

UCLASS()
class NAVISENSE_API UNaviSenseSimSubsystem : public UGameInstanceSubsystem, public FTickableGameObject
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    // ---- Run lifecycle --------------------------------------------------

    /** Begin a run: adopt InRunId, reset the clock to zero, mark active.
     *  Idempotent if the same run id is already active. */
    UFUNCTION(BlueprintCallable, Category = "NaviSense")
    void StartRun(const FString& InRunId);

    /** End the current run: freeze the clock (sim time stops advancing). */
    UFUNCTION(BlueprintCallable, Category = "NaviSense")
    void StopRun();

    UFUNCTION(BlueprintPure, Category = "NaviSense")
    bool IsRunActive() const { return bRunActive; }

    /** Free-form run grouping id, shared with Python on the wire. */
    UPROPERTY(BlueprintReadWrite, Category = "NaviSense")
    FString RunId = TEXT("test-run");

    /** idle | manual | auto | replay. Mirrors the bridge 'mode' string. */
    UPROPERTY(BlueprintReadWrite, Category = "NaviSense")
    FString Mode = TEXT("idle");

    /** Geo-origin for synthetic GPS (lat/lon). Default: Monaco / Port Hercule.
        A script/Blueprint may override at BeginPlay to match the CesiumGeoreference. */
    UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "NaviSense|Geo")
    double RefLatDeg = 43.7350;

    UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "NaviSense|Geo")
    double RefLonDeg = 7.4250;

    // ---- Clock ----------------------------------------------------------

    /** Seconds of accumulated SIM time since the run started (pause-aware).
     *  The bridge sensor packet 't' uses this. */
    UFUNCTION(BlueprintPure, Category = "NaviSense")
    double GetSimTime() const { return AccumulatedSeconds; }

    /** Deterministic fixed-step count since the run started. */
    UFUNCTION(BlueprintPure, Category = "NaviSense")
    int64 GetStepCount() const { return StepCount; }

    UFUNCTION(BlueprintPure, Category = "NaviSense")
    double GetFixedStepSeconds() const { return FixedStepSeconds; }

    /** Reset the sim clock to zero (StartRun calls this). */
    UFUNCTION(BlueprintCallable, Category = "NaviSense")
    void ResetClock();

    /** Deterministic sub-step (s). GetSimTime() itself stays continuous
     *  (≈0 drift vs elapsed sim seconds); StepCount is quantised to this. */
    UPROPERTY(EditAnywhere, Category = "NaviSense", meta = (ClampMin = "0.0001"))
    double FixedStepSeconds = 1.0 / 120.0;

    // ---- FTickableGameObject -------------------------------------------
    virtual void Tick(float DeltaTime) override;
    virtual bool IsTickable() const override { return bInitialized; }
    virtual bool IsTickableWhenPaused() const override { return false; } // PIE pause freezes t
    virtual bool IsTickableInEditor() const override { return false; }
    virtual UWorld* GetTickableGameObjectWorld() const override;
    virtual TStatId GetStatId() const override;

private:
    bool   bInitialized = false;
    bool   bRunActive = false;
    double AccumulatedSeconds = 0.0;   // continuous, pause-aware sim time
    double FixedAccumulator = 0.0;     // remainder feeding the fixed-step counter
    int64  StepCount = 0;              // deterministic fixed-step ticks this run
};
