"""Zig-zag analyser for NaviSense run logs.

Reads ``logs/<run>/state.csv`` produced by the bridge, computes IMO
zig-zag overshoots and oscillation period, and emits a printable report
plus an annotated heading-vs-time plot. Works offline on any logged run.

Metrics computed (per IMO MSC.137(76)):
  1st overshoot angle  — max(|heading - reference|) after the first rudder
                          reversal that follows the first heading capture.
  2nd overshoot angle  — same, after the second reversal.
  Period of oscillation — average time between successive same-direction
                          heading peaks once the manoeuvre is steady.

IMO acceptance criteria for Z-test 10/10 at service speed (V) and Lpp (L):
  1st overshoot ≤ 10 + (5·L/V)/3.6 deg  (loose at low speed; tight at high)
  2nd overshoot ≤ 25 deg
For 20/20:
  1st overshoot ≤ 25 deg

Usage:
    python python/analyse_zigzag.py
    python python/analyse_zigzag.py --run-dir logs/<run_folder> --angle 10
    python python/analyse_zigzag.py --save zigzag.png
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ---------------------------------------------------------------- model
@dataclass
class ZigzagMetrics:
    angle_deg: float
    overshoots_deg: List[float] = field(default_factory=list)
    reversal_times_s: List[float] = field(default_factory=list)
    period_s: Optional[float] = None
    initial_yaw_deg: float = 0.0
    maneuver_start_t: float = 0.0


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


def _unwrap_yaw_deg(seq: List[float]) -> List[float]:
    if not seq:
        return []
    out = [seq[0]]
    for i in range(1, len(seq)):
        d = seq[i] - out[-1]
        if d > 180.0:
            d -= 360.0
        elif d < -180.0:
            d += 360.0
        out.append(out[-1] + d)
    return out


# ---------------------------------------------------------------- core math
def _detect_maneuver_start(rows: List[dict]) -> int:
    """First row where the run leaves 'approach' phase. Falls back to first
    significant rudder command."""
    for i, row in enumerate(rows):
        mode = (row.get("mode", "") or "").strip().lower()
        if mode in ("zigzag", "zigzag_10", "zigzag_20", "zz10", "zz20") or mode.startswith("zigzag"):
            return i
    for i, row in enumerate(rows):
        rud_cmd = _f(row, "rudderCmdDeg") or 0.0
        if abs(rud_cmd) > 0.5:
            return i
    return 0


def compute_metrics(rows: List[dict], expected_angle_deg: float) -> ZigzagMetrics:
    if len(rows) < 50:
        raise ValueError("state.csv has too few rows for zig-zag analysis (<50).")

    t = [(_f(r, "t") or 0.0) for r in rows]
    yaw = [(_f(r, "yawDeg") or 0.0) for r in rows]
    rud_cmd = [(_f(r, "rudderCmdDeg") or 0.0) for r in rows]
    yaw_unw = _unwrap_yaw_deg(yaw)

    i_start = _detect_maneuver_start(rows)
    yaw0 = yaw_unw[i_start]
    t0 = t[i_start]

    # Detect rudder-reversal events (sign flips of commanded rudder over the
    # threshold +/- expected_angle_deg/2).
    reversal_indices: List[int] = []
    last_sign = 0
    for i in range(i_start, len(rows)):
        s = 1 if rud_cmd[i] > expected_angle_deg * 0.5 else (-1 if rud_cmd[i] < -expected_angle_deg * 0.5 else 0)
        if s != 0 and last_sign != 0 and s != last_sign:
            reversal_indices.append(i)
        if s != 0:
            last_sign = s

    # Overshoots: between successive reversals, heading swings past the
    # reference yaw0 by some amount; record max excursion in the *opposite*
    # direction of the previous rudder.
    overshoots: List[float] = []
    boundaries = [i_start] + reversal_indices + [len(rows) - 1]
    for k in range(len(boundaries) - 1):
        a, b = boundaries[k], boundaries[k + 1]
        if b - a < 2:
            continue
        # Sign of rudder during this segment.
        seg_signs = [rud_cmd[i] for i in range(a, b)]
        nonzero = [s for s in seg_signs if abs(s) > expected_angle_deg * 0.5]
        if not nonzero:
            continue
        seg_sign = 1 if nonzero[0] > 0 else -1
        # Overshoot is heading deviation in the direction opposite the
        # previous rudder kick, i.e. heading exceeds the new reference target
        # of seg_sign * expected_angle_deg before the next reversal.
        max_excursion = 0.0
        for i in range(a, b):
            excursion = (yaw_unw[i] - yaw0) * seg_sign - expected_angle_deg
            if excursion > max_excursion:
                max_excursion = excursion
        if max_excursion > 0.0:
            overshoots.append(max_excursion)

    # Period: average time between same-sign reversals (i.e. one full cycle).
    period: Optional[float] = None
    if len(reversal_indices) >= 3:
        diffs: List[float] = []
        for i in range(2, len(reversal_indices)):
            diffs.append(t[reversal_indices[i]] - t[reversal_indices[i - 2]])
        if diffs:
            period = sum(diffs) / len(diffs)

    return ZigzagMetrics(
        angle_deg=expected_angle_deg,
        overshoots_deg=overshoots,
        reversal_times_s=[t[i] - t0 for i in reversal_indices],
        period_s=period,
        initial_yaw_deg=yaw0,
        maneuver_start_t=t0,
    )


# ---------------------------------------------------------------- imo
def imo_report(m: ZigzagMetrics, V_mps: float, L_pp: float) -> str:
    lines = [f"IMO MSC.137(76) zig-zag {m.angle_deg:.0f}/{m.angle_deg:.0f} compliance"]
    o1 = m.overshoots_deg[0] if len(m.overshoots_deg) >= 1 else None
    o2 = m.overshoots_deg[1] if len(m.overshoots_deg) >= 2 else None
    if abs(m.angle_deg - 10.0) < 1e-3:
        # IMO 10/10 limits depend on speed and Lpp.
        v_kn = V_mps * 1.94384
        lim1 = 10.0 + (5.0 * L_pp / max(v_kn, 0.1))   # rough approximation per IMO formula
        lim2 = 25.0
        lines.append(f"  V = {V_mps:.2f} m/s ({v_kn:.2f} kn)  Lpp = {L_pp:.2f} m")
        lines.append(_imo_check("  1st overshoot", o1, lim1, " deg"))
        lines.append(_imo_check("  2nd overshoot", o2, lim2, " deg"))
    elif abs(m.angle_deg - 20.0) < 1e-3:
        lim1 = 25.0
        lines.append(f"  V = {V_mps:.2f} m/s  Lpp = {L_pp:.2f} m")
        lines.append(_imo_check("  1st overshoot", o1, lim1, " deg"))
    else:
        lines.append(f"  (angle {m.angle_deg:.0f} doesn't have a built-in IMO criterion)")
    return "\n".join(lines)


def _imo_check(label: str, value: Optional[float], limit: float, units: str) -> str:
    if value is None:
        return f"{label}: n/a (limit {limit:.2f}{units})"
    ok = "PASS" if value <= limit else "FAIL"
    return f"{label}: {value:.2f}{units}  (limit {limit:.2f}{units})  {ok}"


# ---------------------------------------------------------------- output
def _fmt(v: Optional[float], suffix: str = "") -> str:
    return "n/a" if v is None else f"{v:.2f}{suffix}"


def write_text_report(run_dir: str, m: ZigzagMetrics, V_mps: float, L_pp: float) -> str:
    out_path = os.path.join(run_dir, f"zigzag_{int(m.angle_deg)}_report.txt")
    lines: List[str] = []
    lines.append(f"Zig-zag {m.angle_deg:.0f}/{m.angle_deg:.0f} analysis — {os.path.basename(run_dir)}")
    lines.append("")
    lines.append(f"Maneuver start t  : {m.maneuver_start_t:.2f} s")
    lines.append(f"Initial yaw       : {m.initial_yaw_deg:.2f} deg")
    lines.append(f"Reversals (sim t) : {len(m.reversal_times_s)} -> {[round(x,1) for x in m.reversal_times_s]}")
    lines.append(f"Overshoots (deg)  : {[round(x,2) for x in m.overshoots_deg]}")
    lines.append(f"Period (mean)     : {_fmt(m.period_s, ' s')}")
    lines.append("")
    lines.append(imo_report(m, V_mps, L_pp))
    text = "\n".join(lines) + "\n"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


# ---------------------------------------------------------------- plot
def make_plot(rows: List[dict], m: ZigzagMetrics, save_path: Optional[str]) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[zigzag] matplotlib not installed; skip plot. "
              "Run: pip install matplotlib", file=sys.stderr)
        return

    t = [(_f(r, "t") or 0.0) for r in rows]
    yaw = [(_f(r, "yawDeg") or 0.0) for r in rows]
    rud = [(_f(r, "rudderDeg") or 0.0) for r in rows]
    yaw_unw = _unwrap_yaw_deg(yaw)
    yaw_rel = [y - m.initial_yaw_deg for y in yaw_unw]
    t_rel = [ti - m.maneuver_start_t for ti in t]

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(t_rel, yaw_rel, color="#1f77b4", lw=1.4, label="Heading (rel.)")
    ax1.axhline(+m.angle_deg, color="#999", ls="--", lw=0.8)
    ax1.axhline(-m.angle_deg, color="#999", ls="--", lw=0.8)
    ax1.axhline(0, color="#000", ls=":", lw=0.6)
    ax1.set_xlabel("time since maneuver start [s]")
    ax1.set_ylabel("heading deviation [deg]", color="#1f77b4")
    ax1.tick_params(axis="y", labelcolor="#1f77b4")
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(t_rel, rud, color="#d62728", lw=1.0, alpha=0.7, label="Rudder")
    ax2.set_ylabel("rudder angle [deg]", color="#d62728")
    ax2.tick_params(axis="y", labelcolor="#d62728")

    title_bits = [f"Z-{int(m.angle_deg)}/{int(m.angle_deg)}"]
    if m.overshoots_deg:
        title_bits.append(f"1st OS={m.overshoots_deg[0]:.1f} deg")
    if len(m.overshoots_deg) > 1:
        title_bits.append(f"2nd OS={m.overshoots_deg[1]:.1f} deg")
    if m.period_s:
        title_bits.append(f"period={m.period_s:.1f} s")
    ax1.set_title("Zig-zag — " + ", ".join(title_bits))

    if save_path:
        fig.savefig(save_path, dpi=140, bbox_inches="tight")
        print(f"[zigzag] plot saved -> {save_path}")
        plt.close(fig)
    else:
        plt.show()


# ---------------------------------------------------------------- cli
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log-root", default="logs", help="Root logs folder.")
    p.add_argument("--run-dir", default=None, help="Specific run dir (default: latest).")
    p.add_argument("--angle", type=float, default=10.0, help="Zig-zag angle: 10 for 10/10, 20 for 20/20. Default 10.")
    p.add_argument("--V", type=float, default=2.5, help="Service speed in m/s used for the IMO formula. Default 2.5.")
    p.add_argument("--L-pp", type=float, default=38.0, help="Lpp in metres. Default 38 (DOLPHIN).")
    p.add_argument("--save", default=None, help="Save plot to PNG. Default: zigzag_<angle>.png next to state.csv.")
    p.add_argument("--no-plot", action="store_true", help="Skip plotting.")
    args = p.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(here)
    log_root_abs = args.log_root if os.path.isabs(args.log_root) else os.path.join(project_root, args.log_root)

    run_dir = args.run_dir or _latest_run(log_root_abs)
    if not run_dir:
        print(f"[zigzag] no run dir under {log_root_abs}", file=sys.stderr)
        sys.exit(2)
    if not os.path.isabs(run_dir):
        run_dir = os.path.join(project_root, run_dir)

    state_path = os.path.join(run_dir, "state.csv")
    if not os.path.exists(state_path):
        print(f"[zigzag] no state.csv in {run_dir}", file=sys.stderr)
        sys.exit(2)

    rows = _load_state_csv(state_path)
    metrics = compute_metrics(rows, args.angle)
    text = write_text_report(run_dir, metrics, args.V, args.L_pp)
    print(text)

    if not args.no_plot:
        save_path = args.save
        if save_path is None:
            save_path = os.path.join(run_dir, f"zigzag_{int(args.angle)}.png")
        elif not os.path.isabs(save_path):
            save_path = os.path.join(run_dir, save_path)
        make_plot(rows, metrics, save_path)


if __name__ == "__main__":
    main()
