"""Turning-circle analyser for NaviSense run logs.

Reads ``logs/<run>/state.csv`` produced by the bridge, computes the IMO
MSC.137(76) turning-circle metrics, and emits both a printable report and
an annotated trajectory plot. No Unity or live bridge needed — works on
any logged run.

Metrics computed (per IMO MSC.137(76)):
  Advance (A)              — distance travelled in original heading from
                             rudder-execute point to the moment heading has
                             changed by 90 deg.
  Transfer (T)             — distance in the orthogonal direction at 90 deg.
  Tactical Diameter (DT)   — orthogonal distance at 180 deg heading change.
  Steady Turning Radius R  — average |u/r| over the steady tail of the run.
  Steady Drift Angle beta  — mean |atan2(-v,u)| over the steady tail.
  Time-to-90, Time-to-180  — wall-time markers for video editing.

IMO acceptance criteria (limit checks):
  Advance        ≤ 4.5 × Lpp
  Tactical Diam. ≤ 5.0 × Lpp

Usage:
    # latest run, autodetect rudder-execute moment
    python python/analyse_turning_circle.py
    # specific run
    python python/analyse_turning_circle.py --run-dir logs/<run_folder>
    # different ship length
    python python/analyse_turning_circle.py --L-pp 38.0
    # write plot to PNG instead of showing
    python python/analyse_turning_circle.py --save plot.png
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple


# ---------------------------------------------------------------- model
@dataclass
class TurningCircleMetrics:
    advance_m: Optional[float]
    transfer_m: Optional[float]
    tactical_diameter_m: Optional[float]
    steady_radius_m: Optional[float]
    steady_drift_deg: Optional[float]
    time_to_90_s: Optional[float]
    time_to_180_s: Optional[float]
    rudder_execute_t_s: float
    rudder_execute_xz: Tuple[float, float]
    rudder_execute_yaw_deg: float


# ---------------------------------------------------------------- io
def _latest_run(log_root: str) -> Optional[str]:
    if not os.path.isdir(log_root):
        return None
    candidates: List[str] = []
    for name in os.listdir(log_root):
        full = os.path.join(log_root, name)
        if os.path.isdir(full) and os.path.exists(os.path.join(full, "state.csv")):
            candidates.append(full)
    if not candidates:
        return None
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0]


def _load_state_csv(path: str) -> List[dict]:
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _f(row: dict, key: str) -> Optional[float]:
    v = row.get(key, "")
    if v == "" or v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


# ---------------------------------------------------------------- core math
def _unwrap_yaw_deg(seq: List[float]) -> List[float]:
    """0..360 wrap removal so cumulative turn passes 180/360 cleanly."""
    if not seq:
        return []
    out = [seq[0]]
    offset = 0.0
    for i in range(1, len(seq)):
        d = seq[i] - seq[i - 1]
        if d > 180.0:
            offset -= 360.0
        elif d < -180.0:
            offset += 360.0
        out.append(seq[i] + offset)
    return out


def _detect_rudder_execute_index(rows: List[dict]) -> int:
    """Find the first row where the run leaves the 'approach' phase, i.e.
    when rudder command becomes non-zero and mode != 'approach'.

    Falls back to the first |rudderCmdDeg| > 0.5 if no mode column exists.
    """
    for i, row in enumerate(rows):
        mode = (row.get("mode", "") or "").strip().lower()
        if mode in ("turning_circle", "turning", "turn"):
            return i
    # Fallback: first significant rudder command.
    for i, row in enumerate(rows):
        rud_cmd = _f(row, "rudderCmdDeg") or 0.0
        if abs(rud_cmd) > 0.5:
            return i
    return 0


def compute_metrics(rows: List[dict]) -> TurningCircleMetrics:
    if len(rows) < 10:
        raise ValueError("state.csv has too few rows for analysis (<10).")

    # Column extraction with fallbacks.
    t = [(_f(r, "t") or 0.0) for r in rows]
    x = [(_f(r, "x") or 0.0) for r in rows]
    z = [(_f(r, "z") or 0.0) for r in rows]
    yaw_wrapped = [(_f(r, "yawDeg") or 0.0) for r in rows]
    u_ = [(_f(r, "u") or 0.0) for r in rows]
    v_ = [(_f(r, "v") or 0.0) for r in rows]
    r_ = [(_f(r, "r") or 0.0) for r in rows]

    yaw_unwrapped = _unwrap_yaw_deg(yaw_wrapped)

    i_exec = _detect_rudder_execute_index(rows)
    x0, z0 = x[i_exec], z[i_exec]
    yaw0_deg = yaw_unwrapped[i_exec]
    t0 = t[i_exec]

    # Sign of turn = sign of cumulative heading change a few seconds in.
    look = min(len(rows) - 1, i_exec + max(20, int(0.05 * (len(rows) - i_exec))))
    sign = 1.0 if (yaw_unwrapped[look] - yaw0_deg) >= 0 else -1.0

    # Initial heading direction (Unity x = east-positive, z = north-positive,
    # yaw = clockwise from +Z) to project advance along.
    yaw0_rad = math.radians(yaw0_deg)
    ax = math.sin(yaw0_rad)   # axial component (advance direction)
    az = math.cos(yaw0_rad)
    tx = math.cos(yaw0_rad) * sign       # transverse, toward the turn side
    tz = -math.sin(yaw0_rad) * sign

    def cum_turn_at(i: int) -> float:
        return sign * (yaw_unwrapped[i] - yaw0_deg)

    def find_first(deg: float) -> Optional[int]:
        for i in range(i_exec, len(rows)):
            if cum_turn_at(i) >= deg:
                return i
        return None

    i90 = find_first(90.0)
    i180 = find_first(180.0)

    def proj(i: int, ex: float, ez: float) -> float:
        return (x[i] - x0) * ex + (z[i] - z0) * ez

    advance = proj(i90, ax, az) if i90 is not None else None
    transfer = proj(i90, tx, tz) if i90 is not None else None
    tactical_diam = proj(i180, tx, tz) if i180 is not None else None

    # Steady-state averages over the last 20% of post-execute rows.
    n_post = len(rows) - i_exec
    if n_post > 50:
        tail_start = i_exec + int(0.8 * n_post)
        radii: List[float] = []
        drifts: List[float] = []
        for i in range(tail_start, len(rows)):
            if abs(r_[i]) > 1e-4:
                radii.append(abs(u_[i] / r_[i]))
            if abs(u_[i]) > 0.05:
                drifts.append(abs(math.degrees(math.atan2(-v_[i], u_[i]))))
        steady_radius = sum(radii) / len(radii) if radii else None
        steady_drift_deg = sum(drifts) / len(drifts) if drifts else None
    else:
        steady_radius = None
        steady_drift_deg = None

    return TurningCircleMetrics(
        advance_m=advance,
        transfer_m=transfer,
        tactical_diameter_m=tactical_diam,
        steady_radius_m=steady_radius,
        steady_drift_deg=steady_drift_deg,
        time_to_90_s=(t[i90] - t0) if i90 is not None else None,
        time_to_180_s=(t[i180] - t0) if i180 is not None else None,
        rudder_execute_t_s=t0,
        rudder_execute_xz=(x0, z0),
        rudder_execute_yaw_deg=yaw0_deg,
    )


# ---------------------------------------------------------------- imo
def _imo_check(label: str, value: Optional[float], limit: float, units: str) -> str:
    if value is None:
        return f"{label}: n/a (limit {limit:.2f}{units})"
    ok = "PASS" if value <= limit else "FAIL"
    return f"{label}: {value:.2f}{units}  (limit {limit:.2f}{units})  {ok}"


def imo_report(m: TurningCircleMetrics, L_pp: float) -> str:
    lines = [
        "IMO MSC.137(76) turning-circle compliance",
        f"  Lpp = {L_pp:.2f} m",
        "",
        _imo_check("  Advance / Lpp           <= 4.5",
                   (m.advance_m / L_pp) if m.advance_m else None, 4.5, ""),
        _imo_check("  Tactical Diameter / Lpp <= 5.0",
                   (m.tactical_diameter_m / L_pp) if m.tactical_diameter_m else None, 5.0, ""),
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- output
def write_text_report(run_dir: str, m: TurningCircleMetrics, L_pp: float) -> str:
    out_path = os.path.join(run_dir, "turning_circle_report.txt")
    lines: List[str] = []
    lines.append(f"Turning-circle analysis — {os.path.basename(run_dir)}")
    lines.append("")
    lines.append("Rudder-execute point:")
    lines.append(f"  t = {m.rudder_execute_t_s:.2f} s")
    lines.append(f"  (x, z) = ({m.rudder_execute_xz[0]:.2f}, {m.rudder_execute_xz[1]:.2f}) m")
    lines.append(f"  initial yaw = {m.rudder_execute_yaw_deg:.2f} deg")
    lines.append("")
    lines.append("Metrics:")
    lines.append(f"  Advance              A   = {_fmt(m.advance_m, ' m')}")
    lines.append(f"  Transfer             T   = {_fmt(m.transfer_m, ' m')}")
    lines.append(f"  Tactical Diameter    DT  = {_fmt(m.tactical_diameter_m, ' m')}")
    lines.append(f"  Steady Turn Radius   R   = {_fmt(m.steady_radius_m, ' m')}")
    lines.append(f"  Steady Drift Angle   beta= {_fmt(m.steady_drift_deg, ' deg')}")
    lines.append(f"  Time to 90 deg head      = {_fmt(m.time_to_90_s, ' s')}")
    lines.append(f"  Time to 180 deg head     = {_fmt(m.time_to_180_s, ' s')}")
    lines.append("")
    lines.append(imo_report(m, L_pp))
    text = "\n".join(lines) + "\n"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def _fmt(v: Optional[float], suffix: str = "") -> str:
    return "n/a" if v is None else f"{v:.2f}{suffix}"


# ---------------------------------------------------------------- plot
def make_plot(rows: List[dict], m: TurningCircleMetrics, save_path: Optional[str]) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[turning-circle] matplotlib not installed; skip plot. "
              "Run: pip install matplotlib", file=sys.stderr)
        return

    x = [(_f(r, "x") or 0.0) for r in rows]
    z = [(_f(r, "z") or 0.0) for r in rows]

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.plot(x, z, color="#1f77b4", lw=1.5, label="Trajectory")

    x0, z0 = m.rudder_execute_xz
    ax.scatter([x0], [z0], color="#2ca02c", s=80, zorder=5, label="Rudder execute")

    if m.advance_m is not None and m.transfer_m is not None:
        # Draw the advance/transfer reference lines.
        yaw0 = math.radians(m.rudder_execute_yaw_deg)
        ax_dir = (math.sin(yaw0), math.cos(yaw0))
        # 90-deg point
        x90 = x0 + ax_dir[0] * m.advance_m
        z90 = z0 + ax_dir[1] * m.advance_m
        ax.plot([x0, x90], [z0, z90], "--", color="#888", alpha=0.7, label="Advance ref")
        ax.scatter([x90], [z90], color="#d62728", s=60, marker="x", label=f"90 deg (A={m.advance_m:.1f}m)")

    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("x [m] (Unity east)")
    ax.set_ylabel("z [m] (Unity north)")
    title_bits = []
    if m.tactical_diameter_m:
        title_bits.append(f"DT={m.tactical_diameter_m:.1f}m")
    if m.steady_radius_m:
        title_bits.append(f"R={m.steady_radius_m:.1f}m")
    if m.steady_drift_deg:
        title_bits.append(f"beta={m.steady_drift_deg:.1f} deg")
    ax.set_title("Turning-circle trajectory" + (" — " + ", ".join(title_bits) if title_bits else ""))
    ax.legend(loc="best")

    if save_path:
        fig.savefig(save_path, dpi=140, bbox_inches="tight")
        print(f"[turning-circle] plot saved -> {save_path}")
        plt.close(fig)
    else:
        plt.show()


# ---------------------------------------------------------------- cli
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log-root", default="logs", help="Root logs folder (default: logs).")
    p.add_argument("--run-dir", default=None, help="Specific run dir; default = latest under --log-root.")
    p.add_argument("--L-pp", type=float, default=38.0, help="Lpp in metres for IMO compliance ratios. Default 38 (DOLPHIN).")
    p.add_argument("--save", default=None, help="Save plot to this PNG path. Default: write next to state.csv as turning_circle.png.")
    p.add_argument("--no-plot", action="store_true", help="Skip plotting.")
    args = p.parse_args()

    # Resolve run dir relative to listener root if a relative path was passed.
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(here)
    log_root_abs = args.log_root if os.path.isabs(args.log_root) else os.path.join(project_root, args.log_root)

    run_dir = args.run_dir or _latest_run(log_root_abs)
    if not run_dir:
        print(f"[turning-circle] no run dir found under {log_root_abs}", file=sys.stderr)
        sys.exit(2)
    if not os.path.isabs(run_dir):
        run_dir = os.path.join(project_root, run_dir)

    state_path = os.path.join(run_dir, "state.csv")
    if not os.path.exists(state_path):
        print(f"[turning-circle] no state.csv in {run_dir}", file=sys.stderr)
        sys.exit(2)

    rows = _load_state_csv(state_path)
    metrics = compute_metrics(rows)
    text = write_text_report(run_dir, metrics, args.L_pp)
    print(text)

    if not args.no_plot:
        save_path = args.save
        if save_path is None:
            save_path = os.path.join(run_dir, "turning_circle.png")
        elif not os.path.isabs(save_path):
            save_path = os.path.join(run_dir, save_path)
        make_plot(rows, metrics, save_path)


if __name__ == "__main__":
    main()
