#!/usr/bin/env python3
"""verify_capture_artifacts -- objective D6/D7 capture gate (reusable, headless).

After an in-engine capture session this turns "did we actually get the demo
shots?" into an exit-0/1 gate the nightly / demo-day rehearsal can run, so a
beauty still is never accepted over a broken run:

  C1  SHOTS  -- >= --min-shots PNG stills exist under --shots-dir, each at least
      --min-bytes bytes AND at least --min-width x --min-height pixels (parsed
      straight from the PNG IHDR header; stdlib only, no Pillow). A failed /
      blank HighResShot is a tiny file, and a low-res grab is not a beauty shot,
      so both are rejected. Optional --since-epoch ignores stills older than the
      capture session (so stale shots can't pass the gate).

  C2  RUN HEALTH -- the demo run named by --run-dir (or --latest) passes the
      kinematic-health gate (verify_run_kinematics.analyse_run_dir -> verdict
      PASS). A pretty frame over a spinning / NaN run is not demo evidence.

  C3  FILM (optional, WP-20260708B) -- only when --film-dir is given: >=
      --min-films video clips (.mp4/.m4v/.mov/.mkv/.avi) exist under --film-dir,
      each at least --min-film-bytes bytes, structurally valid (MP4/MOV: `ftyp`
      header + duration read from the `mvhd` box; MKV: EBML magic; AVI: RIFF),
      and (MP4/MOV) at least --min-film-secs long. --since-epoch applies, so a
      stale screen-grab can't pass a fresh session's gate. This is the D7
      soft-launch film gate (a screen-recorded PIE clip, e.g. Win+Alt+R Game
      Bar / OBS -- honesty: NOT an MRQ cinematic render; MRQ stays the D7
      polish path).

PASS iff every requested check passes. Writes a result JSON (default
NaviSense_UE5/Saved/NaviSense_Reports/capture_artifacts_result.json) and exits 0
iff PASS. Pure stdlib (the D8 repro_doctor can call it before `pip install`).

Examples
  # after a monaco_capture capture session (shots + the run that produced them)
  python python/verify_capture_artifacts.py --latest
  # explicit run + a custom shots folder + a 4K floor
  python python/verify_capture_artifacts.py --run-dir logs/<run> \
      --shots-dir "NaviSense_UE5/Saved/Screenshots/WindowsEditor" \
      --min-width 1920 --min-height 1080
  # shots-only (no run health, e.g. checking a film still set)
  python python/verify_capture_artifacts.py --shots-dir <dir> --no-run-health
  # stills + run health + the D7 soft-launch film clip (G_FILM_UE)
  python python/verify_capture_artifacts.py --latest \
      --film-dir "C:/Users/<you>/Videos/Captures"
"""
from __future__ import annotations
import argparse, glob, json, os, sys
from typing import List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "python"))

# Defaults (a demo beauty still: HD floor, real 4K HighResShot PNGs are MBs).
DEF_MIN_SHOTS = 3
DEF_MIN_BYTES = 50_000          # a failed/blank capture is a few KB
DEF_MIN_WIDTH = 1280
DEF_MIN_HEIGHT = 720
DEF_SHOTS_DIR = os.path.join(ROOT, "NaviSense_UE5", "Saved", "Screenshots", "WindowsEditor")
DEF_LOG_ROOT = os.path.join(ROOT, "logs")
DEF_OUT = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports",
                       "capture_artifacts_result.json")
_PNG_SIG = b"\x89PNG\r\n\x1a\n"


# --------------------------------------------------------------- PNG size
def parse_png_size(path: str) -> Optional[Tuple[int, int]]:
    """Return (width, height) read from a PNG's IHDR, or None if not a valid PNG.
    Stdlib only: the first chunk of a PNG is always IHDR and holds w/h as two
    big-endian uint32 at bytes 16..24."""
    try:
        with open(path, "rb") as f:
            head = f.read(24)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != _PNG_SIG or head[12:16] != b"IHDR":
        return None
    w = int.from_bytes(head[16:20], "big")
    h = int.from_bytes(head[20:24], "big")
    if w <= 0 or h <= 0:
        return None
    return (w, h)


def find_shots(shots_dir: str, since_epoch: Optional[float] = None) -> List[str]:
    """All *.png/*.PNG under shots_dir (non-recursive + one level deep), newest
    first, optionally filtered to files modified at/after since_epoch."""
    pats = ("*.png", "*.PNG", os.path.join("*", "*.png"), os.path.join("*", "*.PNG"))
    out: List[str] = []
    for p in pats:
        out.extend(glob.glob(os.path.join(shots_dir, p)))
    out = sorted(set(out), key=lambda p: os.path.getmtime(p), reverse=True)
    if since_epoch is not None:
        out = [p for p in out if os.path.getmtime(p) >= since_epoch - 1.0]
    return out


