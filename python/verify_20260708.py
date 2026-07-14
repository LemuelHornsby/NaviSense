#!/usr/bin/env python3
"""
verify_20260708.py -- WP-20260708 acceptance gate.

KI-030 fix: the demo-readiness report-only aggregator (`demo_rehearsal._latest_run`)
must prefer the newest run that has a COMPLETE evidence pack (kpis.json), so an
interrupted newer run cannot shadow a good earlier one and flip the whole demo
preflight to a false NOT READY. This test proves the new behaviour with a synthetic
log-dir, proves the honesty fallback is preserved, and re-derives the GO verdict +
regression rc's on today's disk. Pure read/aggregate + an isolated tmp fixture --
no product / wire / C++ / schema change; touches only test tooling.

Gates:
  G1  shadow-fix  : with an OLDER complete run + a NEWER incomplete run for the same
                    scenario, _latest_run() returns the OLDER *complete* run.
  G2  honesty     : with NO complete run present, _latest_run() still returns the
                    newest dir with kpis=None (so NOT READY stays honest).
  G3  preflight   : demo_preflight_result.json verdict == GO on today's disk.
  G4  regression  : verify_20260702b + verify_20260704 both exit 0.

Negative controls (must behave as stated, else the test is not really testing):
  N1  a lone incomplete run  -> _latest_run returns (dir, None)  [not a crash]
  N2  an empty log-dir       -> _latest_run returns (None, None)
  N3  tampered kpis (bad json) counts as incomplete (skipped)
"""
import json, os, sys, glob, time, tempfile, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import demo_rehearsal as R  # the module under test

REPORTS = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports")


def _mk_run(base, scenario, stamp, with_kpis, bad_json=False):
    d = os.path.join(base, f"demo-{scenario}_{stamp}")
    os.makedirs(os.path.join(d, "evidence_pack"), exist_ok=True)
    with open(os.path.join(d, "manifest.json"), "w") as fh:
        json.dump({"runId": f"demo-{scenario}", "final": bool(with_kpis)}, fh)
    if with_kpis:
        kj = os.path.join(d, "evidence_pack", "kpis.json")
        with open(kj, "w") as fh:
            if bad_json:
                fh.write("{ this is not json ")
            else:
                json.dump({"health": {"verdict": "PASS"}}, fh)
    # stagger mtimes so 'stamp' order == mtime order
    t = time.time() + (int(stamp) if stamp.isdigit() else 0) * 1e-6
    os.utime(d, (t, t))
    return d


def g1_shadow_fix():
    with tempfile.TemporaryDirectory() as tmp:
        older_complete = _mk_run(tmp, "sc", "100", with_kpis=True)
        time.sleep(0.02)
        newer_incomplete = _mk_run(tmp, "sc", "200", with_kpis=False)
        # force newer to have a strictly larger mtime
        os.utime(newer_incomplete, None)
        run_dir, kpis = R._latest_run("sc", tmp)
        ok = (run_dir == older_complete) and (kpis is not None)
        return ok, f"picked={os.path.basename(run_dir) if run_dir else None} kpis={'yes' if kpis else 'no'} (want older complete)"


def g2_honesty():
    with tempfile.TemporaryDirectory() as tmp:
        _mk_run(tmp, "sc", "100", with_kpis=False)
        time.sleep(0.02)
        newest = _mk_run(tmp, "sc", "200", with_kpis=False)
        os.utime(newest, None)
        run_dir, kpis = R._latest_run("sc", tmp)
        ok = (run_dir == newest) and (kpis is None)
        return ok, f"picked={os.path.basename(run_dir) if run_dir else None} kpis={kpis} (want newest, None)"


def g3_preflight():
    p = os.path.join(REPORTS, "demo_preflight_result.json")
    if not os.path.isfile(p):
        return False, "demo_preflight_result.json missing"
    d = json.load(open(p))
    v = d.get("verdict")
    return v == "GO", f"verdict={v}"


