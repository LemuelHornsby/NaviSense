// Copyright NaviSyn Marine Solutions.
#include "Sensors/SensorBundleComponent.h"
#include "Core/NaviSenseSimSubsystem.h"
#include "Core/NaviSenseCoords.h"
#include "Vessel/NaviSenseShipPawn.h"

USensorBundleComponent::USensorBundleComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
}

void USensorBundleComponent::BeginPlay()
{
    Super::BeginPlay();
    if (const UGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance() : nullptr)
    {
        Sim = GI->GetSubsystem<UNaviSenseSimSubsystem>();
    }
}

TSharedRef<FJsonObject> USensorBundleComponent::BuildSensorsJson()
{
    const double Now = Sim ? Sim->GetSimTime() : 0.0;

    TSharedRef<FJsonObject> Sensors = MakeShared<FJsonObject>();
    Sensors->SetNumberField(TEXT("time"), Now);

    if (!bEmitPlaceholderUntilPhase6)
    {
        return Sensors;
    }

    AActor* Owner = GetOwner();
    const FVector UE = Owner ? Owner->GetActorLocation() : FVector::ZeroVector;
    const FVector Wire = FNaviSenseCoords::UEToWire(UE);   // (x=East, y=Up, z=North) metres
    ANaviSenseShipPawn* Pawn = Cast<ANaviSenseShipPawn>(Owner);

    // ---------- GPS ----------
    const double SpeedMps = Pawn ? Pawn->GetSpeedMetersPerSec() : 0.0;
    const double NoiseM = (GpsPositionNoiseM > 0.f)
        ? FMath::FRandRange(-(double)GpsPositionNoiseM, (double)GpsPositionNoiseM) : 0.0;

    const double Lat0 = Sim ? Sim->RefLatDeg : 43.7350;
    const double Lon0 = Sim ? Sim->RefLonDeg : 7.4250;
    const double MetersPerDegLat = 111320.0;
    const double MetersPerDegLon = 111320.0 * FMath::Cos(FMath::DegreesToRadians(Lat0));
    const double NorthM = Wire.Z + NoiseM;   // wire z = North
    const double EastM  = Wire.X + NoiseM;   // wire x = East
    const double LatDeg = Lat0 + NorthM / MetersPerDegLat;
    const double LonDeg = (MetersPerDegLon > 1.0) ? (Lon0 + EastM / MetersPerDegLon) : Lon0;

    TSharedRef<FJsonObject> Pos = MakeShared<FJsonObject>();
    Pos->SetNumberField(TEXT("x"), Wire.X);
    Pos->SetNumberField(TEXT("y"), Wire.Y);
    Pos->SetNumberField(TEXT("z"), Wire.Z);

    TSharedRef<FJsonObject> Gps = MakeShared<FJsonObject>();
    Gps->SetObjectField(TEXT("worldPosition"), Pos);
    Gps->SetNumberField(TEXT("speed"), SpeedMps);
    Gps->SetNumberField(TEXT("latDeg"), LatDeg);
    Gps->SetNumberField(TEXT("lonDeg"), LonDeg);
    Gps->SetBoolField(TEXT("hasFix"), true);
    Sensors->SetObjectField(TEXT("gps"), Gps);

    // ---------- IMU ----------
    const double HeadingDeg = Owner
        ? FNaviSenseCoords::UEYawToWire(Owner->GetActorRotation().Yaw) : 0.0;
    double YawRate = Pawn ? Pawn->GetYawRateDegPerSec() : 0.0;
    if (ImuYawRateNoiseDegPerSec > 0.f)
    {
        YawRate += FMath::FRandRange(-(double)ImuYawRateNoiseDegPerSec, (double)ImuYawRateNoiseDegPerSec);
    }

    // Body-frame acceleration via finite difference of body velocity (m/s^2).
    const FVector BodyVelMPS = Pawn ? (Pawn->GetBodyVelocityCmPerSec() * 0.01) : FVector::ZeroVector;
    FVector AccMPS2 = FVector::ZeroVector;
    if (PrevSampleTime >= 0.0)
    {
        const double Dt = Now - PrevSampleTime;
        if (Dt > 1e-4)
        {
            AccMPS2 = (BodyVelMPS - PrevBodyVelMPS) / Dt;
        }
    }
    PrevBodyVelMPS = BodyVelMPS;
    PrevSampleTime = Now;

    TSharedRef<FJsonObject> Imu = MakeShared<FJsonObject>();
    Imu->SetNumberField(TEXT("headingDeg"), HeadingDeg);
    Imu->SetNumberField(TEXT("yawRateDegPerSec"), YawRate);
    TSharedRef<FJsonObject> Acc = MakeShared<FJsonObject>();
    Acc->SetNumberField(TEXT("x"), AccMPS2.X);
    Acc->SetNumberField(TEXT("y"), AccMPS2.Y);
    Acc->SetNumberField(TEXT("z"), AccMPS2.Z);
    Imu->SetObjectField(TEXT("acceleration"), Acc);
    Sensors->SetObjectField(TEXT("imu"), Imu);

    // ---------- own-ship pose in the PLANT/wire frame (KI-040) ----------
    // Traffic targets (state.v1 traffic[]) are PLANT-frame wire coords, but 'Wire'
    // above is the pawn's WORLD pose (plant + KI-020 spawn anchor) -- comparing the
    // two shifted every AIS/radar range/bearing by the anchor offset (found live
    // 14 Jul: head-on target reported 255 m abaft the beam instead of 1600 m ahead).
    // Invert the anchoring used by ApplyState/ApplyTraffic
    //   (Loc = Spawn + R(SpawnYaw) * WireUE   =>   WireUE = R(-SpawnYaw) * (Loc - Spawn))
    // so the geometry mirrors python/ais_traffic.range_bearing exactly. GPS/IMU stay
    // world-frame on purpose (their plant+offset contract is what
    // verify_sensors_fidelity D5-D7 validate).
    double PlantE = Wire.X, PlantN = Wire.Z, PlantHeadingDeg = HeadingDeg;
    if (Pawn)
    {
        const FRotator SpawnRotInv(0.0, -Pawn->GetSpawnYawDeg(), 0.0);
        const FVector  RelUE = SpawnRotInv.RotateVector(UE - Pawn->GetSpawnLocation());
        const FVector  PlantWire = FNaviSenseCoords::UEToWire(RelUE);
        PlantE = PlantWire.X;
        PlantN = PlantWire.Z;
        PlantHeadingDeg = FMath::Fmod(HeadingDeg - Pawn->GetSpawnYawDeg() + 720.0, 360.0);
    }

    // ---------- AIS ----------
    // The own-ship AIS receiver reports the scripted contacts the pawn is driving
    // (state.v1 traffic[]) as sensor.v1 ais.targets[]: identity (mmsi/name) +
    // course/speed from the contact, plus receiver-computed range + true/relative
    // bearing from own-ship. Geometry mirrors python/ais_traffic.range_bearing +
    // relative_bearing (compass 0=N, 90=E; rel +ve = starboard). Empty => [] (back-compat).
    TSharedRef<FJsonObject> Ais = MakeShared<FJsonObject>();
    TArray<TSharedPtr<FJsonValue>> AisTargets;
    if (Pawn)
    {
        const double OwnE = PlantE;   // plant/wire frame (KI-040)
        const double OwnN = PlantN;
        for (const FNaviSenseTrafficTarget& T : Pawn->GetTrafficTargets())
        {
            const double dE = T.x - OwnE;
            const double dN = T.z - OwnN;
            const double RangeM = FMath::Sqrt(dE * dE + dN * dN);
            double TrueBrg = FMath::RadiansToDegrees(FMath::Atan2(dE, dN));
            TrueBrg = FMath::Fmod(TrueBrg + 360.0, 360.0);                    // [0,360)
            double RelBrg = FMath::Fmod(TrueBrg - PlantHeadingDeg + 540.0, 360.0) - 180.0;  // (-180,180]
            const double TgtLat = Lat0 + T.z / MetersPerDegLat;
            const double TgtLon = (MetersPerDegLon > 1.0) ? (Lon0 + T.x / MetersPerDegLon) : Lon0;

            TSharedRef<FJsonObject> Tj = MakeShared<FJsonObject>();
            Tj->SetNumberField(TEXT("mmsi"), T.id);
            Tj->SetStringField(TEXT("name"), T.name);
            Tj->SetNumberField(TEXT("rangeM"), RangeM);
            Tj->SetNumberField(TEXT("trueBearingDeg"), TrueBrg);
            Tj->SetNumberField(TEXT("relBearingDeg"), RelBrg);
            Tj->SetNumberField(TEXT("cogDeg"), T.cogDeg);
            Tj->SetNumberField(TEXT("sogKn"), T.sogKn);
            Tj->SetNumberField(TEXT("latDeg"), TgtLat);
            Tj->SetNumberField(TEXT("lonDeg"), TgtLon);
            AisTargets.Add(MakeShared<FJsonValueObject>(Tj));
        }
    }
    Ais->SetArrayField(TEXT("targets"), AisTargets);
    Sensors->SetObjectField(TEXT("ais"), Ais);

    // ---------- CAMERA (WP-14, still-frame metadata sensor) ----------
    // The still-frame camera rides the own-ship chase rig, so its pose == own-ship
    // world position (wire frame, m) and its heading == own heading. The wire
    // carries capture METADATA (pose/FOV/resolution) + a deterministic frameRef
    // naming the HighResShot still the WP-20260630 08_capture_demo_stills.py burst
    // writes to the Screenshots dir; a consumer joins to the PNG on disk by frameRef.
    // This is NOT a live in-band pixel feed (KI-026 honesty). frameRef naming +
    // defaults mirror python/camera_sensor.camera_record (verify_20260701c parity).
    if (bEmitCamera)
    {
        const int32 FrameIdx = CameraFrameIndex++;
        const FString FrameRef = FString::Printf(TEXT("%s%05d.png"), *CameraFramePrefix, FrameIdx);

        TSharedRef<FJsonObject> CamPose = MakeShared<FJsonObject>();
        CamPose->SetNumberField(TEXT("x"), Wire.X);   // East (m)
        CamPose->SetNumberField(TEXT("y"), Wire.Y);   // Up (m)
        CamPose->SetNumberField(TEXT("z"), Wire.Z);   // North (m)

        TSharedRef<FJsonObject> Camera = MakeShared<FJsonObject>();
        Camera->SetNumberField(TEXT("fovDeg"), CameraFovDeg);
        Camera->SetNumberField(TEXT("resX"), CameraResX);
        Camera->SetNumberField(TEXT("resY"), CameraResY);
        Camera->SetNumberField(TEXT("headingDeg"), HeadingDeg);
        Camera->SetNumberField(TEXT("frameIndex"), FrameIdx);
        Camera->SetStringField(TEXT("frameRef"), FrameRef);
        Camera->SetObjectField(TEXT("pose"), CamPose);
        Sensors->SetObjectField(TEXT("camera"), Camera);
    }


    // ---------- RADAR (WP-20260702, Sensor Suite Roadmap Pt 1) ----------
    // The own-ship navigation radar reports the scripted contacts (state.v1
    // traffic[]) it can see within range as ANONYMOUS blips on sensor.v1
    // radar.contacts[]: receiver-computed range + true/relative bearing (same
    // geometry as the AIS block) PLUS a radial (range-rate) speed from own +
    // target velocity, and a closing flag. Unlike AIS it carries NO identity
    // (no mmsi/name) -- a radar return is just a blip. Contacts beyond
    // RadarMaxRangeM are not reported. HONESTY (KI-027): this is a GEOMETRIC
    // radar model derived from the known contact set, NOT an EM-propagation /
    // RCS radar simulation -- there is no beam physics, sea clutter, shadowing,
    // or false-positive model in this first pass. Geometry mirrors
    // python/radar_sensor (verify_20260702 parity). Empty/none-in-range => [].
    if (bEmitRadar)
    {
        const double OwnE = PlantE;   // plant/wire frame (KI-040)
        const double OwnN = PlantN;
        const double OwnHdgRad = FMath::DegreesToRadians(PlantHeadingDeg);
        const double OwnVE = SpeedMps * FMath::Sin(OwnHdgRad);
        const double OwnVN = SpeedMps * FMath::Cos(OwnHdgRad);
        const double KnPerMps = 1.943844;
        const double MpsPerKn = 0.5144444;

        TSharedRef<FJsonObject> Radar = MakeShared<FJsonObject>();
        Radar->SetNumberField(TEXT("maxRangeM"), RadarMaxRangeM);
        Radar->SetNumberField(TEXT("sweepDeg"), 360.0);
        TArray<TSharedPtr<FJsonValue>> Contacts;
        if (Pawn)
        {
            for (const FNaviSenseTrafficTarget& T : Pawn->GetTrafficTargets())
            {
                const double dE = T.x - OwnE;
                const double dN = T.z - OwnN;
                const double RangeM = FMath::Sqrt(dE * dE + dN * dN);
                if (RangeM > RadarMaxRangeM) { continue; }   // out of range -> no blip
                double TrueBrg = FMath::RadiansToDegrees(FMath::Atan2(dE, dN));
                TrueBrg = FMath::Fmod(TrueBrg + 360.0, 360.0);                    // [0,360)
                double RelBrg = FMath::Fmod(TrueBrg - PlantHeadingDeg + 540.0, 360.0) - 180.0;  // (-180,180]
                const double TgtVE = (T.sogKn * MpsPerKn) * FMath::Sin(FMath::DegreesToRadians(T.cogDeg));
                const double TgtVN = (T.sogKn * MpsPerKn) * FMath::Cos(FMath::DegreesToRadians(T.cogDeg));
                double RadialMps = 0.0;                                            // +ve = opening (range increasing)
                if (RangeM > 1e-6)
                {
                    RadialMps = ((TgtVE - OwnVE) * dE + (TgtVN - OwnVN) * dN) / RangeM;
                }

                TSharedRef<FJsonObject> Cj = MakeShared<FJsonObject>();
                Cj->SetNumberField(TEXT("rangeM"), RangeM);
                Cj->SetNumberField(TEXT("trueBearingDeg"), TrueBrg);
                Cj->SetNumberField(TEXT("relBearingDeg"), RelBrg);
                Cj->SetNumberField(TEXT("radialSpeedKn"), RadialMps * KnPerMps);
                Cj->SetBoolField(TEXT("closing"), RadialMps < 0.0);
                Contacts.Add(MakeShared<FJsonValueObject>(Cj));
            }
        }
        Radar->SetArrayField(TEXT("contacts"), Contacts);
        Sensors->SetObjectField(TEXT("radar"), Radar);
    }

    return Sensors;
}
