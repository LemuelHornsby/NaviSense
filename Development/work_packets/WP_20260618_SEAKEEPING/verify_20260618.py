#!/usr/bin/env python3
"""WP-9 (F1 part 3a) -- wave-coupled attitude + 6-DOF/sea-state run evidence.

Exercises the REAL code paths: python/wave_response.py, the listener's
build_state_packet (composition), and python/run_logger.py (now logging the
6-DOF pose + the sea state). All pure-Python / no engine: this packet rides the
EXISTING rollDeg/pitchDeg/heaveM wire keys, so it adds NO new wire key, NO DTO
change and NO new recompile gate -- the only in-engine confirmation folds into
the already-pending G_UE7/G_UE8 eye-checks (now: roll/pitch also answer the swell).

Writes Saved/NaviSense_Reports/wp_20260618_result.json.
"""
from __future__ import annotations
import json, math, sys, tempfile, os
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from python.sea_state import WaveField                                   # noqa
from python.wave_response import (wave_attitude_deg, WAVE_ROLL_CLAMP_DEG,
                                  WAVE_PITCH_CLAMP_DEG)                   # noqa
from python.attitude_proxy import attitude_deg                          # noqa
from python.run_logger import RunLogger, STATE_COLUMNS                  # noqa
import python_listener as L                                             # noqa

checks: dict = {}
def chk(name, ok, detail):
    checks[name] = {"pass": bool(ok), "detail": detail}
    print(("PASS " if ok else "FAIL ") + name + " :: " + detail)

def mk(yaw=0.0, u=4.0, r=0.0, x=0.0, z=0.0, v=0.0):
    st = SimpleNamespace(x=x, y=0.0, z=z, yaw_deg=yaw, u=u, v=v, r=r,
        port_rpm=100, starboard_rpm=100, rudder_deg=5, bow_thruster_norm=0.0,
        port_rpm_cmd=100, starboard_rpm_cmd=100, rudder_cmd_deg=5, bow_thruster_cmd_norm=0.0)
    return SimpleNamespace(state=st)

# --- W1 back-compat: SS0 / no field => wave attitude 0 => packet byte-identical -
z0 = wave_attitude_deg(WaveField(sea_state=0), 10., -5., 33.0, 4.0)
none0 = wave_attitude_deg(None, 10., -5., 33.0, 4.0)
p_no = mk(u=4.0, r=0.06)                       # a turn => maneuvering heel present
p_ss0 = mk(u=4.0, r=0.06); p_ss0._wave_field = WaveField(sea_state=0)
pk_no = L.build_state_packet(1.0, "v", p_no, "auto")
pk_ss0 = L.build_state_packet(1.0, "v", p_ss0, "auto")
chk("W1_backcompat_ss0_identical",
    z0.roll_deg == 0.0 and z0.pitch_deg == 0.0 and none0.roll_deg == 0.0
    and pk_no == pk_ss0,
    "SS0/None => wave attitude (0,0) AND full state.v1 packet byte-identical to rev 1.3 (no-field == SS0)")

# --- W2 maneuvering-only value preserved (composition adds exactly 0 at SS0) ----
att = attitude_deg(p_no.state.u, p_no.state.v, p_no.state.r, 0.0)
chk("W2_maneuvering_preserved",
    abs(pk_no["rollDeg"] - att.roll_deg) < 1e-9 and abs(pk_no["pitchDeg"] - att.pitch_deg) < 1e-9,
    f"no-field rollDeg={pk_no['rollDeg']:.4f}==attitude_proxy heel; pitch matches too (rev 1.2 heel/trim intact)")

# --- W3 determinism / replayability (no RNG at sample time) --------------------
f = WaveField(sea_state=5, heading_deg=0.0, seed=7)
d_same = wave_attitude_deg(f, 12.3, -4.5, 33.0, 7.7) == wave_attitude_deg(f, 12.3, -4.5, 33.0, 7.7)
d_rebuild = (wave_attitude_deg(WaveField(sea_state=5, seed=7), 3., 9., 20., 11.)
             == wave_attitude_deg(WaveField(sea_state=5, seed=7), 3., 9., 20., 11.))
