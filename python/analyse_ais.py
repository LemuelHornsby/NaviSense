"""Analyse scripted AIS traffic against a logged own-ship run (WP-15 / gate D4).

Given one run's ``state.csv`` (the authoritative own-ship track) and an AIS preset,
this reconstructs each scripted target over the run's sim-clock and computes, per
target and over time:

    range, true & relative bearing from own-ship, CPA, TCPA, the COLREGS encounter
    type and own-ship's duty (give-way / stand-on), plus a CPA alert event when a
    target's predicted CPA first falls inside the alert range with a non-negative
    TCPA.

It is pure read-only over the log (own-ship truth only) + the deterministic
``ais_traffic`` model, so the same numbers come out headless as would come out live.
Clock note (KI-024): targets share the OWN-SHIP sim clock (state.csv ``t``), which
is internally consistent (we never join against the UE sensor clock here).

CLI:
    python python/analyse_ais.py --ais head_on                 # latest run
    python python/analyse_ais.py --run-dir logs/<run> --ais harbor_mix --write-csv
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ais_traffic as ais            # noqa: E402
import verify_run_kinematics as vrk  # noqa: E402

ALERT_RANGE_M = ais.DEFAULT_CPA_ALERT_M
TCPA_HORIZON_S = ais.DEFAULT_TCPA_HORIZON_S


# ------------------------------------------------------------------ own-ship track
@dataclass
class OwnTrack:
    t: List[float]
    e: List[float]            # east  = state.csv x
    n: List[float]            # north = state.csv z
    ve: List[float]           # east velocity (m / sim-s)
    vn: List[float]           # north velocity
    heading0_deg: float
    e0: float
    n0: float


def _own_track(rows: List[dict]) -> OwnTrack:
    """Own-ship east/north + velocity (sim-time finite difference) from state.csv."""
    t = [(vrk._f(r, "t") or 0.0) for r in rows]
    e = [(vrk._f(r, "x") or 0.0) for r in rows]    # x = east
    n = [(vrk._f(r, "z") or 0.0) for r in rows]    # z = north
    yaw = [vrk._f(r, "yawDeg") for r in rows]
    nrows = len(rows)
    ve = [0.0] * nrows
    vn = [0.0] * nrows
    for i in range(nrows):
        j0 = max(0, i - 1)
        j1 = min(nrows - 1, i + 1)
        dt = t[j1] - t[j0]
        if dt > 1e-9:
            ve[i] = (e[j1] - e[j0]) / dt
            vn[i] = (n[j1] - n[j0]) / dt
    # Initial heading: prefer course-made-good over the first ~8 s of real motion
    # (robust to a stationary first sample); fall back to the first finite yaw.
    e0, n0 = e[0], n[0]
    heading0 = None
    for i in range(nrows):
        if math.hypot(e[i] - e0, n[i] - n0) > 5.0:        # moved >5 m
            heading0 = ais.compass_from_vec(e[i] - e0, n[i] - n0)
            break
    if heading0 is None:
        for y in yaw:
            if y is not None and math.isfinite(y):
                heading0 = ais.wrap360(y)
                break
    if heading0 is None:
        heading0 = 0.0
    return OwnTrack(t=t, e=e, n=n, ve=ve, vn=vn, heading0_deg=heading0, e0=e0, n0=n0)


# ------------------------------------------------------------------ per-target stats
@dataclass
class TargetSummary:
    mmsi: int
    name: str
    ship_type: str
    min_range_m: float
    t_at_min_range_s: float
    rel_bearing_at_min_deg: float
    true_bearing_at_min_deg: float
    min_cpa_m: float
    tcpa_at_min_cpa_s: float
    encounter_at_min_range: str
    duty_at_min_range: str
    encounter_primary: str          # at the decision moment (first alert, else min range)
    duty_primary: str
    classify_time_s: float
    classify_basis: str             # "alert" | "min_range"
    first_alert_t_s: Optional[float]
    alerted: bool
    samples: int


@dataclass
class AisAnalysis:
    preset: str
    targets: List[TargetSummary]
    own_heading0_deg: float
    own_start_en: Tuple[float, float]
    duration_s: float
    alert_range_m: float
    series: Dict[int, List[Dict[str, float]]]   # mmsi -> subsampled timeseries

    def to_json(self) -> dict:
        return {
            "preset": self.preset,
            "own_heading0_deg": round(self.own_heading0_deg, 2),
            "own_start_en": [round(self.own_start_en[0], 2), round(self.own_start_en[1], 2)],
            "duration_s": round(self.duration_s, 2),
            "alert_range_m": self.alert_range_m,
            "n_targets": len(self.targets),
            "targets": [
                {k: (round(v, 3) if isinstance(v, float) else v)
                 for k, v in asdict(tg).items()}
                for tg in self.targets
            ],
        }


def analyse(rows: List[dict], preset: str,
            alert_range_m: float = ALERT_RANGE_M,
            series_points: int = 240) -> AisAnalysis:
    """Compute the AIS encounter analysis for ``rows`` (own-ship) + ``preset``."""
    if not rows:
        raise ValueError("no state rows")
    track = _own_track(rows)
    field = ais.make_field(preset, track.e0, track.n0, track.heading0_deg)
    n = len(rows)
    duration = (track.t[-1] - track.t[0]) if n > 1 else 0.0

    # per-target running aggregates
    min_range = {tg.mmsi: math.inf for tg in field.targets}
    min_range_snap: Dict[int, ais.EncounterSnapshot] = {}
    min_cpa = {tg.mmsi: math.inf for tg in field.targets}
    min_cpa_tcpa = {tg.mmsi: 0.0 for tg in field.targets}
    first_alert = {tg.mmsi: None for tg in field.targets}
    first_alert_snap: Dict[int, ais.EncounterSnapshot] = {}
    series: Dict[int, List[Dict[str, float]]] = {tg.mmsi: [] for tg in field.targets}
    stride = max(1, n // max(1, series_points))

    for i in range(n):
        ti = track.t[i]
        oe, on = track.e[i], track.n[i]
        ove, ovn = track.ve[i], track.vn[i]
        for tg in field.targets:
            st = tg.state_at(ti)
            tve, tvn = tg.velocity_at(ti)
            snap = ais.encounter_snapshot(ti, oe, on, ove, ovn, st, tve, tvn)
            m = tg.mmsi
            if snap.range_m < min_range[m]:
                min_range[m] = snap.range_m
                min_range_snap[m] = snap
            if snap.cpa_m < min_cpa[m]:
                min_cpa[m] = snap.cpa_m
                min_cpa_tcpa[m] = snap.tcpa_s
            if (first_alert[m] is None and snap.closing
                    and snap.cpa_m <= alert_range_m and 0.0 <= snap.tcpa_s <= TCPA_HORIZON_S):
                first_alert[m] = ti
                first_alert_snap[m] = snap
            if i % stride == 0:
                series[m].append({
                    "t": round(ti, 2), "range_m": round(snap.range_m, 2),
                    "true_bearing_deg": round(snap.true_bearing_deg, 2),
                    "rel_bearing_deg": round(snap.rel_bearing_deg, 2),
                    "cpa_m": round(snap.cpa_m, 2), "tcpa_s": round(snap.tcpa_s, 2),
                    "encounter": snap.encounter,
                })

    summaries: List[TargetSummary] = []
    for tg in field.targets:
        m = tg.mmsi
        snap = min_range_snap.get(m)
        psnap = first_alert_snap.get(m) or snap     # decision moment
        pbasis = "alert" if m in first_alert_snap else "min_range"
        summaries.append(TargetSummary(
            mmsi=m, name=tg.name, ship_type=tg.ship_type,
            min_range_m=min_range[m] if math.isfinite(min_range[m]) else float("nan"),
            t_at_min_range_s=snap.t if snap else 0.0,
            rel_bearing_at_min_deg=snap.rel_bearing_deg if snap else 0.0,
            true_bearing_at_min_deg=snap.true_bearing_deg if snap else 0.0,
            min_cpa_m=min_cpa[m] if math.isfinite(min_cpa[m]) else float("nan"),
            tcpa_at_min_cpa_s=min_cpa_tcpa[m],
            encounter_at_min_range=snap.encounter if snap else "no_risk",
            duty_at_min_range=snap.duty if snap else "none",
            encounter_primary=psnap.encounter if psnap else "no_risk",
            duty_primary=psnap.duty if psnap else "none",
            classify_time_s=psnap.t if psnap else 0.0,
            classify_basis=pbasis,
            first_alert_t_s=first_alert[m],
            alerted=first_alert[m] is not None,
            samples=len(series[m]),
        ))

    return AisAnalysis(
        preset=preset, targets=summaries,
        own_heading0_deg=track.heading0_deg, own_start_en=(track.e0, track.n0),
        duration_s=duration, alert_range_m=alert_range_m, series=series)


# ------------------------------------------------------------------ outputs
AIS_CSV_COLUMNS = [
    "t", "mmsi", "name", "ship_type", "latDeg", "lonDeg", "cogDeg", "sogKn",
    "range_m", "true_bearing_deg", "rel_bearing_deg", "aspect_deg",
    "cpa_m", "tcpa_s", "closing", "encounter", "duty",
]


def write_ais_csv(run_dir: str, rows: List[dict], preset: str,
                  hz: float = 1.0) -> str:
    """Write a ~``hz``-sampled ais.csv into ``run_dir`` (the shape a live run would
    log). Returns the path. One row per target per sample."""
    import csv
    track = _own_track(rows)
    field = ais.make_field(preset, track.e0, track.n0, track.heading0_deg)
    n = len(rows)
    # sample interval in rows from the sim-time spacing
    if n > 1 and (track.t[-1] - track.t[0]) > 0:
        dt = (track.t[-1] - track.t[0]) / (n - 1)
    else:
        dt = 1.0
    stride = max(1, int(round((1.0 / max(hz, 1e-3)) / max(dt, 1e-6))))
    path = os.path.join(run_dir, "ais.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(AIS_CSV_COLUMNS)
        for i in range(0, n, stride):
            ti = track.t[i]
            oe, on = track.e[i], track.n[i]
            ove, ovn = track.ve[i], track.vn[i]
            for tg in field.targets:
                st = tg.state_at(ti)
                tve, tvn = tg.velocity_at(ti)
                snap = ais.encounter_snapshot(ti, oe, on, ove, ovn, st, tve, tvn)
                w.writerow([
                    f"{ti:.2f}", tg.mmsi, tg.name, tg.ship_type,
                    f"{st['lat']:.7f}", f"{st['lon']:.7f}",
                    f"{st['cog_deg']:.2f}", f"{st['sog_mps'] * ais.MPS_TO_KN:.2f}",
                    f"{snap.range_m:.2f}", f"{snap.true_bearing_deg:.2f}",
                    f"{snap.rel_bearing_deg:.2f}", f"{snap.aspect_deg:.2f}",
                    f"{snap.cpa_m:.2f}", f"{snap.tcpa_s:.2f}",
                    "1" if snap.closing else "0", snap.encounter, snap.duty,
                ])
    return path


def make_cpa_plot(analysis: AisAnalysis, out_path: str) -> Optional[str]:
    """Range & CPA vs time per target. Returns the path, or None if matplotlib is
    unavailable / plotting fails (never raises into the caller)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:                       # noqa: BLE001
        return None
    try:
        fig, ax = plt.subplots(figsize=(9, 5))
        for tg in analysis.targets:
            ser = analysis.series.get(tg.mmsi, [])
            if not ser:
                continue
            ts = [p["t"] for p in ser]
            rng = [p["range_m"] for p in ser]
            ax.plot(ts, rng, label=f"{tg.name} ({tg.mmsi}) range")
        ax.axhline(analysis.alert_range_m, color="#d62728", ls="--", lw=1,
                   label=f"alert {analysis.alert_range_m:.0f} m")
        ax.set_xlabel("sim time [s]")
        ax.set_ylabel("range from own-ship [m]")
        ax.set_title(f"AIS traffic — preset '{analysis.preset}'")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(out_path, dpi=110)
        plt.close(fig)
        return out_path
    except Exception:                       # noqa: BLE001
        return None


