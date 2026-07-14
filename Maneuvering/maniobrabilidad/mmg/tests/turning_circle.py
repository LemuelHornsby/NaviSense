"""IMO turning-circle test.

Procedure (IMO MSC.137(76)):
  1. Accelerate the ship to approach speed at design RPM.
  2. Hold course until steady.
  3. Apply maximum rudder (35 deg) in one direction.
  4. Continue until heading has changed by at least 540 deg.

Metrics reported:
  - advance         : forward distance from rudder-order point to 90 deg heading change
  - transfer        : lateral distance from rudder-order point to 90 deg heading change
  - tactical_diameter : lateral distance from rudder-order point to 180 deg heading change
  - steady_turn_radius : radius of the tail circle

Usage:
  $ python -m mmg.tests.turning_circle                      # uses DOLPHIN.yaml
  $ python -m mmg.tests.turning_circle --rudder 35 --side stbd
  $ python -m mmg.tests.turning_circle --live 127.0.0.1:5005 # drive Unity via bridge

Offline mode runs the MMG model in isolation. Live mode connects as a
controller client to python_listener.py -- which must already be running --
and pushes actuator commands while reading back sensor packets.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

# Make the `mmg` package importable when invoking as a script.
_HERE = Path(__file__).resolve().parent
_PARENT = _HERE.parent.parent  # .../maniobrabilidad
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

from mmg import MmgPlant, load_config
from mmg.tests.trajectory import TrajectoryLog


def run_offline(
    plant: MmgPlant,
    approach_rpm: float = 300.0,
    rudder_deg: float = 35.0,
    side: str = "stbd",
    approach_seconds: float = 60.0,
    turn_seconds: float = 180.0,
    dt: float = 0.05,
) -> TrajectoryLog:
    sign = +1.0 if side == "stbd" else -1.0
    log = TrajectoryLog()
    t = 0.0

    # Phase 1: approach.
    plant.apply_commands(approach_rpm, approach_rpm, 0.0, 0.0)
    for _ in range(int(approach_seconds / dt)):
        plant.step(dt)
        log.record(t, plant.state)
        t += dt

    # Zero origin at rudder-order instant so advance/transfer are easy to read.
    x0 = plant.state.x
    z0 = plant.state.z
    yaw0 = plant.state.yaw_deg

    # Phase 2: apply rudder.
    plant.apply_commands(approach_rpm, approach_rpm, sign * rudder_deg, 0.0)
    for _ in range(int(turn_seconds / dt)):
        plant.step(dt)
        log.record(t, plant.state)
        t += dt

    # --- Metrics --------------------------------------------------------
    metrics = compute_metrics(log, x0, z0, yaw0, side)
    print("\n[turning-circle] metrics:")
    for k, v in metrics.items():
        print(f"  {k:24s} = {v}")
    return log


def compute_metrics(log: TrajectoryLog, x0: float, z0: float, yaw0: float, side: str) -> dict:
    sign = +1.0 if side == "stbd" else -1.0

    # Unwrap the heading trace so we can measure cumulative turn past 180 deg.
    unwrapped = _unwrap_heading(log.yaw_deg)
    u0 = unwrapped[0]

    def cumulative_change(i: int) -> float:
        return sign * (unwrapped[i] - u0)

    # Find index where cumulative heading has changed by 90 and 180 deg.
    i90 = _first_cross(log, lambda i: cumulative_change(i) >= 90.0)
    i180 = _first_cross(log, lambda i: cumulative_change(i) >= 180.0)

    # Advance is axial distance in the initial heading direction.
    yaw0_rad = math.radians(yaw0)
    ax = math.sin(yaw0_rad)   # initial heading x-component (Unity convention)
    az = math.cos(yaw0_rad)
    # Transfer is the orthogonal component, toward the turn direction.
    tx = math.cos(yaw0_rad) * sign
    tz = -math.sin(yaw0_rad) * sign

    def proj(i, ex, ez):
        dx = log.x[i] - x0
        dz = log.z[i] - z0
        return dx * ex + dz * ez

    advance = proj(i90, ax, az) if i90 is not None else None
    transfer = proj(i90, tx, tz) if i90 is not None else None
    tactical_diameter = proj(i180, tx, tz) if i180 is not None else None

    # Steady turn radius: average radius over last 20% of the log.
    n = len(log.t)
    tail = range(int(0.8 * n), n)
    if tail:
        rad = []
        for i in tail:
            if abs(log.r[i]) > 1e-4:
                rad.append(abs(log.u[i] / log.r[i]))
        steady_turn_radius = sum(rad) / len(rad) if rad else None
    else:
        steady_turn_radius = None

    return {
        "advance_m": _fmt(advance),
        "transfer_m": _fmt(transfer),
        "tactical_diameter_m": _fmt(tactical_diameter),
        "steady_turn_radius_m": _fmt(steady_turn_radius),
        "tactical_diameter_over_L_pp": _fmt(tactical_diameter / 38.0 if tactical_diameter else None),
    }


def _first_cross(log: TrajectoryLog, predicate) -> int | None:
    for i in range(len(log.t)):
        if predicate(i):
            return i
    return None


def _unwrap_heading(yaw_deg_seq) -> list[float]:
    """Undo the 0..360 wrap so cumulative turn is continuous."""
    if not yaw_deg_seq:
        return []
    out = [yaw_deg_seq[0]]
    offset = 0.0
    for i in range(1, len(yaw_deg_seq)):
        delta = yaw_deg_seq[i] - yaw_deg_seq[i - 1]
        if delta > 180.0:
            offset -= 360.0
        elif delta < -180.0:
            offset += 360.0
        out.append(yaw_deg_seq[i] + offset)
    return out


def _fmt(v):
    return f"{v:.2f}" if isinstance(v, float) else "n/a"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="MMG turning-circle test (offline).")
    p.add_argument("--config", default="DOLPHIN.yaml")
    p.add_argument("--rpm", type=float, default=300.0)
    p.add_argument("--rudder", type=float, default=35.0)
    p.add_argument("--side", choices=["stbd", "port"], default="stbd")
    p.add_argument("--approach", type=float, default=60.0)
    p.add_argument("--turn", type=float, default=180.0)
    p.add_argument("--dt", type=float, default=0.05)
    p.add_argument("--csv", default=None, help="Optional output CSV path.")
    args = p.parse_args()

    cfg = load_config(args.config)
    plant = MmgPlant(cfg)
    log = run_offline(
        plant,
        approach_rpm=args.rpm,
        rudder_deg=args.rudder,
        side=args.side,
        approach_seconds=args.approach,
        turn_seconds=args.turn,
        dt=args.dt,
    )
    if args.csv:
        log.to_csv(args.csv)
        print(f"[turning-circle] wrote {args.csv}")


if __name__ == "__main__":
    main()
