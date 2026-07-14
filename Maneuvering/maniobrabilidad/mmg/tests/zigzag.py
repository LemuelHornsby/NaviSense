"""IMO zig-zag test (10/10 or 20/20).

A 10/10 zig-zag means: rudder is commanded to +10 deg until heading changes
by 10 deg, then to -10 deg until heading has changed by -10 deg, and so on.

First-overshoot angle = max heading excursion past the reversal trigger
after the first reversal. IMO allows:
    10/10: first overshoot <= 10 + L/U * (something) ... typically <15 deg
    20/20: first overshoot <= 25 deg

Usage:
    python -m mmg.tests.zigzag                # 10/10 with DOLPHIN.yaml
    python -m mmg.tests.zigzag --angle 20
    python -m mmg.tests.zigzag --csv out.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PARENT = _HERE.parent.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

from mmg import MmgPlant, load_config
from mmg.tests.trajectory import TrajectoryLog


def run_offline(
    plant: MmgPlant,
    angle_deg: float = 10.0,
    approach_rpm: float = 300.0,
    approach_seconds: float = 60.0,
    max_seconds: float = 300.0,
    n_reversals: int = 4,
    dt: float = 0.05,
) -> TrajectoryLog:
    log = TrajectoryLog()
    t = 0.0

    # Approach phase.
    plant.apply_commands(approach_rpm, approach_rpm, 0.0, 0.0)
    for _ in range(int(approach_seconds / dt)):
        plant.step(dt)
        log.record(t, plant.state)
        t += dt

    yaw0 = plant.state.yaw_deg
    current_rudder_sign = +1.0          # first command is positive
    reversals_done = 0

    plant.apply_commands(approach_rpm, approach_rpm, current_rudder_sign * angle_deg, 0.0)

    # Track cumulative (unwrapped) heading so dh doesn't flip sign on wraparound.
    unwrapped_yaw = yaw0
    last_yaw = yaw0

    t_phase_end = t + max_seconds
    while t < t_phase_end and reversals_done < n_reversals + 1:
        plant.step(dt)
        log.record(t, plant.state)
        t += dt

        # Unwrap yaw step-to-step.
        delta = plant.state.yaw_deg - last_yaw
        if delta > 180.0:
            delta -= 360.0
        elif delta < -180.0:
            delta += 360.0
        unwrapped_yaw += delta
        last_yaw = plant.state.yaw_deg

        dh = unwrapped_yaw - yaw0

        # Detect whether we've crossed the trigger threshold.
        crossed = (current_rudder_sign > 0 and dh >= angle_deg) \
                  or (current_rudder_sign < 0 and dh <= -angle_deg)
        if crossed:
            reversals_done += 1
            current_rudder_sign *= -1.0
            plant.apply_commands(
                approach_rpm, approach_rpm,
                current_rudder_sign * angle_deg,
                0.0,
            )

    # Compute overshoots by scanning the log: between consecutive rudder
    # reversals, the peak |dh - trigger| is the overshoot.
    overshoots = _compute_overshoots(log, yaw0, angle_deg)
    print(f"\n[zigzag] {int(angle_deg)}/{int(angle_deg)} results:")
    for i, v in enumerate(overshoots[:3]):
        print(f"  overshoot #{i+1}: {v:+.2f} deg")

    return log


def _unwrap(yaw_deg_seq, yaw0):
    out = []
    offset = 0.0
    for i, y in enumerate(yaw_deg_seq):
        if i > 0:
            delta = y - yaw_deg_seq[i - 1]
            if delta > 180.0:
                offset -= 360.0
            elif delta < -180.0:
                offset += 360.0
        out.append(y + offset - yaw0)
    return out


def _compute_overshoots(log: TrajectoryLog, yaw0: float, angle: float) -> list[float]:
    deltas = _unwrap(log.yaw_deg, yaw0)
    overshoots: list[float] = []
    # Find zero-crossings; between them, take the signed extremum.
    # The overshoot at each extremum = |peak| - angle, reported signed.
    peak = deltas[0] if deltas else 0.0
    last_crossing_sign = 1 if peak >= 0 else -1
    for d in deltas[1:]:
        s = 1 if d >= 0 else -1
        if s != last_crossing_sign:
            # We just crossed zero. Record |peak|-angle as overshoot of previous half-cycle.
            overshoots.append(abs(peak) - angle)
            peak = d
            last_crossing_sign = s
        else:
            if abs(d) > abs(peak):
                peak = d
    # Close out the final half-cycle.
    overshoots.append(abs(peak) - angle)
    return overshoots


def main():
    p = argparse.ArgumentParser(description="MMG zig-zag test (offline).")
    p.add_argument("--config", default="DOLPHIN.yaml")
    p.add_argument("--angle", type=float, default=10.0, help="10 for 10/10, 20 for 20/20.")
    p.add_argument("--rpm", type=float, default=300.0)
    p.add_argument("--approach", type=float, default=60.0)
    p.add_argument("--max", dest="max_seconds", type=float, default=300.0)
    p.add_argument("--reversals", type=int, default=4)
    p.add_argument("--dt", type=float, default=0.05)
    p.add_argument("--csv", default=None)
    args = p.parse_args()

    cfg = load_config(args.config)
    plant = MmgPlant(cfg)
    log = run_offline(
        plant,
        angle_deg=args.angle,
        approach_rpm=args.rpm,
        approach_seconds=args.approach,
        max_seconds=args.max_seconds,
        n_reversals=args.reversals,
        dt=args.dt,
    )
    if args.csv:
        log.to_csv(args.csv)
        print(f"[zigzag] wrote {args.csv}")


if __name__ == "__main__":
    main()
