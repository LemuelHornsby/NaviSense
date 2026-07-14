#!/usr/bin/env python3
"""verify_20260708c -- WP-20260708C gate: sensor.v1 raw evidence sink + objective
sensor-suite gate (turns the Step-1 console eye-checks into on-disk gates).

  G1  RAW-SINK    -- RunLogger now writes sensor_raw.jsonl: feed 350 synthetic
                     sensor.v1 packets (built with the SAME Python mirrors the
                     C++ is verified against: ais_sensor / radar_sensor /
                     camera_sensor) -> exactly 305 sampled envelopes (all of the
                     first 300 + 1-in-10 after), every line parseable, manifest
                     reports sensorRawLines.
  G2  SUITE-PASS  -- verify_sensor_suite --run <that dir> passes 4/4
                     (R0 raw-present + R1 AIS + R2 radar + R3 camera).
  G3  BACK-COMPAT -- sensor.csv is unchanged by the sink: same 16-column
                     header, one row per packet (350).
  G4  REGRESSION  -- preflight_demo --report-only still exits 0 verdict GO and
                     wp_20260708b_result.json still reads pass=true.

Negative controls (the suite gate must FAIL bad sensor evidence):
  N1  ais.targets[] stripped from every packet        -> R1 FAIL, exit 1.
  N2  a radar blip leaks identity (mmsi injected)     -> R2 FAIL, exit 1.
  N3  camera{} block absent from every packet         -> R3 FAIL, exit 1.

Fixtures live in git-ignored logs/_selftest (23 Jun rule: rehearsals never
shadow a real run; --latest also skips "_" dirs). Writes
Saved/NaviSense_Reports/wp_20260708c_result.json; exit 0 iff all pass.
"""
from __future__ import annotations
import json, os, shutil, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "python"))

from python.run_logger import RunLogger, SENSOR_COLUMNS          # noqa: E402
from python.ais_sensor import build_ais_targets                  # noqa: E402
from python.radar_sensor import build_radar                      # noqa: E402
from python.camera_sensor import camera_record                   # noqa: E402
import verify_sensor_suite as vss                                 # noqa: E402

OUT = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports",
                   "wp_20260708c_result.json")
SELFTEST = os.path.join(ROOT, "logs", "_selftest")
N_PACKETS = 350
EXPECTED_RAW = 300 + (N_PACKETS - 300) // 10   # sampling rule -> 305


def make_packet(i: int, strip_ais=False, leak_mmsi=False, no_camera=False):
    """One synthetic navisense.sensor.v1 wire packet built from the mirrors."""
    t = i / 60.0
    own_e, own_n, hdg = 10.0 + 1.5 * t, 20.0 + 0.8 * t, (35.0 + t) % 360.0
    wire_targets = [
        {"id": 247039300, "name": "SLOWBELLE", "x": 400.0 + 2.0 * t,
         "z": 300.0 - 1.0 * t, "cogDeg": 210.0, "sogKn": 6.0},
        {"id": 247039301, "name": "AZURFERRY", "x": -600.0 + 4.0 * t,
         "z": 500.0, "cogDeg": 90.0, "sogKn": 14.0},
    ]
    sensors = {
        "gps": {"worldPosition": {"x": own_e, "y": 0.0, "z": own_n},
                "speed": 1.7, "latDeg": 43.735, "lonDeg": 7.425, "hasFix": True},
        "imu": {"headingDeg": hdg, "yawRateDegPerSec": 1.0,
                "acceleration": {"x": 0.0, "y": 0.0, "z": 0.0}},
        "ais": {"targets": [] if strip_ais
                else build_ais_targets(own_e, own_n, hdg, wire_targets)},
        "radar": build_radar(own_e, own_n, hdg, 1.7, wire_targets),
    }
    if leak_mmsi:
        for c in sensors["radar"]["contacts"]:
            c["mmsi"] = 247039300
    if not no_camera:
        sensors["camera"] = camera_record(own_e, 2.5, own_n, hdg, frame_index=i)
    return {"schema": "navisense.sensor.v1", "t": t, "sensors": sensors}


def write_raw_dir(name: str, **kw) -> str:
    """A bare run dir with a hand-written sensor_raw.jsonl (for neg-controls)."""
    d = os.path.join(SELFTEST, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "sensor_raw.jsonl"), "w", encoding="utf-8") as f:
        for i in range(1, 61):
            f.write(json.dumps({"wall_time": time.time(), "t_mono": i / 60.0,
                                "msg": make_packet(i, **kw)}) + "\n")
    return d


