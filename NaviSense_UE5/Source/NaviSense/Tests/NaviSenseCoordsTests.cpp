// Copyright NaviSyn Marine Solutions.
// =====================================================================
// WP-5 (F7) — C++ Automation tests for FNaviSenseCoords.
// The ONE place wire<->Unreal conversion lives must be regression-locked
// (Risk R3). Run headless:
//   UnrealEditor-Cmd.exe <proj> -ExecCmds="Automation RunTests NaviSense; Quit"
//                         -unattended -nullrhi -log
// or in-editor: Tools > Test Automation > NaviSense.Coords.*
// =====================================================================
#include "Misc/AutomationTest.h"
#include "Core/NaviSenseCoords.h"

#if WITH_DEV_AUTOMATION_TESTS

// --- Axis mapping + metres<->cm + round-trip -------------------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FNaviSenseCoordsRoundTripTest,
    "NaviSense.Coords.RoundTrip",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNaviSenseCoordsRoundTripTest::RunTest(const FString&)
{
    // wire (x=East, y=Up, z=North) metres -> UE (X=North, Y=East, Z=Up) cm.
    const FVector E = FNaviSenseCoords::WireToUE(1.0, 0.0, 0.0); // East
    const FVector U = FNaviSenseCoords::WireToUE(0.0, 1.0, 0.0); // Up
    const FVector N = FNaviSenseCoords::WireToUE(0.0, 0.0, 1.0); // North
    TestEqual(TEXT("wire +East  -> UE +Y, 1 m = 100 cm"), E, FVector(0, 100, 0), 1e-4);
    TestEqual(TEXT("wire +Up    -> UE +Z, 1 m = 100 cm"), U, FVector(0, 0, 100), 1e-4);
    TestEqual(TEXT("wire +North -> UE +X, 1 m = 100 cm"), N, FVector(100, 0, 0), 1e-4);

    // Round-trip wire -> UE -> wire.
    const double x = 12.5, y = 3.0, z = -45.25;
    const FVector Ue = FNaviSenseCoords::WireToUE(x, y, z);
    const FVector Wire = FNaviSenseCoords::UEToWire(Ue);
    TestEqual(TEXT("round-trip x (East)"),  Wire.X, x, 1e-6);
    TestEqual(TEXT("round-trip y (Up)"),    Wire.Y, y, 1e-6);
    TestEqual(TEXT("round-trip z (North)"), Wire.Z, z, 1e-6);
    return true;
}

// --- Yaw carries directly, normalised to [0,360) --------------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FNaviSenseCoordsYawSignTest,
    "NaviSense.Coords.YawSign",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNaviSenseCoordsYawSignTest::RunTest(const FString&)
{
    // Heading carries across with NO negation (handedness preserved by the swap).
    TestEqual(TEXT("yaw 0"),    FNaviSenseCoords::WireYawToUE(0.0),    0.0,   1e-9);
    TestEqual(TEXT("yaw 90"),   FNaviSenseCoords::WireYawToUE(90.0),   90.0,  1e-9);
    TestEqual(TEXT("yaw -10 -> 350"), FNaviSenseCoords::WireYawToUE(-10.0), 350.0, 1e-9);
    TestEqual(TEXT("yaw 370 -> 10"),  FNaviSenseCoords::WireYawToUE(370.0), 10.0,  1e-9);

    // Round-trip a few headings.
    for (double Y : {0.0, 10.0, 123.4, 270.0, 359.9})
    {
        const double Back = FNaviSenseCoords::UEYawToWire(FNaviSenseCoords::WireYawToUE(Y));
        TestEqual(TEXT("yaw round-trip"), Back, Y, 1e-6);
    }

    // Yaw-rate sign: a POSITIVE wire r (rad/s) is a POSITIVE deg/s (starboard).
    // This locks the sign that the WP-2 G7 zig-zag test asserts in-engine.
    TestTrue(TEXT("+r rad/s -> +deg/s (starboard)"),
             FNaviSenseCoords::YawRateRadToDeg(0.1) > 0.0);
    TestEqual(TEXT("yaw-rate magnitude"),
              FNaviSenseCoords::YawRateRadToDeg(1.0), 57.2957795, 1e-4);
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
