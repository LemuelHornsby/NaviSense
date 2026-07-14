#!/usr/bin/env python3
# =====================================================================
# NaviSense WP-6 Verify — native fallback / manual mode (F4) for 2026-06-17
# (pre-authored 2026-06-14 in the autonomous run).
#
# The real test is a PIE gate (drivable with no Python at stable FPS). This
# script verifies the MANUAL KINEMATIC MODEL by mirroring the exact integration
# in ANaviSenseShipPawn::UpdateManual (FInterpTo surge + speed-scaled yaw).
#
# Checks:
#   M1  full throttle -> speed approaches cruise
#   M2  "yaw needs way": full rudder at zero speed -> ~no turn
#   M3  with way, +rudder turns starboard (+yaw), -rudder turns port (-yaw)
#   M4  reverse throttle -> makes sternway (speed < 0)
#   M5  pawn source files exist
#
# Manual (UE): G_UE  with NO listener, drive in Monaco at stable FPS; 'M' toggles.
#
# Writes: NaviSense_UE5/Saved/NaviSense_Reports/wp_20260617_result.json
# =====================================================================
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
REPORT_DIR = os.path.join(PROJ, "NaviSense_UE5", "Saved", "NaviSense_Reports")
REPORT_FILE = os.path.join(REPORT_DIR, "wp_20260617_result.json")


def finterp(cur, target, dt, speed):
    """Mirror of UE FMath::FInterpTo."""
    if speed <= 0.0:
        return target
    dist = target - cur
    if abs(dist) < 1e-8:
        return target
    delta = dist * max(0.0, min(dt * speed, 1.0))
    return cur + delta


class ManualMirror:
    def __init__(self, cruise=600.0, accel=0.6, max_yaw=12.0, slew=2.5):
        self.cruise, self.accel, self.max_yaw, self.slew = cruise, accel, max_yaw, slew
        self.thr = self.rud = self.speed = self.yaw = 0.0

    def step(self, dt, thr_in, rud_in):
        self.thr = finterp(self.thr, thr_in, dt, self.slew)
        self.rud = finterp(self.rud, rud_in, dt, self.slew)
        self.speed = finterp(self.speed, self.thr * self.cruise, dt, self.accel)
        sf = min(1.0, abs(self.speed) / self.cruise) if self.cruise > 1 else 0.0
        yaw_rate = self.rud * self.max_yaw * sf
        self.yaw += yaw_rate * dt
        return yaw_rate


def run(thr, rud, secs, dt=1 / 60, m=None):
    m = m or ManualMirror()
    for _ in range(int(secs / dt)):
        m.step(dt, thr, rud)
    return m


results, passed, total = {}, 0, 0
def check(name, ok, detail):
    global passed, total
    total += 1; passed += bool(ok)
    results[name] = {"pass": bool(ok), "detail": detail}
    print(("PASS" if ok else "FAIL"), name, "-", detail)


# M1 — throttle builds speed toward cruise
m = run(1.0, 0.0, 30.0)
check("M1_throttle_to_cruise", m.speed > 0.95 * m.cruise,
      f"speed={m.speed:.1f} cm/s (cruise {m.cruise:.0f})")

# M2 — yaw needs way: full rudder from rest barely turns
m = ManualMirror()
yaw0 = m.yaw
run(0.0, 1.0, 5.0, m=m)
check("M2_yaw_needs_way", abs(m.yaw - yaw0) < 0.5,
      f"|dyaw|={abs(m.yaw - yaw0):.3f} deg at zero throttle (expect ~0)")

# M3 — with way, +rudder -> starboard (+), -rudder -> port (-)
m = run(1.0, 0.0, 10.0)                # build way
y_before = m.yaw
run(1.0, 1.0, 5.0, m=m); stbd = m.yaw - y_before
m2 = run(1.0, 0.0, 10.0)
y2 = m2.yaw
run(1.0, -1.0, 5.0, m=m2); port = m2.yaw - y2
check("M3_rudder_sign", stbd > 0.5 and port < -0.5,
      f"+rud dyaw={stbd:.2f} (>0), -rud dyaw={port:.2f} (<0)")

# M4 — reverse throttle makes sternway
m = run(-1.0, 0.0, 20.0)
check("M4_astern", m.speed < -0.5 * m.cruise, f"speed={m.speed:.1f} cm/s (astern)")

# M5 — pawn source exists
ph = os.path.join(PROJ, "NaviSense_UE5", "Source", "NaviSense", "Vessel", "NaviSenseShipPawn.h")
pc = os.path.join(PROJ, "NaviSense_UE5", "Source", "NaviSense", "Vessel", "NaviSenseShipPawn.cpp")
check("M5_pawn_files_exist", os.path.isfile(ph) and os.path.isfile(pc),
      f"h={os.path.isfile(ph)} cpp={os.path.isfile(pc)}")

results["G_UE_drivable"] = {
    "pass": "MANUAL_REQUIRED",
    "detail": ("In Monaco with NO listener: set pawn MotionSource=Manual (or tap 'M'); "
               "drive with W/S throttle, A/D rudder; vessel moves at stable FPS."),
}

os.makedirs(REPORT_DIR, exist_ok=True)
with open(REPORT_FILE, "w") as f:
    json.dump({"packet": "WP-6", "date": "2026-06-17", "preauthored": "2026-06-14",
               "theme": "Native fallback / manual mode (F4)",
               "gates_passed": passed, "gates_total": total, "gates_manual": 1,
               "auto_result": "PASS" if passed == total else "PARTIAL",
               "checks": results,
               "note": "M1-M5 verify the manual kinematic model (mirror of UpdateManual). "
                       "G_UE (drive with no Python at stable FPS) closes WP-6 + Week 1."}, f, indent=2)

print("=" * 60)
print(f"WP-6 manual-model verify: {passed}/{total} automated checks PASS  -> {REPORT_FILE}")
sys.exit(0 if passed == total else 1)
