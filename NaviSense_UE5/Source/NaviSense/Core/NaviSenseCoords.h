// Copyright NaviSyn Marine Solutions.
// =====================================================================
// FNaviSenseCoords — the ONE place Unity-wire <-> Unreal conversion lives.
// =====================================================================
// The Python bridge speaks Unity's frame: left-handed, Y-up, metres, with
// yaw measured clockwise from North (0 deg = +Z = North, 90 deg = +X = East).
// Unreal is left-handed, Z-up, centimetres. We map:
//     wire +X (East)  -> UE +Y
//     wire +Y (Up)    -> UE +Z
//     wire +Z (North) -> UE +X
// Handedness is preserved by this swap, so YAW DEGREES CARRY ACROSS DIRECTLY
// (do NOT negate the angle). Validate with the zig-zag sign test: command
// +10 deg rudder and confirm the bow swings to starboard in BOTH the HUD and
// the Python log. If it swings the wrong way, fix it HERE, never with a local
// negate elsewhere.
//
// Master Guide: Section 2.3 + Appendix B.
// =====================================================================
#pragma once

#include "CoreMinimal.h"

struct FNaviSenseCoords
{
    static constexpr double M_TO_CM = 100.0;
    static constexpr double CM_TO_M = 0.01;

    /** wire (x=East, y=Up, z=North) metres  ->  UE (X=North, Y=East, Z=Up) cm */
    static FORCEINLINE FVector WireToUE(double x, double y, double z)
    {
        return FVector(z * M_TO_CM, x * M_TO_CM, y * M_TO_CM);
    }

    /** UE cm  ->  wire metres, returned packed as (x=East, y=Up, z=North). */
    static FORCEINLINE FVector UEToWire(const FVector& UE)
    {
        return FVector(UE.Y * CM_TO_M, UE.Z * CM_TO_M, UE.X * CM_TO_M);
    }

    /** Heading carries directly; normalise to [0,360). */
    static FORCEINLINE double WireYawToUE(double YawDeg)
    {
        return FMath::Fmod(FMath::Fmod(YawDeg, 360.0) + 360.0, 360.0);
    }

    static FORCEINLINE double UEYawToWire(double UEYaw)
    {
        return FMath::Fmod(FMath::Fmod(UEYaw, 360.0) + 360.0, 360.0);
    }

    /** Convenience: radians/sec (wire 'r') -> degrees/sec (for visuals/HUD). */
    static FORCEINLINE double YawRateRadToDeg(double r)
    {
        return FMath::RadiansToDegrees(r);
    }

    // --- 6-DOF attitude (schema v1 rev 1.2) ---------------------------------
    // Wire attitude carries to UE directly: UE positive Pitch = bow-up, positive
    // Roll = starboard-down, matching the wire sign conventions. If the rendered
    // HEEL is mirrored (boat leans the wrong way in a turn), flip the sign HERE
    // only -- never with a local negate -- exactly as for WireYawToUE.
    /** wire pitch (+bow-up) -> UE Pitch (deg). */
    static FORCEINLINE double WirePitchToUE(double PitchDeg) { return PitchDeg; }
    /** wire roll (+starboard-down) -> UE Roll (deg). */
    static FORCEINLINE double WireRollToUE(double RollDeg) { return RollDeg; }

    // --- 6-DOF heave (schema v1 rev 1.3) ------------------------------------
    // Wire heave is +UP in metres (a wave crest lifts the hull). UE Z is up, cm,
    // so heave maps straight through *M_TO_CM, exactly like the +Y(Up)->+Z term
    // in WireToUE. If the hull bobs INVERTED (sinks on a crest), flip the sign
    // HERE only -- never with a local negate (invariant #1).
    /** wire heave (+up, metres) -> UE Z offset (cm). */
    static FORCEINLINE double WireHeaveToUE(double HeaveM) { return HeaveM * M_TO_CM; }

    // --- Synthetic GPS geo-projection (equirectangular, small-area) --------
    // Same flat-earth approximation SensorBundleComponent::BuildSensorsJson uses
    // for the plant's GPS block (metres-from-origin -> lat/lon degrees). Added
    // here (invariant #1: coordinate conversions single-sourced) as the SECOND
    // caller -- the bridge dashboard (WP_20260701) -- needs the IDENTICAL
    // projection so the live HUD lat/lon always agrees with the sensor.v1 GPS
    // block. SensorBundleComponent.cpp is left untouched (zero regression risk
    // to the validated verify_sensors_fidelity gate); it keeps its own inline
    // copy of the same constant (111320.0) -- verify_20260701.py parity-checks
    // the two literals match.
    static constexpr double METERS_PER_DEG_LAT = 111320.0;

    static FORCEINLINE double MetersPerDegLon(double Lat0Deg)
    {
        return METERS_PER_DEG_LAT * FMath::Cos(FMath::DegreesToRadians(Lat0Deg));
    }
    /** North-of-origin metres -> latitude, degrees. */
    static FORCEINLINE double NorthMToLatDeg(double NorthM, double Lat0Deg)
    {
        return Lat0Deg + NorthM / METERS_PER_DEG_LAT;
    }
    /** East-of-origin metres -> longitude, degrees. */
    static FORCEINLINE double EastMToLonDeg(double EastM, double Lat0Deg, double Lon0Deg)
    {
        const double MPerDegLon = MetersPerDegLon(Lat0Deg);
        return (MPerDegLon > 1.0) ? (Lon0Deg + EastM / MPerDegLon) : Lon0Deg;
    }

    /** Full wire attitude -> UE FRotator(Pitch, Yaw, Roll). */
    static FORCEINLINE FRotator WireAttitudeToUE(double YawDeg, double PitchDeg, double RollDeg)
    {
        return FRotator(WirePitchToUE(PitchDeg), WireYawToUE(YawDeg), WireRollToUE(RollDeg));
    }
};