chk("W3_deterministic", d_same and d_rebuild,
    "wave_attitude_deg reproducible within a field and across same-seed rebuilds -> replayable")

# --- W4 directional correctness: head sea => pitch, beam sea => roll ------------
def rms(yaw):
    rr = pp = 0.0
    N = 4000
    for k in range(N):
        a = wave_attitude_deg(f, 0.0, 0.0, yaw, k * 0.05)
        rr += a.roll_deg ** 2; pp += a.pitch_deg ** 2
    return math.sqrt(rr / N), math.sqrt(pp / N)
hr, hp = rms(0.0)     # bow into N-travelling waves => head sea
br, bp = rms(90.0)    # bow east => beam sea
chk("W4_directional",
    hp > 2.0 * hr and br > 2.0 * bp,
    f"head sea pitch_rms {hp:.2f} >> roll_rms {hr:.2f}; beam sea roll_rms {br:.2f} >> pitch_rms {bp:.2f}")

# --- W5 clamps: wave term within its clamp; composed within hard TOTAL caps -----
f9 = WaveField(sea_state=9, seed=3)
mxr = mxp = 0.0
for k in range(6000):
    a = wave_attitude_deg(f9, k * 7.0, k * 3.0, (k * 13) % 360, k * 0.07)
    mxr = max(mxr, abs(a.roll_deg)); mxp = max(mxp, abs(a.pitch_deg))
pcomp = mk(u=6.0, r=0.10); pcomp._wave_field = f9     # hard turn + SS9 worst case
cr = cp = 0.0
for k in range(3000):
    pcomp.state.x = k * 5.0; pcomp.state.z = k * 2.0; pcomp.state.yaw_deg = (k * 11) % 360
    pk = L.build_state_packet(k * 0.05, "v", pcomp, "auto")
    cr = max(cr, abs(pk["rollDeg"])); cp = max(cp, abs(pk["pitchDeg"]))
chk("W5_clamped",
    mxr <= WAVE_ROLL_CLAMP_DEG + 1e-9 and mxp <= WAVE_PITCH_CLAMP_DEG + 1e-9
    and cr <= L.TOTAL_ROLL_CLAMP_DEG + 1e-9 and cp <= L.TOTAL_PITCH_CLAMP_DEG + 1e-9,
    f"wave |roll|<= {WAVE_ROLL_CLAMP_DEG} (got {mxr:.2f}) |pitch|<= {WAVE_PITCH_CLAMP_DEG} (got {mxp:.2f}); "
    f"composed |roll|<= {L.TOTAL_ROLL_CLAMP_DEG} (got {cr:.2f}) |pitch|<= {L.TOTAL_PITCH_CLAMP_DEG} (got {cp:.2f})")

# --- W6 no schema drift: state.v1 top-level keys unchanged (invariant #3 guard) -
EXPECTED = {"schema","runId","t","x","y","z","yawDeg","rollDeg","pitchDeg","heaveM",
            "u","v","r","portRpm","starboardRpm","rudderDeg","bowThrusterNorm",
            "portRpmCmd","starboardRpmCmd","rudderCmdDeg","bowThrusterCmdNorm","mode"}
keys = set(pk_no.keys())
chk("W6_no_schema_drift",
    keys == EXPECTED,
    f"state.v1 carries exactly the 22 rev-1.3 keys (no new wire key added). extra={sorted(keys-EXPECTED)} missing={sorted(EXPECTED-keys)}")

# --- W7 composition active in a beam sea (roll varies around maneuvering base) --
pb = mk(yaw=90.0, u=4.0, r=0.0); pb._wave_field = WaveField(sea_state=6, heading_deg=0.0, seed=7)
rolls = []
for k in range(800):
    pb.state.x = 0.0; pb.state.z = 0.0
    rolls.append(L.build_state_packet(k * 0.05, "v", pb, "auto")["rollDeg"])
chk("W7_composition_active",
    (max(rolls) - min(rolls)) > 1.0,
    f"SS6 beam sea: composed rollDeg swings {min(rolls):+.2f}..{max(rolls):+.2f} (wave coupling on the wire)")