def _run(mod):
    r = subprocess.run([sys.executable, os.path.join(HERE, mod)],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode


def g4_regression():
    rc_link = _run("verify_20260702b.py")
    rc_reh = _run("verify_20260704.py")
    ok = (rc_link == 0) and (rc_reh == 0)
    return ok, f"verify_20260702b rc={rc_link} verify_20260704 rc={rc_reh}"


def n1_lone_incomplete():
    with tempfile.TemporaryDirectory() as tmp:
        d = _mk_run(tmp, "sc", "100", with_kpis=False)
        run_dir, kpis = R._latest_run("sc", tmp)
        return (run_dir == d and kpis is None), f"picked={os.path.basename(run_dir) if run_dir else None} kpis={kpis}"


def n2_empty_dir():
    with tempfile.TemporaryDirectory() as tmp:
        run_dir, kpis = R._latest_run("sc", tmp)
        return (run_dir is None and kpis is None), f"({run_dir},{kpis})"


def n3_bad_json():
    with tempfile.TemporaryDirectory() as tmp:
        older_good = _mk_run(tmp, "sc", "100", with_kpis=True)
        time.sleep(0.02)
        newer_bad = _mk_run(tmp, "sc", "200", with_kpis=True, bad_json=True)
        os.utime(newer_bad, None)
        run_dir, kpis = R._latest_run("sc", tmp)
        # bad json newer run must be treated as incomplete -> pick older good
        return (run_dir == older_good and kpis is not None), f"picked={os.path.basename(run_dir) if run_dir else None}"


def main():
    gates = [("G1", "shadow-fix", g1_shadow_fix),
             ("G2", "honesty", g2_honesty),
             ("G3", "preflight GO", g3_preflight),
             ("G4", "regression", g4_regression)]
    negs = [("N1", "lone incomplete", n1_lone_incomplete),
            ("N2", "empty log-dir", n2_empty_dir),
            ("N3", "bad-json = incomplete", n3_bad_json)]

    checks, passed = [], 0
    print("=" * 60)
    print("WP-20260708 verify -- readiness aggregator shadow fix (KI-030)")
    print("=" * 60)
    for gid, name, fn in gates:
        ok, detail = fn()
        passed += bool(ok)
        checks.append({"id": gid, "name": name, "pass": bool(ok), "detail": detail})
        print(f"  [{'OK ' if ok else 'XX '}] {gid} {name:16s} {detail}")
    print("  " + "-" * 56)
    neg_ok = 0
    negs_out = []
    for nid, name, fn in negs:
        ok, detail = fn()
        neg_ok += bool(ok)
        negs_out.append({"id": nid, "name": name, "pass": bool(ok), "detail": detail})
        print(f"  [{'OK ' if ok else 'XX '}] {nid} {name:20s} {detail}")

    all_ok = (passed == len(gates)) and (neg_ok == len(negs))
    print("  " + "-" * 56)
    print(f"  gates {passed}/{len(gates)} + neg {neg_ok}/{len(negs)} -> "
          f"{'PASS' if all_ok else 'FAIL'}")
    print("=" * 60)

    out = {
        "packet": "WP-20260708",
        "date": "2026-07-08",
        "title": "Demo-readiness aggregator shadow fix (KI-030)",
        "pass": all_ok,
        "gates_passed": passed, "gates_total": len(gates),
        "neg_passed": neg_ok, "neg_total": len(negs),
        "checks": checks, "neg_controls": negs_out,
        "note": ("_latest_run now prefers the newest COMPLETE evidence-pack run so an "
                 "interrupted newer run cannot flip the demo preflight to a false NOT "
                 "READY. Test-tooling only; no product/wire/C++/schema change."),
    }
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(REPORTS, "wp_20260708_result.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"[verify] wrote {os.path.join(REPORTS, 'wp_20260708_result.json')}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
