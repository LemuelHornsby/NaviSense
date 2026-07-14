#!/usr/bin/env python3
"""WP-8 (F1 part 2) -- 6-DOF schema v1.3 (heave + sea state) auto-verify.

Exercises the REAL code paths the listener uses (python/sea_state.py and
build_state_packet), plus static DTO<->wire parity / single-source / backward-compat
checks. The only thing this cannot do from the sandbox is render the hull bobbing on
the swell, so the "rides the waves" eye-check is the single MANUAL gate (G_UE8).

Writes Saved/NaviSense_Reports/wp_20260617_heave_seastate_result.json.
"""
from __future__ import annotations
import json, math, re, statistics, sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from python.sea_state import WaveField, HEAVE_CLAMP_M, SEA_STATES  # noqa
import python_listener as L  # noqa

checks: dict = {}
def chk(name, ok, detail):
    checks[name] = {"pass": bool(ok), "detail": detail}
    print(("PASS " if ok else "FAIL ") + name + " :: " + detail)

# --- H1 SS0 => identically flat (backward-compatible: no heave) ---------------
w0 = WaveField(sea_state=0)
flat = all(w0.elevation(e, n, t) == 0.0
           for e in (0., 25., 100.) for n in (0., -40.) for t in (0., 1.3, 7.7))
chk("H1_ss0_flat", (not w0.active) and flat,
    "SS0 (calm) => elevation==0 everywhere => byte-identical to rev 1.2")

# --- H2 deterministic / replayable (no RNG at sample time) -------------------
w5 = WaveField(sea_state=5)
det_same = w5.elevation(12.3, -4.5, 7.7) == w5.elevation(12.3, -4.5, 7.7)
det_rebuild = (WaveField(sea_state=5).elevation(3., 9., 11.)
               == WaveField(sea_state=5).elevation(3., 9., 11.))
chk("H2_deterministic", det_same and det_rebuild,
    "elevation(e,n,t) reproducible within a field and across rebuilds (same seed) -> replayable")

# --- H3 realized significant height == target Hs (model fidelity) ------------
errs = [abs(WaveField(sea_state=ss).significant_height() - SEA_STATES[ss][0]) for ss in (3, 5, 7)]
chk("H3_significant_height_matches", max(errs) < 1e-6,
    f"analytic Hs == target for SS3/5/7 (max err {max(errs):.2e} m)")

# --- H4 zero temporal mean (no DC offset that would sink/raise the hull) -----
samp = [w5.elevation(0., 0., t * 0.1) for t in range(3000)]
mean = statistics.mean(samp)
rms = math.sqrt(sum(s * s for s in samp) / len(samp))
chk("H4_zero_mean", abs(mean) < 0.05 * SEA_STATES[5][0],
    f"SS5 temporal mean {mean:+.4f} m ~ 0 (no waterline drift); sampled RMS {rms:.3f} ~ Hs/4 {SEA_STATES[5][0]/4:.3f}")

# --- H5 bounded by the heave clamp (visual never detaches the hull) ----------
w9 = WaveField(sea_state=9)
big = [abs(w9.elevation(e * 7., e * 3., e * 0.13)) for e in range(4000)]
chk("H5_clamped", max(big) <= HEAVE_CLAMP_M + 1e-9,
    f"SS9 |heave| max {max(big):.3f} <= clamp {HEAVE_CLAMP_M} m")

# --- H6 monotone energy with sea state (calm -> phenomenal) ------------------
hs = [WaveField(sea_state=s).significant_height() for s in range(10)]
mono = hs[0] == 0.0 and all(hs[i] < hs[i + 1] for i in range(1, 9))
chk("H6_monotone_energy", mono,
    "Hs strictly increases SS1..SS9 and SS0==0: " + ",".join(f"{h:.2f}" for h in hs))

# --- H7 continuity (smooth bob: bounded step over a 30 Hz tick; no pops) ------
prev = w5.elevation(50., 20., 0.0); max_step = 0.0
for k in range(1, 2000):
    cur = w5.elevation(50., 20., k * (1 / 30.0))
    max_step = max(max_step, abs(cur - prev)); prev = cur
chk("H7_continuous", max_step < 0.5,
    f"SS5 max per-tick (30 Hz) heave step {max_step:.3f} m < 0.5 (smooth)")

# --- H8 listener emits heaveM on state.v1 (real build_state_packet) ----------
def mk(x=0.0, z=0.0, u=4.0, r=0.05):
    st = SimpleNamespace(x=x, y=0.0, z=z, yaw_deg=20.0, u=u, v=0.0, r=r,
        port_rpm=100, starboard_rpm=100, rudder_deg=5, bow_thruster_norm=0.0,
        port_rpm_cmd=100, starboard_rpm_cmd=100, rudder_cmd_deg=5, bow_thruster_cmd_norm=0.0)
    return SimpleNamespace(state=st)
