#!/usr/bin/env python3
"""Acceptance gates for WP-20260709D (one-command demo-session closeout).

Gates
  G1 tool-parses   verify_demo_session.py compiles; --help rc 0 and names all
                   three sections + --film-dir/--skip.
  G2 partial-pass  --skip sensors,capture -> rc 0; result JSON pass=true,
                   colregs section PASS, skipped list recorded honestly.
  G3 fail-propagates  empty tmp --film-dir with --skip sensors,colregs ->
                   rc 1; result JSON gates_failed includes G_FILM_UE +
                   G_CAPTURE_UE (a sub-tool FAIL can never be masked).
  G4 regression    verify_20260709c rc 0.
Neg controls
  N1 all sections skipped -> rejected rc 2.
  N2 unknown --skip token -> rejected rc 2.
  N3 nonexistent --film-dir -> rejected rc 2 (no sections even run).

Writes Saved/NaviSense_Reports/wp_20260709d_result.json. Stdlib only.
"""
import json, os, py_compile, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOL = os.path.join(HERE, "verify_demo_session.py")
REPORTS = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports")
OUT = os.path.join(REPORTS, "wp_20260709d_result.json")
PY = sys.executable


def run(args, **kw):
    return subprocess.run([PY] + args, cwd=ROOT, capture_output=True,
                          text=True, timeout=600, **kw)


def main():
    checks, negs = [], []

    # G1
    try:
        py_compile.compile(TOOL, doraise=True)
        h = run([TOOL, "--help"])
        ok = (h.returncode == 0 and all(k in h.stdout for k in
              ("sensors", "capture", "colregs", "--film-dir", "--skip")))
        detail = f"help rc={h.returncode}; sections+flags documented={ok}"
    except Exception as e:
        ok, detail = False, f"compile failed: {e}"
    checks.append({"id": "G1", "name": "tool-parses", "pass": ok, "detail": detail})

    # G2
    j2 = os.path.join(tempfile.mkdtemp(), "r2.json")
    p2 = run([TOOL, "--skip", "sensors,capture", "--json-out", j2])
    try:
        r2 = json.load(open(j2))
        ok = (p2.returncode == 0 and r2["pass"] is True
              and r2["sections"][0]["section"] == "colregs"
              and r2["sections"][0]["pass"] is True
              and sorted(r2["skipped"]) == ["capture", "sensors"])
        detail = f"rc=0, colregs PASS, skipped recorded={r2['skipped']}"
    except Exception as e:
        ok, detail = False, f"rc={p2.returncode}; parse: {e}"
    checks.append({"id": "G2", "name": "partial-pass", "pass": ok, "detail": detail})

    # G3
    empty = tempfile.mkdtemp()
    j3 = os.path.join(tempfile.mkdtemp(), "r3.json")
    p3 = run([TOOL, "--skip", "sensors,colregs", "--film-dir", empty,
              "--json-out", j3])
    try:
        r3 = json.load(open(j3))
        ok = (p3.returncode == 1 and r3["pass"] is False
              and "G_FILM_UE" in r3["gates_failed"]
              and "G_CAPTURE_UE" in r3["gates_failed"])
        detail = f"rc=1, gates_failed={r3['gates_failed']}"
    except Exception as e:
        ok, detail = False, f"rc={p3.returncode}; parse: {e}"
    checks.append({"id": "G3", "name": "fail-propagates", "pass": ok, "detail": detail})

    # G4
    p4 = run([os.path.join(HERE, "verify_20260709c.py")])
    checks.append({"id": "G4", "name": "regression", "pass": p4.returncode == 0,
                   "detail": f"verify_20260709c rc={p4.returncode}"})

    # Negs
    n1 = run([TOOL, "--skip", "sensors,capture,colregs"])
    negs.append({"id": "N1", "name": "all-skip rejected", "pass": n1.returncode == 2,
                 "detail": f"rc={n1.returncode}"})
    n2 = run([TOOL, "--skip", "bogus"])
    negs.append({"id": "N2", "name": "unknown skip rejected", "pass": n2.returncode == 2,
                 "detail": f"rc={n2.returncode}"})
    n3 = run([TOOL, "--film-dir", os.path.join(empty, "does_not_exist"),
              "--skip", "sensors,colregs"])
    negs.append({"id": "N3", "name": "missing film-dir rejected", "pass": n3.returncode == 2,
                 "detail": f"rc={n3.returncode}"})

    all_pass = all(c["pass"] for c in checks) and all(n["pass"] for n in negs)
    result = {"packet": "WP-20260709D", "date": time.strftime("%Y-%m-%d"),
              "title": "one-command demo-session closeout (verify_demo_session.py)",
              "pass": all_pass,
              "gates_passed": sum(c["pass"] for c in checks),
              "gates_total": len(checks),
              "neg_passed": sum(n["pass"] for n in negs),
              "neg_total": len(negs),
              "checks": checks, "neg_controls": negs}
    os.makedirs(REPORTS, exist_ok=True)
    json.dump(result, open(OUT, "w", encoding="utf-8"), indent=2)
    for c in checks + negs:
        print(f"[{c['id']}] {'PASS' if c['pass'] else 'FAIL'} {c['name']}: {c['detail']}")
    print(f"WP-20260709D {'PASS' if all_pass else 'FAIL'} -> {OUT}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
