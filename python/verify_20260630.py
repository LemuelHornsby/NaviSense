#!/usr/bin/env python3
"""verify_20260630 -- demo-capture enablement (D6 stills / D7 frames + the
in-engine batch).

Proves, headless, that the capture toolchain shipped this packet actually gates
the demo evidence:

  G1  the editor capturer Phase5_Systems/08_capture_demo_stills.py parses and
      really drives HighResShot + writes capture_manifest.json (static AST/text).
  G2  the shots check accepts a set of full-res stills (>= min count, size, res).
  G3  the run-health check is wired to verify_run_kinematics and PASSES on a real
      healthy run (so the gate uses the same K1-K8 verdict as the nightly).
  G4  the stdlib PNG-size parser reads IHDR correctly and rejects non-PNG bytes.
  G5  END-TO-END: evaluate() = PASS for {3 full-res stills + a healthy run}; the
      four capture scenarios (monaco_capture / rough_turning_circle /
      building_sea_transit / storm_ride) resolve to real controllers; and the Z0
      compile-readiness guard is still green (C++ untouched this packet).

Negative controls (MUST FIRE = the gate correctly FAILS):
  N1  only 2 stills -> shots check FAILS (count floor).
  N2  a 640x480 grab among them -> shots check FAILS (resolution floor); a
      low-res frame is not a beauty shot.
  N3  a spinning-on-the-spot run -> run-health FAILS (verdict FAIL), so a pretty
      frame is never accepted over a broken run.

Exit 0 iff all gates pass and all controls fire.
"""
from __future__ import annotations
import ast, json, os, struct, subprocess, sys, tempfile, time, zlib, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "python"))

import verify_capture_artifacts as vca   # noqa: E402  (module under test)
import scenarios as SC                   # noqa: E402

EDITOR_SCRIPT = os.path.join(ROOT, "NaviSense_UE5", "Content", "NaviSense",
                             "Python", "Phase5_Systems", "08_capture_demo_stills.py")
Z0 = os.path.join(ROOT, "Development", "work_packets", "WP_20260615_COMPILE_AUDIT",
                  "verify_compile_readiness.py")
STATE_HEADER = ("wall_time,t,mode,x,y,z,yawDeg,u,v,r,portRpm,starboardRpm,rudderDeg,"
                "bowThrusterNorm,portRpmCmd,starboardRpmCmd,rudderCmdDeg,"
                "bowThrusterCmdNorm,speed_mag,rudder_error_deg,rollDeg,pitchDeg,heaveM")
KNOWN_CONTROLLERS = {"turning_circle", "zigzag10", "zigzag20", "demo", "transit"}


# ----------------------------------------------------------------- fixtures
def make_png(path: str, w: int, h: int) -> None:
    """Write a minimal but VALID RGB PNG (IHDR+IDAT+IEND), all-black pixels."""
    def chunk(typ: bytes, data: bytes) -> bytes:
        body = typ + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)        # 8-bit RGB
    raw = b"".join(b"\x00" + b"\x00\x00\x00" * w for _ in range(h))  # filter + pixels
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw, 1)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def write_run(dirpath: str, kind: str) -> None:
    """Synthesize a logs/<run> dir (real state.csv schema). kind: 'spin' -> a
    pirouette (K5 FAIL); used only for the FAIL control."""
    os.makedirs(dirpath, exist_ok=True)
    rows = [STATE_HEADER]
    n, dt, base = 200, 0.1, 1.0e9
    for i in range(n):
        t = i * dt
        approach = i < 20
        mode = "approach" if approach else "turning"
        yaw = 0.0 if approach else (i * 2.0) % 360.0      # 2 deg/tick spin
        r = 0.0 if approach else 0.349                    # rad/s (<0.60 cap)
        u = 2.0
        x = z = 0.0                                       # NO translation -> spin on spot
        row = [f"{base+t:.6f}", f"{t:.6f}", mode, f"{x:.6f}", "0.000000", f"{z:.6f}",
               f"{yaw:.6f}", f"{u:.6f}", "0.000000", f"{r:.6f}", "300", "300",
               "15.000000", "0.000000", "300", "300", "15.000000", "0.000000",
               f"{u:.6f}", "0.000000", "0.000000", "0.000000", "0.000000"]
        rows.append(",".join(row))
    with open(os.path.join(dirpath, "state.csv"), "w") as f:
        f.write("\n".join(rows) + "\n")
    with open(os.path.join(dirpath, "manifest.json"), "w") as f:
        json.dump({"controllerKind": "turning_circle", "tickHz": 10,
                   "scenario": "spin_test", "plantKind": "stub", "stateRows": n}, f)


