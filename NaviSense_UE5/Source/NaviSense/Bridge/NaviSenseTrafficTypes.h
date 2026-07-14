// Copyright NaviSyn Marine Solutions.
// =====================================================================
// FNaviSenseTrafficTarget — one scripted AIS traffic contact for in-engine
// rendering (WP-15B). Kept in its OWN header so the DTO<->wire-key parity
// guard (verify_compile_readiness B1) keeps scanning FNaviSenseState's
// top-level state.v1 keys only, not these nested per-target fields.
//
// Pose mirrors own-ship's wire semantics (x=East, y=Up, z=North metres;
// yawDeg CW from North), so the pawn applies the SAME NaviSenseCoords
// conversion + spawn anchor. On the Python side every target is a
// deterministic, constant-velocity function of sim-time, so the rendered
// ship matches exactly what the evidence pack scores (CPA/TCPA + COLREGS).
// Field names == JSON keys (invariant #3). Empty array => no traffic =>
// renders exactly as before.
// =====================================================================
#pragma once

#include "CoreMinimal.h"
#include "NaviSenseTrafficTypes.generated.h"

USTRUCT(BlueprintType)
struct FNaviSenseTrafficTarget
{
    GENERATED_BODY()

    UPROPERTY() int32   id = 0;          // MMSI (stable per target; maps to a slot)
    UPROPERTY() FString name;            // e.g. "MERIDIAN"
    UPROPERTY() double  x = 0.0;         // East  (m, wire frame)
    UPROPERTY() double  y = 0.0;         // Up    (m) — usually 0 (horizontal plane)
    UPROPERTY() double  z = 0.0;         // North (m, wire frame)
    UPROPERTY() double  yawDeg = 0.0;    // heading = course over ground (CW from North)
    UPROPERTY() double  sogKn = 0.0;     // speed over ground (knots) — HUD label only
    UPROPERTY() double  cogDeg = 0.0;    // course over ground (deg)  — HUD label only
};
