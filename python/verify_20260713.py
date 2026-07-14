"""verify_20260713.py - WP_20260713 gate: evidence-pack P0 view-completeness.

Proves build_evidence_pack.py now refuses to bake demo evidence from a
partial/stale view of a FINAL run (KI-038: the 12-Jul live pack was silently
built from 11,117 of 23,393 rows because the sandbox mount served a frozen
mid-run snapshot of state.csv).

Gates (TC-51):
  G1  pack module compiles + exposes PartialViewError/_view_completeness
  G2  complete fixture (rows == manifest stateRows)  -> pack builds, view_complete=true
  G3  partial fixture (60% of stateRows, final:true) -> pack REFUSES (exit 3, KI-038 msg,
      no evidence_pack/ written)
  G4  same partial fixture + --allow-partial         -> builds, watermarked PARTIAL VIEW,
      kpis view_complete=false
  G5  TRUNCATED manifest.json (invalid JSON)         -> pack REFUSES (exit 3, KI-038 msg)
      [the loophole caught LIVE on 13 Jul: vrk._load_manifest forgives bad JSON -> {}
       -> the row gate silently skipped; a broken manifest is itself a broken view]
  G6  truncated manifest + --allow-partial           -> builds, watermarked, view_complete=false
Neg-controls (gate must NOT overfire):
  N1  final:false (genuinely mid-run) + short rows   -> builds normally
  N2  final:true but no stateRows key                -> builds normally (gate skipped)
INFO (non-gating): P0 verdict of THIS machine's view of the real 12-Jul live run.

Writes NaviSense_UE5/Saved/NaviSense_Reports/wp_20260713_result.json
Exit 0 only if all 4 gates pass and both neg-controls hold.
"""
import csv, datetime, json, os, shutil, subprocess, sys, tempfile, time

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
PACK = os.path.join(_HERE, "build_evidence_pack.py")
REAL_RUN = os.path.join(ROOT, "logs", "demo-monaco_capture_20260712_125800")
OUT = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports",
                   "wp_20260713_result.json")
N_ROWS = 3000  # fixture size (rows of real transit data)


def _fixture(tmp, name, declared_rows, final=True, include_key=True):
    """Run-dir fixture: first N_ROWS of the real state.csv + a minimal manifest."""
    d = os.path.join(tmp, name)
    os.makedirs(d)
    src = os.path.join(REAL_RUN, "state.csv")
    with open(src, newline="", encoding="utf-8") as f_in, \
         open(os.path.join(d, "state.csv"), "w", newline="", encoding="utf-8") as f_out:
        for i, line in enumerate(f_in):
            if i > N_ROWS:
                break
            f_out.write(line)
    man = {"runId": name, "controllerKind": "transit", "tickHz": 30.0,
           "plantKind": "mmg", "seaState": 2, "final": final,
           "startedAtLocal": "2026-07-13 fixture"}
    if include_key:
        man["stateRows"] = declared_rows
    with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f)
    return d


def _build(run_dir, extra=()):
    cmd = [sys.executable, PACK, "--run-dir", run_dir, "--no-plot", "--no-html",
           *extra]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=300)
    return r