# --- W8 run_logger captures the 6-DOF pose columns -----------------------------
have_cols = all(c in STATE_COLUMNS for c in ("rollDeg", "pitchDeg", "heaveM"))
tmp = tempfile.mkdtemp()
lg = RunLogger.create(log_dir=tmp, run_id="v", plant_kind="mmg", controller_kind="zigzag10",
                      tick_hz=30.0, sea_state=5, wave_heading_deg=45.0, wave_seed=7)
lg.record_state({"t": 0.1, "mode": "approach", "x": 1, "y": 0, "z": 2, "yawDeg": 10,
                 "u": 4, "v": 0.1, "r": 0.05, "rudderDeg": 5, "rudderCmdDeg": 6,
                 "rollDeg": -2.13, "pitchDeg": 0.8, "heaveM": 0.42})
lg.finalise()
state_csv = (Path(lg.run_dir) / "state.csv").read_text().splitlines()
tail_hdr = state_csv[0].split(",")[-3:]
tail_row = state_csv[1].split(",")[-3:]
chk("W8_logger_logs_6dof",
    have_cols and tail_hdr == ["rollDeg", "pitchDeg", "heaveM"]
    and tail_row == ["-2.130000", "0.800000", "0.420000"],
    f"state.csv appends rollDeg/pitchDeg/heaveM; recorded row tail={tail_row}")

# --- W9 run_logger records the sea state (D3 'recorded in the run log') ---------
man = json.loads((Path(lg.run_dir) / "manifest.json").read_text())
idx = (Path(tmp) / "runs.csv").read_text().splitlines()
idx_ok = idx[0].split(",")[-1] == "sea_state" and idx[1].split(",")[-1] == "SS5"
chk("W9_logger_records_sea_state",
    man.get("seaState") == 5 and man.get("waveHeadingDeg") == 45.0 and idx_ok,
    f"manifest.seaState={man.get('seaState')} (+heading/seed); runs.csv sea_state column = SS5 (D3 evidence)")

passed = sum(1 for v in checks.values() if v["pass"]); total = len(checks)
out = {
    "packet": "WP-9 (F1 part 3a)",
    "date": "2026-06-18",
    "theme": "Wave-coupled roll/pitch on the existing wire + 6-DOF/sea-state run-log evidence",
    "advances_gate": ("D2 (6-DOF water ride): hull now ROLLS/PITCHES with the swell, not just heaves; "
                      "D3 (sea states): the active sea state is now recorded in the run log (manifest + runs.csv)."),
    "rides_existing_wire": True,
    "new_recompile_gate": False,
    "gates_passed": passed, "gates_total": total, "gates_manual": 1,
    "auto_result": "PASS" if passed == total else "FAIL",
    "checks": checks,
    "manual_gate": {
        "G_UE7_8_swell_attitude": {
            "pass": "MANUAL_REQUIRED",
            "detail": ("Folds into the already-pending G_UE7/G_UE8 recompile+PIE eye-checks (no NEW recompile): "
                       "with the listener on `--controller turning_circle --sea-state 5`, confirm the hull now "
                       "ROLLS toward/with a beam swell and PITCHES into a head swell (smoothly, no jitter), in "
                       "addition to the heave bob; sits flat again at --sea-state 0. Wrong-way axis = 1-line sign "
                       "flip in NaviSenseCoords::WireRollToUE / WirePitchToUE only (invariant #1).")
        }
    },
    "note": ("Plant stays 3-DOF; this is a deterministic kinematic wave-slope proxy sampled at the wire boundary "
             "(python/wave_response.py reads python/sea_state.py's slope_rad), replayable with WP-4's sim clock. "
             "Rides the existing rollDeg/pitchDeg/heaveM keys: no DTO/schema change, no new recompile. Sampling "
             "the *rendered* UE water surface is the remaining F1 pt3 (engine-side).")
}
rep = ROOT / "NaviSense_UE5/Saved/NaviSense_Reports/wp_20260618_result.json"
rep.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"\n{'PASS' if passed==total else 'FAIL'}  {passed}/{total} checks -> {rep}")
sys.exit(0 if passed == total else 1)
