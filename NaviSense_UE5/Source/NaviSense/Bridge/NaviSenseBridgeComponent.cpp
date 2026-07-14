// Copyright NaviSyn Marine Solutions.
#include "Bridge/NaviSenseBridgeComponent.h"
#include "Bridge/BridgeSocketRunnable.h"
#include "Core/NaviSenseSimSubsystem.h"
#include "NaviSense.h"

#include "Sockets.h"
#include "SocketSubsystem.h"
#include "Interfaces/IPv4/IPv4Address.h"
#include "IPAddress.h"
#include "HAL/RunnableThread.h"
#include "JsonObjectConverter.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Engine/Engine.h"                          // GEngine on-screen status
#include "ProfilingDebugging/CpuProfilerTrace.h"    // TRACE_CPUPROFILER_EVENT_SCOPE

// Forward-declared elsewhere; included for the build hint. The pawn applies
// state in Phase 4–5. We call into it via an interface-free Cast in ApplyState.
#include "Vessel/NaviSenseShipPawn.h"
#include "Sensors/SensorBundleComponent.h"

namespace
{
    constexpr int32 kOnScreenStatusKey = 7701;   // stable key so messages replace
    constexpr int32 kPendingTxCapBytes = 64 * 1024;
}

UNaviSenseBridgeComponent::UNaviSenseBridgeComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
}

void UNaviSenseBridgeComponent::BeginPlay()
{
    Super::BeginPlay();
    if (const UGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance() : nullptr)
    {
        Sim = GI->GetSubsystem<UNaviSenseSimSubsystem>();
    }
    CurrentBackoff = ReconnectBackoffMinSec;
    if (bAutoConnectOnBeginPlay)
    {
        Connect();
    }
}

void UNaviSenseBridgeComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    Disconnect();
    Super::EndPlay(Reason);
}

// =====================================================================
// Public link control
// =====================================================================
void UNaviSenseBridgeComponent::Connect()
{
    bWantLink = true;
    if (Socket)
    {
        return; // already linked
    }

    SetConnectionState(ENaviSenseBridgeState::Connecting);
    if (TryConnect())
    {
        return; // connected immediately (Python already up)
    }

    // Python not up yet — fall into the backoff retry loop (handled in Tick).
    if (bAutoReconnect)
    {
        ReconnectTimer = CurrentBackoff;
    }
    else
    {
        SetConnectionState(ENaviSenseBridgeState::Disconnected);
    }
}

void UNaviSenseBridgeComponent::Disconnect()
{
    bWantLink = false;
    TearDownLink();
    PendingTx.Reset();
    if (Sim) { Sim->StopRun(); }   // freeze the sim clock when the link is closed (WP-4)
    SetConnectionState(ENaviSenseBridgeState::Disconnected);
}

// =====================================================================
// Internal link lifecycle
// =====================================================================
bool UNaviSenseBridgeComponent::TryConnect()
{
    if (Socket)
    {
        return true;
    }

    ISocketSubsystem* SS = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM);
    if (!SS)
    {
        UE_LOG(LogNaviSense, Error, TEXT("No socket subsystem available."));
        return false;
    }

    FSocket* NewSocket = SS->CreateSocket(NAME_Stream, TEXT("NaviSenseBridge"), false);
    if (!NewSocket)
    {
        UE_LOG(LogNaviSense, Error, TEXT("Failed to create socket."));
        return false;
    }

    TSharedRef<FInternetAddr> Addr = SS->CreateInternetAddr();
    bool bValidIp = false;
    Addr->SetIp(*Host, bValidIp);
    Addr->SetPort(Port);

    if (!bValidIp || !NewSocket->Connect(*Addr))
    {
        // Quiet at Verbose: this fires every backoff tick until Python is up.
        UE_LOG(LogNaviSense, Verbose,
            TEXT("Bridge connect attempt FAILED to %s:%d (is python_listener.py running?)"),
            *Host, Port);
        SS->DestroySocket(NewSocket);
        return false;
    }

    // Non-blocking so the game-thread Send() can never stall a frame.
    NewSocket->SetNonBlocking(true);

    Socket = NewSocket;
    bConnectionDropped = false;
    SecondsSinceLastState = 0.f;
    CurrentBackoff = ReconnectBackoffMinSec;   // reset backoff on a good link

    Runner = new FBridgeSocketRunnable(Socket, &LineQueue, &bConnectionDropped);
    Thread = FRunnableThread::Create(Runner, TEXT("NaviSenseBridgeRx"));

    SetConnectionState(ENaviSenseBridgeState::Connected);
    UE_LOG(LogNaviSense, Display, TEXT("Bridge connected %s:%d"), *Host, Port);
    return true;
}