# --------------------------------------------------------------- video (C3)
_VIDEO_EXTS = (".mp4", ".m4v", ".mov", ".mkv", ".avi")
_EBML_SIG = b"\x1aE\xdf\xa3"
DEF_MIN_FILMS = 1
DEF_MIN_FILM_BYTES = 5_000_000       # a real 1080p clip of ~1 min is tens of MB
DEF_MIN_FILM_SECS = 20.0             # soft-launch clip floor (target 60-90 s)


def _mvhd_duration_s(buf: bytes, i: int) -> Optional[float]:
    """Parse an `mvhd` box at index i in buf -> duration (s), sanity-bounded."""
    if i < 0 or i + 36 > len(buf):
        return None
    ver = buf[i + 4]
    if ver == 1:
        ts = int.from_bytes(buf[i + 24:i + 28], "big")
        dur = int.from_bytes(buf[i + 28:i + 36], "big")
    else:
        ts = int.from_bytes(buf[i + 16:i + 20], "big")
        dur = int.from_bytes(buf[i + 20:i + 24], "big")
    if ts <= 0 or dur <= 0:
        return None
    secs = dur / ts
    # sane timescale (1..6e6) + 0.1 s .. 12 h guards a stray 'mvhd' match inside mdat
    if not (1 <= ts <= 6_000_000) or not (0.1 <= secs <= 43_200.0):
        return None
    return secs


