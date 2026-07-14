#!/usr/bin/env python3
"""verify_sensor_suite -- objective gate for the in-engine sensor.v1 rich blocks.

Turns the three Step-1 console eye-checks (PENDING_EDITOR_GATES.md) into an
on-disk, exit-0/1 gate over a real run's ``sensor_raw.jsonl`` (written by
run_logger since WP-20260708C):

  R0  RAW-PRESENT -- sensor_raw.jsonl exists with >= --min-lines parseable
                     ``navisense.sensor.v1`` envelopes.
  R1  AIS    (G_AIS_SENSOR_UE) -- ais.targets[] is POPULATED in >= --min-hits
      packets; every target carries the 9 wire keys {mmsi,name,rangeM,
      trueBearingDeg,relBearingDeg,cogDeg,sogKn,latDeg,lonDeg}; rangeM finite
      and > 0; bearings in range; range VARIES over the run (tracking, not a
      frozen array).
  R2  RADAR  (G_RADAR_UE) -- radar{} present in >= --min-hits packets with
      {maxRangeM,sweepDeg,contacts[]}; every contact ANONYMOUS (no mmsi/name)
      with {rangeM,trueBearingDeg,relBearingDeg,radialSpeedKn,closing}; every
      rangeM <= maxRangeM (out-of-range blips must be dropped).
  R3  CAMERA (G_CAMERA_UE) -- camera{} present in >= --min-hits packets with
      {fovDeg,resX,resY,headingDeg,frameIndex,frameRef,pose{x,y,z}}; frameIndex
      non-decreasing; frameRef looks like a HighResShot still name (*.png).

Usage:
  python python/verify_sensor_suite.py --latest                # newest real run
  python python/verify_sensor_suite.py --run logs/<run_dir>
  python python/verify_sensor_suite.py --latest --require ais,radar   # no camera

Notes: a run only exercises what the scenario feeds it -- use a traffic
scenario (e.g. monaco_capture) to light up all three blocks. --require picks
which blocks are gated (default: ais,radar,camera). "_"-prefixed log dirs
(_selftest/_rehearsal/_debug*) are never auto-picked by --latest.
Writes Saved/NaviSense_Reports/sensor_suite_result.json. Stdlib only.
"""
from __future__ import annotations
import argparse, json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports",
                           "sensor_suite_result.json")
LOGS = os.path.join(ROOT, "logs")

AIS_KEYS = ("mmsi", "name", "rangeM", "trueBearingDeg", "relBearingDeg",
            "cogDeg", "sogKn", "latDeg", "lonDeg")
RADAR_CONTACT_KEYS = ("rangeM", "trueBearingDeg", "relBearingDeg",
                     "radialSpeedKn", "closing")
RADAR_IDENTITY_KEYS = ("mmsi", "name")   # must NOT appear on a blip
CAMERA_KEYS = ("fovDeg", "resX", "resY", "headingDeg", "frameIndex",
               "frameRef", "pose")


def _finite(x) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def find_latest_run(logs_dir: str):
    """Newest real run dir containing sensor_raw.jsonl (skips _-prefixed)."""
    best, best_m = None, -1.0
    if not os.path.isdir(logs_dir):
        return None
    for name in os.listdir(logs_dir):
        if name.startswith("_"):
            continue
        d = os.path.join(logs_dir, name)
        raw = os.path.join(d, "sensor_raw.jsonl")
        if os.path.isdir(d) and os.path.isfile(raw):
            m = os.path.getmtime(raw)
            if m > best_m:
                best, best_m = d, m
    return best


def load_raw(run_dir: str):
    """Parse sensor_raw.jsonl -> list of wire msgs (envelope 'msg' unwrapped)."""
    path = os.path.join(run_dir, "sensor_raw.jsonl")
    msgs, bad = [], 0
    if not os.path.isfile(path):
        return msgs, bad, path
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                env = json.loads(line)
                m = env.get("msg") if isinstance(env, dict) else None
                if isinstance(m, dict):
                    msgs.append(m)
                else:
                    bad += 1
            except Exception:
                bad += 1
    return msgs, bad, path


def check_raw_present(msgs, bad, path, min_lines):
    n = len(msgs)
    schema_ok = sum(1 for m in msgs
                    if str(m.get("schema", "")).startswith("navisense.sensor"))
    ok = n >= min_lines and bad == 0 and schema_ok == n and n > 0
    return ok, (f"{n} parseable envelope(s) (need >= {min_lines}), "
                f"{bad} bad line(s), {schema_ok}/{n} sensor.v1 schema [{path}]")


def check_ais(msgs, min_hits):
    hits, ranges = 0, {}
    for m in msgs:
        targets = ((m.get("sensors") or {}).get("ais") or {}).get("targets") or []
        if not targets:
            continue
        hits += 1
        for t in targets:
            missing = [k for k in AIS_KEYS if k not in t]
            if missing:
                return False, f"target missing keys {missing}: {t}"
            if not _finite(t["rangeM"]) or float(t["rangeM"]) <= 0:
                return False, f"bad rangeM: {t.get('rangeM')!r}"
            if not (-180.0 <= float(t["relBearingDeg"]) <= 180.0):
                return False, f"relBearingDeg out of [-180,180]: {t['relBearingDeg']}"
            if not (0.0 <= float(t["trueBearingDeg"]) < 360.0):
                return False, f"trueBearingDeg out of [0,360): {t['trueBearingDeg']}"
            ranges.setdefault(t["mmsi"], []).append(float(t["rangeM"]))
    if hits < min_hits:
        return False, f"only {hits} packet(s) with populated ais.targets[] (need >= {min_hits})"
    moving = any(max(v) - min(v) > 1.0 for v in ranges.values() if len(v) > 1)
    if not moving:
        return False, "no target range varies > 1 m across the run (frozen array?)"
    return True, (f"{hits} populated packet(s), {len(ranges)} distinct mmsi, "
                  f"9/9 keys, ranges track")