def main() -> int:
    checks, neg = [], []
    stamp = time.strftime("%Y%m%d_%H%M%S")
    os.makedirs(SELFTEST, exist_ok=True)

    # ---- G1: the real RunLogger writes the sampled raw sink ----------------
    logger = RunLogger.create(SELFTEST, run_id=f"wp08c_{stamp}", plant_kind="selftest",
                              controller_kind="selftest", tick_hz=60.0)
    run_dir = logger.run_dir
    for i in range(1, N_PACKETS + 1):
        logger.record_sensor(make_packet(i))
    logger.finalise()
    raw_path = os.path.join(run_dir, "sensor_raw.jsonl")
    lines = [l for l in open(raw_path, encoding="utf-8")] if os.path.isfile(raw_path) else []
    parse_ok = all(self_parse(l) for l in lines)
    manifest = json.load(open(os.path.join(run_dir, "manifest.json")))
    g1 = (os.path.isfile(raw_path) and len(lines) == EXPECTED_RAW and parse_ok
          and manifest.get("sensorRawLines") == EXPECTED_RAW)
    checks.append({"id": "G1", "name": "raw-sink", "pass": g1,
                   "detail": f"{len(lines)} envelope(s) (expect {EXPECTED_RAW}), "
                             f"parse_ok={parse_ok}, manifest sensorRawLines="
                             f"{manifest.get('sensorRawLines')}"})

    # ---- G2: objective suite gate passes on the good run -------------------
    tmp_out = os.path.join(SELFTEST, f"suite_{stamp}.json")
    rc = vss.main(["--run", run_dir, "--json-out", tmp_out])
    res = json.load(open(tmp_out)) if os.path.isfile(tmp_out) else {}
    g2 = rc == 0 and res.get("gates_passed") == 4 and res.get("gates_total") == 4
    checks.append({"id": "G2", "name": "suite-pass", "pass": g2,
                   "detail": f"rc={rc} gates={res.get('gates_passed')}/{res.get('gates_total')}"})

    # ---- G3: sensor.csv unchanged (back-compat) ----------------------------
    with open(os.path.join(run_dir, "sensor.csv"), encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        n_rows = sum(1 for _ in f)
    g3 = header == SENSOR_COLUMNS and n_rows == N_PACKETS
    checks.append({"id": "G3", "name": "back-compat", "pass": g3,
                   "detail": f"header {len(header)} col(s) match={header == SENSOR_COLUMNS}, "
                             f"rows={n_rows}/{N_PACKETS}"})

    # ---- G4: regression -- preflight still GO, 0708B intact ----------------
    pf = subprocess.run([sys.executable, os.path.join(ROOT, "preflight_demo.py"),
                         "--report-only"], capture_output=True, text=True, cwd=ROOT)
    pf_json = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports",
                           "demo_preflight_result.json")
    go = json.load(open(pf_json)).get("go") is True if os.path.isfile(pf_json) else False
    b_json = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports",
                          "wp_20260708b_result.json")
    b_ok = json.load(open(b_json)).get("pass") is True if os.path.isfile(b_json) else False
    g4 = pf.returncode == 0 and go and b_ok
    checks.append({"id": "G4", "name": "regression", "pass": g4,
                   "detail": f"preflight rc={pf.returncode} GO={go} wp_20260708b pass={b_ok}"})

    # ---- Negative controls --------------------------------------------------
    for nid, name, kw, want_fail_gate in (
            ("N1", "ais stripped", {"strip_ais": True}, "R1"),
            ("N2", "radar identity leak", {"leak_mmsi": True}, "R2"),
            ("N3", "camera absent", {"no_camera": True}, "R3")):
        d = write_raw_dir(f"wp08c_{nid}_{stamp}", **kw)
        out = os.path.join(SELFTEST, f"suite_{nid}_{stamp}.json")
        rc = vss.main(["--run", d, "--json-out", out])
        res = json.load(open(out)) if os.path.isfile(out) else {"checks": []}
        failed = {c["id"] for c in res.get("checks", []) if not c["pass"]}
        ok = rc == 1 and want_fail_gate in failed
        neg.append({"id": nid, "name": name, "pass": ok,
                    "detail": f"rc={rc} failed_gates={sorted(failed)} "
                              f"(must include {want_fail_gate})"})

    ok_all = all(c["pass"] for c in checks) and all(n["pass"] for n in neg)
    result = {"packet": "WP-20260708C", "date": time.strftime("%Y-%m-%d"),
              "title": "sensor.v1 raw evidence sink + objective sensor-suite gate",
              "pass": ok_all,
              "gates_passed": sum(c["pass"] for c in checks), "gates_total": len(checks),
              "neg_passed": sum(n["pass"] for n in neg), "neg_total": len(neg),
              "checks": checks, "neg_controls": neg,
              "selftest_run_dir": run_dir}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    for c in checks + neg:
        print(f"  {c['id']} {c['name']:<20} {'PASS' if c['pass'] else 'FAIL'}  {c['detail']}")
    print(f"[wp_20260708c] {'PASS' if ok_all else 'FAIL'} -> {OUT}")
    return 0 if ok_all else 1


def self_parse(line: str) -> bool:
    try:
        env = json.loads(line)
        return isinstance(env.get("msg"), dict) and "sensors" in env["msg"]
    except Exception:
        return False


if __name__ == "__main__":
    sys.exit(main())
