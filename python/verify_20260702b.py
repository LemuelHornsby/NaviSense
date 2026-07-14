#!/usr/bin/env python3
"""
verify_20260702b.py  -- WP-20260702B Pre-Rebuild Integration Audit

The single most demo-critical remaining action is ONE shared C++ rebuild that now
carries a week of stacked additive C++: the Build.cs UMG/Slate/SlateCore module
enable (WP-20260701 dashboard, a rebuild-FORCING module change), the pawn's
BlueprintPure/BlueprintCallable dashboard getters + SetHelm/SetThrottle/SetBowThruster,
the retained-traffic accessor, and three raw-JSON sensor.v1 blocks (AIS / camera /
radar) in SensorBundleComponent. If that rebuild fails at compile or link, Lemuel
loses an in-engine session and the 11-Jul demo slips.

This gate audits the WHOLE stacked surface HEADLESS (no new C++, no new rebuild risk),
so Lemuel can run the consolidated in-engine session (PENDING_EDITOR_GATES.md) once and
expect it to build first try. It complements Z0 (which checks named A1-F1 contracts +
the KI-004 truncation guard) by adding the link-failure guard Z0 does NOT do:
declaration<->definition parity for every NEW UFUNCTION, the Build.cs module change,
and sensor-block integrity.

5 gates + 3 negative controls that must FIRE (each check has teeth). Stdlib only.
Writes Saved/NaviSense_Reports/wp_20260702b_result.json ; exit 0 iff PASS.
"""
import os, re, sys, json, tempfile, shutil, subprocess

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(WS, "NaviSense_UE5", "Source", "NaviSense")
Z0  = os.path.join(WS, "Development", "work_packets",
                   "WP_20260615_COMPILE_AUDIT", "verify_compile_readiness.py")
BUILDCS = os.path.join(SRC, "NaviSense.Build.cs")
PAWN_H  = os.path.join(SRC, "Vessel", "NaviSenseShipPawn.h")
PAWN_C  = os.path.join(SRC, "Vessel", "NaviSenseShipPawn.cpp")
SBC_H   = os.path.join(SRC, "Sensors", "SensorBundleComponent.h")
SBC_C   = os.path.join(SRC, "Sensors", "SensorBundleComponent.cpp")
REPORTS = os.path.join(WS, "NaviSense_UE5", "Saved", "NaviSense_Reports")
REGRESS = ["verify_20260701.py", "verify_20260701b.py",
           "verify_20260701c.py", "verify_20260702.py", "verify_20260629b.py"]

def read(p):
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def strip_code(t):
    """Remove // and /* */ comments and string/char literals so brace/token
    scans don't trip on text inside them."""
    out, i, n = [], 0, len(t)
    while i < n:
        c = t[i]
        if c == '/' and i+1 < n and t[i+1] == '/':
            while i < n and t[i] != '\n': i += 1
        elif c == '/' and i+1 < n and t[i+1] == '*':
            i += 2
            while i+1 < n and not (t[i] == '*' and t[i+1] == '/'): i += 1
            i += 2
        elif c == '"':
            i += 1
            while i < n and t[i] != '"':
                if t[i] == '\\': i += 1
                i += 1
            i += 1
        elif c == "'":
            i += 1
            while i < n and t[i] != "'":
                if t[i] == '\\': i += 1
                i += 1
            i += 1
        else:
            out.append(c); i += 1
    return "".join(out)

def strip_comments(t):
    """Remove // and /* */ comments but KEEP string literals (module names in
    Build.cs are strings, so we must not strip them to detect them)."""
    out, i, n = [], 0, len(t)
    while i < n:
        c = t[i]
        if c == '/' and i+1 < n and t[i+1] == '/':
            while i < n and t[i] != '\n': i += 1
        elif c == '/' and i+1 < n and t[i+1] == '*':
            i += 2
            while i+1 < n and not (t[i] == '*' and t[i+1] == '/'): i += 1
            i += 2
        else:
            out.append(c); i += 1
    return "".join(out)

def brace_balanced(p):
    s = strip_code(read(p))
    return s.count("{") == s.count("}")