def first_healthy_run() -> str:
    import verify_run_kinematics as vrk
    runs = sorted((d for d in glob.glob(os.path.join(ROOT, "logs", "unreal-test-run_*"))
                   if os.path.isdir(d)), key=os.path.getmtime, reverse=True)
    for d in runs:
        if os.sep + "_selftest" + os.sep in d + os.sep:
            continue
        try:
            if vrk.analyse_run_dir(d).get("verdict") == "PASS":
                return d
        except Exception:
            continue
    return ""


CFG = {"min_shots": 3, "min_bytes": 200, "min_w": 1280, "min_h": 720, "since_epoch": None}


# -------------------------------------------------------------------- gates
def g1_editor_script():
    if not os.path.exists(EDITOR_SCRIPT):
        return False, "08_capture_demo_stills.py missing"
    src = open(EDITOR_SCRIPT, encoding="utf-8", errors="replace").read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return False, f"syntax error: {e}"
    has_main = any(isinstance(n, ast.FunctionDef) and n.name == "main" for n in tree.body)
    refs = ("HighResShot" in src and "capture_manifest.json" in src
            and "import unreal" in src and "execute_console_command" in src)
    ok = has_main and refs
    return ok, (f"parses, main()={has_main}, HighResShot+manifest+unreal+console={refs}")


def g2_shots_accept():
    with tempfile.TemporaryDirectory() as d:
        for i in range(3):
            make_png(os.path.join(d, f"HighresScreenshot0000{i}.png"), 1920, 1080)
        ok, det, _ = vca.check_shots(d, CFG["min_shots"], CFG["min_bytes"], CFG["min_w"], CFG["min_h"])
    return ok, det


def g3_run_health_real():
    run = first_healthy_run()
    if not run:
        return False, "no healthy real run found in logs/ to anchor C2"
    ok, det, data = vca.check_run_health(run)
    return ok and data.get("verdict") == "PASS", det


def g4_png_parser():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.png"); make_png(p, 800, 600)
        sz = vca.parse_png_size(p)
        bad = os.path.join(d, "b.png")
        open(bad, "wb").write(b"not a png at all, just bytes" * 4)
        szbad = vca.parse_png_size(bad)
        p2 = os.path.join(d, "c.png"); make_png(p2, 1920, 1080)
        sz2 = vca.parse_png_size(p2)
    ok = sz == (800, 600) and szbad is None and sz2 == (1920, 1080)
    return ok, f"800x600->{sz}, garbage->{szbad}, 1920x1080->{sz2}"