void UNaviSenseBridgeComponent::TearDownLink()
{
    if (Runner) { Runner->Stop(); }
    if (Thread) { Thread->WaitForCompletion(); delete Thread; Thread = nullptr; }
    if (Runner) { delete Runner; Runner = nullptr; }

    if (Socket)
    {
        Socket->Close();
        if (ISocketSubsystem* SS = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM))
        {
            SS->DestroySocket(Socket);
        }
        Socket = nullptr;
    }

    // Drop any half-received lines so a reconnect starts clean.
    FString Discard;
    while (LineQueue.Dequeue(Discard)) {}
    bConnectionDropped = false;
}

void UNaviSenseBridgeComponent::HandleDisconnected()
{
    UE_LOG(LogNaviSense, Warning, TEXT("Bridge link dropped."));
    TearDownLink();
    PendingTx.Reset();   // stale outbound bytes are meaningless on a new link
    if (Sim) { Sim->StopRun(); }   // end the run; reconnect starts a fresh one (WP-4)

    if (bWantLink && bAutoReconnect)
    {
        SetConnectionState(ENaviSenseBridgeState::Connecting);
        CurrentBackoff = ReconnectBackoffMinSec;   // start fast, then back off
        ReconnectTimer = CurrentBackoff;
    }
    else
    {
        SetConnectionState(ENaviSenseBridgeState::Disconnected);
    }
}

void UNaviSenseBridgeComponent::SetConnectionState(ENaviSenseBridgeState NewState)
{
    if (NewState == ConnState)
    {
        return;
    }
    ConnState = NewState;
    OnConnectionChanged.Broadcast(NewState);

    if (bShowOnScreenStatus && GEngine)
    {
        FColor Color = FColor::White;
        FString Msg;
        switch (NewState)
        {
        case ENaviSenseBridgeState::Connected:
            Color = FColor::Green;  Msg = TEXT("NaviSense bridge: CONNECTED");                    break;
        case ENaviSenseBridgeState::Connecting:
            Color = FColor::Yellow; Msg = TEXT("NaviSense bridge: RECONNECTING…");                break;
        case ENaviSenseBridgeState::Stale:
            Color = FColor::Red;    Msg = TEXT("NaviSense bridge: STALE — holding position");     break;
        default:
            Color = FColor(160,160,160); Msg = TEXT("NaviSense bridge: DISCONNECTED");            break;
        }
        const float Hold = (NewState == ENaviSenseBridgeState::Connected) ? 2.5f : 3600.f;
        GEngine->AddOnScreenDebugMessage(kOnScreenStatusKey, Hold, Color, Msg);
    }
}

// =====================================================================
// Tick: drop handling -> reconnect -> drain -> staleness -> send
// =====================================================================
void UNaviSenseBridgeComponent::TickComponent(float Dt, ELevelTick, FActorComponentTickFunction*)
{
    // 0) The rx thread flags a dropped link; act on it on the game thread.
    if (bConnectionDropped)
    {
        HandleDisconnected();
    }

    // 1) Backoff reconnect while we want a link but don't have one.
    if (!Socket && bWantLink && bAutoReconnect && ConnState == ENaviSenseBridgeState::Connecting)
    {
        ReconnectTimer -= Dt;
        if (ReconnectTimer <= 0.f)
        {
            if (!TryConnect())
            {
                ReconnectTimer = CurrentBackoff;
                CurrentBackoff = FMath::Min(CurrentBackoff * 2.f, ReconnectBackoffMaxSec);
            }
        }
    }

    // 2) Drain inbound state packets (game thread) and apply to the pawn.
    bool bGotState = false;
    FString Line;
    while (LineQueue.Dequeue(Line))
    {
        FNaviSenseState State;
        if (FJsonObjectConverter::JsonObjectStringToUStruct(Line, &State, 0, 0)
            && State.schema.StartsWith(TEXT("navisense.state")))
        {
            // Run lifecycle (WP-4): adopt Python's RunId and reset the sim clock
            // at the first state of a run so both ends share one t-origin.
            if (Sim && !State.runId.IsEmpty()
                && (!Sim->IsRunActive() || Sim->RunId != State.runId))
            {
                Sim->StartRun(State.runId);
            }
            if (bLogTraffic)
            {
                UE_LOG(LogNaviSense, Verbose, TEXT("RX state t=%.3f yaw=%.1f"), State.t, State.yawDeg);
            }
            ApplyState(State);
            bGotState = true;
        }
    }

    // 3) Staleness failsafe (only meaningful while a socket is open).
    if (Socket)
    {
        if (bGotState)
        {
            SecondsSinceLastState = 0.f;
            if (ConnState == ENaviSenseBridgeState::Stale)
            {
                SetConnectionState(ENaviSenseBridgeState::Connected);   // resumed
            }
        }
        else
        {
            SecondsSinceLastState += Dt;
            if (ConnState == ENaviSenseBridgeState::Connected
                && SecondsSinceLastState > StaleStateTimeoutSec)
            {
                SetConnectionState(ENaviSenseBridgeState::Stale);
                if (ANaviSenseShipPawn* Pawn = Cast<ANaviSenseShipPawn>(GetOwner()))
                {
                    Pawn->NotifyBridgeStale();   // freeze at last good pose
                }
            }
        }
    }

    // 4) Emit sensor packet at SendRateHz — serialise into the TX buffer only.
    if (Socket && SendRateHz > 0.f)
    {
        SendAccumulator += Dt;
        if (SendAccumulator >= 1.f / SendRateHz)
        {
            SendAccumulator = 0.f;
            QueueSensorPacket();
        }
    }

    // 5) Flush the TX buffer non-blocking (never stalls the frame).
    PumpTx();
}