def parse_mp4_duration_s(path: str) -> Optional[float]:
    """Duration in seconds from an MP4/MOV `mvhd` box, or None if not parseable.
    Reads the head (faststart clips) and, if the `moov` is at the END of the file
    (Game Bar / Unreal editor / OBS recorders are non-faststart by default), the tail -
    so a large, valid non-faststart recording parses without reading the whole file
    (KI-041: the old head-only 4 MB read false-rejected every moov-at-end clip). Stdlib
    only: `mvhd` is version(1)+flags(3), then v0: ctime4 mtime4 timescale4 duration4 /
    v1: ctime8 mtime8 timescale4 duration8 (big-endian)."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            head = f.read(4_000_000 if size > 4_000_000 else size)
            if len(head) < 16 or head[4:8] != b"ftyp":
                return None
            d = _mvhd_duration_s(head, head.find(b"mvhd"))       # 1) faststart: moov up front
            if d is not None:
                return d
            tail_len = 20_000_000 if size > 20_000_000 else size  # 2) moov at end (non-faststart)
            f.seek(size - tail_len)
            tail = f.read(tail_len)
            return _mvhd_duration_s(tail, tail.rfind(b"mvhd"))
    except OSError:
        return None


def find_films(film_dir: str, since_epoch: Optional[float] = None) -> List[str]:
    """All video files under film_dir (non-recursive + one level deep), newest
    first, optionally filtered to files modified at/after since_epoch."""
    out: List[str] = []
    for ext in _VIDEO_EXTS:
        for pat in ("*" + ext, "*" + ext.upper(),
                    os.path.join("*", "*" + ext), os.path.join("*", "*" + ext.upper())):
            out.extend(glob.glob(os.path.join(film_dir, pat)))
    out = sorted(set(out), key=lambda p: os.path.getmtime(p), reverse=True)
    if since_epoch is not None:
        out = [p for p in out if os.path.getmtime(p) >= since_epoch - 1.0]
    return out


def check_film(film_dir: str, min_films: int, min_bytes: int, min_secs: float,
               since_epoch: Optional[float] = None) -> Tuple[bool, str, dict]:
    files = find_films(film_dir, since_epoch)
    good, rejected = [], []
    for p in files:
        name = os.path.basename(p)
        try:
            nbytes = os.path.getsize(p)
        except OSError:
            rejected.append((name, "unreadable")); continue
        if nbytes < min_bytes:
            rejected.append((name, f"{nbytes}B < {min_bytes}B")); continue
        ext = os.path.splitext(p)[1].lower()
        dur: Optional[float] = None
        if ext in (".mp4", ".m4v", ".mov"):
            dur = parse_mp4_duration_s(p)
            if dur is None:
                rejected.append((name, "not a valid MP4/MOV (ftyp/mvhd)")); continue
            if dur < min_secs:
                rejected.append((name, f"{dur:.1f}s < {min_secs:.0f}s")); continue
        elif ext == ".mkv":
            try:
                with open(p, "rb") as f:
                    magic = f.read(4)
            except OSError:
                rejected.append((name, "unreadable")); continue
            if magic != _EBML_SIG:
                rejected.append((name, "not a valid MKV (EBML)")); continue
        elif ext == ".avi":
            try:
                with open(p, "rb") as f:
                    h = f.read(12)
            except OSError:
                rejected.append((name, "unreadable")); continue
            if h[:4] != b"RIFF" or h[8:12] != b"AVI ":
                rejected.append((name, "not a valid AVI (RIFF)")); continue
        good.append((name, nbytes, dur))
    data = {"film_dir": film_dir, "found": len(files), "accepted": len(good),
            "min_films": min_films, "min_bytes": min_bytes, "min_secs": min_secs,
            "rejected": rejected[:10],
            "examples": [{"f": f, "bytes": b,
                          "secs": (round(d, 1) if d is not None else None)}
                         for f, b, d in good[:5]]}
    if len(good) >= min_films:
        return True, (f"{len(good)} valid clip(s) >= {min_films} "
                      f"(>= {min_bytes}B; MP4/MOV >= {min_secs:.0f}s)"), data
    return False, (f"only {len(good)} valid clip(s) < {min_films} required "
                   f"({len(files)} video(s) found, {len(rejected)} rejected)"), data


# ------------------------------------------------------------------- checks
def check_shots(shots_dir: str, min_shots: int, min_bytes: int,
                min_w: int, min_h: int,
                since_epoch: Optional[float] = None) -> Tuple[bool, str, dict]:
    files = find_shots(shots_dir, since_epoch)
    good, rejected = [], []
    for p in files:
        try:
            nbytes = os.path.getsize(p)
        except OSError:
            rejected.append((os.path.basename(p), "unreadable")); continue
        size = parse_png_size(p)
        if size is None:
            rejected.append((os.path.basename(p), "not a valid PNG")); continue
        w, h = size
        if nbytes < min_bytes:
            rejected.append((os.path.basename(p), f"{nbytes}B < {min_bytes}B")); continue
        if w < min_w or h < min_h:
            rejected.append((os.path.basename(p), f"{w}x{h} < {min_w}x{min_h}")); continue
        good.append((os.path.basename(p), w, h, nbytes))
    data = {"shots_dir": shots_dir, "found": len(files), "accepted": len(good),
            "min_shots": min_shots, "min_bytes": min_bytes,
            "min_wh": [min_w, min_h], "rejected": rejected[:10],
            "examples": [{"f": f, "w": w, "h": h, "bytes": b} for f, w, h, b in good[:5]]}
    if len(good) >= min_shots:
        return True, (f"{len(good)} valid still(s) >= {min_shots} "
                      f"(>= {min_w}x{min_h}, >= {min_bytes}B)"), data
    return False, (f"only {len(good)} valid still(s) < {min_shots} required "
                   f"({len(files)} png found, {len(rejected)} rejected)"), data


def check_run_health(run_dir: Optional[str]) -> Tuple[bool, str, dict]:
    if not run_dir:
        return False, "no run dir resolved (need --run-dir or --latest)", {}
    try:
        import verify_run_kinematics as vrk
        res = vrk.analyse_run_dir(run_dir)
    except Exception as e:  # noqa: BLE001
        return False, f"could not analyse {os.path.basename(run_dir)}: {e}", {"run_dir": run_dir}
    ok = res.get("verdict") == "PASS"
    data = {"run_dir": os.path.basename(run_dir.rstrip("/")),
            "verdict": res.get("verdict"), "controller": res.get("controller"),
            "gates": f"{res.get('gates_passed')}/{res.get('gates_total')}",
            "failed_gates": res.get("failed_gates", [])}
    msg = (f"run {data['run_dir']} kinematic-health {data['verdict']} "
           f"({data['gates']} gates, controller={data['controller']})")
    if not ok:
        msg += f" failed={data['failed_gates']}"
    return ok, msg, data


def resolve_run_dir(run_dir: Optional[str], latest: bool, log_root: str) -> Optional[str]:
    if run_dir:
        return run_dir
    if latest:
        runs = [d for d in glob.glob(os.path.join(log_root, "unreal-test-run_*"))
                if os.path.isdir(d)]
        runs = [d for d in runs if os.sep + "_selftest" + os.sep not in d + os.sep]
        if runs:
            return max(runs, key=os.path.getmtime)
    return None


def evaluate(shots_dir: str, run_dir: Optional[str], cfg: dict,
             want_run_health: bool = True, film_dir: Optional[str] = None) -> dict:
    checks = []
    ok1, det1, d1 = check_shots(shots_dir, cfg["min_shots"], cfg["min_bytes"],
                                cfg["min_w"], cfg["min_h"], cfg.get("since_epoch"))
    checks.append({"id": "C1", "name": "beauty_stills_present", "ok": ok1,
                   "detail": det1, "data": d1})
    if want_run_health:
        ok2, det2, d2 = check_run_health(run_dir)
        checks.append({"id": "C2", "name": "run_kinematic_health", "ok": ok2,
                       "detail": det2, "data": d2})
    if film_dir is not None:
        ok3, det3, d3 = check_film(film_dir, cfg.get("min_films", DEF_MIN_FILMS),
                                   cfg.get("min_film_bytes", DEF_MIN_FILM_BYTES),
                                   cfg.get("min_film_secs", DEF_MIN_FILM_SECS),
                                   cfg.get("since_epoch"))
        checks.append({"id": "C3", "name": "demo_film_present", "ok": ok3,
                       "detail": det3, "data": d3})
    verdict = "PASS" if all(c["ok"] for c in checks) else "FAIL"
    return {"checks": checks, "verdict": verdict,
            "checks_passed": sum(1 for c in checks if c["ok"]),
            "checks_total": len(checks)}


def main() -> None:
    ap = argparse.ArgumentParser(description="D6/D7 capture-artifact gate (headless).")
    ap.add_argument("--shots-dir", default=DEF_SHOTS_DIR)
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--latest", action="store_true", help="use the newest logs/ run")
    ap.add_argument("--no-run-health", action="store_true", help="skip C2 (shots only)")
    ap.add_argument("--min-shots", type=int, default=DEF_MIN_SHOTS)
    ap.add_argument("--min-bytes", type=int, default=DEF_MIN_BYTES)
    ap.add_argument("--min-width", type=int, default=DEF_MIN_WIDTH)
    ap.add_argument("--min-height", type=int, default=DEF_MIN_HEIGHT)
    ap.add_argument("--since-epoch", type=float, default=None,
                    help="ignore stills older than this epoch (capture-session start)")
    ap.add_argument("--film-dir", default=None,
                    help="enable C3: dir holding the screen-recorded demo clip(s) "
                         "(e.g. %%USERPROFILE%%\\Videos\\Captures for Game Bar)")
    ap.add_argument("--min-films", type=int, default=DEF_MIN_FILMS)
    ap.add_argument("--min-film-bytes", type=int, default=DEF_MIN_FILM_BYTES)
    ap.add_argument("--min-film-secs", type=float, default=DEF_MIN_FILM_SECS)
    ap.add_argument("--log-root", default=DEF_LOG_ROOT)
    ap.add_argument("--json-out", default=DEF_OUT)
    a = ap.parse_args()

    cfg = {"min_shots": a.min_shots, "min_bytes": a.min_bytes,
           "min_w": a.min_width, "min_h": a.min_height, "since_epoch": a.since_epoch,
           "min_films": a.min_films, "min_film_bytes": a.min_film_bytes,
           "min_film_secs": a.min_film_secs}
    want_health = not a.no_run_health
    run_dir = resolve_run_dir(a.run_dir, a.latest, a.log_root) if want_health else None
    res = evaluate(a.shots_dir, run_dir, cfg, want_run_health=want_health,
                   film_dir=a.film_dir)

    print("verify_capture_artifacts -- D6/D7 capture gate\n")
    for c in res["checks"]:
        print(f"  [{'PASS' if c['ok'] else 'FAIL'}] {c['id']} {c['name']}: {c['detail']}")
    print(f"\n  Checks {res['checks_passed']}/{res['checks_total']}  => {res['verdict']}")

    try:
        os.makedirs(os.path.dirname(a.json_out), exist_ok=True)
        with open(a.json_out, "w") as f:
            json.dump({"tool": "verify_capture_artifacts",
                       "shots_dir": a.shots_dir, "film_dir": a.film_dir,
                       "run_dir": (os.path.basename(run_dir.rstrip("/")) if run_dir else None),
                       "config": cfg, "checks": res["checks"],
                       "verdict": res["verdict"]}, f, indent=2)
        print(f"  wrote {a.json_out}")
    except OSError as e:
        print(f"  (could not write {a.json_out}: {e})")
    sys.exit(0 if res["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
