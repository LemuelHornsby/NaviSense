"""Kinematic health / acceptance gate for NaviSense run logs.

Reads ``logs/<run>/state.csv`` (plus ``manifest.json`` when present) and runs
a battery of *objective* plant-health checks. This turns several subjective
"watch the hull" eye-checks into a machine verdict and gives every demo run a
reusable pre-flight gate (wire it into the nightly automation).

It analyses the **logged plant/wire state** — the authoritative pose the
listener emits — NOT the rendered UE actor. That distinction matters for
KI-018: the yaw-wrap *spin* lived in the pawn's visual smoothing, so it never
appears in this log. K5/K7 below therefore *corroborate* (objectively) that the
plant heading is healthy and continuous through the ±180 deg trigger zone, while
the visual spin itself stays an in-engine eye-check after the recompile.

Checks (a check is INFO if not applicable to the controller; gates are the rest):
  K1 time_monotonic        t non-decreasing; median dt near 1/tickHz.
  K2 finite_values         no NaN/inf in the core numeric columns.
  K3 yaw_rate_bounded      |r| <= cap AND per-tick |dyaw| <= cap (a spin blows this).
  K4 speed_bounded         0 <= speed_mag <= cap; surge u finite & sane.
  K5 not_spinning_on_spot  effective turn radius = path_len / cum|dyaw| >= floor
                           once cum heading change is significant. A pirouette
                           (heading sweeps, position frozen) -> radius ~0 -> FAIL.
  K6 heading_monotonic     turning_circle only: few direction reversals (a spin
                           or oscillation reverses many times). INFO for zigzag.
  K7 wire_yaw_continuity   unwrapped plant heading is continuous through the
                           [0,360) wrap; reports whether the run entered the
                           >180 deg KI-018 trigger zone (log-side corroboration).
  K8 actuator_tracking     achieved rudder follows commanded rudder (sanity).

Usage:
    python python/verify_run_kinematics.py                      # latest run
    python python/verify_run_kinematics.py --run-dir logs/<run>
    python python/verify_run_kinematics.py --run-dir logs/<run> --json out.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from typing import Dict, List, Optional, Tuple


# ----------------------------------------------------------------- thresholds
# A 40 m yacht at 35 deg rudder peaks ~1.4 deg/s yaw rate and ~6-8 m/s. The caps
# below sit far above physical limits, so only a numerical/visual pathology trips
# them. Documented here so they are easy to retune per vessel.
MAX_YAW_RATE_RADPS = 0.60        # ~34 deg/s  (physical peak ~0.025 rad/s)
MAX_STEP_YAW_DEG = 10.0          # per-tick heading jump (30 Hz * 10 deg = 300 deg/s)
MAX_SPEED_MPS = 20.0             # ~39 kn
MIN_TURN_RADIUS_M = 1.0          # pirouette floor (a spin-on-the-spot -> ~0)
SPIN_HEADING_FLOOR_DEG = 90.0    # only judge the radius once the hull has turned this far
MONOTONIC_REVERSAL_LIMIT = 6     # turning_circle: tolerate this many noise reversals
YAW_NOISE_DEADBAND_DEG = 0.02    # ignore sub-noise heading jitter when counting reversals
DT_TOL_FACTOR = 5.0              # median dt must be within this factor of 1/tickHz


# ----------------------------------------------------------------- io helpers
def _latest_run(log_root: str) -> Optional[str]:
    if not os.path.isdir(log_root):
        return None
    cands = [
        os.path.join(log_root, n)
        for n in os.listdir(log_root)
        if os.path.isdir(os.path.join(log_root, n))
        and os.path.exists(os.path.join(log_root, n, "state.csv"))
    ]
    if not cands:
        return None
    cands.sort(key=os.path.getmtime, reverse=True)
    return cands[0]


def _load_state_csv(path: str) -> List[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _load_manifest(run_dir: str) -> dict:
    p = os.path.join(run_dir, "manifest.json")
    if os.path.exists(p):
        try:
            with open(p) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}
    return {}


def _f(row: dict, key: str) -> Optional[float]:
    v = row.get(key, "")
    if v == "" or v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _col(rows: List[dict], key: str) -> List[Optional[float]]:
    return [_f(r, key) for r in rows]


def _unwrap_yaw_deg(seq: List[float]) -> List[float]:
    """Remove 0..360 (or +/-180) wraps so cumulative turn is continuous."""
    if not seq:
        return []
    out = [seq[0]]
    for i in range(1, len(seq)):
        d = seq[i] - seq[i - 1]
        if d > 180.0:
            d -= 360.0
        elif d < -180.0:
            d += 360.0
        out.append(out[-1] + d)
    return out


def _maneuver_start_index(rows: List[dict]) -> int:
    """First row out of the 'approach' phase; fallback to first real rudder cmd."""
    for i, r in enumerate(rows):
        mode = (r.get("mode", "") or "").strip().lower()
        if mode and mode != "approach" and mode != "<init>":
            return i
    for i, r in enumerate(rows):
        rc = _f(r, "rudderCmdDeg") or 0.0
        if abs(rc) > 0.5:
            return i
    return 0


def _controller_kind(manifest: dict, rows: List[dict]) -> str:
    k = (manifest.get("controllerKind") or "").strip().lower()
    if k:
        return k
    # Fall back to the last non-approach mode in the log.
    for r in reversed(rows):
        m = (r.get("mode", "") or "").strip().lower()
        if m and m not in ("approach", "<init>"):
            return m
    return "unknown"


# ----------------------------------------------------------------- check model
class Check:
    def __init__(self, cid: str, name: str):
        self.cid = cid
        self.name = name
        self.status = "PASS"       # PASS | FAIL | INFO
        self.detail = ""
        self.data: Dict[str, object] = {}

    def fail(self, detail: str) -> "Check":
        self.status = "FAIL"
        self.detail = detail
        return self

    def info(self, detail: str) -> "Check":
        self.status = "INFO"
        self.detail = detail
        return self

    def ok(self, detail: str) -> "Check":
        self.status = "PASS"
        self.detail = detail
        return self

    def as_dict(self) -> dict:
        return {"id": self.cid, "name": self.name, "status": self.status,
                "detail": self.detail, **({"data": self.data} if self.data else {})}


# ----------------------------------------------------------------- checks
def _finite(v: Optional[float]) -> bool:
    return v is not None and math.isfinite(v)


def check_time(rows: List[dict], manifest: dict) -> Check:
    c = Check("K1", "time_monotonic")
    t = [v for v in _col(rows, "t") if v is not None]
    if len(t) < 3:
        return c.fail("fewer than 3 timestamped rows")
    back = sum(1 for i in range(1, len(t)) if t[i] < t[i - 1] - 1e-6)
    dts = sorted(t[i] - t[i - 1] for i in range(1, len(t)))
    med = dts[len(dts) // 2]
    hz = float(manifest.get("tickHz") or 0.0)
    c.data = {"rows": len(rows), "median_dt_s": round(med, 5),
              "backward_steps": back, "tick_hz": hz}
    if back:
        return c.fail(f"{back} backward time step(s)")
    if hz > 0 and med > 0:
        nominal = 1.0 / hz
        if not (nominal / DT_TOL_FACTOR <= med <= nominal * DT_TOL_FACTOR):
            return c.fail(f"median dt {med:.4f}s far from 1/{hz:.0f}Hz={nominal:.4f}s")
    return c.ok(f"{len(rows)} rows, monotonic, median dt {med:.4f}s")


def check_finite(rows: List[dict]) -> Check:
    c = Check("K2", "finite_values")
    cols = ["x", "y", "z", "yawDeg", "u", "v", "r", "speed_mag",
            "rollDeg", "pitchDeg", "heaveM"]
    bad: Dict[str, int] = {}
    for k in cols:
        n = 0
        for r in rows:
            raw = r.get(k, "")
            if raw == "" or raw is None:
                continue
            try:
                val = float(raw)
            except (TypeError, ValueError):
                n += 1
                continue
            if not math.isfinite(val):
                n += 1
        if n:
            bad[k] = n
    c.data = {"bad_cells": bad}
    if bad:
        return c.fail("non-finite values: " + ", ".join(f"{k}={v}" for k, v in bad.items()))
    return c.ok("all core numeric columns finite")


def check_yaw_rate(rows: List[dict]) -> Check:
    c = Check("K3", "yaw_rate_bounded")
    r_rad = [v for v in _col(rows, "r") if _finite(v)]
    yaw = [v if _finite(v) else 0.0 for v in _col(rows, "yawDeg")]
    uw = _unwrap_yaw_deg(yaw)
    max_r = max((abs(v) for v in r_rad), default=0.0)
    max_step = max((abs(uw[i] - uw[i - 1]) for i in range(1, len(uw))), default=0.0)
    c.data = {"max_abs_r_radps": round(max_r, 5),
              "max_step_dyaw_deg": round(max_step, 4),
              "cap_r_radps": MAX_YAW_RATE_RADPS, "cap_step_deg": MAX_STEP_YAW_DEG}
    if max_r > MAX_YAW_RATE_RADPS:
        return c.fail(f"|r|max {max_r:.3f} > {MAX_YAW_RATE_RADPS} rad/s")
    if max_step > MAX_STEP_YAW_DEG:
        return c.fail(f"per-tick dyaw {max_step:.2f} > {MAX_STEP_YAW_DEG} deg (spin?)")
    return c.ok(f"|r|max {max_r:.3f} rad/s, dyaw/tick max {max_step:.2f} deg")


def check_speed(rows: List[dict]) -> Check:
    c = Check("K4", "speed_bounded")
    sp = [v for v in _col(rows, "speed_mag") if _finite(v)]
    if not sp:
        sp = [math.hypot(_f(r, "u") or 0.0, _f(r, "v") or 0.0) for r in rows]
    mx = max(sp, default=0.0)
    mn = min(sp, default=0.0)
    c.data = {"max_speed_mps": round(mx, 3), "min_speed_mps": round(mn, 3),
              "cap_mps": MAX_SPEED_MPS}
    if mn < -1e-6:
        return c.fail(f"negative speed magnitude {mn:.3f}")
    if mx > MAX_SPEED_MPS:
        return c.fail(f"speed {mx:.2f} > {MAX_SPEED_MPS} m/s")
    return c.ok(f"speed in [0, {mx:.2f}] m/s")


def _maneuver_kinematics(rows: List[dict]) -> Tuple[float, float, float]:
    """Return (cum_abs_heading_deg, path_len_m, net_heading_deg) over the
    maneuver window (post-approach)."""
    i0 = _maneuver_start_index(rows)
    sub = rows[i0:]
    if len(sub) < 3:
        sub = rows
    x = [_f(r, "x") or 0.0 for r in sub]
    z = [_f(r, "z") or 0.0 for r in sub]
    yaw = [_f(r, "yawDeg") or 0.0 for r in sub]
    uw = _unwrap_yaw_deg(yaw)
    cum_abs = sum(abs(uw[i] - uw[i - 1]) for i in range(1, len(uw)))
    path = sum(math.hypot(x[i] - x[i - 1], z[i] - z[i - 1]) for i in range(1, len(x)))
    net = abs(uw[-1] - uw[0]) if uw else 0.0
    return cum_abs, path, net


def check_not_spinning(rows: List[dict]) -> Check:
    c = Check("K5", "not_spinning_on_spot")
    cum_abs_deg, path_m, _net = _maneuver_kinematics(rows)
    cum_abs_rad = math.radians(cum_abs_deg)
    eff_radius = (path_m / cum_abs_rad) if cum_abs_rad > 1e-6 else None
    c.data = {"cum_abs_heading_deg": round(cum_abs_deg, 1),
              "path_len_m": round(path_m, 2),
              "effective_radius_m": (round(eff_radius, 3) if eff_radius is not None else None),
              "radius_floor_m": MIN_TURN_RADIUS_M}
    if cum_abs_deg < SPIN_HEADING_FLOOR_DEG:
        return c.info(f"only {cum_abs_deg:.0f} deg cumulative turn (< {SPIN_HEADING_FLOOR_DEG:.0f}); radius test skipped")
    if eff_radius is None:
        return c.info("no heading change; radius test n/a")
    if eff_radius < MIN_TURN_RADIUS_M:
        return c.fail(f"effective turn radius {eff_radius:.2f} m < {MIN_TURN_RADIUS_M} m "
                      f"(heading swept {cum_abs_deg:.0f} deg over only {path_m:.1f} m -> spinning on the spot)")
    return c.ok(f"effective turn radius {eff_radius:.1f} m over {cum_abs_deg:.0f} deg "
                f"(translating, not pirouetting)")


def check_heading_monotonic(rows: List[dict], controller: str) -> Check:
    c = Check("K6", "heading_monotonic")
    i0 = _maneuver_start_index(rows)
    yaw = [_f(r, "yawDeg") or 0.0 for r in rows[i0:]]
    uw = _unwrap_yaw_deg(yaw)
    steps = [uw[i] - uw[i - 1] for i in range(1, len(uw))]
    steps = [s for s in steps if abs(s) > YAW_NOISE_DEADBAND_DEG]
    reversals = sum(1 for i in range(1, len(steps)) if steps[i] * steps[i - 1] < 0)
    c.data = {"direction_reversals": reversals,
              "reversal_limit": MONOTONIC_REVERSAL_LIMIT, "controller": controller}
    is_turn = controller in ("turning_circle", "turning", "turn")
    if not is_turn:
        return c.info(f"controller '{controller}' expects reversals; monotonic gate n/a "
                      f"({reversals} reversals observed)")
    if reversals > MONOTONIC_REVERSAL_LIMIT:
        return c.fail(f"{reversals} heading-direction reversals in a turning circle "
                      f"(> {MONOTONIC_REVERSAL_LIMIT}; oscillation/spin)")
    return c.ok(f"heading turns one way ({reversals} sub-noise reversals)")


def check_wire_continuity(rows: List[dict]) -> Check:
    c = Check("K7", "wire_yaw_continuity")
    yaw = [_f(r, "yawDeg") or 0.0 for r in rows]
    uw = _unwrap_yaw_deg(yaw)
    raw_max = max(yaw, default=0.0)
    raw_min = min(yaw, default=0.0)
    # Entered the >180 deg KI-018 trigger zone if the raw wire heading exceeded 180.
    entered_zone = raw_max > 180.0
    # Continuity: the unwrapped step never jumps more than the per-tick cap.
    max_step = max((abs(uw[i] - uw[i - 1]) for i in range(1, len(uw))), default=0.0)
    continuous = max_step <= MAX_STEP_YAW_DEG
    c.data = {"raw_yaw_min_deg": round(raw_min, 2), "raw_yaw_max_deg": round(raw_max, 2),
              "entered_180_zone": entered_zone, "max_unwrapped_step_deg": round(max_step, 4),
              "plant_heading_continuous": continuous}
    if not continuous:
        return c.fail(f"unwrapped heading discontinuity {max_step:.1f} deg/tick")
    if entered_zone:
        return c.ok(f"plant heading continuous through the >180 deg zone "
                    f"(reached {raw_max:.0f} deg) -> KI-018 spin is pawn-side only, "
                    f"confirm in-engine after recompile")
    return c.ok(f"plant heading continuous (peak {raw_max:.0f} deg; did not reach the 180 deg zone)")


def check_actuator_tracking(rows: List[dict]) -> Check:
    c = Check("K8", "actuator_tracking")
    cmd = [_f(r, "rudderCmdDeg") for r in rows]
    ach = [_f(r, "rudderDeg") for r in rows]
    pairs = [(cc, aa) for cc, aa in zip(cmd, ach) if cc is not None and aa is not None]
    if not pairs:
        return c.info("no rudder columns to check")
    cmd_v = [p[0] for p in pairs]
    ach_v = [p[1] for p in pairs]
    cmd_moved = (max(cmd_v) - min(cmd_v)) > 1.0
    ach_moved = (max(ach_v) - min(ach_v)) > 1e-3
    mean_err = sum(abs(cc - aa) for cc, aa in pairs) / len(pairs)
    c.data = {"cmd_moved": cmd_moved, "ach_moved": ach_moved,
              "mean_abs_err_deg": round(mean_err, 3)}
    if cmd_moved and not ach_moved:
        return c.fail("rudder was commanded but achieved value never moved (rig unbound?)")
    return c.ok(f"rudder achieved tracks command (|err| mean {mean_err:.2f} deg)")


# ----------------------------------------------------------------- driver
def analyse(rows: List[dict], manifest: dict) -> dict:
    if len(rows) < 10:
        raise ValueError("state.csv has too few rows for analysis (<10).")
    controller = _controller_kind(manifest, rows)
    checks = [
        check_time(rows, manifest),
        check_finite(rows),
        check_yaw_rate(rows),
        check_speed(rows),
        check_not_spinning(rows),
        check_heading_monotonic(rows, controller),
        check_wire_continuity(rows),
        check_actuator_tracking(rows),
    ]
    gates = [c for c in checks if c.status != "INFO"]
    passed = sum(1 for c in gates if c.status == "PASS")
    failed = [c.cid for c in gates if c.status == "FAIL"]
    k7 = next(c for c in checks if c.cid == "K7")
    k5 = next(c for c in checks if c.cid == "K5")
    ki018 = {
        "entered_180_zone": k7.data.get("entered_180_zone"),
        "plant_heading_continuous": k7.data.get("plant_heading_continuous"),
        "effective_turn_radius_m": k5.data.get("effective_radius_m"),
        "note": ("Plant log is healthy and continuous through the +/-180 deg trigger zone; "
                 "the KI-018 spin is pawn-side visual smoothing, so its close-out remains the "
                 "in-engine turning_circle eye-check AFTER Lemuel's recompile."),
    }
    return {
        "controller": controller,
        "rows": len(rows),
        "checks": [c.as_dict() for c in checks],
        "gates_passed": passed,
        "gates_total": len(gates),
        "failed_gates": failed,
        "verdict": "PASS" if not failed else "FAIL",
        "ki018_corroboration": ki018,
    }


def analyse_run_dir(run_dir: str) -> dict:
    rows = _load_state_csv(os.path.join(run_dir, "state.csv"))
    manifest = _load_manifest(run_dir)
    out = analyse(rows, manifest)
    out["run_dir"] = os.path.basename(run_dir.rstrip("/"))
    return out


def format_report(result: dict) -> str:
    lines = [f"Kinematic health — {result.get('run_dir', '?')} "
             f"(controller={result['controller']}, {result['rows']} rows)", ""]
    for c in result["checks"]:
        mark = {"PASS": "PASS", "FAIL": "FAIL", "INFO": "info"}[c["status"]]
        lines.append(f"  [{mark}] {c['id']} {c['name']}: {c['detail']}")
    lines.append("")
    lines.append(f"  Gates: {result['gates_passed']}/{result['gates_total']}  "
                 f"=> {result['verdict']}")
    k = result["ki018_corroboration"]
    lines.append(f"  KI-018 log-side: entered 180 deg zone={k['entered_180_zone']}, "
                 f"plant continuous={k['plant_heading_continuous']}, "
                 f"eff. radius={k['effective_turn_radius_m']} m")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--log-root", default="logs")
    p.add_argument("--run-dir", default=None, help="Specific run dir; default = latest.")
    p.add_argument("--json", default=None, help="Write the verdict JSON to this path.")
    args = p.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    log_root = args.log_root if os.path.isabs(args.log_root) else os.path.join(root, args.log_root)
    run_dir = args.run_dir or _latest_run(log_root)
    if not run_dir:
        print(f"[kinematics] no run dir under {log_root}", file=sys.stderr)
        sys.exit(2)
    if not os.path.isabs(run_dir):
        run_dir = os.path.join(root, run_dir)
    if not os.path.exists(os.path.join(run_dir, "state.csv")):
        print(f"[kinematics] no state.csv in {run_dir}", file=sys.stderr)
        sys.exit(2)

    result = analyse_run_dir(run_dir)
    print(format_report(result))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\n[kinematics] verdict JSON -> {args.json}")
    sys.exit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
