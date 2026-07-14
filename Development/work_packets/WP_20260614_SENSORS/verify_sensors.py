"""WP-SENSOR-1 verify: confirm GPS/IMU emit real values in the newest run.
Run from anywhere: python Development/work_packets/WP_20260614_SENSORS/verify_sensors.py
"""
import csv, glob, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))  # workspace root
cands = sorted(glob.glob(os.path.join(ROOT, "logs", "*", "sensor.csv")), key=os.path.getmtime)
res = {"packet": "WP-SENSOR-1", "checks": {}, "pass": False}

if not cands:
    res["error"] = "no logs/*/sensor.csv found — run a session first"
    print("WP-SENSOR-1: NO DATA —", res["error"])
else:
    newest = cands[-1]
    res["run"] = os.path.basename(os.path.dirname(newest))
    rows = list(csv.DictReader(open(newest)))
    def col(n): return [float(r[n]) for r in rows if r.get(n) not in (None, "", "nan")]
    lat, lon, spd, yr = col("gps_latDeg"), col("gps_lonDeg"), col("gps_speed"), col("imu_yawRateDegPerSec")
    S1 = bool(lat and lon and 43.0 <= max(lat) <= 44.5 and 6.5 <= max(lon) <= 8.5)
    S2 = bool(spd and max(spd) > 0.5)
    S3 = bool(yr and max(abs(v) for v in yr) > 0.5)
    res["checks"] = {"S1_latlon": S1, "S2_speed": S2, "S3_yawrate": S3}
    res["samples"] = {"lat_max": max(lat) if lat else None, "lon_max": max(lon) if lon else None,
                      "speed_max": max(spd) if spd else None,
                      "yawrate_absmax": (max(abs(v) for v in yr) if yr else None)}
    res["pass"] = S1 and S2 and S3
    print("WP-SENSOR-1:", "PASS" if res["pass"] else "FAIL", "|", res["checks"], "|", res["samples"])

outdir = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports")
try:
    os.makedirs(outdir, exist_ok=True)
    json.dump(res, open(os.path.join(outdir, "wp_sensors_result.json"), "w"), indent=2)
except OSError:
    pass