def check_radar(msgs, min_hits):
    hits, blips = 0, 0
    for m in msgs:
        radar = (m.get("sensors") or {}).get("radar")
        if not isinstance(radar, dict):
            continue
        hits += 1
        for k in ("maxRangeM", "sweepDeg", "contacts"):
            if k not in radar:
                return False, f"radar block missing '{k}'"
        max_range = float(radar["maxRangeM"])
        for c in radar["contacts"] or []:
            blips += 1
            leaked = [k for k in RADAR_IDENTITY_KEYS if k in c]
            if leaked:
                return False, f"radar blip NOT anonymous -- leaked {leaked}: {c}"
            missing = [k for k in RADAR_CONTACT_KEYS if k not in c]
            if missing:
                return False, f"contact missing keys {missing}: {c}"
            if not _finite(c["rangeM"]) or float(c["rangeM"]) > max_range + 1.0:
                return False, f"contact rangeM {c.get('rangeM')!r} beyond maxRangeM {max_range}"
    if hits < min_hits:
        return False, f"only {hits} packet(s) with radar{{}} (need >= {min_hits})"
    if blips == 0:
        return False, "radar{} present but zero blips over the whole run"
    return True, f"{hits} radar packet(s), {blips} anonymous blip(s), all <= maxRangeM"


def check_camera(msgs, min_hits):
    hits, last_idx = 0, None
    for m in msgs:
        cam = (m.get("sensors") or {}).get("camera")
        if not isinstance(cam, dict):
            continue
        hits += 1
        missing = [k for k in CAMERA_KEYS if k not in cam]
        if missing:
            return False, f"camera block missing keys {missing}"
        pose = cam["pose"]
        if not isinstance(pose, dict) or any(k not in pose for k in ("x", "y", "z")):
            return False, f"camera pose malformed: {pose!r}"
        idx = int(cam["frameIndex"])
        if last_idx is not None and idx < last_idx:
            return False, f"frameIndex decreased {last_idx} -> {idx}"
        last_idx = idx
        ref = str(cam["frameRef"])
        if not ref.endswith(".png"):
            return False, f"frameRef not a .png still name: {ref!r}"
    if hits < min_hits:
        return False, f"only {hits} packet(s) with camera{{}} (need >= {min_hits})"
    return True, f"{hits} camera packet(s), frameIndex monotonic, frameRef *.png"


def evaluate(run_dir: str, require, min_lines: int, min_hits: int):
    msgs, bad, path = load_raw(run_dir)
    checks = []
    ok0, det0 = check_raw_present(msgs, bad, path, min_lines)
    checks.append({"id": "R0", "gate": "raw-present", "pass": ok0, "detail": det0})
    gates = {"ais": ("R1", "G_AIS_SENSOR_UE", check_ais),
             "radar": ("R2", "G_RADAR_UE", check_radar),
             "camera": ("R3", "G_CAMERA_UE", check_camera)}
    for name in ("ais", "radar", "camera"):
        if name not in require:
            continue
        rid, gate, fn = gates[name]
        ok, det = (fn(msgs, min_hits) if ok0 else (False, "skipped: R0 failed"))
        checks.append({"id": rid, "gate": gate, "pass": ok, "detail": det})
    return checks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run", help="run directory containing sensor_raw.jsonl")
    g.add_argument("--latest", action="store_true",
                   help="newest real run under logs/ with sensor_raw.jsonl")
    ap.add_argument("--require", default="ais,radar,camera",
                    help="comma list of blocks to gate (default: ais,radar,camera)")
    ap.add_argument("--min-lines", type=int, default=30,
                    help="min parseable raw envelopes for R0 (default 30)")
    ap.add_argument("--min-hits", type=int, default=10,
                    help="min packets a block must appear in (default 10)")
    ap.add_argument("--json-out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    require = {s.strip().lower() for s in args.require.split(",") if s.strip()}
    unknown = require - {"ais", "radar", "camera"}
    if unknown:
        ap.error(f"--require: unknown block(s) {sorted(unknown)}")

    run_dir = args.run or find_latest_run(LOGS)
    if not run_dir or not os.path.isdir(run_dir):
        print("[sensor_suite] FAIL: no run directory with sensor_raw.jsonl found "
              "(the raw sink exists only on runs made after WP-20260708C)")
        return 1

    checks = evaluate(run_dir, require, args.min_lines, args.min_hits)
    npass = sum(1 for c in checks if c["pass"])
    verdict = npass == len(checks)
    result = {"tool": "verify_sensor_suite", "packet": "WP-20260708C",
              "run_dir": os.path.abspath(run_dir),
              "require": sorted(require), "pass": verdict,
              "gates_passed": npass, "gates_total": len(checks),
              "checks": checks}
    os.makedirs(os.path.dirname(args.json_out), exist_ok=True)
    with open(args.json_out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    for c in checks:
        print(f"  {c['id']} {c['gate']:<16} {'PASS' if c['pass'] else 'FAIL'}  {c['detail']}")
    print(f"[sensor_suite] {'PASS' if verdict else 'FAIL'} {npass}/{len(checks)} "
          f"on {run_dir} -> {args.json_out}")
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