pl = mk(); pl._wave_field = WaveField(sea_state=6)
seen = []
for i in range(40):
    pl.state.z = 0.7 * i
    seen.append(L.build_state_packet(i * 0.1, "verify", pl, "auto")["heaveM"])
emit_ok = (all(isinstance(h, float) for h in seen)
           and any(h != 0.0 for h in seen) and all(abs(h) <= HEAVE_CLAMP_M for h in seen))
chk("H8_listener_emits_heave", emit_ok,
    f"state.v1 carries heaveM; SS6 range {min(seen):+.3f}..{max(seen):+.3f} m, all within clamp")

# --- H9 backward-compat: no field => heaveM 0.0 (a v1.2 sender unchanged) -----
p0 = L.build_state_packet(0.0, "verify", mk(), "auto")  # no _wave_field attribute
chk("H9_backward_compatible", "heaveM" in p0 and p0["heaveM"] == 0.0,
    "no wave field => heaveM=0.0 => v1.2 wire/behaviour unchanged")

# --- H10 DTO<->wire parity for heaveM (static; invariant #3) ------------------
dto = (ROOT / "NaviSense_UE5/Source/NaviSense/Bridge/NaviSenseBridgeTypes.h").read_text(encoding="utf-8")
lst = (ROOT / "python_listener.py").read_text(encoding="utf-8")
dto_has = bool(re.search(r"double\s+heaveM\s*=\s*0\.0", dto))
wire_has = ('"heaveM":' in lst)
chk("H10_dto_wire_parity", dto_has and wire_has,
    f"DTO has 'double heaveM = 0.0' (default 0 => backward-compat)={dto_has}; listener emits 'heaveM'={wire_has}")

# --- H11 conversion lives only in NaviSenseCoords.h (invariant #1) ------------
coords = (ROOT / "NaviSense_UE5/Source/NaviSense/Core/NaviSenseCoords.h").read_text(encoding="utf-8")
pawn = (ROOT / "NaviSense_UE5/Source/NaviSense/Vessel/NaviSenseShipPawn.cpp").read_text(encoding="utf-8")
single = ("WireHeaveToUE" in coords
          and "FNaviSenseCoords::WireHeaveToUE" in pawn
          and "WireHeaveToUE(double" not in pawn)   # defined only in coords
chk("H11_heave_conversion_single_source", single,
    "WireHeaveToUE defined in NaviSenseCoords.h; pawn only CALLS it (sign/axis single-source)")

# --- H12 pawn rides heave on Z (target set, smoothed, applied) ----------------
pawn_applies = ("TargetHeaveCm" in pawn and "CurrentHeaveCm" in pawn
                and re.search(r"Loc\.Z\s*=.*CurrentHeaveCm", pawn) is not None)
chk("H12_pawn_applies_heave", pawn_applies,
    "pawn sets TargetHeaveCm from the wire, smooths to CurrentHeaveCm, adds it to Loc.Z (Tick)")

passed = sum(1 for v in checks.values() if v["pass"]); total = len(checks)
out = {
    "packet": "WP-8 (F1 part 2)",
    "date": "2026-06-17",
    "theme": "6-DOF schema v1.3 -- wave-driven heave + deterministic sea-state field",
    "advances_gate": "D2 (6-DOF water ride) heave half; seeds D3 (sea states). Heel/trim = WP-7 (v1.2).",
    "gates_passed": passed, "gates_total": total, "gates_manual": 1,
    "auto_result": "PASS" if passed == total else "FAIL",
    "checks": checks,
    "manual_gate": {
        "G_UE8_rides_the_swell": {
            "pass": "MANUAL_REQUIRED",
            "detail": ("In PIE with the listener running e.g. `--controller turning_circle --sea-state 5`: "
                       "confirm the hull RISES AND FALLS on the swell smoothly (no vertical jitter) at stable "
                       "FPS, and sits flat again at --sea-state 0. If it sinks on a crest (inverted), flip the "
                       "sign in NaviSenseCoords::WireHeaveToUE only.")
        }
    },
    "note": ("Plant stays 3-DOF; heave is a deterministic kinematic wave-field proxy sampled at the wire "
             "boundary (python/sea_state.py), replayable with WP-4's sim clock. H1-H12 auto-verified here; "
             "G_UE8 is the in-editor eye-check. Sampling the *rendered* UE water surface is F1 part 3.")
}
rep = ROOT / "NaviSense_UE5/Saved/NaviSense_Reports/wp_20260617_heave_seastate_result.json"
rep.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"\n{'PASS' if passed==total else 'FAIL'}  {passed}/{total} checks -> {rep}")
sys.exit(0 if passed == total else 1)
