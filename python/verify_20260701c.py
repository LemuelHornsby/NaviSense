#!/usr/bin/env python3
"""verify_20260701c -- Camera sensor (WP-14, still-frame metadata) on sensor.v1 (D4).

WP-20260701C wires the LAST concrete D4 sensor gap -- a camera sensor -- using the
low-risk STILL-FRAME approach (recommended over a live SceneCaptureComponent2D, and
over Cesium GPS given KI-014). USensorBundleComponent::BuildSensorsJson now emits a
sensor.v1 ``camera`` block: capture metadata (pose in the wire frame + heading + FOV
+ resolution) plus a deterministic ``frameRef`` naming the HighResShot still the
WP-20260630 08_capture_demo_stills.py burst writes. Proves, headless:

  G1  the C++ is wired: BuildSensorsJson emits a ``camera`` block (fovDeg/resX/resY/
      headingDeg/frameIndex/frameRef/pose{x,y,z}) gated on bEmitCamera, using the
      chase-rig pose (Wire.X/Y/Z) + the IMU HeadingDeg, with a monotonic frame index.
  G2  parity -- the reusable python/camera_sensor mirror produces the SAME keys and
      the SAME frameRef naming (NaviSense_00000.png ...) as the C++ Printf, and the
      pose maps own-ship (East,Up,North) exactly.
  G3  schema / honesty -- record carries the right keys+types; pose uses the wire
      frame; defaults (FOV/res/prefix) match between C++ header and the mirror; the
      frame index is monotonic (deterministic ordering).
  G4  determinism -- the mirror replays bit-for-bit for a given (pose, frame index).
  G5  regression -- Z0 16/16 (C++ still compile-ready) + the AIS-feed (verify_20260701b),
      dashboard (verify_20260701) and traffic (verify_20260629b) gates still PASS
      (this packet is additive to all three).

Negative controls (MUST FIRE):
  N1  a camera block hardcoded to bEmitCamera=false / no SetObjectField("camera") is
      detected as "not wired".
  N2  a wrong frameRef pattern (missing zero-pad / wrong prefix) disagrees with the
      C++ Printf("%s%05d.png") naming.
  N3  the metadata tracks pose/heading -- moving own-ship / changing heading changes
      the emitted pose/headingDeg (not a stub), and the frame index advances.

Exit 0 iff all gates pass and all controls fire.
"""
from __future__ import annotations
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "python"))

import camera_sensor as cam          # noqa: E402  (module under test)

SBC_C = os.path.join(ROOT, "NaviSense_UE5", "Source", "NaviSense", "Sensors", "SensorBundleComponent.cpp")
SBC_H = os.path.join(ROOT, "NaviSense_UE5", "Source", "NaviSense", "Sensors", "SensorBundleComponent.h")
Z0 = os.path.join(ROOT, "Development", "work_packets", "WP_20260615_COMPILE_AUDIT", "verify_compile_readiness.py")
REQ_KEYS = {"fovDeg", "resX", "resY", "headingDeg", "frameIndex", "frameRef", "pose"}
POSE_KEYS = {"x", "y", "z"}


def _read(p):
    return open(p, encoding="utf-8", errors="replace").read()


def _run(path, *args):
    r = subprocess.run([sys.executable, path, *args], capture_output=True, text=True)
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    return r.returncode, tail[-90:]


# ----------------------------------------------------------------- source scan
def _sbc_cam_block(src: str) -> str:
    i = src.find("// ---------- CAMERA")
    if i < 0:
        return ""
    j = src.find("return Sensors;", i)
    return src[i:j] if j > i else src[i:]


def cam_block_is_wired(sbc_src: str) -> bool:
    blk = _sbc_cam_block(sbc_src)
    if not blk:
        return False
    return ("if (bEmitCamera)" in blk
            and 'SetObjectField(TEXT("camera")' in blk
            and 'SetStringField(TEXT("frameRef")' in blk
            and 'SetObjectField(TEXT("pose")' in blk
            and "CameraFrameIndex++" in blk)


