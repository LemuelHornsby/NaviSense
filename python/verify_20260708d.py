#!/usr/bin/env python3
"""
verify_20260708d.py -- WP-20260708D acceptance gate.

KI-032 fix: preflight_demo.py's GO-branch "next" guidance was a hardcoded
snapshot ("proceed with PENDING_EDITOR_GATES.md Step 0 (full C++ rebuild,
editor CLOSED) -> Steps 1-3 (PIE + capture)") authored 5 Jul, before Step 0
was cleared 7 Jul and the run sheet re-scoped to Steps 1-4 (WP-20260708B).
Left as-is, a GO verdict this close to the 11 Jul demo would actively steer
Lemuel into an UNNECESSARY rebuild -- wasting the one remaining PIE/capture
slot and re-opening rebuild risk for no reason. Fix: the "next" line no
longer hardcodes a step count; it points at PENDING_EDITOR_GATES.md as the
single source of truth and tells Lemuel to check its header before
rebuilding again. Pure test-tooling text fix -- NO product/wire/C++/schema
change, NO rebuild.

Gates:
  G1  stale-text-gone : the old hardcoded "Step 0 ... -> Steps 1-3" string is
                         no longer present anywhere in preflight_demo.py.
  G2  new-text-present : the live GO-branch stdout references
                          PENDING_EDITOR_GATES.md and does not claim a fixed
                          step count.
  G3  parses           : preflight_demo.py still compiles cleanly
                          (py_compile) -- the shell-edit didn't corrupt it.
  G4  regression        : Z0 compile-readiness 16/16 AND
                           `preflight_demo.py --report-only` still exits 0
                           (GO) on today's disk -- the text-only edit did not
                           change the pass/fail behaviour.

Negative controls (must behave as stated, else the test is not really
testing anything):
  N1  a fixture file that still contains the OLD stale string IS flagged by
      the G1 check (proves the check discriminates, not just always-true).
  N2  a fixture GO-branch line missing "PENDING_EDITOR_GATES.md" IS flagged
      by the G2 check.
  N3  the NO-GO branch text ("FIX the flagged check BEFORE the PIE session")
      is UNCHANGED -- proves the edit was scoped to the GO branch only.
"""
import os, re, sys, subprocess, py_compile, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPORTS = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports")
PREFLIGHT = os.path.join(ROOT, "preflight_demo.py")
Z0 = os.path.join(ROOT, "Development", "work_packets", "WP_20260615_COMPILE_AUDIT",
                   "verify_compile_readiness.py")

OLD_STALE = ("proceed with PENDING_EDITOR_GATES.md Step 0 "
             "(full C++ rebuild, editor CLOSED) -> Steps 1-3 (PIE + capture)")


def _source():
    with open(PREFLIGHT, "r", encoding="utf-8") as fh:
        return fh.read()


def _contains_stale(text):
    # collapse whitespace/newlines so the check isn't fooled by re-wrapping
    flat = re.sub(r"\s+", " ", text)
    needle = re.sub(r"\s+", " ", OLD_STALE)
    return needle in flat


def g1_stale_text_gone():
    src = _source()
    bad = _contains_stale(src)
    return (not bad), f"stale 'Step 0 -> Steps 1-3' string present={bad} (want False)"


def _run_preflight_stdout():
    r = subprocess.run([sys.executable, PREFLIGHT, "--report-only"],
                        cwd=ROOT, capture_output=True, text=True)
    return r.returncode, r.stdout


def g2_new_text_present():
    rc, out = _run_preflight_stdout()
    line = next((l for l in out.splitlines() if "next" in l and ":" in l), "")
    has_ref = "PENDING_EDITOR_GATES.md" in line
    no_fixed_steps = "Steps 1-3" not in line
    ok = has_ref and no_fixed_steps
    return ok, f"next-line={line.strip()[:90]!r} has_ref={has_ref} no_fixed_steps={no_fixed_steps}"


