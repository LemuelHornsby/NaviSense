"""Actuator correspondence analyser.

Verifies that what Python *commanded* matches what Unity's actuators
*achieved*. Useful to confirm the bridge round-trip is healthy and that
the actuator dynamics in Unity are responding the way the MMG-side
controllers expect.

For each axis, the analyser:
  1. Plots commanded vs achieved over time.
  2. Computes the mean / max / RMS lag-error.
  3. Flags channels where the achieved value never moves (a sign that
     the command isn't reaching the Unity actuator, or that the visual
     rig isn't bound).

Usage:
    python python/analyse_actuators.py
    python python/analyse_actuators.py --run-dir logs/<run> --save actuators.png
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from typing import List, Optional, Tuple


def _latest_run(log_root: str) -> Optional[str]:
    if not os.path.isdir(log_root):
        return None
    cands: List[str] = []
    for n in os.listdir(log_root):
        full = os.path.join(log_root, n)
        if os.path.isdir(full) and os.path.exists(os.path.join(full, "state.csv")):
            cands.append(full)
    if not cands:
        return None
    cands.sort(key=os.path.getmtime, reverse=True)
    return cands[0]


def _load(path: str) -> List[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _f(row: dict, key: str) -> float:
    v = row.get(key, "")
    if v == "" or v is None:
        return 0.0
    try:
        return float(v)
    except ValueError:
        return 0.0


def stats(cmd: List[float], ach: List[float]) -> Tuple[float, float, float, bool]:
    """Return (mean_err, max_err, rms_err, achieved_changed_flag)."""
    if not cmd:
        return 0.0, 0.0, 0.0, False
    errs = [c - a for c, a in zip(cmd, ach)]
    abs_errs = [abs(e) for e in errs]
    mean_err = sum(abs_errs) / len(abs_errs)
    max_err = max(abs_errs)
    rms_err = math.sqrt(sum(e * e for e in errs) / len(errs))
    changed = (max(ach) - min(ach)) > 1e-3
    return mean_err, max_err, rms_err, changed


def write_text_report(run_dir: str, summaries: List[Tuple[str, str, Tuple[float, float, float, bool]]]) -> str:
    out_path = os.path.join(run_dir, "actuators_report.txt")
    lines = [f"Actuator correspondence — {os.path.basename(run_dir)}", ""]
    for name, units, (mean_e, max_e, rms_e, changed) in summaries:
        flag = "" if changed else "  [WARN: achieved value never changed]"
        lines.append(f"  {name:18s}  |err| mean={mean_e:.3f}{units}  max={max_e:.3f}{units}  rms={rms_e:.3f}{units}{flag}")
    text = "\n".join(lines) + "\n"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def make_plot(rows: List[dict], save_path: Optional[str]) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[actuators] matplotlib not installed; skip plot.", file=sys.stderr)
        return

    t = [_f(r, "t") for r in rows]
    rud = [_f(r, "rudderDeg") for r in rows]
    rud_cmd = [_f(r, "rudderCmdDeg") for r in rows]
    port_rpm = [_f(r, "portRpm") for r in rows]
    port_cmd = [_f(r, "portRpmCmd") for r in rows]
    stbd_rpm = [_f(r, "starboardRpm") for r in rows]
    stbd_cmd = [_f(r, "starboardRpmCmd") for r in rows]
    bt = [_f(r, "bowThrusterNorm") for r in rows]
    bt_cmd = [_f(r, "bowThrusterCmdNorm") for r in rows]

    fig, axes = plt.subplots(4, 1, figsize=(10, 9), sharex=True)
    axes[0].plot(t, rud_cmd, color="#d62728", lw=1.0, label="Cmd")
    axes[0].plot(t, rud, color="#1f77b4", lw=1.4, label="Achieved")
    axes[0].set_ylabel("rudder [deg]"); axes[0].legend(loc="upper right"); axes[0].grid(True, alpha=0.3)

    axes[1].plot(t, port_cmd, color="#d62728", lw=1.0, label="Cmd")
    axes[1].plot(t, port_rpm, color="#1f77b4", lw=1.4, label="Achieved")
    axes[1].set_ylabel("port RPM"); axes[1].legend(loc="upper right"); axes[1].grid(True, alpha=0.3)

    axes[2].plot(t, stbd_cmd, color="#d62728", lw=1.0, label="Cmd")
    axes[2].plot(t, stbd_rpm, color="#1f77b4", lw=1.4, label="Achieved")
    axes[2].set_ylabel("stbd RPM"); axes[2].legend(loc="upper right"); axes[2].grid(True, alpha=0.3)

    axes[3].plot(t, bt_cmd, color="#d62728", lw=1.0, label="Cmd")
    axes[3].plot(t, bt, color="#1f77b4", lw=1.4, label="Achieved")
    axes[3].set_ylabel("bow thrust [norm]"); axes[3].set_xlabel("t [s]"); axes[3].legend(loc="upper right"); axes[3].grid(True, alpha=0.3)

    fig.suptitle("Commanded vs Achieved actuator state")
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=140, bbox_inches="tight")
        print(f"[actuators] plot saved -> {save_path}")
        plt.close(fig)
    else:
        plt.show()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log-root", default="logs")
    p.add_argument("--run-dir", default=None)
    p.add_argument("--save", default=None)
    p.add_argument("--no-plot", action="store_true")
    args = p.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(here)
    log_root_abs = args.log_root if os.path.isabs(args.log_root) else os.path.join(project_root, args.log_root)

    run_dir = args.run_dir or _latest_run(log_root_abs)
    if not run_dir:
        print(f"[actuators] no run dir under {log_root_abs}", file=sys.stderr)
        sys.exit(2)
    if not os.path.isabs(run_dir):
        run_dir = os.path.join(project_root, run_dir)

    state_path = os.path.join(run_dir, "state.csv")
    if not os.path.exists(state_path):
        print(f"[actuators] no state.csv in {run_dir}", file=sys.stderr)
        sys.exit(2)

    rows = _load(state_path)
    summaries = [
        ("rudderDeg", " deg",
         stats([_f(r, "rudderCmdDeg") for r in rows], [_f(r, "rudderDeg") for r in rows])),
        ("portRpm",   " rpm",
         stats([_f(r, "portRpmCmd") for r in rows], [_f(r, "portRpm") for r in rows])),
        ("starboardRpm", " rpm",
         stats([_f(r, "starboardRpmCmd") for r in rows], [_f(r, "starboardRpm") for r in rows])),
        ("bowThrusterNorm", "",
         stats([_f(r, "bowThrusterCmdNorm") for r in rows], [_f(r, "bowThrusterNorm") for r in rows])),
    ]
    text = write_text_report(run_dir, summaries)
    print(text)

    if not args.no_plot:
        save_path = args.save
        if save_path is None:
            save_path = os.path.join(run_dir, "actuators.png")
        elif not os.path.isabs(save_path):
            save_path = os.path.join(run_dir, save_path)
        make_plot(rows, save_path)


if __name__ == "__main__":
    main()