void UNaviSenseBridgeComponent::ApplyState(const FNaviSenseState& State)
{
    if (ANaviSenseShipPawn* Pawn = Cast<ANaviSenseShipPawn>(GetOwner()))
    {
        Pawn->ApplyOwnShipState(State);
        Pawn->ApplyTraffic(State.traffic);
    }
}

// =====================================================================
// Outbound: build JSON (cheap) into PendingTx, flush non-blocking
// =====================================================================
void UNaviSenseBridgeComponent::QueueSensorPacket()
{
    TRACE_CPUPROFILER_EVENT_SCOPE(NaviSenseBridge_QueueSensorPacket);

    TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
    Root->SetStringField(TEXT("schema"), TEXT("navisense.sensor.v1"));
    Root->SetStringField(TEXT("runId"), Sim ? Sim->RunId : TEXT("test-run"));
    Root->SetNumberField(TEXT("t"), Sim ? Sim->GetSimTime() : 0.0);

    // The sensor bundle fills gps/imu/ais (Phase 6). Until it exists, emit a
    // minimal but valid 'sensors' block so the protocol is exercised end-to-end.
    if (SensorBundle)
    {
        Root->SetObjectField(TEXT("sensors"), SensorBundle->BuildSensorsJson());
    }
    else
    {
        TSharedRef<FJsonObject> Sensors = MakeShared<FJsonObject>();
        Sensors->SetNumberField(TEXT("time"), Sim ? Sim->GetSimTime() : 0.0);
        Root->SetObjectField(TEXT("sensors"), Sensors);
    }

    FString Out;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Out);
    FJsonSerializer::Serialize(Root, Writer);
    Out.ReplaceInline(TEXT("\r"), TEXT(""));   // no stray CR
    Out.ReplaceInline(TEXT("\n"), TEXT(""));   // single-line JSON only...
    Out += TEXT("\n");                         // ...then exactly one trailing newline

    auto Utf8 = StringCast<ANSICHAR>(*Out);
    PendingTx.Append(reinterpret_cast<const uint8*>(Utf8.Get()), Utf8.Length());

    // Bound the buffer if Python ever stops reading (slow consumer): drop the
    // oldest bytes so we never grow without limit and never block.
    if (PendingTx.Num() > kPendingTxCapBytes)
    {
        PendingTx.RemoveAt(0, PendingTx.Num() - kPendingTxCapBytes, EAllowShrinking::No);
    }
}

void UNaviSenseBridgeComponent::PumpTx()
{
    if (!Socket || PendingTx.Num() == 0)
    {
        return;
    }
    TRACE_CPUPROFILER_EVENT_SCOPE(NaviSenseBridge_PumpTx);

    int32 Sent = 0;
    if (Socket->Send(PendingTx.GetData(), PendingTx.Num(), Sent))
    {
        if (Sent > 0)
        {
            PendingTx.RemoveAt(0, Sent, EAllowShrinking::No);   // keep any unsent tail
        }
    }
    // If Send returns false it's almost always EWOULDBLOCK (kernel buffer full):
    // leave the bytes queued and try again next tick. A truly broken socket is
    // detected by the rx thread, which drives the reconnect path above.
}
