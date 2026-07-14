#!/usr/bin/env python3
"""verify_20260708b -- WP-20260708B gate: D7 film check (C3) + run-sheet refresh.

Proves, on isolated tmp fixtures plus today's disk:

  G1  FILM-PASS   -- a structurally valid 30 s / 6 MB MP4 in a tmp film dir is
                     ACCEPTED by check_film (duration read from mvhd).
  G2  BACK-COMPAT -- evaluate() WITHOUT film_dir emits exactly the pre-existing
                     C1(/C2) checks (no C3), and a valid stills fixture passes
                     C1 -- the existing G_CAPTURE_UE path is unchanged.
  G3  RUN-SHEET   -- PENDING_EDITOR_GATES.md is refreshed: Step 0 marked
                     CLEARED (7 Jul rebuild), Step 4 + G_FILM_UE present, and
                     the film gate command is documented.
  G4  REGRESSION  -- `preflight_demo.py --report-only` exits 0 with verdict GO
                     on today's disk, and this morning's wp_20260708_result.json
                     still reads pass=true (the KI-030 fix is intact).

Negative controls (the gate must FAIL bad film artifacts):
  N1  an undersized (100 KB) MP4 is REJECTED (byte floor).
  N2  a 5 s MP4 is REJECTED (duration floor -- a stray 2-second grab can't pass).
  N3  a 6 MB file named .mp4 with no ftyp/mvhd is REJECTED (structure check).

Writes Saved/NaviSense_Reports/wp_20260708b_result.json; exit 0 iff all pass.
Stdlib only.
"""
from __future__ import annotations
import json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "python"))
import verify_capture_artifacts as vca  # noqa: E402

OUT = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports",
                   "wp_20260708b_result.json")
RUNSHEET = os.path.join(ROOT, "Development", "work_packets", "PENDING_EDITOR_GATES.md")


# ------------------------------------------------------------------ fixtures
def make_mp4(path: str, secs: float, total_bytes: int, valid: bool = True) -> None:
    """Minimal MP4: ftyp + moov/mvhd(timescale 1000, duration secs) + mdat pad."""
    if not valid:
        with open(path, "wb") as f:
            f.write(b"\x00" * total_bytes)
        return
    ftyp = (16).to_bytes(4, "big") + b"ftypisom" + b"\x00\x00\x02\x00"
    mvhd = ((108).to_bytes(4, "big") + b"mvhd" + b"\x00" + b"\x00" * 3
            + (0).to_bytes(4, "big") + (0).to_bytes(4, "big")
            + (1000).to_bytes(4, "big") + (int(secs * 1000)).to_bytes(4, "big")
            + b"\x00" * 80)
    moov = (8 + len(mvhd)).to_bytes(4, "big") + b"moov" + mvhd
    pad = max(0, total_bytes - len(ftyp) - len(moov) - 8)
    mdat = (8 + pad).to_bytes(4, "big") + b"mdat" + b"\x00" * pad
    with open(path, "wb") as f:
        f.write(ftyp + moov + mdat)


