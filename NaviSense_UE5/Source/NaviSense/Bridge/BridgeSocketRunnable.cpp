// Copyright NaviSyn Marine Solutions.
#include "Bridge/BridgeSocketRunnable.h"
#include "NaviSense.h"
#include "Sockets.h"
#include "SocketSubsystem.h"

uint32 FBridgeSocketRunnable::Run()
{
    uint8 Buffer[4096];
    ISocketSubsystem* SS = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM);

    while (bRun)
    {
        if (!Socket)
        {
            FPlatformProcess::Sleep(0.05f);
            continue;
        }

        // Block up to 100 ms waiting for readable data. This keeps the thread
        // off a hot spin AND stays responsive to Stop() (checked each loop).
        // On a closed connection the socket becomes "readable" and the Recv
        // below returns 0 bytes — that is how we detect a graceful peer close.
        const bool bReadable = Socket->Wait(ESocketWaitConditions::WaitForRead,
                                            FTimespan::FromMilliseconds(100));
        if (!bRun)
        {
            break;
        }
        if (!bReadable)
        {
            continue;   // idle link, no data yet — perfectly normal
        }

        int32 BytesRead = 0;
        if (Socket->Recv(Buffer, sizeof(Buffer), BytesRead))
        {
            if (BytesRead == 0)
            {
                // Peer closed the connection gracefully (FIN). Link is down.
                SignalDropped();
                break;
            }

            // TCP may coalesce/split packets — append and split strictly on '\n'.
            Carry += FString(FUTF8ToTCHAR(reinterpret_cast<const ANSICHAR*>(Buffer), BytesRead));

            int32 NewlineIdx = INDEX_NONE;
            while (Carry.FindChar(TEXT('\n'), NewlineIdx))
            {
                FString Line = Carry.Left(NewlineIdx);
                Carry = Carry.RightChop(NewlineIdx + 1);
                Line.TrimStartAndEndInline();
                if (!Line.IsEmpty() && LineQueue)
                {
                    LineQueue->Enqueue(Line);   // hand one JSON line to the game thread
                }
            }
        }
        else
        {
            // Recv failed. On a non-blocking socket "would block" is benign
            // (no data) — anything else means the link is broken.
            const ESocketErrors Err = SS ? SS->GetLastErrorCode() : SE_NO_ERROR;
            if (Err != SE_EWOULDBLOCK && Err != SE_NO_ERROR)
            {
                SignalDropped();
                break;
            }
            FPlatformProcess::Sleep(0.002f);   // transient; don't spin hot
        }
    }
    return 0;
}
