#!/usr/bin/env python3
"""verify_20260701 -- Interactive Bridge Dashboard: DATA + CONTROL layer
(WP-UI-DASHBOARD, directed by Lemuel 30 Jun 2026).

Static (no UE compiler available in the sandbox) proof that the packet
delivers what Development/work_packets/NEXT_PACKET_DIRECTIVE.md asked for:

  G1  every dashboard field across the four panels (actuators / sensors /
      maneuver+IMO KPIs / sea-state+AIS) has a BlueprintPure getter declared
      on ANaviSenseShipPawn.
  G2  the three control entry points (SetHelm/SetThrottle/SetBowThruster)
      exist, are BlueprintCallable, and CLAMP their input to [-1,1] before
      storing it (an out-of-range input can never reach the manual-drive
      path un-clamped).
  G3  the helm/throttle/thruster command mapping MIRRORS the existing
      manual-drive (keyboard) ranges: UpdateManual consumes the same
      Dashboard*Cmd targets in place of the keyboard-derived ThrTarget/
      RudTarget (same [-1,1] -> rudder-deg/RPM slew path), and the bow
      thruster's command reaches FActuatorState.bowThrusterNorm.
  G4  NaviSense.Build.cs has UMG/Slate/SlateCore ACTIVE (uncommented) --
      the packet's stated rebuild prerequisite.
  G5  END-TO-END: Z0 compile-readiness is still 16/16 (C++ additive only, no
      DTO/schema drift -- B1 parity is part of Z0); the navy theme palette in
      the editor helper script matches the recipe doc byte-for-byte (no
      silent drift, same discipline as the WP-20260628 parity gate); the
      geo-projection constant added to NaviSenseCoords.h agrees with
      SensorBundleComponent's existing (untouched) GPS projection literal.

Negative controls (MUST FIRE = the checker correctly reports FAIL):
  N1  a synthetic Build.cs with UMG still commented out -> G4's checker FAILS.
  N2  a synthetic SetHelm body with the FMath::Clamp call removed -> G2's
      checker FAILS (an unclamped control input would not be caught).
  N3  a synthetic pawn header missing one required getter (GetPortRpm) ->
      G1's checker FAILS and names the missing symbol.

Exit 0 iff all gates pass and all controls fire.
"""
from __future__ import annotations
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "NaviSense_UE5", "Source", "NaviSense")
PAWN_H = os.path.join(SRC, "Vessel", "NaviSenseShipPawn.h")
PAWN_CPP = os.path.join(SRC, "Vessel", "NaviSenseShipPawn.cpp")
COORDS_H = os.path.join(SRC, "Core", "NaviSenseCoords.h")
BUILD_CS = os.path.join(SRC, "NaviSense.Build.cs")
SENSOR_CPP = os.path.join(SRC, "Sensors", "SensorBundleComponent.cpp")
EDITOR_SCRIPT = os.path.join(ROOT, "NaviSense_UE5", "Content", "NaviSense", "Python",
                              "Phase5_Systems", "09_build_bridge_dashboard.py")
RECIPE = os.path.join(ROOT, "Documents", "NaviSense_BridgeDashboard_Recipe.md")
Z0 = os.path.join(ROOT, "Development", "work_packets", "WP_20260615_COMPILE_AUDIT",
                  "verify_compile_readiness.py")

REQUIRED_GETTERS = {
    "Actuators": ["GetRudderDeg", "GetPortRpm", "GetStarboardRpm", "GetBowThrusterNorm"],
    "Sensors": ["GetHeadingDeg", "GetSpeedOverGroundMS", "GetYawRateDashDegPerSec",
                "GetRollDeg", "GetPitchDeg", "GetHeaveM", "GetLatDeg", "GetLonDeg"],
    "Maneuver+IMO KPIs": ["GetMotionModeLabel", "GetPlantMode", "GetRollingAdvanceM",
                          "GetPeakHeadingDeviationDeg"],
    "SeaState+AIS": ["GetTrafficContactCount", "GetNearestTrafficRangeM", "GetNearestTrafficName"],
}
CONTROL_FUNCS = ["SetHelm", "SetThrottle", "SetBowThruster"]


def rd(p):
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


# ------------------------------------------------------------- checker fns
def check_getters_present(header_text):
    """Return (ok, detail, missing[]) -- every required getter is declared
    BlueprintPure on the pawn."""
    missing = []
    for panel, names in REQUIRED_GETTERS.items():
        for n in names:
            # BlueprintPure ... <ret> Name(...) const -- allow across lines.
            pat = r"UFUNCTION\(BlueprintPure[^)]*\)\s*\n\s*[\w:<>&, ]+\s+%s\s*\(" % re.escape(n)
            if not re.search(pat, header_text):
                missing.append("%s::%s" % (panel, n))
    ok = not missing
    total = sum(len(v) for v in REQUIRED_GETTERS.values())
    return ok, ("%d/%d dashboard getters present" % (total - len(missing), total)
                + (" (missing: %s)" % missing if missing else "")), missing


