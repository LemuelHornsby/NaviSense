// Copyright NaviSyn Marine Solutions.
// =====================================================================
// UNaviSenseBridgeComponent — TCP client that speaks the v1.1 protocol.
// Connects out to 127.0.0.1:5005, drains inbound state.v1 on the game
// thread, and emits sensor.v1 at SendRateHz. Mirrors Unity's
// PythonBridgeManager. Master Guide: Section 8 (HIGH PRIORITY).
//
// WP-3 (F3) bridge robustness:
//   * exponential-backoff (re)connect (0.5 -> 8 s), survives Python restarts
//   * stale-state failsafe: > StaleStateTimeoutSec without state.v1 => pawn
//     holds position + on-screen warning + Stale connection event
//   * non-blocking, queued send (no game-thread hitch from the socket syscall)
//   * BlueprintAssignable connection-state delegate for the HUD
// =====================================================================
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Containers/Queue.h"
#include "HAL/ThreadSafeBool.h"
#include "Bridge/NaviSenseBridgeTypes.h"
#include "NaviSenseBridgeComponent.generated.h"

class FSocket;
class FRunnableThread;
class FBridgeSocketRunnable;
class UNaviSenseSimSubsystem;
class USensorBundleComponent;

/** Coarse link health, surfaced to Blueprints/HUD. */
UENUM(BlueprintType)
enum class ENaviSenseBridgeState : uint8
{
    Disconnected    UMETA(DisplayName = "Disconnected"),  // no link, not trying
    Connecting      UMETA(DisplayName = "Connecting"),    // (re)connect in progress / backing off
    Connected       UMETA(DisplayName = "Connected"),     // link up, fresh state flowing
    Stale           UMETA(DisplayName = "Stale")          // link up but no state.v1 for > timeout
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnBridgeConnectionChanged, ENaviSenseBridgeState, NewState);

UCLASS(ClassGroup = NaviSense, meta = (BlueprintSpawnableComponent))
class NAVISENSE_API UNaviSenseBridgeComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UNaviSenseBridgeComponent();

    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float Dt, ELevelTick, FActorComponentTickFunction*) override;

    UPROPERTY(EditAnywhere, Category = "NaviSense|Bridge")
    FString Host = TEXT("127.0.0.1");

    UPROPERTY(EditAnywhere, Category = "NaviSense|Bridge")
    int32 Port = 5005;

    UPROPERTY(EditAnywhere, Category = "NaviSense|Bridge")
    bool bAutoConnectOnBeginPlay = true;

    /** Sensor packet send rate (Hz). Default mirrors Unity's 5 Hz. */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Bridge")
    float SendRateHz = 5.f;

    UPROPERTY(EditAnywhere, Category = "NaviSense|Bridge")
    bool bLogTraffic = false;

    // ---- WP-3 robustness knobs ----------------------------------------

    /** Keep retrying the link (initial connect + after a drop) with backoff. */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Bridge|Robustness")
    bool bAutoReconnect = true;

    /** First retry delay (s). Doubles each failed attempt up to the max. */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Bridge|Robustness", meta = (ClampMin = "0.05"))
    float ReconnectBackoffMinSec = 0.5f;

    /** Cap on the retry delay (s). */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Bridge|Robustness", meta = (ClampMin = "0.5"))
    float ReconnectBackoffMaxSec = 8.f;

    /** No state.v1 for longer than this (s) while linked => Stale + pawn hold. */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Bridge|Robustness", meta = (ClampMin = "0.1"))
    float StaleStateTimeoutSec = 1.f;

    /** Show built-in on-screen connection warnings (independent of any HUD BP). */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Bridge|Robustness")
    bool bShowOnScreenStatus = true;

    /** Optional: the sensor bundle that builds the sensors{} JSON block. */
    UPROPERTY(EditAnywhere, Category = "NaviSense|Bridge")
    TObjectPtr<USensorBundleComponent> SensorBundle;

    /** Fires whenever the link state changes — bind this on the HUD. */
    UPROPERTY(BlueprintAssignable, Category = "NaviSense|Bridge")
    FOnBridgeConnectionChanged OnConnectionChanged;

    UFUNCTION(BlueprintCallable, Category = "NaviSense|Bridge")
    void Connect();

    UFUNCTION(BlueprintCallable, Category = "NaviSense|Bridge")
    void Disconnect();

    /** True while a socket is open (Connected or Stale). */
    UFUNCTION(BlueprintPure, Category = "NaviSense|Bridge")
    bool IsConnected() const { return Socket != nullptr; }

    UFUNCTION(BlueprintPure, Category = "NaviSense|Bridge")
    ENaviSenseBridgeState GetConnectionState() const { return ConnState; }

    UFUNCTION(BlueprintPure, Category = "NaviSense|Bridge")
    float GetSecondsSinceLastState() const { return SecondsSinceLastState; }

private:
    // --- link lifecycle ---
    bool TryConnect();           // one synchronous connect attempt; true on success
    void TearDownLink();         // stop rx thread + close socket (no state change)
    void HandleDisconnected();   // called when the rx thread reports a drop
    void SetConnectionState(ENaviSenseBridgeState NewState);

    // --- io ---
    void QueueSensorPacket();    // serialise sensor.v1 into PendingTx (cheap, game thread)
    void PumpTx();               // non-blocking flush of PendingTx (no hitch)
    void ApplyState(const FNaviSenseState& State);

    FSocket* Socket = nullptr;
    FRunnableThread* Thread = nullptr;
    FBridgeSocketRunnable* Runner = nullptr;
    TQueue<FString, EQueueMode::Spsc> LineQueue;
    FThreadSafeBool bConnectionDropped = false;   // set by rx thread, read on tick

    // outbound byte buffer, drained non-blocking each tick
    TArray<uint8> PendingTx;

    // connection / health state
    ENaviSenseBridgeState ConnState = ENaviSenseBridgeState::Disconnected;
    bool  bWantLink = false;            // intent: keep (re)connecting until Disconnect()
    float SecondsSinceLastState = 0.f;
    float ReconnectTimer = 0.f;
    float CurrentBackoff = 0.5f;

    float SendAccumulator = 0.f;

    UPROPERTY() TObjectPtr<UNaviSenseSimSubsystem> Sim = nullptr;
};