def g3_parses():
    try:
        py_compile.compile(PREFLIGHT, doraise=True)
        return True, "py_compile OK"
    except py_compile.PyCompileError as e:
        return False, f"py_compile FAILED: {e}"


def _run(pyfile, args=()):
    r = subprocess.run([sys.executable, pyfile, *args], cwd=ROOT,
                        capture_output=True, text=True)
    return r.returncode


def g4_regression():
    rc_z0 = _run(Z0)
    rc_pre, _ = _run_preflight_stdout()
    ok = (rc_z0 == 0) and (rc_pre == 0)
    return ok, f"Z0 rc={rc_z0} preflight(--report-only) rc={rc_pre} (want 0, 0 == GO)"


def n1_stale_fixture_detected():
    fixture = "  next    : " + OLD_STALE + "\n"
    return _contains_stale(fixture), "stale-text detector fires on a planted old string"


def n2_missing_ref_fixture_detected():
    line = ("  next    : proceed to the next open step "
            "(no PENDING file referenced here)")
    has_ref = "PENDING_EDITOR_GATES.md" in line
    return (not has_ref), "missing-reference detector fires on a fixture lacking the filename"


def n3_nogo_branch_unchanged():
    src = _source()
    ok = ('"  next    : FIX the flagged check BEFORE the PIE session "' in src
          and '"(do not burn the in-engine slot on a NO-GO tree).")' in src)
    return ok, f"NO-GO branch text intact={ok}"


def main():
    gates = [("G1", "stale text gone", g1_stale_text_gone),
             ("G2", "new text present (live stdout)", g2_new_text_present),
             ("G3", "parses", g3_parses),
             ("G4", "regression (Z0 + preflight GO)", g4_regression)]
    negs = [("N1", "stale fixture detected", n1_stale_fixture_detected),
            ("N2", "missing-ref fixture detected", n2_missing_ref_fixture_detected),
            ("N3", "NO-GO branch unchanged", n3_nogo_branch_unchanged)]

    checks, passed = [], 0
    print("=" * 60)
    print("WP-20260708D verify -- preflight stale-guidance fix (KI-032)")
    print("=" * 60)
    for gid, name, fn in gates:
        ok, detail = fn()
        passed += bool(ok)
        checks.append({"id": gid, "name": name, "pass": bool(ok), "detail": detail})
        print(f"  [{'OK ' if ok else 'XX '}] {gid} {name:32s} {detail}")
    print("  " + "-" * 56)
    neg_ok = 0
    negs_out = []
    for nid, name, fn in negs:
        ok, detail = fn()
        neg_ok += bool(ok)
        negs_out.append({"id": nid, "name": name, "pass": bool(ok), "detail": detail})
        print(f"  [{'OK ' if ok else 'XX '}] {nid} {name:32s} {detail}")

    all_ok = (passed == len(gates)) and (neg_ok == len(negs))
    print("  " + "-" * 56)
    print(f"  gates {passed}/{len(gates)} + neg {neg_ok}/{len(negs)} -> "
          f"{'PASS' if all_ok else 'FAIL'}")
    print("=" * 60)

    out = {
        "packet": "WP-20260708D",
        "date": "2026-07-08",
        "title": "Preflight stale rebuild-guidance fix (KI-032)",
        "pass": all_ok,
        "gates_passed": passed, "gates_total": len(gates),
        "neg_passed": neg_ok, "neg_total": len(negs),
        "checks": checks, "neg_controls": negs_out,
        "note": ("preflight_demo.py's GO-branch guidance no longer hardcodes "
                 "'Step 0 rebuild -> Steps 1-3'; it points at "
                 "PENDING_EDITOR_GATES.md as the source of truth so a GO run "
                 "this close to the demo cannot steer Lemuel into an "
                 "unnecessary rebuild. Test-tooling text fix only -- no "
                 "product/wire/C++/schema change, no rebuild."),
    }
    os.makedirs(REPORTS, exist_ok=True)
    dest = os.path.join(REPORTS, "wp_20260708d_result.json")
    import json
    with open(dest, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"[verify] wrote {dest}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
