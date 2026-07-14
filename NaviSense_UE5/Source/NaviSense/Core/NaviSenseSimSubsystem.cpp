// Copyright NaviSyn Marine Solutions.
#include "Core/NaviSenseSimSubsystem.h"
#include "NaviSense.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "Stats/Stats.h"

void UNaviSenseSimSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    bInitialized = true;
    // Begin a default run so the clock ticks out of the box (manual mode, tests).
    // The bridge re-stamps this with Python's RunId on connect to align t-origins.
    StartRun(RunId);
    UE_LOG(LogNaviSense, Display,
        TEXT("Sim subsystem up. RunId=%s Mode=%s fixedStep=%.4fs"),
        *RunId, *Mode, FixedStepSeconds);
}

void UNaviSenseSimSubsystem::Deinitialize()
{
    bRunActive = false;
    bInitialized = false;
    UE_LOG(LogNaviSense, Display, TEXT("Sim subsystem shutting down."));
    Super::Deinitialize();
}

void UNaviSenseSimSubsystem::StartRun(const FString& InRunId)
{
    if (bRunActive && RunId == InRunId)
    {
        return; // already running this exact run — idempotent
    }
    if (!InRunId.IsEmpty())
    {
        RunId = InRunId;
    }
    ResetClock();
    bRunActive = true;
    Mode = TEXT("auto");
    UE_LOG(LogNaviSense, Display, TEXT("Run started: %s"), *RunId);
}

void UNaviSenseSimSubsystem::StopRun()
{
    if (!bRunActive)
    {
        return;
    }
    bRunActive = false;
    Mode = TEXT("idle");
    UE_LOG(LogNaviSense, Display,
        TEXT("Run stopped: %s at t=%.3f s (%lld steps)"),
        *RunId, AccumulatedSeconds, static_cast<long long>(StepCount));
}

void UNaviSenseSimSubsystem::ResetClock()
{
    AccumulatedSeconds = 0.0;
    FixedAccumulator = 0.0;
    StepCount = 0;
}

void UNaviSenseSimSubsystem::Tick(float DeltaTime)
{
    // Not ticked while the game is paused (IsTickableWhenPaused()==false), so a
    // PIE pause simply does not advance sim time — no wall-clock drift.
    if (!bRunActive)
    {
        return;
    }

    const double Dt = static_cast<double>(DeltaTime);
    AccumulatedSeconds += Dt;            // continuous, pause-aware sim time
    FixedAccumulator   += Dt;

    const double Step = (FixedStepSeconds > 0.0) ? FixedStepSeconds : (1.0 / 120.0);

    // Advance the deterministic step counter. Cap iterations so a one-off huge
    // DeltaTime (breakpoint, hitch) can never spin the loop forever.
    int32 Safety = 0;
    while (FixedAccumulator >= Step && Safety < 100000)
    {
        FixedAccumulator -= Step;
        ++StepCount;
        ++Safety;
    }
    if (FixedAccumulator >= Step)
    {
        FixedAccumulator = 0.0; // pathological frame: drop the remainder
    }
}

UWorld* UNaviSenseSimSubsystem::GetTickableGameObjectWorld() const
{
    return GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
}

TStatId UNaviSenseSimSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UNaviSenseSimSubsystem, STATGROUP_Tickables);
}
