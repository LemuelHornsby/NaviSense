#!/usr/bin/env python3
"""verify_20260714b -- regression gate for the two closeout-tooling fixes (WP_20260714B).

KI-041  verify_capture_artifacts.parse_mp4_duration_s only read the first 4 MB, so a
        non-faststart recording (moov at END -- Game Bar / Unreal editor / OBS default)
        was false-rejected -> the D7 film gate could never pass on Lemuel's real clips.
KI-042  verify_colregs.matrix() did a bare json.load, so ONE NUL-padded result file
        (D: mount, KI-038 family) crashed the whole live COLREGS matrix.

Self-contained + stdlib-only: builds synthetic MP4/JSON fixtures in a temp dir, so it
does NOT depend on the (mount-unstable) live films. Gates G1-G4 + neg-controls N1-N3.
Exit 0 = all gates pass AND all neg-controls behave; else exit 1.
Writes Saved/NaviSense_Reports/wp_20260714b_result.json.
"""
import json, os, struct, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from verify_capture_artifacts import parse_mp4_duration_s          # noqa: E402
from verify_colregs import _load_result, matrix                    # noqa: E402

REPORTS = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports")


def _box(typ: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + typ + payload


def _mvhd(timescale: int, duration: int) -> bytes:
    body = bytes([0, 0, 0, 0])                       # version 0 + flags
    body += b"\x00" * 8                              # ctime + mtime
    body += struct.pack(">I", timescale)
    body += struct.pack(">I", duration)
    body += b"\x00" * 80                             # rate..next_track_id (padding)
    return _box(b"mvhd", body)


def _ftyp() -> bytes:
    return _box(b"ftyp", b"mp42" + b"\x00\x00\x00\x00" + b"mp42")


def _write(path: str, data: bytes):
    with open(path, "wb") as f:
        f.write(data)


def run():
    checks = []

    def add(cid, name, ok, detail):
        checks.append({"id": cid, "name": name, "pass": bool(ok), "detail": detail})

    with tempfile.TemporaryDirectory() as td:
        moov = _box(b"moov", _mvhd(1000, 42000))     # 42.0 s

        # G1 -- moov-at-END (non-faststart), moov pushed beyond the 4 MB head window
        big_mdat = _box(b"mdat", b"\x00" * 4_200_000)
        p1 = os.path.join(td, "endmoov.mp4")
        _write(p1, _ftyp() + big_mdat + moov)
        d1 = parse_mp4_duration_s(p1)
        add("G1", "film_moov_at_end_parses",
            d1 is not None and abs(d1 - 42.0) < 0.5,
            f"moov-at-end clip parsed dur={d1} (expected ~42.0s) [was None pre-KI-041]")

        # G2 -- faststart (moov up front) still parses
        p2 = os.path.join(td, "faststart.mp4")
        _write(p2, _ftyp() + moov + _box(b"mdat", b"\x00" * 1000))
        d2 = parse_mp4_duration_s(p2)
        add("G2", "film_faststart_still_parses",
            d2 is not None and abs(d2 - 42.0) < 0.5,
            f"faststart clip parsed dur={d2} (expected ~42.0s)")

        # N1 -- no moov anywhere -> still correctly rejected (None)
        p3 = os.path.join(td, "nomoov.mp4")
        _write(p3, _ftyp() + _box(b"mdat", b"\x00" * 2000))
        d3 = parse_mp4_duration_s(p3)
        add("N1", "neg_no_moov_rejected", d3 is None,
            f"file with no moov -> {d3} (expected None)")

        # N2 -- stray 'mvhd' bytes inside mdat with absurd timescale -> sanity-bounded reject
        stray = b"mvhd" + bytes([0, 0, 0, 0]) + b"\x00" * 8 + b"\xff\xff\xff\xff" + b"\xff\xff\xff\xff"
        p4 = os.path.join(td, "stray.mp4")
        _write(p4, _ftyp() + _box(b"mdat", b"\x11" * 500 + stray + b"\x11" * 500))
        d4 = parse_mp4_duration_s(p4)
        add("N2", "neg_stray_mvhd_in_mdat_rejected", d4 is None,
            f"stray mvhd (absurd timescale) -> {d4} (expected None; sanity bounds hold)")

        # G3 -- colregs _load_result RECOVERS a valid-body result NUL-padded by the mount
        good = json.dumps({"pass": True, "run_dir": "x", "gates_passed": 3,
                           "gates_total": 3}).encode() + b"\x00" * 24
        p5 = os.path.join(td, "colregs_head_on_result.json")
        _write(p5, good)
        obj, note = _load_result(p5)
        add("G3", "colregs_nul_padded_recovered",
            obj is not None and obj.get("pass") is True and note is not None,
            f"NUL-padded valid result recovered (pass={obj and obj.get('pass')}, note={note!r})")

        # G4 -- matrix() does not crash when a scenario file is NUL-padded (uses the temp dir)
        for sc in ("colregs_crossing_giveway", "colregs_crossing_standon", "colregs_overtaking"):
            _write(os.path.join(td, f"{sc}_result.json"),
                   json.dumps({"pass": True, "run_dir": sc}).encode())
        crashed = False
        try:
            mres = matrix(td)
        except Exception as e:            # noqa: BLE001
            crashed = True
            mres = {"error": repr(e)}
        add("G4", "matrix_survives_padded_file",
            (not crashed) and mres.get("pass") is True,
            f"matrix() ran without crashing (pass={mres.get('pass')}) [was JSONDecodeError pre-KI-042]")

        # N3 -- a genuinely body-corrupt JSON is reported CORRUPT (None), never silently passed
        _write(os.path.join(td, "bad.json"), b'{"pass": true, "run')   # truncated body
        objb, noteb = _load_result(os.path.join(td, "bad.json"))
        add("N3", "neg_body_corrupt_flagged", objb is None,
            f"body-corrupt JSON -> obj={objb} note={noteb!r} (expected None/flagged)")

    gates = [c for c in checks if c["id"].startswith("G")]
    negs = [c for c in checks if c["id"].startswith("N")]
    gpass = sum(c["pass"] for c in gates)
    npass = sum(c["pass"] for c in negs)
    ok = all(c["pass"] for c in checks)
    result = {
        "tool": "verify_20260714b",
        "packet": "WP_20260714B",
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "theme": "closeout-tooling fixes: KI-041 film moov-at-end + KI-042 colregs matrix NUL-pad robustness",
        "auto_result": "PASS" if ok else "FAIL",
        "gates_passed": gpass, "gates_total": len(gates),
        "neg_controls_passed": npass, "neg_controls_total": len(negs),
        "checks": checks,
    }
    os.makedirs(REPORTS, exist_ok=True)
    outp = os.path.join(REPORTS, "wp_20260714b_result.json")
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"verify_20260714b -- KI-041 film parser + KI-042 colregs matrix\n")
    for c in checks:
        print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['id']} {c['name']}: {c['detail']}")
    print(f"\n  Gates {gpass}/{len(gates)} + neg-controls {npass}/{len(negs)} => "
          f"{'PASS' if ok else 'FAIL'}\n  wrote {outp}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(run())