def make_png(path: str, w: int, h: int, total_bytes: int) -> None:
    head = (vca._PNG_SIG + (13).to_bytes(4, "big") + b"IHDR"
            + w.to_bytes(4, "big") + h.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00")
    with open(path, "wb") as f:
        f.write(head + b"\x00" * max(0, total_bytes - len(head)))


# ------------------------------------------------------------------ checks
def main() -> None:
    checks, neg = [], []
    tmp = tempfile.mkdtemp(prefix="wp0708b_")
    film_dir = os.path.join(tmp, "films"); os.makedirs(film_dir)
    shots_dir = os.path.join(tmp, "shots"); os.makedirs(shots_dir)

    try:
        # G1 valid clip accepted
        make_mp4(os.path.join(film_dir, "demo_clip.mp4"), 30.0, 6_000_000)
        ok, det, data = vca.check_film(film_dir, 1, vca.DEF_MIN_FILM_BYTES,
                                       vca.DEF_MIN_FILM_SECS)
        secs = (data["examples"][0]["secs"] if data["examples"] else None)
        checks.append({"id": "G1", "name": "film-pass", "pass": bool(ok and secs == 30.0),
                       "detail": f"accepted={data['accepted']} secs={secs} ({det})"})

        # G2 back-compat: no film_dir => no C3; stills fixture passes C1
        for i in range(3):
            make_png(os.path.join(shots_dir, f"NaviSense_{i:05d}.png"),
                     3840, 2160, 60_000)
        cfg = {"min_shots": 3, "min_bytes": 50_000, "min_w": 1280, "min_h": 720}
        res = vca.evaluate(shots_dir, None, cfg, want_run_health=False)
        ids = [c["id"] for c in res["checks"]]
        ok2 = ids == ["C1"] and res["verdict"] == "PASS"
        res_f = vca.evaluate(shots_dir, None, cfg, want_run_health=False,
                             film_dir=film_dir)
        ids_f = [c["id"] for c in res_f["checks"]]
        ok2 = ok2 and ids_f == ["C1", "C3"] and res_f["verdict"] == "PASS"
        checks.append({"id": "G2", "name": "back-compat", "pass": bool(ok2),
                       "detail": f"no-film checks={ids} verdict={res['verdict']}; "
                                 f"with-film checks={ids_f} verdict={res_f['verdict']}"})

        # G3 run-sheet refreshed
        txt = open(RUNSHEET, encoding="utf-8").read()
        need = ["CLEARED 7 Jul", "Step 4", "G_FILM_UE", "--film-dir",
                "Do NOT rebuild"]
        missing = [n for n in need if n not in txt]
        checks.append({"id": "G3", "name": "run-sheet", "pass": not missing,
                       "detail": ("all markers present" if not missing
                                  else f"missing={missing}")})

        # G4 regression: preflight GO live + this morning's KI-030 gate intact
        rc = subprocess.run([sys.executable, os.path.join(ROOT, "preflight_demo.py"),
                             "--report-only"], cwd=ROOT, capture_output=True,
                            text=True, timeout=300).returncode
        go = False
        pf = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports",
                          "demo_preflight_result.json")
        if os.path.exists(pf):
            go = json.load(open(pf)).get("verdict") == "GO"
        morning = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports",
                               "wp_20260708_result.json")
        m_ok = os.path.exists(morning) and json.load(open(morning)).get("pass") is True
        checks.append({"id": "G4", "name": "regression", "pass": bool(rc == 0 and go and m_ok),
                       "detail": f"preflight rc={rc} verdict_GO={go} wp_20260708 pass={m_ok}"})

        # N1 undersized
        nd = os.path.join(tmp, "n1"); os.makedirs(nd)
        make_mp4(os.path.join(nd, "tiny.mp4"), 30.0, 100_000)
        ok, det, _ = vca.check_film(nd, 1, vca.DEF_MIN_FILM_BYTES, vca.DEF_MIN_FILM_SECS)
        neg.append({"id": "N1", "name": "undersized rejected", "pass": not ok, "detail": det})

        # N2 too short
        nd = os.path.join(tmp, "n2"); os.makedirs(nd)
        make_mp4(os.path.join(nd, "short.mp4"), 5.0, 6_000_000)
        ok, det, _ = vca.check_film(nd, 1, vca.DEF_MIN_FILM_BYTES, vca.DEF_MIN_FILM_SECS)
        neg.append({"id": "N2", "name": "short-duration rejected", "pass": not ok, "detail": det})

        # N3 invalid structure
        nd = os.path.join(tmp, "n3"); os.makedirs(nd)
        make_mp4(os.path.join(nd, "junk.mp4"), 0, 6_000_000, valid=False)
        ok, det, _ = vca.check_film(nd, 1, vca.DEF_MIN_FILM_BYTES, vca.DEF_MIN_FILM_SECS)
        neg.append({"id": "N3", "name": "invalid-structure rejected", "pass": not ok, "detail": det})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    gp = sum(1 for c in checks if c["pass"]); np_ = sum(1 for c in neg if c["pass"])
    ok_all = gp == len(checks) and np_ == len(neg)
    print("verify_20260708b -- WP-20260708B film gate + run-sheet refresh\n")
    for c in checks + neg:
        print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['id']} {c['name']}: {c['detail']}")
    print(f"\n  Gates {gp}/{len(checks)} + neg-controls {np_}/{len(neg)} "
          f"=> {'PASS' if ok_all else 'FAIL'}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"packet": "WP-20260708B", "date": "2026-07-08",
                   "title": "D7 film gate (C3) + in-engine run-sheet refresh",
                   "pass": ok_all, "gates_passed": gp, "gates_total": len(checks),
                   "neg_passed": np_, "neg_total": len(neg),
                   "checks": checks, "neg_controls": neg}, f, indent=2)
    print(f"  wrote {OUT}")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
