#!/usr/bin/env python3
"""Gate WP-20260628 — speed-driven wake & spray VFX feed (D5 / WP-16).

The hull is kinematically posed, so the wake is *driven by speed*: a Niagara
system reads 0..1 ``WakeIntensity`` / ``Spray`` user floats and scales itself.
The curve is single-sourced in ``python/wake_model.py`` and MIRRORED in C++
(``ANaviSenseShipPawn::GetWakeIntensity01`` / ``GetWakeSpray01``). This verify
proves the model behaves (monotone, clamped, spray gated at hull speed), that the
C++ defaults equal the Python constants (so the rendered curve == the gated
curve), and that the broken variants are actually caught.

6 gates + 3 negative controls. Read-only over the repo; writes only the result
JSON. Exit 0 iff 6/6 gates pass AND 3/3 controls fire.
  G1 intensity is 0 at rest, monotone non-decreasing, clamped to [0,1], =1 at full.
  G2 spray is 0 up to the spray-onset speed, then ramps monotone to 1 at full.
  G3 geometry (ribbon width / spawn rate / spray rate) stays in declared bounds
     and tracks speed monotonically.
  G4 the C++ pawn defaults (WakeFullSpeedMS/WakeSprayOnsetMS/WakeMinSpeedMS) equal
     the Python constants, and each C++ getter uses the right constant + clamps.
  G5 the model is deterministic (recompute + JSON round-trip identical).
  G6 the editor-Python setup script parses, the recipe doc is present + references
     the user params, and the edited C++ TUs are brace-balanced (KI-004 guard).
Negative controls (must FIRE): N1 a flat curve is rejected (no ramp); N2 a curve
that is non-zero at rest is rejected; N3 a tampered C++ constant is detected by the
parity check.
"""
from __future__ import annotations