# ------------------------------------------------------------------ CLI
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--log-root", default="logs")
    p.add_argument("--run-dir", default=None, help="Specific run dir; default = latest.")
    p.add_argument("--ais", default="head_on", help="AIS preset (see --list).")
    p.add_argument("--list", action="store_true", help="List AIS presets and exit.")
    p.add_argument("--alert-range-m", type=float, default=ALERT_RANGE_M)
    p.add_argument("--write-csv", action="store_true", help="Write ais.csv into the run dir.")
    args = p.parse_args()

    if args.list:
        print(ais.format_presets())
        return

    root = os.path.dirname(_HERE)
    log_root = args.log_root if os.path.isabs(args.log_root) else os.path.join(root, args.log_root)
    run_dir = args.run_dir or vrk._latest_run(log_root)
    if not run_dir:
        print(f"[ais] no run dir under {log_root}", file=sys.stderr)
        sys.exit(2)
    if not os.path.isabs(run_dir):
        run_dir = os.path.join(root, run_dir)

    rows = vrk._load_state_csv(os.path.join(run_dir, "state.csv"))
    an = analyse(rows, args.ais, alert_range_m=args.alert_range_m)
    print(f"[ais] run={os.path.basename(run_dir)} preset={an.preset} "
          f"own_heading0={an.own_heading0_deg:.1f} deg dur={an.duration_s:.0f} s")
    for tg in an.targets:
        print(f"  {tg.name:10s} ({tg.mmsi}) min_range={tg.min_range_m:8.1f} m "
              f"@t={tg.t_at_min_range_s:6.1f}s  CPA={tg.min_cpa_m:7.1f} m "
              f"TCPA={tg.tcpa_at_min_cpa_s:6.1f}s  {tg.encounter_primary} "
              f"[{tg.duty_primary}/{tg.classify_basis}]  alert={'Y' if tg.alerted else 'n'}")
    if args.write_csv:
        path = write_ais_csv(run_dir, rows, args.ais)
        print(f"[ais] wrote {path}")


if __name__ == "__main__":
    main()