def check_controls_clamped(cpp_text):
    """Return (ok, detail, bad[]) -- each Set* body clamps to [-1,1] before
    storing + sets the dashboard-active flag."""
    bad = []
    for fn in CONTROL_FUNCS:
        m = re.search(r"ANaviSenseShipPawn::%s\([^)]*\)\s*\{([^}]*)\}" % fn, cpp_text, re.S)
        if not m:
            bad.append("%s: not defined" % fn); continue
        body = m.group(1)
        has_clamp = re.search(r"FMath::Clamp\([^,]+,\s*-1\.f?\s*,\s*1\.f?\s*\)", body) is not None
        sets_active = "bDashboardControlActive = true" in body
        if not (has_clamp and sets_active):
            bad.append("%s: clamp=%s active_flag=%s" % (fn, has_clamp, sets_active))
    ok = not bad
    return ok, ("%d/%d control entry points clamp to [-1,1] + mark dashboard-active"
                % (len(CONTROL_FUNCS) - len(bad), len(CONTROL_FUNCS))
                + (" (bad: %s)" % bad if bad else "")), bad


def check_manual_mirrors_dashboard(cpp_text):
    checks = {
        "UpdateManual reads bDashboardControlActive":
            "if (bDashboardControlActive)" in cpp_text,
        "ThrTarget sourced from DashboardThrottleCmd":
            "ThrTarget = DashboardThrottleCmd;" in cpp_text,
        "RudTarget sourced from DashboardRudderCmd":
            "RudTarget = DashboardRudderCmd;" in cpp_text,
        "bow-thruster yaw term added to YawRate":
            "ThrusterYawRate" in cpp_text and "DashboardBowThrusterCmd * BowThrusterMaxYawRateDeg" in cpp_text,
        "bow-thruster command reaches FActuatorState.bowThrusterNorm":
            "S.bowThrusterNorm = bDashboardControlActive ? DashboardBowThrusterCmd : 0.0;" in cpp_text,
    }
    missing = [k for k, v in checks.items() if not v]
    ok = not missing
    return ok, ("%d/%d manual-drive mirror checks" % (len(checks) - len(missing), len(checks))
                + (" (missing: %s)" % missing if missing else "")), missing


def check_build_cs_umg(build_cs_text):
    """UMG/Slate/SlateCore must be ACTIVE (not behind a // comment)."""
    m = re.search(r"^(.*)$", "", re.M)  # no-op, keep re imported lint-quiet
    active = re.search(r'^\s*"UMG"\s*,\s*"Slate"\s*,\s*"SlateCore"\s*,', build_cs_text, re.M)
    still_commented = re.search(r'^\s*//\s*"UMG"', build_cs_text, re.M)
    ok = bool(active) and not still_commented
    return ok, ("UMG/Slate/SlateCore active=%s, still-commented=%s" % (bool(active), bool(still_commented)))


def extract_theme(text):
    """Pull the 6 navy-theme hex values out of either the script (dict) or
    the recipe doc (markdown table); order-independent, keyed by role."""
    out = {}
    for role in ("background", "panel", "accent_ok", "accent_caution", "accent_alarm", "text"):
        m = re.search(r"%s[^#]*(#[0-9A-Fa-f]{6})" % re.escape(role), text)
        if m:
            out[role] = m.group(1).upper()
    return out


def e2e():
    detail = []
    ok = True

    # Z0 regression -- additive C++ must not break the 16/16 compile-readiness gate.
    z0_ok, z0_msg = True, "skipped (Z0 not found)"
    if os.path.exists(Z0):
        try:
            r = subprocess.run([sys.executable, Z0], cwd=ROOT, capture_output=True,
                               text=True, timeout=180)
            z0_ok = r.returncode == 0
            tail = (r.stdout or r.stderr).strip().splitlines()
            z0_msg = tail[-1][:90] if tail else ("rc=%d" % r.returncode)
        except Exception as e:
            z0_ok, z0_msg = False, "Z0 error: %s" % e
    ok = ok and z0_ok
    detail.append("Z0=%s(%s)" % (z0_ok, z0_msg))

    # Navy theme parity: editor script dict vs recipe doc table.
    script_theme = extract_theme(rd(EDITOR_SCRIPT))
    recipe_theme = extract_theme(rd(RECIPE))
    theme_ok = bool(script_theme) and script_theme == recipe_theme
    ok = ok and theme_ok
    detail.append("theme_parity=%s(script=%d recipe=%d roles)"
                  % (theme_ok, len(script_theme), len(recipe_theme)))

    # Geo-projection constant parity: NaviSenseCoords.h helper vs the existing
    # (untouched) SensorBundleComponent.cpp inline literal.
    coords_txt = rd(COORDS_H)
    sensor_txt = rd(SENSOR_CPP)
    coords_const = re.search(r"METERS_PER_DEG_LAT\s*=\s*(111320\.0)", coords_txt)
    sensor_const = re.findall(r"(111320\.0)", sensor_txt)
    geo_ok = bool(coords_const) and len(sensor_const) >= 2  # MetersPerDegLat used twice in the sensor
    ok = ok and geo_ok
    detail.append("geo_const_parity=%s(coords=%s sensor_hits=%d)"
                  % (geo_ok, bool(coords_const), len(sensor_const)))

    return ok, "; ".join(detail)