def main():
    gates, negs = {}, {}
    t0 = time.time()

    # G1 - compiles + gate surface exists
    import py_compile
    try:
        py_compile.compile(PACK, doraise=True)
        sys.path.insert(0, _HERE)
        import build_evidence_pack as bep
        ok = hasattr(bep, "PartialViewError") and hasattr(bep, "_view_completeness")
        s = bep._view_completeness([{}] * 50, {"final": True, "stateRows": 100})
        ok = ok and s["complete"] is False and "PARTIAL" in s["note"]
        gates["G1_compile_and_gate_surface"] = "PASS" if ok else "FAIL"
    except Exception as e:
        gates["G1_compile_and_gate_surface"] = f"FAIL ({type(e).__name__}: {e})"

    tmp = tempfile.mkdtemp(prefix="wp20260713_")
    try:
        # G2 - complete view builds
        d = _fixture(tmp, "fix_complete", N_ROWS)
        r = _build(d)
        ok = r.returncode == 0
        if ok:
            k = json.load(open(os.path.join(d, "evidence_pack", "kpis.json"),
                               encoding="utf-8"))
            ok = k["meta"]["view_complete"] is True and \
                 k["meta"]["state_rows_read"] == N_ROWS
        gates["G2_complete_view_builds"] = "PASS" if ok else \
            f"FAIL (rc={r.returncode} {r.stderr.strip()[:120]})"

        # G3 - partial view refused, nothing written
        d = _fixture(tmp, "fix_partial", N_ROWS * 5 // 3)  # 60% visible
        r = _build(d)
        ok = (r.returncode == 3 and "KI-038" in (r.stderr + r.stdout)
              and not os.path.exists(os.path.join(d, "evidence_pack")))
        gates["G3_partial_view_refused_exit3"] = "PASS" if ok else \
            f"FAIL (rc={r.returncode}, pack_written={os.path.exists(os.path.join(d, 'evidence_pack'))})"

        # G4 - --allow-partial builds a watermarked forensic pack
        r = _build(d, extra=("--allow-partial",))
        ok = r.returncode == 0
        if ok:
            k = json.load(open(os.path.join(d, "evidence_pack", "kpis.json"),
                               encoding="utf-8"))
            md = open(os.path.join(d, "evidence_pack", "EVIDENCE.md"),
                      encoding="utf-8").read()
            ok = k["meta"]["view_complete"] is False and "PARTIAL VIEW" in md
        gates["G4_allow_partial_watermarked"] = "PASS" if ok else \
            f"FAIL (rc={r.returncode} {r.stderr.strip()[:120]})"

        # N1 - final:false must NOT trip the gate (mid-run forensics stay legal)
        d = _fixture(tmp, "fix_midrun", N_ROWS * 5 // 3, final=False)
        r = _build(d)
        negs["N1_midrun_not_refused"] = "HELD" if r.returncode == 0 else \
            f"OVERFIRED (rc={r.returncode})"

        # N2 - missing stateRows must NOT trip the gate
        d = _fixture(tmp, "fix_nokey", 0, final=True, include_key=False)
        r = _build(d)
        ok = r.returncode == 0
        if ok:
            k = json.load(open(os.path.join(d, "evidence_pack", "kpis.json"),
                               encoding="utf-8"))
            ok = "gate skipped" in k["meta"]["view_note"]
        negs["N2_no_staterows_not_refused"] = "HELD" if ok else \
            f"OVERFIRED (rc={r.returncode})"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

        # G5/G6 - truncated manifest.json (the live 13-Jul loophole)
        d = _fixture(tmp, "fix_badman", N_ROWS)
        mp = os.path.join(d, "manifest.json")
        blob = open(mp, "rb").read()
        open(mp, "wb").write(blob[: int(len(blob) * 0.6)])  # cut mid-token
        r = _build(d)
        ok = (r.returncode == 3 and "KI-038" in (r.stderr + r.stdout)
              and not os.path.exists(os.path.join(d, "evidence_pack")))
        gates["G5_truncated_manifest_refused"] = "PASS" if ok else             f"FAIL (rc={r.returncode})"
        r = _build(d, extra=("--allow-partial",))
        ok = r.returncode == 0
        if ok:
            k = json.load(open(os.path.join(d, "evidence_pack", "kpis.json"),
                               encoding="utf-8"))
            ok = k["meta"]["view_complete"] is False and                  "manifest" in k["meta"]["view_note"]
        gates["G6_truncated_manifest_allow_partial"] = "PASS" if ok else             f"FAIL (rc={r.returncode})"

    # INFO - what does THIS machine see of the real 12-Jul live run?
    # Probe a COPY: the probe must never write into the real run dir.
    info = "real run dir not found"
    if os.path.isdir(REAL_RUN):
        probe = tempfile.mkdtemp(prefix="wp20260713_probe_")
        d = os.path.join(probe, "probe_125800")
        os.makedirs(d)
        for fn in ("state.csv", "manifest.json"):
            sp = os.path.join(REAL_RUN, fn)
            if os.path.exists(sp):
                shutil.copyfile(sp, os.path.join(d, fn))
        r = _build(d)  # refused (exit 3) => this machine has a partial view
        shutil.rmtree(probe, ignore_errors=True)
        if r.returncode == 3:
            info = ("THIS MACHINE SEES A PARTIAL VIEW of run 125800 - P0 gate "
                    "correctly refused (KI-038 live catch). Rebuild the pack on "
                    "Windows, where verify_run_kinematics saw all 23,393 rows.")
        elif r.returncode == 0:
            info = ("full view visible here - pack rebuilt clean on run 125800 "
                    "(this is the Windows/full-view outcome)")
        else:
            info = f"unexpected rc={r.returncode}: {r.stderr.strip()[:160]}"

    ok_all = all(v == "PASS" for v in gates.values()) and \
             all(v == "HELD" for v in negs.values())
    res = {"packet": "WP_20260713", "tc": "TC-51",
           "generated": datetime.datetime.now().isoformat(timespec="seconds"),
           "elapsed_s": round(time.time() - t0, 1),
           "gates": gates, "neg_controls": negs,
           "info_probe_real_run_125800": info,
           "verdict": "PASS" if ok_all else "FAIL",
           "note": "P0 view-completeness + manifest-integrity gate on build_evidence_pack.py "
                   "(KI-038). Fixtures = first 3,000 rows of the real 12-Jul "
                   "live run; real evidence_pack/ on disk is never touched."}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
