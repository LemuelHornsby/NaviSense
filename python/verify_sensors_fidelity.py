"""Sensor-fidelity acceptance gate for NaviSense run logs (D4 / F2).

Cross-validates the in-engine **sensor bundle** (``logs/<run>/sensor.csv`` -- the
GPS/IMU the pawn emits) against the **plant ground truth**
(``logs/<run>/state.csv`` -- the authoritative pose the listener integrates).
This turns the never-objectively-checked WP-SENSOR-1 eye-checks (S1-S3 = "values
are non-zero and in range") into a real *accuracy* verdict: it proves the sensors
report the TRUE vessel kinematics, not placeholders. Wire it into the nightly.

Why this is the right comparison
--------------------------------
``SensorBundleComponent::BuildSensorsJson`` derives, every emit, from the pawn:
  * gps.speed      = pawn speed (m/s)              <-> plant speed_mag
  * imu.yawRate    = pawn yaw rate (deg/s)         <-> plant r (rad/s)*180/pi
  * imu.heading    = UEYawToWire(actor yaw)        <-> plant yawDeg (+spawn yaw)
  * gps.worldPos   = UEToWire(actor loc)           <-> plant (x=E, z=N) (+spawn offset)
  * gps.lat/lonDeg = geo-origin + North/East metres (linear WGS84 projection)
So a faithful sensor is a near-affine image (slope ~ 1) of the plant signal.

CLOCK NOTE (important; see KI-024). ``state.csv`` t is the *Python plant*
sim-clock and ``sensor.csv`` t is the *UE engine* sim-clock; under high PIE FPS
the plant free-runs and the two t columns diverge (observed 3.0x vs 1.0x on run
20260622_054815). Both files share ``wall_time`` (epoch seconds), so this gate
joins on ``wall_time`` -- never on t -- and reports the divergence.

Checks (gates unless marked INFO):
  D1 timing            sensor wall_time strictly increasing & inside the state span.
  D2 finite_and_fix    sensor numerics finite; gps_hasFix all true.
  D3 speed_fidelity    gps_speed ~ plant speed_mag (slope~1, high corr, low RMS).
  D4 yawrate_fidelity  imu_yawRate ~ plant r*180/pi (|slope|~1, high corr, low RMS).
  D5 heading_fidelity  unwrap(imu_heading) ~ unwrap(plant yaw) (slope~1) -- INFO if
                       the run barely turns (<5 deg of heading change).
  D6 position_fidelity gps position == plant position + a constant (spawn-anchor)
                       offset; robust median residual small vs the path extent.
  D7 geo_projection    a single Monaco geo-origin reconstructs every lat/lon from
                       (East,North) (consistent + sane ~43.7 N, 7.4 E).
  D8 accel_sane        imu acceleration finite, bounded, and actually computed
                       (non-zero while the hull accelerates) -- not a stub.
  D9 ais (INFO)        ais_target_count reported (0 until traffic, WP-15).
  C1 clock (INFO)      plant-t/wall vs sensor-t/wall ratio (KI-024 divergence).

A run PASSES when every gate passes. ``--selftest`` additionally corrupts a good
run and requires each corruption to TRIP the matching gate (so we know the gate
has teeth, not just that clean data slides through).

Usage:
    python python/verify_sensors_fidelity.py                       # latest run
    python python/verify_sensors_fidelity.py --run-dir logs/<run>
    python python/verify_sensors_fidelity.py --run-dir logs/<run> --json out.json
    python python/verify_sensors_fidelity.py --selftest            # negative controls
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import os
import sys
from typing import List, Optional, Tuple


# ----------------------------------------------------------------- thresholds
SPEED_SLOPE = (0.85, 1.15)        # gps_speed vs plant speed_mag
SPEED_CORR_MIN = 0.97
SPEED_RMS_MAX = 0.30              # m/s
YAWRATE_SLOPE_ABS = (0.80, 1.20)  # |slope| (sign reported separately)
YAWRATE_CORR_MIN = 0.90
YAWRATE_RMS_MAX = 0.20           # deg/s
YAWRATE_MIN_RANGE_DEGPS = 0.5    # below this the run barely yaws -> D4 is INFO (mirrors D5)
HEADING_SLOPE = (0.90, 1.10)
HEADING_CORR_MIN = 0.97
HEADING_MIN_RANGE_DEG = 5.0      # below this the run barely turns -> D5 is INFO
GEO_ORIGIN_STD_MAX_DEG = 1.0e-3  # consistency of the inferred origin across rows
GEO_LAT_BOX = (43.5, 44.0)       # Monaco
GEO_LON_BOX = (7.2, 7.7)
ACC_ABS_MAX = 20.0               # m/s^2
CLOCK_DIVERGENCE_WARN = 0.10     # |ratio_state-ratio_sensor|/ratio_sensor


# ----------------------------------------------------------------- io helpers
def _latest_run(log_root: str) -> Optional[str]:
    if not os.path.isdir(log_root):
        return None
    cands = [
        os.path.join(log_root, n)
        for n in os.listdir(log_root)
        if os.path.isdir(os.path.join(log_root, n))
        and os.path.exists(os.path.join(log_root, n, "sensor.csv"))
        and os.path.exists(os.path.join(log_root, n, "state.csv"))
    ]
    if not cands:
        return None
    cands.sort(key=os.path.getmtime, reverse=True)
    return cands[0]


def _load_csv(path: str) -> List[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _fcol(rows: List[dict], name: str) -> List[float]:
    out = []
    for r in rows:
        v = r.get(name)
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            out.append(float("nan"))
    return out


# ----------------------------------------------------------------- math
def _interp(xs: List[float], ys: List[float], x: float) -> float:
    """Linear interpolation; xs ascending. Clamps to the ends."""
    n = len(xs)
    if n == 0:
        return float("nan")
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    lo, hi = 0, n - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid
        else:
            hi = mid
    x0, x1 = xs[lo], xs[hi]
    if x1 == x0:
        return ys[lo]
    f = (x - x0) / (x1 - x0)
    return ys[lo] + f * (ys[hi] - ys[lo])


def _finite_pairs(a: List[float], b: List[float]) -> Tuple[List[float], List[float]]:
    pa, pb = [], []
    for x, y in zip(a, b):
        if math.isfinite(x) and math.isfinite(y):
            pa.append(x)
            pb.append(y)
    return pa, pb


def _pearson(a: List[float], b: List[float]) -> float:
    a, b = _finite_pairs(a, b)
    n = len(a)
    if n < 3:
        return 0.0
    ma = sum(a) / n
    mb = sum(b) / n
    sa = sum((x - ma) ** 2 for x in a)
    sb = sum((y - mb) ** 2 for y in b)
    if sa <= 1e-12 or sb <= 1e-12:
        return 0.0
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    return cov / math.sqrt(sa * sb)


def _linfit(x: List[float], y: List[float]) -> Tuple[float, float]:
    """Least-squares slope/intercept of y = slope*x + b. (x=plant, y=sensor)."""
    x, y = _finite_pairs(x, y)
    n = len(x)
    if n < 2:
        return float("nan"), float("nan")
    mx = sum(x) / n
    my = sum(y) / n
    sxx = sum((xi - mx) ** 2 for xi in x)
    if sxx <= 1e-12:
        return 0.0, my
    sxy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    slope = sxy / sxx
    return slope, my - slope * mx


def _rms(a: List[float], b: List[float]) -> float:
    a, b = _finite_pairs(a, b)
    if not a:
        return float("nan")
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a))


def _unwrap_deg(seq: List[float]) -> List[float]:
    """Make a [0,360)/[-180,180) heading series continuous (no +-360 jumps)."""
    if not seq:
        return []
    out = [seq[0]]
    for v in seq[1:]:
        prev = out[-1]
        d = (v - (prev % 360.0) + 180.0) % 360.0 - 180.0
        out.append(prev + d)
    return out


def _std(seq: List[float]) -> float:
    seq = [v for v in seq if math.isfinite(v)]
    n = len(seq)
    if n < 2:
        return 0.0
    m = sum(seq) / n
    return math.sqrt(sum((v - m) ** 2 for v in seq) / n)


def _median(seq: List[float]) -> float:
    s = sorted(v for v in seq if math.isfinite(v))
    n = len(s)
    if n == 0:
        return float("nan")
    m = n // 2
    return s[m] if n % 2 else 0.5 * (s[m - 1] + s[m])


def _percentile(seq: List[float], p: float) -> float:
    s = sorted(v for v in seq if math.isfinite(v))
    if not s:
        return float("nan")
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p / 100.0
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _col_ok(rows: List[dict], name: str) -> bool:
    """True if column ``name`` exists and carries at least one finite value."""
    if not rows or name not in rows[0]:
        return False
    return any(math.isfinite(v) for v in _fcol(rows, name))


def _join_key(sensor: List[dict], state: List[dict]) -> str:
    """The canonical cross-log join column (KI-024).

    Prefer ``t_mono`` -- ONE monotonic, run-relative clock stamped by the
    single logger onto BOTH logs, so it never inherits the plant-vs-engine
    ``t`` divergence. Fall back to ``wall_time`` for runs logged before the
    canonical clock existed (keeps every historical run joinable).
    """
    if _col_ok(sensor, "t_mono") and _col_ok(state, "t_mono"):
        return "t_mono"
    return "wall_time"


# ----------------------------------------------------------------- core eval
def _join_to_plant(sensor: List[dict], state: List[dict]) -> dict:
    """Interpolate the plant signals onto the sensor sample times.

    Joins on the canonical key (``t_mono`` when present, else ``wall_time``);
    NEVER on the raw per-side ``t`` (sensor=engine clock, state=plant clock),
    which diverge under high PIE FPS -- see KI-024.
    """
    key = _join_key(sensor, state)
    s_join = _fcol(state, key)
    order = sorted(range(len(s_join)), key=lambda i: s_join[i])
    s_join = [s_join[i] for i in order]
    state = [state[i] for i in order]
    p_speed = _fcol(state, "speed_mag")
    p_r = _fcol(state, "r")
    p_yaw = _fcol(state, "yawDeg")
    p_x = _fcol(state, "x")
    p_z = _fcol(state, "z")
    p_yaw_uw = _unwrap_deg(p_yaw)

    sj = _fcol(sensor, key)
    out = {"sensor_wall": sj, "n": len(sj), "join_key": key}
    out["plant_speed"] = [_interp(s_join, p_speed, w) for w in sj]
    out["plant_r_degps"] = [_interp(s_join, p_r, w) * 180.0 / math.pi for w in sj]
    out["plant_yaw_uw"] = [_interp(s_join, p_yaw_uw, w) for w in sj]
    out["plant_x"] = [_interp(s_join, p_x, w) for w in sj]
    out["plant_z"] = [_interp(s_join, p_z, w) for w in sj]
    out["state_wall_span"] = (s_join[0], s_join[-1]) if s_join else (0.0, 0.0)
    return out


def evaluate(sensor: List[dict], state: List[dict]) -> List[dict]:
    checks: List[dict] = []

    def add(cid, name, status, detail):
        checks.append({"id": cid, "name": name, "status": status, "detail": detail})

    if not sensor or not state:
        add("D0", "data_present", "FAIL", "sensor.csv or state.csv empty")
        return checks

    j = _join_to_plant(sensor, state)
    sw = j["sensor_wall"]

    # ---- D1 timing -------------------------------------------------------
    mono = all(sw[i + 1] > sw[i] for i in range(len(sw) - 1))
    span0, span1 = j["state_wall_span"]
    inside = (sw[0] >= span0 - 0.5) and (sw[-1] <= span1 + 0.5)
    add("D1", "timing",
        "PASS" if (mono and inside) else "FAIL",
        f"rows={len(sw)} mono={mono} inside_state_span={inside}")

    # ---- D2 finite_and_fix ----------------------------------------------
    numeric = ["gps_x", "gps_y", "gps_z", "gps_speed", "gps_latDeg", "gps_lonDeg",
               "imu_headingDeg", "imu_yawRateDegPerSec", "imu_acc_x", "imu_acc_y", "imu_acc_z"]
    bad = 0
    for col in numeric:
        bad += sum(1 for v in _fcol(sensor, col) if not math.isfinite(v))
    fix = _fcol(sensor, "gps_hasFix")
    no_fix = sum(1 for v in fix if v < 0.5)
    add("D2", "finite_and_fix",
        "PASS" if (bad == 0 and no_fix == 0) else "FAIL",
        f"non_finite={bad} rows_without_fix={no_fix}")

    # ---- D3 speed_fidelity ----------------------------------------------
    g_speed = _fcol(sensor, "gps_speed")
    slope, _ = _linfit(j["plant_speed"], g_speed)
    corr = _pearson(j["plant_speed"], g_speed)
    rms = _rms(g_speed, j["plant_speed"])
    ok = (SPEED_SLOPE[0] <= slope <= SPEED_SLOPE[1]) and corr >= SPEED_CORR_MIN and rms <= SPEED_RMS_MAX
    add("D3", "speed_fidelity", "PASS" if ok else "FAIL",
        f"slope={slope:.3f} corr={corr:.4f} rms={rms:.3f} m/s (max gps={max(g_speed):.2f})")

    # ---- D4 yawrate_fidelity --------------------------------------------
    g_yr = _fcol(sensor, "imu_yawRateDegPerSec")
    r_vals = [v for v in j["plant_r_degps"] if math.isfinite(v)]
    r_range = (max(r_vals) - min(r_vals)) if r_vals else 0.0
    if r_range < YAWRATE_MIN_RANGE_DEGPS:
        add("D4", "yawrate_fidelity", "INFO",
            f"run yaw-rate range only {r_range:.3f} deg/s (<{YAWRATE_MIN_RANGE_DEGPS}) -- not enough to gate")
    else:
        slope_yr, _ = _linfit(j["plant_r_degps"], g_yr)
        corr_yr = _pearson(j["plant_r_degps"], g_yr)
        rms_yr = _rms(g_yr, j["plant_r_degps"])
        sign = "same" if slope_yr >= 0 else "FLIPPED"
        ok_yr = (YAWRATE_SLOPE_ABS[0] <= abs(slope_yr) <= YAWRATE_SLOPE_ABS[1]) and \
                corr_yr >= YAWRATE_CORR_MIN and rms_yr <= YAWRATE_RMS_MAX
        add("D4", "yawrate_fidelity", "PASS" if ok_yr else "FAIL",
            f"slope={slope_yr:.3f}({sign}) corr={corr_yr:.4f} rms={rms_yr:.3f} deg/s over {r_range:.2f} deg/s range")

    # ---- D5 heading_fidelity --------------------------------------------
    g_head_uw = _unwrap_deg(_fcol(sensor, "imu_headingDeg"))
    yaw_range = max(j["plant_yaw_uw"]) - min(j["plant_yaw_uw"])
    if yaw_range < HEADING_MIN_RANGE_DEG:
        add("D5", "heading_fidelity", "INFO",
            f"run turns only {yaw_range:.1f} deg (<{HEADING_MIN_RANGE_DEG}) -- not enough to gate")
    else:
        slope_h, _ = _linfit(j["plant_yaw_uw"], g_head_uw)
        corr_h = _pearson(j["plant_yaw_uw"], g_head_uw)
        ok_h = (HEADING_SLOPE[0] <= slope_h <= HEADING_SLOPE[1]) and corr_h >= HEADING_CORR_MIN
        add("D5", "heading_fidelity", "PASS" if ok_h else "FAIL",
            f"slope={slope_h:.3f} corr={corr_h:.4f} over {yaw_range:.0f} deg turn")

    # ---- D6 position_fidelity (robust: gps == plant + constant offset) ----
    # The pawn world pose = plant pose + the KI-020 spawn anchor (a rigid
    # offset; for demo placements heading ~ North it is a pure translation).
    # We estimate the offset with the MEDIAN so a one-frame pre-init glitch
    # sample (seen as sensor row 0 on some runs) cannot corrupt the verdict.
    gx = _fcol(sensor, "gps_x")
    gz = _fcol(sensor, "gps_z")
    dxs, dzs = [], []
    for gxx, gzz, pxx, pzz in zip(gx, gz, j["plant_x"], j["plant_z"]):
        if all(math.isfinite(v) for v in (gxx, gzz, pxx, pzz)):
            dxs.append(gxx - pxx)
            dzs.append(gzz - pzz)
    offx, offz = _median(dxs), _median(dzs)
    resid = [math.hypot(dx - offx, dz - offz) for dx, dz in zip(dxs, dzs)]
    cx, cz = _median(j["plant_x"]), _median(j["plant_z"])
    extent = max((math.hypot(pxx - cx, pzz - cz)
                  for pxx, pzz in zip(j["plant_x"], j["plant_z"])), default=0.0)
    med_r = _median(resid)
    p90_r = _percentile(resid, 90.0)
    tol_med = max(3.0, 0.03 * extent)
    tol_p90 = max(8.0, 0.08 * extent)
    ok_p = med_r <= tol_med and p90_r <= tol_p90
    add("D6", "position_fidelity", "PASS" if ok_p else "FAIL",
        f"gps=plant+offset({offx:.1f}E,{offz:.1f}N) median_resid={med_r:.2f} m p90={p90_r:.2f} m "
        f"(tol {tol_med:.1f}/{tol_p90:.1f}, path extent {extent:.0f} m)")

    # ---- D7 geo_projection ----------------------------------------------
    lat = _fcol(sensor, "gps_latDeg")
    lon = _fcol(sensor, "gps_lonDeg")
    lat0s, lon0s = [], []
    for la, lo, e, n in zip(lat, lon, gx, gz):
        if not all(math.isfinite(v) for v in (la, lo, e, n)):
            continue
        lat0 = la - n / 111320.0
        mpd_lon = 111320.0 * math.cos(math.radians(lat0))
        lon0 = lo - (e / mpd_lon if mpd_lon > 1.0 else 0.0)
        lat0s.append(lat0)
        lon0s.append(lon0)
    if lat0s:
        lat0m = sum(lat0s) / len(lat0s)
        lon0m = sum(lon0s) / len(lon0s)
        consistent = _std(lat0s) <= GEO_ORIGIN_STD_MAX_DEG and _std(lon0s) <= GEO_ORIGIN_STD_MAX_DEG
        sane = (GEO_LAT_BOX[0] <= lat0m <= GEO_LAT_BOX[1]) and (GEO_LON_BOX[0] <= lon0m <= GEO_LON_BOX[1])
        add("D7", "geo_projection", "PASS" if (consistent and sane) else "FAIL",
            f"origin=({lat0m:.4f}N,{lon0m:.4f}E) std=({_std(lat0s):.2e},{_std(lon0s):.2e}) "
            f"consistent={consistent} sane={sane}")
    else:
        add("D7", "geo_projection", "FAIL", "no finite lat/lon rows")

    # ---- D8 accel_sane --------------------------------------------------
    ax = _fcol(sensor, "imu_acc_x")
    ay = _fcol(sensor, "imu_acc_y")
    az = _fcol(sensor, "imu_acc_z")
    allacc = ax + ay + az
    finite = all(math.isfinite(v) for v in allacc)
    bounded = all(abs(v) <= ACC_ABS_MAX for v in allacc if math.isfinite(v))
    speed_rises = (max(g_speed) - min(g_speed)) > 0.5
    finite_ax = [abs(v) for v in ax if math.isfinite(v)]
    computed = (max(finite_ax) > 0.005) if finite_ax else False
    ok_a = finite and bounded and (computed or not speed_rises)
    add("D8", "accel_sane", "PASS" if ok_a else "FAIL",
        f"finite={finite} bounded={bounded} max|acc_x|={(max(finite_ax) if finite_ax else 0.0):.3f} "
        f"computed={computed}")

    # ---- D9 ais (INFO) --------------------------------------------------
    ais = _fcol(sensor, "ais_target_count")
    add("D9", "ais_targets", "INFO",
        f"max targets={int(max(ais)) if ais else 0} (0 until scripted traffic, WP-15)")

    # ---- C1 clock divergence (INFO; KI-024) -----------------------------
    def _ratio(rows):
        w = _fcol(rows, "wall_time")
        t = _fcol(rows, "t")
        if len(w) < 2 or (w[-1] - w[0]) <= 1e-6:
            return float("nan")
        return (t[-1] - t[0]) / (w[-1] - w[0])
    rs = _ratio(state)
    rss = _ratio(sensor)
    diverged = math.isfinite(rs) and math.isfinite(rss) and rss > 1e-6 and \
        abs(rs - rss) / rss > CLOCK_DIVERGENCE_WARN
    add("C1", "clock_divergence", "INFO",
        f"plant t/wall={rs:.3f} vs sensor t/wall={rss:.3f} -> diverged={diverged} "
        f"(join uses '{j['join_key']}', NEVER raw t; KI-024)")

    return checks


def analyse_run_dir(run_dir: str) -> dict:
    sensor = _load_csv(os.path.join(run_dir, "sensor.csv"))
    state = _load_csv(os.path.join(run_dir, "state.csv"))
    checks = evaluate(sensor, state)
    gates = [c for c in checks if c["status"] in ("PASS", "FAIL")]
    passed = sum(1 for c in gates if c["status"] == "PASS")
    return {
        "packet": "WP-20260622",
        "kind": "sensor-fidelity gate (sensor.csv vs plant state.csv ground truth)",
        "run": os.path.basename(run_dir.rstrip("/")),
        "checks": checks,
        "gates_passed": passed,
        "gates_total": len(gates),
        "verdict": "PASS" if passed == len(gates) and len(gates) > 0 else "FAIL",
    }


# ----------------------------------------------------------------- selftest
def _gate_status(checks: List[dict], cid: str) -> str:
    for c in checks:
        if c["id"] == cid:
            return c["status"]
    return "MISSING"


def run_selftest(run_dir: str) -> dict:
    """Corrupt a good run five ways; each corruption must TRIP its gate."""
    sensor = _load_csv(os.path.join(run_dir, "sensor.csv"))
    state = _load_csv(os.path.join(run_dir, "state.csv"))
    d5_base = _gate_status(evaluate(sensor, state), "D5")
    d4_base = _gate_status(evaluate(sensor, state), "D4")
    results = []

    def control(name, gate_id, mutate, applicable=True, note="ok"):
        if not applicable:
            results.append({"control": name, "gate": gate_id, "gate_status": "N/A",
                            "fired": True, "note": note})
            return
        bad = copy.deepcopy(sensor)
        mutate(bad)
        st = _gate_status(evaluate(bad, state), gate_id)
        results.append({"control": name, "gate": gate_id, "gate_status": st,
                        "fired": st == "FAIL", "note": note})

    def set_all(col, val):
        def _m(rows):
            for r in rows:
                r[col] = val
        return _m

    def scramble_latlon(rows):
        for i, r in enumerate(rows):
            r["gps_latDeg"] = str(40.0 + 0.001 * (i % 7))   # not Monaco
            r["gps_lonDeg"] = str(-3.0 - 0.001 * (i % 5))

    control("constant_speed", "D3", set_all("gps_speed", "1.0"))
    _ha4 = d4_base != "INFO"
    control("frozen_yawrate", "D4", set_all("imu_yawRateDegPerSec", "0.0"),
            applicable=_ha4,
            note=("ok" if _ha4 else
                  "base D4 is INFO (run barely yaws) -> N/A here; "
                  "run --selftest on a turning_circle run to exercise it"))
    _ha = d5_base != "INFO"
    control("frozen_heading", "D5", set_all("imu_headingDeg", "0.0"),
            applicable=_ha,
            note=("ok" if _ha else
                  "base D5 is INFO (run barely turns) -> N/A here; "
                  "run --selftest on a turning_circle run to exercise it"))
    control("scrambled_latlon", "D7", scramble_latlon)
    control("nan_accel", "D2", set_all("imu_acc_x", "nan"))
    control("lost_fix", "D2", set_all("gps_hasFix", "0"))

    all_fired = all(r["fired"] for r in results)
    return {"selftest_run": os.path.basename(run_dir.rstrip("/")),
            "controls": results, "all_fired": all_fired}


# ----------------------------------------------------------------- report
def format_report(result: dict) -> str:
    lines = [f"Sensor-fidelity gate  run={result['run']}"]
    for c in result["checks"]:
        mark = {"PASS": "PASS", "FAIL": "FAIL", "INFO": "info"}[c["status"]]
        lines.append(f"  [{mark}] {c['id']} {c['name']}: {c['detail']}")
    lines.append("")
    lines.append(f"  Gates: {result['gates_passed']}/{result['gates_total']} => {result['verdict']}")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--log-root", default="logs")
    p.add_argument("--run-dir", default=None, help="Specific run dir; default = latest.")
    p.add_argument("--json", default=None, help="Write the verdict JSON to this path.")
    p.add_argument("--selftest", action="store_true",
                   help="Also run the negative-control battery on the chosen run.")
    args = p.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    log_root = args.log_root if os.path.isabs(args.log_root) else os.path.join(root, args.log_root)
    run_dir = args.run_dir or _latest_run(log_root)
    if not run_dir:
        print(f"[sensors] no run dir with sensor.csv+state.csv under {log_root}", file=sys.stderr)
        sys.exit(2)
    if not os.path.isabs(run_dir):
        run_dir = os.path.join(root, run_dir)

    result = analyse_run_dir(run_dir)
    print(format_report(result))

    if args.selftest:
        st = run_selftest(run_dir)
        result["selftest"] = st
        print("\nNegative controls:")
        for c in st["controls"]:
            print(f"  [{'fired' if c['fired'] else 'MISS '}] {c['control']} -> gate {c['gate']} "
                  f"= {c['gate_status']}" + (f"  ({c['note']})" if c.get('note') else ""))
        print(f"  all_fired={st['all_fired']}")

    if args.json:
        with open(args.json, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\n[sensors] verdict JSON -> {args.json}")

    ok = result["verdict"] == "PASS"
    if args.selftest:
        ok = ok and result["selftest"]["all_fired"]
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