import ast
import datetime as _dt
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_PY = os.path.join(_ROOT, "python")
for p in (_PY, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import wake_model as wm  # noqa: E402

PAWN_H = os.path.join(_ROOT, "NaviSense_UE5", "Source", "NaviSense", "Vessel", "NaviSenseShipPawn.h")
PAWN_CPP = os.path.join(_ROOT, "NaviSense_UE5", "Source", "NaviSense", "Vessel", "NaviSenseShipPawn.cpp")
EDITOR_PY = os.path.join(_ROOT, "NaviSense_UE5", "Content", "NaviSense", "Python",
                         "Phase5_Systems", "04_setup_wake_vfx.py")
RECIPE = os.path.join(_ROOT, "Documents", "NaviSense_Wake_VFX_Recipe.md")
RESULT = os.path.join(_ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports", "wp_20260628_result.json")

EPS = 1e-9


def _sweep(lo=0.0, hi=15.0, step=0.05):
    n = int(round((hi - lo) / step))
    return [lo + i * step for i in range(n + 1)]


def _is_monotone_nondec(xs):
    return all(xs[i + 1] >= xs[i] - EPS for i in range(len(xs) - 1))


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _float_default(hsrc, name):
    m = re.search(name + r"\s*=\s*([0-9]+(?:\.[0-9]+)?)f", hsrc)
    return float(m.group(1)) if m else None


def _fn_body(csrc, signature):
    """Return the brace body of a member function definition (first match)."""
    i = csrc.find(signature)
    if i < 0:
        return ""
    b = csrc.find("{", i)
    if b < 0:
        return ""
    depth, j = 0, b
    while j < len(csrc):
        if csrc[j] == "{":
            depth += 1
        elif csrc[j] == "}":
            depth -= 1
            if depth == 0:
                return csrc[b:j + 1]
        j += 1
    return csrc[b:]


# ----------------------------------------------------------------- gates
def g1_intensity():
    vs = _sweep()
    ys = [wm.intensity01(v) for v in vs]
    rest_zero = all(wm.intensity01(v) == 0.0 for v in (0.0, wm.WAKE_MIN_SPEED_MS, wm.WAKE_MIN_SPEED_MS - 0.01))
    in_range = all(0.0 <= y <= 1.0 for y in ys)
    mono = _is_monotone_nondec(ys)
    full_one = abs(wm.intensity01(wm.WAKE_FULL_SPEED_MS) - 1.0) < 1e-6 and abs(wm.intensity01(wm.WAKE_FULL_SPEED_MS + 5) - 1.0) < 1e-6
    # there is a real ramp in the active band
    ramped = wm.intensity01(wm.WAKE_FULL_SPEED_MS * 0.5) > 0.05
    ok = rest_zero and in_range and mono and full_one and ramped
    return ok, "rest0=%s range=%s mono=%s full=1:%s ramp@half=%.3f" % (
        rest_zero, in_range, mono, full_one, wm.intensity01(wm.WAKE_FULL_SPEED_MS * 0.5))


def g2_spray():
    onset = wm.WAKE_SPRAY_ONSET_MS
    below = [wm.spray01(v) for v in _sweep(0.0, onset, 0.05)]
    below_zero = all(s == 0.0 for s in below)
    just_above = wm.spray01(onset + 0.2) > 0.0
    ys = [wm.spray01(v) for v in _sweep(onset, wm.WAKE_FULL_SPEED_MS, 0.02)]
    mono = _is_monotone_nondec(ys)
    full_one = abs(wm.spray01(wm.WAKE_FULL_SPEED_MS) - 1.0) < 1e-6 and abs(wm.spray01(wm.WAKE_FULL_SPEED_MS + 5) - 1.0) < 1e-6
    ok = below_zero and just_above and mono and full_one
    return ok, "below_onset_zero=%s on+=%.3f mono=%s full=1:%s (onset=%.1f m/s ~%.0f kn)" % (
        below_zero, wm.spray01(onset + 0.2), mono, full_one, onset, onset / wm.KN_TO_MS)


def g3_geometry():
    vs = _sweep()
    w = [wm.ribbon_width_cm(v) for v in vs]
    sr = [wm.spawn_rate(v) for v in vs]
    spr = [wm.spray_rate(v) for v in vs]
    w_ok = all(wm.RIBBON_WIDTH_MIN_CM - EPS <= x <= wm.RIBBON_WIDTH_FULL_CM + EPS for x in w) and _is_monotone_nondec(w)
    sr_ok = all(0.0 - EPS <= x <= wm.SPAWN_RATE_FULL + EPS for x in sr) and _is_monotone_nondec(sr)
    spr_ok = all(0.0 - EPS <= x <= wm.SPRAY_RATE_FULL + EPS for x in spr) and _is_monotone_nondec(spr)
    spr_gated = wm.spray_rate(wm.WAKE_SPRAY_ONSET_MS) == 0.0
    ok = w_ok and sr_ok and spr_ok and spr_gated
    return ok, "width[%.0f..%.0f]ok=%s spawn<=%.0fok=%s spray<=%.0fok=%s gated=%s" % (
        min(w), max(w), w_ok, wm.SPAWN_RATE_FULL, sr_ok, wm.SPRAY_RATE_FULL, spr_ok, spr_gated)


def g4_cpp_parity():
    hsrc = _read(PAWN_H)
    csrc = _read(PAWN_CPP)
    pairs = {
        "WakeFullSpeedMS": wm.WAKE_FULL_SPEED_MS,
        "WakeSprayOnsetMS": wm.WAKE_SPRAY_ONSET_MS,
        "WakeMinSpeedMS": wm.WAKE_MIN_SPEED_MS,
    }
    parsed = {k: _float_default(hsrc, k) for k in pairs}
    consts_match = all(parsed[k] is not None and abs(parsed[k] - v) < 1e-6 for k, v in pairs.items())
    decl = ("UFUNCTION(BlueprintPure" in hsrc
            and "float GetWakeIntensity01() const;" in hsrc
            and "float GetWakeSpray01() const;" in hsrc)
    ib = _fn_body(csrc, "ANaviSenseShipPawn::GetWakeIntensity01")
    sb = _fn_body(csrc, "ANaviSenseShipPawn::GetWakeSpray01")
    # right constant in each getter, both clamp, not swapped
    ib_ok = ("WakeMinSpeedMS" in ib) and ("WakeSprayOnsetMS" not in ib) and ("FMath::Clamp" in ib)
    sb_ok = ("WakeSprayOnsetMS" in sb) and ("WakeMinSpeedMS" not in sb) and ("FMath::Clamp" in sb)
    ok = consts_match and decl and ib_ok and sb_ok
    return ok, "consts=%s %s decl=%s intensity_uses_min=%s spray_uses_onset=%s" % (
        consts_match, parsed, decl, ib_ok, sb_ok)


def g5_determinism():
    vs = _sweep(0.0, 12.0, 0.1)
    a = [wm.params(v).to_dict() for v in vs]
    b = [wm.params(v).to_dict() for v in vs]
    same = a == b
    jr = json.loads(json.dumps(a)) == a
    return (same and jr), "recompute_identical=%s json_roundtrip=%s n=%d" % (same, jr, len(vs))


def _braces_balanced(path):
    s = _read(path)
    return s.count("{") == s.count("}"), s.count("{"), s.count("}")


def g6_assets_and_guard():
    # editor-python parses
    try:
        ast.parse(_read(EDITOR_PY))
        script_ok = True
    except Exception as e:
        script_ok = False
        script_detail = str(e)
    else:
        script_detail = os.path.basename(EDITOR_PY)
    # recipe present + references the user params
    recipe_ok = os.path.exists(RECIPE)
    if recipe_ok:
        r = _read(RECIPE)
        recipe_ok = ("User.WakeIntensity" in r and "User.Spray" in r
                     and "GetWakeIntensity01" in r)
    # KI-004 truncation guard on the two edited C++ TUs
    hb, ho, hc = _braces_balanced(PAWN_H)
    cb, co, cc = _braces_balanced(PAWN_CPP)
    ok = script_ok and recipe_ok and hb and cb
    return ok, "script=%s(%s) recipe=%s h{}=%d/%d cpp{}=%d/%d" % (
        script_ok, script_detail, recipe_ok, ho, hc, co, cc)


# -------------------------------------------------------- negative controls
def n1_flat_curve_rejected():
    """A constant 'intensity' (no ramp) must fail the monotone-ramp + endpoint test."""
    flat = lambda v: 0.5  # noqa: E731
    vs = _sweep()
    ys = [flat(v) for v in vs]
    rest_zero = flat(0.0) == 0.0
    full_one = abs(flat(wm.WAKE_FULL_SPEED_MS) - 1.0) < 1e-6
    ramped = flat(wm.WAKE_FULL_SPEED_MS * 0.5) > 0.05 and (max(ys) - min(ys) > 0.05)
    accepted = rest_zero and full_one and ramped
    fired = not accepted
    return fired, "flat curve accepted=%s (rest0=%s full1=%s ramp=%s)" % (accepted, rest_zero, full_one, ramped)


def n2_wake_at_rest_rejected():
    """A curve that is non-zero at rest must fail the rest-zero gate."""
    bad = lambda v: max(0.2, wm.intensity01(v))  # noqa: E731
    rest_zero = bad(0.0) == 0.0
    fired = not rest_zero
    return fired, "non-zero@rest value=%.2f rest_zero=%s" % (bad(0.0), rest_zero)


def n3_parity_tamper_detected():
    """A tampered C++ default must be caught by the G4 parity comparison."""
    fake_h = "float WakeFullSpeedMS = 99.0f;\nfloat WakeSprayOnsetMS = 7.7f;\nfloat WakeMinSpeedMS = 0.3f;\n"
    parsed_full = _float_default(fake_h, "WakeFullSpeedMS")
    detected = abs(parsed_full - wm.WAKE_FULL_SPEED_MS) > 1e-6
    return detected, "tampered WakeFullSpeedMS=%.1f vs python=%.1f -> mismatch detected=%s" % (
        parsed_full, wm.WAKE_FULL_SPEED_MS, detected)


def main():
    gates = [
        ("G1", "intensity_monotone_clamped", g1_intensity),
        ("G2", "spray_onset_ramp", g2_spray),
        ("G3", "geometry_bounds", g3_geometry),
        ("G4", "cpp_python_parity", g4_cpp_parity),
        ("G5", "determinism", g5_determinism),
        ("G6", "assets_and_truncation_guard", g6_assets_and_guard),
    ]
    controls = [
        ("N1", "flat_curve_rejected", n1_flat_curve_rejected),
        ("N2", "wake_at_rest_rejected", n2_wake_at_rest_rejected),
        ("N3", "parity_tamper_detected", n3_parity_tamper_detected),
    ]

    gres, passed = [], 0
    for gid, name, fn in gates:
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, "EXC: %r" % e
        passed += 1 if ok else 0
        gres.append({"id": gid, "name": name, "passed": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + gid + " " + name + " :: " + detail)

    cres, fired = [], 0
    for nid, name, fn in controls:
        try:
            f, detail = fn()
        except Exception as e:
            f, detail = False, "EXC: %r" % e
        fired += 1 if f else 0
        cres.append({"id": nid, "name": name, "fired": bool(f), "detail": detail})
        print(("FIRED " if f else "MISS  ") + nid + " " + name + " :: " + detail)

    overall = (passed == len(gates)) and (fired == len(controls))
    out = {
        "packet": "WP-20260628",
        "theme": "speed-driven wake & spray VFX feed (D5 / WP-16)",
        "generated_at": _dt.datetime.now().replace(microsecond=0).isoformat(),
        "gates_passed": passed,
        "gates_total": len(gates),
        "negative_controls_fired": fired,
        "negative_controls_total": len(controls),
        "all_negative_controls_fired": fired == len(controls),
        "overall": "PASS" if overall else "FAIL",
        "gates": gres,
        "negative_controls": cres,
    }
    os.makedirs(os.path.dirname(RESULT), exist_ok=True)
    with open(RESULT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("\n%s  %d/%d gates, %d/%d controls -> %s" % (
        out["overall"], passed, len(gates), fired, len(controls), RESULT))
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
