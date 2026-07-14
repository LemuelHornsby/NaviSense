#!/usr/bin/env python3
"""WP-7 (F1 part 1) — 6-DOF schema v1.2 (heel + trim) auto-verify.

Exercises the REAL code paths the listener uses (python/attitude_proxy.py and
build_state_packet), plus static DTO<->wire parity / backward-compat checks.
The only thing this cannot do from the sandbox is render the hull, so the
"heels into the turn" eye-check is the single MANUAL gate (G_UE).

Writes Saved/NaviSense_Reports/wp_20260616_schema_v12_result.json.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from python.attitude_proxy import attitude_deg, ROLL_CLAMP_DEG, PITCH_CLAMP_DEG  # noqa
import python_listener as L  # noqa

checks: dict[str, dict] = {}
def chk(name, ok, detail):
    checks[name] = {"pass": bool(ok), "detail": detail}
    print(("PASS " if ok else "FAIL ") + name + " :: " + detail)

# --- A1..A4 heel (roll) ------------------------------------------------------
a = attitude_deg(5.0, 0.0, 0.10)     # u=5 m/s, +r => starboard turn
chk("A1_heel_outboard_stbd_turn", a.roll_deg < 0,
    f"stbd turn (+r) -> roll={a.roll_deg:.2f} deg (<0 = port-down = outboard)")
b = attitude_deg(5.0, 0.0, -0.10)
chk("A2_heel_flips_with_turn", b.roll_deg > 0,
    f"port turn (-r) -> roll={b.roll_deg:.2f} deg (>0 = starboard-down)")
c = attitude_deg(5.0, 0.0, 0.0)
chk("A3_no_heel_when_straight", c.roll_deg == 0.0,
    f"r=0 -> roll={c.roll_deg:.2f} deg")
d = attitude_deg(50.0, 0.0, 5.0)
chk("A4_heel_clamped", abs(d.roll_deg) == ROLL_CLAMP_DEG,
    f"extreme u*r -> |roll|={abs(d.roll_deg):.2f} == clamp {ROLL_CLAMP_DEG}")

# --- A5 trim (pitch) ---------------------------------------------------------
e = attitude_deg(3.0, 0.0, 0.0, du_dt=1.0)    # accelerating -> bow up
f = attitude_deg(3.0, 0.0, 0.0, du_dt=-100.0) # hard decel -> clamp bow down
chk("A5_trim_sign_and_clamp", e.pitch_deg > 0 and f.pitch_deg == -PITCH_CLAMP_DEG,
    f"accel pitch={e.pitch_deg:.2f}(>0 bow-up); decel pitch={f.pitch_deg:.2f}==-{PITCH_CLAMP_DEG}")

# --- A6 real wire emission (build_state_packet) ------------------------------
def mk(u, r):
    st = SimpleNamespace(x=1.0, y=0.0, z=2.0, yaw_deg=30.0, u=u, v=0.0, r=r,
        port_rpm=100, starboard_rpm=100, rudder_deg=10, bow_thruster_norm=0.0,
        port_rpm_cmd=100, starboard_rpm_cmd=100, rudder_cmd_deg=10, bow_thruster_cmd_norm=0.0)
    return SimpleNamespace(state=st)
plant = mk(5.0, 0.10)
p1 = L.build_state_packet(0.0, "verify", plant, "auto")   # seeds accel cache
plant.state.u = 6.0
p2 = L.build_state_packet(0.1, "verify", plant, "auto")   # du/dt = 10 m/s^2
emit_ok = ("rollDeg" in p2 and "pitchDeg" in p2
           and isinstance(p2["rollDeg"], float) and p2["rollDeg"] < 0
           and p2["pitchDeg"] > 0)
chk("A6_listener_emits_attitude", emit_ok,
    f"state.v1 packet now carries rollDeg={p2['rollDeg']:.2f}, pitchDeg={p2['pitchDeg']:.2f}")

# --- A7 DTO<->wire parity for the two new keys (static) ----------------------
dto = (ROOT / "NaviSense_UE5/Source/NaviSense/Bridge/NaviSenseBridgeTypes.h").read_text(encoding="utf-8")
lst = (ROOT / "python_listener.py").read_text(encoding="utf-8")
dto_has = bool(re.search(r"double\s+rollDeg", dto) and re.search(r"double\s+pitchDeg", dto))
wire_has = ('"rollDeg":' in lst and '"pitchDeg":' in lst)
chk("A7_dto_wire_attitude_parity", dto_has and wire_has,
    f"DTO has rollDeg/pitchDeg={dto_has}; listener emits both={wire_has}")

# --- A8 backward-compat: v1.1 sender (no attitude) renders identical ---------
compat = bool(re.search(r"double\s+rollDeg\s*=\s*0\.0", dto)
              and re.search(r"double\s+pitchDeg\s*=\s*0\.0", dto))
chk("A8_backward_compatible_defaults", compat,
    "attitude fields default 0.0 => a v1.1 packet leaves the hull level (no behaviour change)")

# --- A9 conversion lives only in NaviSenseCoords.h (invariant #1) ------------
coords = (ROOT / "NaviSense_UE5/Source/NaviSense/Core/NaviSenseCoords.h").read_text(encoding="utf-8")
pawn = (ROOT / "NaviSense_UE5/Source/NaviSense/Vessel/NaviSenseShipPawn.cpp").read_text(encoding="utf-8")
single_source = ("WireAttitudeToUE" in coords and "WireRollToUE" in coords
                 and "FNaviSenseCoords::WireRollToUE" in pawn
                 and "WireRollToUE(double" not in pawn)  # defined only in coords
chk("A9_attitude_conversion_single_source", single_source,
    "WirePitch/Roll/AttitudeToUE defined in NaviSenseCoords.h; pawn only calls them")

passed = sum(1 for v in checks.values() if v["pass"])
total = len(checks)
out = {
    "packet": "WP-7 (F1 part 1)",
    "date": "2026-06-16",
    "theme": "6-DOF schema v1.2 — heel (roll) + trim (pitch) visual attitude",
    "advances_gate": "D2 (6-DOF water ride) — attitude half; heave + water-surface = F1 part 2",
    "gates_passed": passed,
    "gates_total": total,
    "gates_manual": 1,
    "auto_result": "PASS" if passed == total else "FAIL",
    "checks": checks,
    "manual_gate": {
        "G_UE_heels_into_turn": {
            "pass": "MANUAL_REQUIRED",
            "detail": ("In PIE with the listener running zigzag10/turning_circle: confirm the hull "
                       "HEELS in the turns (a few degrees) and noses up slightly when accelerating, "
                       "with no jitter at stable FPS. Default is OUTBOARD heel (leans away from the "
                       "turn). To invert, flip the sign in NaviSenseCoords::WireRollToUE only.")
        }
    },
    "note": ("Plant stays 3-DOF; attitude is a kinematic visual proxy computed at the wire boundary "
             "(python/attitude_proxy.py). A1-A9 auto-verified here; G_UE is the in-editor eye-check.")
}
rep = ROOT / "NaviSense_UE5/Saved/NaviSense_Reports/wp_20260616_schema_v12_result.json"
rep.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"\n{'PASS' if passed==total else 'FAIL'}  {passed}/{total} checks -> {rep}")
sys.exit(0 if passed == total else 1)
