"""WP-20260620 verify harness — run-log health gate + D6 evidence pack.

Auto-verifies the two new pure-Python tools added this packet:
  * python/verify_run_kinematics.py  (objective kinematic-health gate)
  * python/build_evidence_pack.py    (consolidated IMO-KPI evidence pack, D6)

It does NOT need Unreal or a live bridge. It proves the health gate both
PASSES clean data and FAILS injected pathologies (a spin-on-the-spot, a
NaN/teleport, an oscillating turn), then proves the evidence pack emits the
right IMO KPIs for both a turning-circle and a zig-zag run, and that the pack
is read-only over the source log.

Gates:
  V1 real_log_plant_healthy     real 18-Jun turning_circle log -> 8/8 PASS,
                                KI-018 log-side corroboration (continuous past 180 deg).
  V2 synth_good_turn_pass       a clean synthetic circle -> PASS.
  V3 synth_pirouette_caught     heading sweeps, position frozen -> K5 FAIL.
  V4 synth_nan_teleport_caught  NaN + a per-tick heading jump -> K2 & K3 FAIL.
  V5 synth_oscillation_caught   a turning_circle that wobbles -> K6 FAIL.
  V6 evidence_pack_turning_kpis pack on the real log -> turning-circle IMO KPIs.
  V7 evidence_pack_zigzag_kpis  pack on a synthetic zig-zag -> overshoot KPIs.
  V8 readonly_no_state_mutation pack build leaves state.csv byte-identical.

Usage:
    python Development/work_packets/WP_20260620/verify_20260620.py
    python Development/work_packets/WP_20260620/verify_20260620.py --json out.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))   # workspace root
_PY = os.path.join(_ROOT, "python")
if _PY not in sys.path:
    sys.path.insert(0, _PY)

import verify_run_kinematics as vrk       # noqa: E402
import build_evidence_pack as bep         # noqa: E402

REAL_RUN = os.path.join(_ROOT, "logs", "unreal-test-run_20260618_201335")

STATE_COLUMNS = [
    "wall_time", "t", "mode", "x", "y", "z", "yawDeg", "u", "v", "r",
    "portRpm", "starboardRpm", "rudderDeg", "bowThrusterNorm",
    "portRpmCmd", "starboardRpmCmd", "rudderCmdDeg", "bowThrusterCmdNorm",
    "speed_mag", "rudder_error_deg", "rollDeg", "pitchDeg", "heaveM",
]


# ----------------------------------------------------------------- fixtures
def _row(**kw):
    r = {c: "" for c in STATE_COLUMNS}
    r.update({"x": 0.0, "y": 0.0, "z": 0.0, "yawDeg": 0.0, "u": 0.0, "v": 0.0,
              "r": 0.0, "rudderDeg": 0.0, "rudderCmdDeg": 0.0, "speed_mag": 0.0,
              "rollDeg": 0.0, "pitchDeg": 0.0, "heaveM": 0.0,
              "portRpm": 0.0, "starboardRpm": 0.0, "portRpmCmd": 0.0,
              "starboardRpmCmd": 0.0, "bowThrusterNorm": 0.0, "bowThrusterCmdNorm": 0.0})
    r.update(kw)
    return r


def _write_run(base, name, rows, manifest):
    d = os.path.join(base, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "state.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=STATE_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    with open(os.path.join(d, "manifest.json"), "w") as f:
        json.dump(manifest, f)
    return d


def _manifest(controller, hz=10.0, sea=0):
    return {"runId": "synth", "plantKind": "mmg", "controllerKind": controller,
            "tickHz": hz, "seaState": sea, "durationSeconds": 0.0}


def _good_turn(dt=0.1, R=50.0, appr_s=10.0, turn_deg=270.0, rate_dps=6.0):
    """Clean starboard turning circle: straight approach, then a constant-rate
    turn whose position rides a circle of radius R (translating, not spinning)."""
    rows = []
    t = 0.0
    n_appr = int(appr_s / dt)
    u = 3.0
    z = 0.0
    for _ in range(n_appr):
        z += u * dt
        rows.append(_row(t=round(t, 3), mode="approach", x=0.0, z=round(z, 4),
                         yawDeg=0.0, u=u, speed_mag=u, r=0.0,
                         rudderCmdDeg=0.0, rudderDeg=0.0))
        t += dt
    x0, z0 = 0.0, z
    steps = int(turn_deg / (rate_dps * dt))
    r_rad = math.radians(rate_dps)
    for i in range(1, steps + 1):
        th = math.radians(rate_dps * dt * i)
        x = x0 + R - R * math.cos(th)
        z = z0 + R * math.sin(th)
        yaw = (rate_dps * dt * i) % 360.0
        rows.append(_row(t=round(t, 3), mode="turning_circle", x=round(x, 4),
                         z=round(z, 4), yawDeg=round(yaw, 4), u=u, speed_mag=u,
                         r=round(r_rad, 5), rudderCmdDeg=35.0, rudderDeg=35.0))
        t += dt
    return rows


def _pirouette(dt=0.1, appr_s=10.0, spin_deg=720.0, rate_dps=6.0):
    """Heading sweeps many turns while position stays frozen -> spin on the spot.
    Yaw step is small so K3 stays clean; only K5 should catch it."""
    rows = _good_turn(dt=dt, appr_s=appr_s, turn_deg=0.0)  # just the approach
    x, z = 0.0, rows[-1]["z"]
    t = rows[-1]["t"] + dt
    steps = int(spin_deg / (rate_dps * dt))
    r_rad = math.radians(rate_dps)
    cum = 0.0
    for _ in range(steps):
        cum += rate_dps * dt
        rows.append(_row(t=round(t, 3), mode="turning_circle", x=x, z=round(z, 4),
                         yawDeg=round(cum % 360.0, 4), u=0.05, speed_mag=0.05,
                         r=round(r_rad, 5), rudderCmdDeg=35.0, rudderDeg=35.0))
        t += dt
    return rows


def _nan_teleport(dt=0.1):
    rows = _good_turn(dt=dt, turn_deg=120.0)
    # Corrupt: NaN in surge, and a 90 deg single-tick heading jump.
    j = len(rows) - 20
    rows[j]["u"] = "nan"
    base = float(rows[j + 1]["yawDeg"])
    rows[j + 2]["yawDeg"] = round((base + 90.0) % 360.0, 4)   # jump up
    rows[j + 3]["yawDeg"] = round(base % 360.0, 4)            # jump back
    return rows


def _oscillation(dt=0.1, appr_s=10.0, cycles=10, amp=30.0, period_s=6.0):
    """A 'turning_circle' that wobbles: heading swings +/-amp many times while
    translating forward. Many direction reversals -> K6 FAIL, K5 still PASS."""
    rows = []
    t = 0.0
    u = 4.0
    z = 0.0
    n_appr = int(appr_s / dt)
    for _ in range(n_appr):
        z += u * dt
        rows.append(_row(t=round(t, 3), mode="approach", x=0.0, z=round(z, 4),
                         yawDeg=0.0, u=u, speed_mag=u, rudderCmdDeg=0.0))
        t += dt
    n = int(cycles * period_s / dt)
    w = 2.0 * math.pi / period_s
    prev_yaw = 0.0
    for i in range(1, n + 1):
        yaw = amp * math.sin(w * (i * dt))
        dyaw = yaw - prev_yaw
        prev_yaw = yaw
        z += u * dt
        x = 5.0 * math.sin(w * (i * dt))
        rows.append(_row(t=round(t, 3), mode="turning_circle", x=round(x, 4),
                         z=round(z, 4), yawDeg=round(yaw % 360.0, 4), u=u,
                         speed_mag=u, r=round(math.radians(dyaw / dt), 5),
                         rudderCmdDeg=35.0, rudderDeg=35.0))
        t += dt
    return rows


def _zigzag(dt=0.1, appr_s=10.0, halves=6, half_s=8.0, capture=10.0, peak=13.0):
    """Synthetic zig-zag: rudder flips +/-, heading triangles to +/-peak so it
    overshoots the +/-capture target; vessel translates forward."""
    rows = []
    t = 0.0
    u = 3.0
    z = 0.0
    n_appr = int(appr_s / dt)
    for _ in range(n_appr):
        z += u * dt
        rows.append(_row(t=round(t, 3), mode="approach", x=0.0, z=round(z, 4),
                         yawDeg=0.0, u=u, speed_mag=u, rudderCmdDeg=0.0))
        t += dt
    n_half = int(half_s / dt)
    yaw = 0.0
    sign = 1.0           # first half: rudder +, heading rises toward +peak
    for h in range(halves):
        start_yaw = yaw
        end_yaw = sign * peak
        for i in range(1, n_half + 1):
            frac = i / n_half
            yaw = start_yaw + (end_yaw - start_yaw) * frac
            z += u * dt
            x_prev = rows[-1]["x"] if rows else 0.0
            rows.append(_row(t=round(t, 3), mode="zigzag10",
                             x=round(float(x_prev) + math.sin(math.radians(yaw)) * u * dt, 4),
                             z=round(z, 4), yawDeg=round(yaw % 360.0, 4), u=u,
                             speed_mag=u, rudderCmdDeg=sign * capture,
                             rudderDeg=sign * capture))
            t += dt
        sign = -sign
    return rows


# ----------------------------------------------------------------- gate runner
class Gates:
    def __init__(self):
        self.results = []

    def check(self, vid, name, ok, detail):
        self.results.append({"id": vid, "name": name,
                             "status": "PASS" if ok else "FAIL", "detail": detail})
        print(f"  [{'PASS' if ok else 'FAIL'}] {vid} {name}: {detail}")
        return ok

    @property
    def passed(self):
        return sum(1 for r in self.results if r["status"] == "PASS")

    @property
    def total(self):
        return len(self.results)


def _analyse_dir(d):
    rows = vrk._load_state_csv(os.path.join(d, "state.csv"))
    man = vrk._load_manifest(d)
    return vrk.analyse(rows, man)


def run() -> dict:
    g = Gates()
    tmp = tempfile.mkdtemp(prefix="wp20260620_")
    try:
        # V1 — real log
        if os.path.exists(os.path.join(REAL_RUN, "state.csv")):
            res = _analyse_dir(REAL_RUN)
            ki = res["ki018_corroboration"]
            ok = (res["verdict"] == "PASS" and res["gates_passed"] == res["gates_total"]
                  and ki["entered_180_zone"] is True and ki["plant_heading_continuous"] is True
                  and (ki["effective_turn_radius_m"] or 0) > 10.0)
            g.check("V1", "real_log_plant_healthy", ok,
                    f"{res['gates_passed']}/{res['gates_total']} gates, entered180={ki['entered_180_zone']}, "
                    f"continuous={ki['plant_heading_continuous']}, eff_radius={ki['effective_turn_radius_m']}m")
        else:
            g.check("V1", "real_log_plant_healthy", False, f"real run missing at {REAL_RUN}")

        # V2 — good synthetic turn
        d = _write_run(tmp, "good_turn", _good_turn(), _manifest("turning_circle"))
        res = _analyse_dir(d)
        g.check("V2", "synth_good_turn_pass", res["verdict"] == "PASS",
                f"verdict={res['verdict']} {res['gates_passed']}/{res['gates_total']}")

        # V3 — pirouette caught by K5
        d = _write_run(tmp, "pirouette", _pirouette(), _manifest("turning_circle"))
        res = _analyse_dir(d)
        ok = res["verdict"] == "FAIL" and "K5" in res["failed_gates"]
        g.check("V3", "synth_pirouette_caught", ok,
                f"verdict={res['verdict']} failed={res['failed_gates']} (expect K5)")

        # V4 — NaN + teleport caught by K2 & K3
        d = _write_run(tmp, "nan_teleport", _nan_teleport(), _manifest("turning_circle"))
        res = _analyse_dir(d)
        ok = res["verdict"] == "FAIL" and "K2" in res["failed_gates"] and "K3" in res["failed_gates"]
        g.check("V4", "synth_nan_teleport_caught", ok,
                f"verdict={res['verdict']} failed={res['failed_gates']} (expect K2 & K3)")

        # V5 — oscillating turn caught by K6
        d = _write_run(tmp, "oscillation", _oscillation(), _manifest("turning_circle"))
        res = _analyse_dir(d)
        ok = res["verdict"] == "FAIL" and "K6" in res["failed_gates"]
        g.check("V5", "synth_oscillation_caught", ok,
                f"verdict={res['verdict']} failed={res['failed_gates']} (expect K6)")

        # V6 — evidence pack turning KPIs (real log, no plot)
        if os.path.exists(os.path.join(REAL_RUN, "state.csv")):
            packtmp = os.path.join(tmp, "real_copy")
            shutil.copytree(REAL_RUN, packtmp,
                            ignore=shutil.ignore_patterns("evidence_pack"))
            out = bep.build_pack(packtmp, make_plots=False)
            k = out["kpis"]
            mv = k["maneuver"]
            ok = (mv.get("kind") == "turning_circle" and mv.get("advance_m") is not None
                  and mv.get("tactical_diameter_m") is not None
                  and mv.get("imo_tactical_diameter_pass") is not None
                  and k["health"]["verdict"] in ("PASS", "FAIL")
                  and os.path.exists(os.path.join(out["pack_dir"], "EVIDENCE.md"))
                  and os.path.exists(os.path.join(out["pack_dir"], "kpis.json")))
            g.check("V6", "evidence_pack_turning_kpis", ok,
                    f"kind={mv.get('kind')} A={mv.get('advance_m')} DT={mv.get('tactical_diameter_m')} "
                    f"IMO_DT={mv.get('imo_tactical_diameter_pass')} health={k['health']['verdict']}")
        else:
            g.check("V6", "evidence_pack_turning_kpis", False, "real run missing")

        # V7 — evidence pack zig-zag KPIs
        d = _write_run(tmp, "zigzag", _zigzag(), _manifest("zigzag10"))
        out = bep.build_pack(d, make_plots=False)
        mv = out["kpis"]["maneuver"]
        ok = (mv.get("kind") == "zigzag" and len(mv.get("overshoots_deg") or []) >= 1
              and mv.get("first_overshoot_deg") is not None
              and mv.get("imo_first_overshoot_pass") is not None)
        g.check("V7", "evidence_pack_zigzag_kpis", ok,
                f"kind={mv.get('kind')} overshoots={[round(x,2) for x in (mv.get('overshoots_deg') or [])][:3]} "
                f"1stIMO={mv.get('imo_first_overshoot_pass')}")

        # V8 — read-only: state.csv unchanged by pack build
        d = _write_run(tmp, "readonly", _good_turn(), _manifest("turning_circle"))
        sp = os.path.join(d, "state.csv")
        before = hashlib.sha256(open(sp, "rb").read()).hexdigest()
        bep.build_pack(d, make_plots=False)
        after = hashlib.sha256(open(sp, "rb").read()).hexdigest()
        g.check("V8", "readonly_no_state_mutation", before == after,
                f"state.csv sha256 {'unchanged' if before == after else 'CHANGED'}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    verdict = "PASS" if g.passed == g.total else "FAIL"
    print(f"\n  {g.passed}/{g.total} gates => {verdict}")
    return {"gates": g.results, "gates_passed": g.passed,
            "gates_total": g.total, "verdict": verdict}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", default=None)
    args = p.parse_args()
    print("WP-20260620 verify — run-log health gate + D6 evidence pack\n")
    res = run()
    if args.json:
        with open(args.json, "w") as f:
            json.dump(res, f, indent=2)
        print(f"\n[verify] wrote {args.json}")
    sys.exit(0 if res["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