# ------------------------------------------------------------------- gates
def g1_cpp_wired():
    c, h = _read(SBC_C), _read(SBC_H)
    blk = _sbc_cam_block(c)
    wired = cam_block_is_wired(c)
    keys = all(f'TEXT("{k}")' in blk for k in ("fovDeg", "resX", "resY", "headingDeg", "frameIndex"))
    uses_pose = ("Wire.X" in blk and "Wire.Y" in blk and "Wire.Z" in blk and "HeadingDeg" in blk)
    hdr = ("bEmitCamera" in h and "CameraFovDeg" in h and "CameraResX" in h
           and "CameraFramePrefix" in h and "CameraFrameIndex" in h)
    ok = wired and keys and uses_pose and hdr
    return ok, f"wired={wired} keys={keys} chase_pose+heading={uses_pose} hdr_fields={hdr}"


def g2_parity():
    # frameRef naming parity with the C++ Printf("%s%05d.png")
    refs = [cam.frame_ref(i) for i in (0, 7, 42, 12345)]
    exp = ["NaviSense_00000.png", "NaviSense_00007.png", "NaviSense_00042.png", "NaviSense_12345.png"]
    naming = (refs == exp)
    # C++ uses %05d + CameraFramePrefix="NaviSense_"
    c, h = _read(SBC_C), _read(SBC_H)
    cpp_fmt = 'FString::Printf(TEXT("%s%05d.png")' in c and 'CameraFramePrefix = TEXT("NaviSense_")' in h
    # pose maps (East,Up,North) exactly
    rec = cam.camera_record(120.0, 3.0, 800.0, 45.0, 5)
    pose_ok = (rec["pose"] == {"x": 120.0, "y": 3.0, "z": 800.0} and rec["headingDeg"] == 45.0
               and rec["frameIndex"] == 5 and rec["frameRef"] == "NaviSense_00005.png")
    ok = naming and cpp_fmt and pose_ok
    return ok, f"frameRef_naming={naming} cpp_printf+prefix={cpp_fmt} pose(E,Up,N)+idx={pose_ok}"


def g3_schema_honesty():
    rec = cam.camera_record(10.0, 2.0, -30.0, 90.0, 0)
    keys = (set(rec) == REQ_KEYS and set(rec["pose"]) == POSE_KEYS)
    types = (isinstance(rec["fovDeg"], float) and isinstance(rec["resX"], int)
             and isinstance(rec["resY"], int) and isinstance(rec["frameIndex"], int)
             and isinstance(rec["frameRef"], str))
    # defaults match C++ header
    h = _read(SBC_H)
    defaults = (f"CameraFovDeg = {int(cam.DEFAULT_FOV_DEG)}." in h
                and f"CameraResX = {cam.DEFAULT_RES_X}" in h
                and f"CameraResY = {cam.DEFAULT_RES_Y}" in h)
    # honesty label present (KI-026 family) in both C++ and mirror
    c = _read(SBC_C)
    honest = ("NOT a live" in c and "not a" in cam.__doc__.lower())
    # monotonic frame index across calls
    r0 = cam.camera_record(0, 0, 0, 0, 0)
    r1 = cam.camera_record(0, 0, 0, 0, 1)
    mono = (r1["frameIndex"] == r0["frameIndex"] + 1
            and r1["frameRef"] != r0["frameRef"])
    ok = keys and types and defaults and honest and mono
    return ok, f"keys={keys} types={types} defaults_match={defaults} honesty_label={honest} monotonic={mono}"


def g4_determinism():
    a = cam.camera_record(123.4, 5.6, -78.9, 33.0, 9)
    b = cam.camera_record(123.4, 5.6, -78.9, 33.0, 9)
    ok = (json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))
    return ok, f"bit-identical replay={ok}"