# ---------------------------------------------------------------- checks
def check_buildcs(path):
    """The rebuild-forcing module change is present and un-commented, and the
    bridge's existing public deps survived the edit."""
    code = strip_comments(read(path))
    priv_need = ["UMG", "Slate", "SlateCore"]
    pub_need  = ["Json", "JsonUtilities", "Sockets", "Networking"]
    missing = [m for m in priv_need + pub_need
               if not re.search(r'"%s"' % re.escape(m), code)]
    ok = not missing
    return ok, ("all module deps present (UMG/Slate/SlateCore + Json/JsonUtilities/"
                "Sockets/Networking)" if ok else "MISSING module deps: %s" % missing)

def declared_ufunctions(hpath):
    """Non-inline UFUNCTION-declared methods (end in ';', no inline body)."""
    lines = read(hpath).splitlines()
    names = []
    for i, l in enumerate(lines):
        if "UFUNCTION" not in l:
            continue
        for j in range(i+1, min(i+5, len(lines))):
            s = lines[j].strip()
            if not s or s.startswith("//"):
                continue
            m = re.search(r'([A-Za-z_]\w*)\s*\(', s)
            if m and s.endswith(";") and "{" not in s:
                names.append(m.group(1))
            break
    return names

def check_pawn_parity(hpath, cpath):
    """Every NEW non-inline UFUNCTION declared on the pawn has a definition in the
    .cpp -> the link-failure guard Z0 does not perform. Also the retained-traffic
    inline accessor the sensor blocks depend on is present."""
    cpp = read(cpath)
    decls = declared_ufunctions(hpath)
    missing = [n for n in decls
               if not re.search(r'ANaviSenseShipPawn::%s\s*\(' % re.escape(n), cpp)]
    has_traffic_acc = bool(re.search(r'GetTrafficTargets\s*\(\s*\)\s*const', read(hpath)))
    ok = (not missing) and has_traffic_acc and len(decls) >= 12
    detail = ("%d UFUNCTION decls all defined; GetTrafficTargets accessor present"
              % len(decls)) if ok else \
             ("missing defs=%s traffic_acc=%s ndecls=%d"
              % (missing, has_traffic_acc, len(decls)))
    return ok, detail

def check_sensor_blocks(cpath, hpath):
    """The three sensor.v1 blocks are wired, correctly gated, and pull from the
    pawn's retained traffic; both SBC TUs are brace-balanced; the pawn header is
    included (GetTrafficTargets resolves)."""
    cpp = read(cpath)
    ais_ok    = 'SetObjectField(TEXT("ais")' in cpp and \
                cpp.count("GetTrafficTargets()") >= 1
    cam_ok    = 'SetObjectField(TEXT("camera")' in cpp and "bEmitCamera" in cpp
    radar_ok  = 'SetObjectField(TEXT("radar")' in cpp and "bEmitRadar" in cpp
    incl_ok   = "NaviSenseShipPawn" in cpp   # include or forward + use
    braces_ok = brace_balanced(cpath) and brace_balanced(hpath)
    ok = ais_ok and cam_ok and radar_ok and incl_ok and braces_ok
    detail = ("ais=%s camera(gated)=%s radar(gated)=%s pawn_ref=%s braces=%s"
              % (ais_ok, cam_ok, radar_ok, incl_ok, braces_ok))
    return ok, detail

def run_py(script):
    p = subprocess.run([sys.executable, os.path.join(WS, "python", script)],
                       cwd=WS, capture_output=True, text=True)
    return p.returncode

