// Copyright NaviSyn Marine Solutions.
// =====================================================================
// FBridgeSocketRunnable — background thread that owns the receive loop.
//
// THREADING RULE (do not violate): this thread does PURE byte/JSON work and
// pushes complete newline-delimited lines into an SPSC queue. It NEVER touches
// UObjects or the scene. The game thread (bridge component Tick) drains the
// queue and applies to actors. Master Guide: Section 8.1, Risk R2.
//
// WP-3 addition: the thread also detects a dropped link (peer closed or socket
// error) and raises a thread-safe flag the game thread polls. It still touches
// NO UObjects — the flag is a plain atomic owned by the component.
// =====================================================================
#pragma once

#include "CoreMinimal.h"
#include "HAL/Runnable.h"
#include "HAL/ThreadSafeBool.h"
#include "Containers/Queue.h"

class FSocket;

class FBridgeSocketRunnable : public FRunnable
{
public:
    // InDropped is owned by the component; we set it true exactly once when the
    // link goes down, then exit Run(). nullptr is tolerated (drop is silent).
    FBridgeSocketRunnable(FSocket* InSocket,
                          TQueue<FString, EQueueMode::Spsc>* InLineQueue,
                          FThreadSafeBool* InDropped)
        : Socket(InSocket), LineQueue(InLineQueue), Dropped(InDropped) {}

    virtual uint32 Run() override;
    virtual void Stop() override { bRun = false; }

private:
    void SignalDropped()
    {
        if (Dropped) { *Dropped = true; }
    }

    FSocket* Socket = nullptr;
    TQueue<FString, EQueueMode::Spsc>* LineQueue = nullptr;
    FThreadSafeBool* Dropped = nullptr;   // game thread reads; we write once
    FThreadSafeBool bRun = true;
    FString Carry;   // partial-line buffer across Recv() calls
};
