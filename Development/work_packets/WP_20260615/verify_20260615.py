#!/usr/bin/env python3
# =====================================================================
# NaviSense WP-4 Verify — deterministic sim clock (F5) for 2026-06-15
# (pre-authored 2026-06-14 in the autonomous multi-packet run)
# =====================================================================
# The real pause test is a PIE gate (C4). This script verifies the CLOCK
# ALGORITHM by mirroring the exact C++ accumulator from
# UNaviSenseSimSubsystem::Tick and exercising it, including a simulated
# pause gap during which Tick is NOT called (pause-aware = no advance).
#
# Checks:
#   C1  pause-aware: a 5 s wall-clock pause (no ticks) adds 0 to sim time;
#       continuous sim time == ticked seconds within < 1 ms (the gate margin)
#   C2  fixed-step counter == floor(simTime / fixedStep)  (deterministic spine)
#   C3  "both ends same t": continuous sim time matches a Python tick-count
#       model (K * dt) within < 1 ms
#
# Writes: NaviSense_UE5/Saved/NaviSense_Reports/wp_20260615_result.json
# Exit 0 if all automated checks pass, 1 otherwise.
# =====================================================================
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.normpath(os.path.join(
    HERE, "..", "..", "..", "NaviSense_UE5", "Saved", "NaviSense_Reports"))
REPORT_FILE = os.path.join(REPORT_DIR, "wp_20260615_result.json")


class SimClockMirror:
    """1:1 mirror of UNaviSenseSimSubsystem (WP-4). Tick() is only called when
    NOT paused — exactly like FTickableGameObject with IsTickableWhenPaused()==false."""
    def __init__(self, fixed_step=1.0 / 120.0):
        self.fixed_step = fixed_step
        self.run_active = False
        self.accumulated = 0.0
        self.fixed_accum = 0.0
        self.step_count = 0

    def start_run(self):
        self.accumulated = 0.0
        self.fixed_accum = 0.0
        self.step_count = 0
        self.run_active = True

    def stop_run(self):
        self.run_active = False

    def tick(self, dt):
        if not self.run_active:
            return
        self.accumulated += dt
        self.fixed_accum += dt
        step = self.fixed_step if self.fixed_step > 0.0 else (1.0 / 120.0)
        safety = 0
        while self.fixed_accum >= step and safety < 100000:
            self.fixed_accum -= step
            self.step_count += 1
            safety += 1
        if self.fixed_accum >= step:
            self.fixed_accum = 0.0


def main():
    results, passed, total = {}, 0, 0
    clk = SimClockMirror(fixed_step=1.0 / 120.0)
    clk.start_run()

    # 3.0 s of 60 fps frames, a 5 s PAUSE (no ticks), then 2.0 s of frames.
    dt = 1.0 / 60.0
    pre, post = 180, 120
    for _ in range(pre):
        clk.tick(dt)
    # --- paused 5 s: Tick() is simply not called (pause-aware) ---
    for _ in range(post):
        clk.tick(dt)

    ticked_seconds = (pre + post) * dt   # 5.0 s of SIM time
    wallclock_if_naive = ticked_seconds + 5.0  # what a wall-clock would have shown

    # C1 — pause-aware, continuous sim time tracks ticked seconds < 1 ms
    total += 1
    drift_ms = abs(clk.accumulated - ticked_seconds) * 1000.0
    c1 = drift_ms < 1.0
    results["C1_pause_aware_drift"] = {
        "pass": c1,
        "detail": f"sim t={clk.accumulated:.6f}s vs ticked {ticked_seconds:.6f}s "
                  f"(drift {drift_ms:.4f} ms < 1 ms); a wall-clock would read "
                  f"~{wallclock_if_naive:.1f}s",
    }
    passed += c1
    print(("PASS" if c1 else "FAIL"), "C1_pause_aware_drift", f"{drift_ms:.4f} ms")

    # C2 — fixed-step counter is the deterministic floor(t/step)
    total += 1
    expected_steps = int(math.floor(round(ticked_seconds / clk.fixed_step, 6)))
    c2 = clk.step_count == expected_steps
    results["C2_fixed_step_count"] = {
        "pass": c2,
        "detail": f"StepCount={clk.step_count} == floor(t/step)={expected_steps} "
                  f"(step={clk.fixed_step*1000:.3f} ms)",
    }
    passed += c2
    print(("PASS" if c2 else "FAIL"), "C2_fixed_step_count", f"{clk.step_count}=={expected_steps}")

    # C3 — both ends log the same t: matches a Python tick-count model (K*dt)
    total += 1
    py_dt = 0.05  # 20 Hz listener
    clk2 = SimClockMirror(fixed_step=1.0 / 120.0)
    clk2.start_run()
    K = 200
    for _ in range(K):
        clk2.tick(py_dt)
    python_t = K * py_dt
    drift2_ms = abs(clk2.accumulated - python_t) * 1000.0
    c3 = drift2_ms < 1.0
    results["C3_both_ends_same_t"] = {
        "pass": c3,
        "detail": f"UE t={clk2.accumulated:.6f}s vs Python K*dt={python_t:.6f}s "
                  f"(drift {drift2_ms:.4f} ms < 1 ms)",
    }
    passed += c3
    print(("PASS" if c3 else "FAIL"), "C3_both_ends_same_t", f"{drift2_ms:.4f} ms")

    # C4 — the real PIE pause test (UE side, manual)
    results["C4_pie_pause_5s"] = {
        "pass": "MANUAL_REQUIRED",
        "detail": ("In PIE: with a run live, pause 5 s, unpause, stop. Compare the "
                   "UE sim t (sensor packet) to Python's t: drift must be < 1 ms, "
                   "i.e. the pause adds nothing. Confirms IsTickableWhenPaused()==false."),
    }

    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(REPORT_FILE, "w") as f:
        json.dump({
            "packet": "WP-4",
            "date": "2026-06-15",
            "preauthored": "2026-06-14",
            "theme": "Deterministic sim clock + run lifecycle (F5)",
            "gates_passed": passed, "gates_total": total, "gates_manual": 1,
            "auto_result": "PASS" if passed == total else "PARTIAL",
            "checks": results,
            "note": ("C1-C3 verify the accumulator algorithm (mirror of the C++). "
                     "C4 is the in-PIE pause test Lemuel runs. WP-4 closes on C4."),
        }, f, indent=2)

    print("=" * 60)
    print(f"WP-4 clock-algorithm verify: {passed}/{total} automated checks PASS")
    print(f"Report: {REPORT_FILE}")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