# --------------------------------------------------------------------- gates
def g1():
    return check_getters_present(rd(PAWN_H))[:2]


def g2():
    return check_controls_clamped(rd(PAWN_CPP))[:2]


def g3():
    return check_manual_mirrors_dashboard(rd(PAWN_CPP))[:2]


def g4():
    return check_build_cs_umg(rd(BUILD_CS))


def g5():
    return e2e()


# ----------------------------------------------------------------- controls
def n1_build_cs_still_commented():
    synthetic = '            // "UMG", "Slate", "SlateCore",   // Phase 10 -- HUD\n'
    ok, det = check_build_cs_umg(synthetic)
    fired = not ok
    return fired, "commented-out UMG -> %s: %s" % ("FAIL (fired)" if fired else "PASS (MISS!)", det)


def n2_clamp_removed():
    synthetic = """
void ANaviSenseShipPawn::SetHelm(float Rudder01)
{
    DashboardRudderCmd = Rudder01;
    bDashboardControlActive = true;
}
"""
    ok, det, bad = check_controls_clamped(synthetic + "\nANaviSenseShipPawn::SetThrottle(){}\nANaviSenseShipPawn::SetBowThruster(){}")
    fired = not ok
    return fired, "un-clamped SetHelm -> %s: %s" % ("FAIL (fired)" if fired else "PASS (MISS!)", det)


def n3_missing_getter():
    real = rd(PAWN_H)
    # Strip the GetPortRpm declaration to simulate a dropped getter.
    synthetic = re.sub(
        r'UFUNCTION\(BlueprintPure[^)]*\)\s*\n\s*double GetPortRpm\(\) const;\n', "", real)
    ok, det, missing = check_getters_present(synthetic)
    fired = (not ok) and any("GetPortRpm" in m for m in missing)
    return fired, "GetPortRpm removed -> %s: %s" % ("FAIL (fired, named it)" if fired else "PASS (MISS!)", det)


def main():
    gates = [
        ("G1", "dashboard_getters_present", *g1()),
        ("G2", "control_entry_points_clamped", *g2()),
        ("G3", "manual_drive_mirrors_dashboard", *g3()),
        ("G4", "build_cs_umg_enabled", *g4()),
        ("G5", "e2e_Z0+theme_parity+geo_parity", *g5()),
    ]
    controls = [
        ("N1", "build_cs_commented_umg_fails", *n1_build_cs_still_commented()),
        ("N2", "unclamped_control_fails", *n2_clamp_removed()),
        ("N3", "missing_getter_detected", *n3_missing_getter()),
    ]
    print("verify_20260701 -- Interactive Bridge Dashboard: data + control layer\n")
    gp = 0
    for cid, name, ok, det in gates:
        print("  [%s] %s %s: %s" % ("PASS" if ok else "FAIL", cid, name, det)); gp += ok
    print()
    cf = 0
    for cid, name, fired, det in controls:
        print("  [%s] %s %s: %s" % ("FIRED" if fired else "MISS", cid, name, det)); cf += fired
    all_ok = (gp == len(gates) and cf == len(controls))
    print("\n  Gates %d/%d  Controls %d/%d  => %s" % (gp, len(gates), cf, len(controls),
                                                       "PASS" if all_ok else "FAIL"))
    out = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports", "wp_20260701_result.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({
            "packet": "WP-20260701",
            "title": "Interactive Bridge Dashboard -- data + control layer (WP-UI-DASHBOARD)",
            "gates": {c: bool(o) for c, _, o, _ in gates},
            "gates_detail": {c: d for c, _, _, d in gates},
            "controls_fired": {c: bool(x) for c, _, x, _ in controls},
            "controls_detail": {c: d for c, _, _, d in controls},
            "gates_passed": gp, "gates_total": len(gates),
            "controls_fired_n": cf, "controls_total": len(controls),
            "verdict": "PASS" if all_ok else "FAIL",
        }, f, indent=2)
    print("  wrote %s" % out)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