def g5_regression():
    z_rc, z_msg = _run(Z0)
    a_rc, _ = _run(os.path.join(ROOT, "python", "verify_20260701b.py"))
    d_rc, _ = _run(os.path.join(ROOT, "python", "verify_20260701.py"))
    t_rc, _ = _run(os.path.join(ROOT, "python", "verify_20260629b.py"))
    ok = (z_rc == 0 and a_rc == 0 and d_rc == 0 and t_rc == 0)
    return ok, f"Z0 rc={z_rc}({z_msg}); ais rc={a_rc}; dashboard rc={d_rc}; traffic rc={t_rc}"


# ----------------------------------------------------------------- controls
def n1_unwired_detected():
    stub = ("    // ---------- CAMERA ----------\n"
            "    // (camera disabled -- no block)\n")
    fired = not cam_block_is_wired(stub)
    return fired, f"unwired stub wired?={not fired} -> {'fired' if fired else 'MISS'}"


def n2_wrong_frameref():
    good = cam.frame_ref(5)                       # NaviSense_00005.png
    bad_pad = "NaviSense_5.png"                    # missing zero-pad
    bad_prefix = "Frame_00005.png"                 # wrong prefix
    fired = (good == "NaviSense_00005.png" and good != bad_pad and good != bad_prefix)
    return fired, f"good={good} != {bad_pad}/{bad_prefix} -> {'fired' if fired else 'MISS'}"


def n3_tracks_pose_heading():
    r0 = cam.camera_record(0.0, 0.0, 0.0, 0.0, 0)
    r1 = cam.camera_record(500.0, 4.0, 800.0, 137.0, 1)
    fired = (r1["pose"] != r0["pose"] and r1["headingDeg"] == 137.0
             and r0["headingDeg"] == 0.0 and r1["frameIndex"] == 1)
    return fired, (f"pose {r0['pose']}->{r1['pose']}, hdg 0->137, idx 0->1 "
                   f"-> {'fired' if fired else 'MISS'}")


def main():
    gates = [
        ("G1", "cpp_camera_wired", *g1_cpp_wired()),
        ("G2", "frameref_and_pose_parity", *g2_parity()),
        ("G3", "schema_honesty_defaults", *g3_schema_honesty()),
        ("G4", "determinism", *g4_determinism()),
        ("G5", "regression_Z0+ais+dashboard+traffic", *g5_regression()),
    ]
    controls = [
        ("N1", "unwired_detected", *n1_unwired_detected()),
        ("N2", "wrong_frameref_caught", *n2_wrong_frameref()),
        ("N3", "tracks_pose_heading", *n3_tracks_pose_heading()),
    ]
    print("verify_20260701c -- Camera sensor (WP-14, still-frame metadata) on sensor.v1\n")
    gp = 0
    for cid, name, ok, det in gates:
        print(f"  [{'PASS' if ok else 'FAIL'}] {cid} {name}: {det}"); gp += ok
    print()
    cf = 0
    for cid, name, fired, det in controls:
        print(f"  [{'FIRED' if fired else 'MISS'}] {cid} {name}: {det}"); cf += fired
    all_ok = (gp == len(gates) and cf == len(controls))
    print(f"\n  Gates {gp}/{len(gates)}  Controls {cf}/{len(controls)}  => {'PASS' if all_ok else 'FAIL'}")
    out = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports", "wp_20260701c_result.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"packet": "WP-20260701C",
                   "title": "Camera sensor (WP-14, still-frame metadata) on sensor.v1 (D4)",
                   "model": "Opus 4.8",
                   "gates": {c: bool(o) for c, _, o, _ in gates},
                   "gates_detail": {c: d for c, _, _, d in gates},
                   "controls_fired": {c: bool(x) for c, _, x, _ in controls},
                   "controls_detail": {c: d for c, _, _, d in controls},
                   "gates_passed": gp, "gates_total": len(gates),
                   "controls_fired_n": cf, "controls_total": len(controls),
                   "verdict": "PASS" if all_ok else "FAIL"}, f, indent=2)
    print(f"  wrote {out}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