# ---------------------------------------------------------------- gates
def main():
    gates, detail = {}, {}

    # G1 -- Z0 compile-readiness (the named A1-F1 contracts + KI-004 truncation guard)
    z = subprocess.run([sys.executable, Z0], cwd=WS, capture_output=True, text=True)
    g1 = (z.returncode == 0) and ("16/16" in (z.stdout + z.stderr))
    gates["G1"] = g1
    detail["G1"] = "Z0 rc=%d 16/16=%s" % (z.returncode, "16/16" in (z.stdout+z.stderr))

    # G2 -- Build.cs module integrity (the rebuild-forcing change)
    g2, d2 = check_buildcs(BUILDCS); gates["G2"] = g2; detail["G2"] = d2

    # G3 -- pawn UFUNCTION decl<->def parity (link-failure guard)
    g3, d3 = check_pawn_parity(PAWN_H, PAWN_C); gates["G3"] = g3; detail["G3"] = d3

    # G4 -- sensor.v1 block integrity (AIS/camera/radar)
    g4, d4 = check_sensor_blocks(SBC_C, SBC_H); gates["G4"] = g4; detail["G4"] = d4

    # G5 -- regression: every stacked packet's own verify still passes
    rcs = {s: run_py(s) for s in REGRESS}
    g5 = all(v == 0 for v in rcs.values())
    gates["G5"] = g5
    detail["G5"] = "regression rc: " + ", ".join("%s=%d" % (k, v) for k, v in rcs.items())

    # -------------------------------------------------- negative controls
    controls, cdetail = {}, {}
    tmp = tempfile.mkdtemp(prefix="wp702b_")
    try:
        # N1 -- comment out the UMG dep => G2 must FAIL
        b = os.path.join(tmp, "Build.cs")
        shutil.copy(BUILDCS, b)
        t = read(b).replace('"UMG"', '// "UMG"', 1)
        open(b, "w", encoding="utf-8").write(t)
        n1_ok, _ = check_buildcs(b)
        controls["N1"] = (n1_ok is False)
        cdetail["N1"] = "commented-out UMG dep detected=%s" % (not n1_ok)

        # N2 -- add a declared-but-undefined UFUNCTION => G3 must FAIL
        h = os.path.join(tmp, "Pawn.h")
        shutil.copy(PAWN_H, h)
        ht = read(h).replace(
            "double GetHeadingDeg() const;",
            "double GetHeadingDeg() const;\n"
            "    UFUNCTION(BlueprintPure)\n"
            "    double GetBogusUndefinedXYZ() const;", 1)
        open(h, "w", encoding="utf-8").write(ht)
        n2_ok, _ = check_pawn_parity(h, PAWN_C)
        controls["N2"] = (n2_ok is False)
        cdetail["N2"] = "undefined UFUNCTION (link failure) detected=%s" % (not n2_ok)

        # N3 -- drop the radar block => G4 must FAIL
        c = os.path.join(tmp, "SBC.cpp")
        shutil.copy(SBC_C, c)
        ct = re.sub(r'Sensors->SetObjectField\(TEXT\("radar"\)[^;]*;', "", read(c))
        open(c, "w", encoding="utf-8").write(ct)
        n3_ok, _ = check_sensor_blocks(c, SBC_H)
        controls["N3"] = (n3_ok is False)
        cdetail["N3"] = "removed radar block detected=%s" % (not n3_ok)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    gp = sum(1 for v in gates.values() if v)
    cf = sum(1 for v in controls.values() if v)
    verdict = "PASS" if (gp == len(gates) and cf == len(controls)) else "FAIL"

    result = {
        "packet": "WP-20260702B",
        "title": "Pre-rebuild integration audit + consolidated in-engine gate runbook",
        "scope": ("headless audit of the stacked C++ awaiting the single shared rebuild; "
                  "no new C++, no new rebuild risk"),
        "gates": gates, "gates_detail": detail,
        "controls_fired": controls, "controls_detail": cdetail,
        "gates_passed": gp, "gates_total": len(gates),
        "controls_fired_n": cf, "controls_total": len(controls),
        "verdict": verdict,
    }
    os.makedirs(REPORTS, exist_ok=True)
    outp = os.path.join(REPORTS, "wp_20260702b_result.json")
    with open(outp, "w") as f:
        json.dump(result, f, indent=2)

    for g in sorted(gates):     print("%s %s :: %s" % ("PASS" if gates[g] else "FAIL", g, detail[g]))
    for cN in sorted(controls): print("%s %s :: %s" % ("FIRED" if controls[cN] else "MISS", cN, cdetail[cN]))
    print("\n%s  %d/%d gates + %d/%d controls -> %s" %
          (verdict, gp, len(gates), cf, len(controls), outp))
    sys.exit(0 if verdict == "PASS" else 1)

if __name__ == "__main__":
    main()