def g5_e2e():
    run = first_healthy_run()
    with tempfile.TemporaryDirectory() as d:
        for i in range(3):
            make_png(os.path.join(d, f"shot{i}.png"), 3840, 2160)
        res = vca.evaluate(d, run, CFG, want_run_health=True)
    e2e_ok = res["verdict"] == "PASS"
    # capture scenarios resolve to real controllers
    names = ["monaco_capture", "rough_turning_circle", "building_sea_transit", "storm_ride"]
    sc_ok, sc_detail = True, []
    for nm in names:
        try:
            s = SC.get_scenario(nm)
            good = s.controller in KNOWN_CONTROLLERS
            sc_ok = sc_ok and good
            sc_detail.append(f"{nm}:{s.controller}{'' if good else '?!'}")
        except Exception as e:
            sc_ok = False; sc_detail.append(f"{nm}:ERR({e})")
    # Z0 compile-readiness (C++ untouched this packet)
    z0_ok, z0_msg = True, "skipped (Z0 not found)"
    if os.path.exists(Z0):
        try:
            r = subprocess.run([sys.executable, Z0], cwd=ROOT, capture_output=True,
                               text=True, timeout=180)
            z0_ok = r.returncode == 0
            tail = (r.stdout or r.stderr).strip().splitlines()
            z0_msg = tail[-1][:80] if tail else f"rc={r.returncode}"
        except Exception as e:
            z0_ok, z0_msg = False, f"Z0 error: {e}"
    ok = e2e_ok and sc_ok and z0_ok
    return ok, (f"evaluate={res['verdict']}({res['checks_passed']}/{res['checks_total']}); "
                f"scenarios[{','.join(sc_detail)}]={sc_ok}; Z0={z0_ok} ({z0_msg})")


# ----------------------------------------------------------------- controls
def n1_too_few_shots():
    with tempfile.TemporaryDirectory() as d:
        for i in range(2):
            make_png(os.path.join(d, f"s{i}.png"), 1920, 1080)
        ok, det, _ = vca.check_shots(d, CFG["min_shots"], CFG["min_bytes"], CFG["min_w"], CFG["min_h"])
    return (not ok), f"2 stills -> shots {'FAIL (fired)' if not ok else 'PASS (MISS!)'}: {det}"


def n2_low_res():
    with tempfile.TemporaryDirectory() as d:
        make_png(os.path.join(d, "ok0.png"), 1920, 1080)
        make_png(os.path.join(d, "ok1.png"), 1920, 1080)
        make_png(os.path.join(d, "small.png"), 640, 480)        # below the floor
        ok, det, _ = vca.check_shots(d, CFG["min_shots"], CFG["min_bytes"], CFG["min_w"], CFG["min_h"])
    return (not ok), f"640x480 in set -> shots {'FAIL (fired)' if not ok else 'PASS (MISS!)'}: {det}"


def n3_spin_run():
    with tempfile.TemporaryDirectory() as d:
        run = os.path.join(d, "unreal-test-run_spin")
        write_run(run, "spin")
        ok, det, data = vca.check_run_health(run)
    fired = (not ok) and data.get("verdict") == "FAIL"
    return fired, f"spin run verdict={data.get('verdict')} failed={data.get('failed_gates')} -> {'fired' if fired else 'MISS'}"


def main():
    gates = [
        ("G1", "editor_capturer_drives_highresshot", *g1_editor_script()),
        ("G2", "shots_check_accepts_fullres", *g2_shots_accept()),
        ("G3", "run_health_wired_real_pass", *g3_run_health_real()),
        ("G4", "png_size_parser", *g4_png_parser()),
        ("G5", "e2e_evaluate+scenarios+Z0", *g5_e2e()),
    ]
    controls = [
        ("N1", "too_few_shots_fails", *n1_too_few_shots()),
        ("N2", "low_res_fails", *n2_low_res()),
        ("N3", "spinning_run_fails_health", *n3_spin_run()),
    ]
    print("verify_20260630 -- demo-capture enablement (D6 stills / D7 frames)\n")
    gp = 0
    for cid, name, ok, det in gates:
        print(f"  [{'PASS' if ok else 'FAIL'}] {cid} {name}: {det}"); gp += ok
    print()
    cf = 0
    for cid, name, fired, det in controls:
        print(f"  [{'FIRED' if fired else 'MISS'}] {cid} {name}: {det}"); cf += fired
    all_ok = (gp == len(gates) and cf == len(controls))
    print(f"\n  Gates {gp}/{len(gates)}  Controls {cf}/{len(controls)}  => {'PASS' if all_ok else 'FAIL'}")
    out = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports", "wp_20260630_result.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"packet": "WP-20260630",
                   "title": "Demo-capture enablement (D6 stills / D7 frames + in-engine batch)",
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
