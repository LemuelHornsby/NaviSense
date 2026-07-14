# WP_20260714B — Closeout verify + film/COLREGS tooling fixes

**Date:** 2026-07-14 (Tue, scheduled run) · **Type:** test-tooling only — NO C++ / wire / DTO / rebuild
**Trigger:** re-ran the objective closeout verifiers against Session A's LIVE runs (the interactive
session captured film + closed D2/KI-034 but never ran the closeout gates). Found + FIXED two bugs
that would have silently blocked the demo closeout.

## Findings (both FIXED this session)
- **KI-041 (S2) — D7 film gate could never pass on real footage.**
  `verify_capture_artifacts.parse_mp4_duration_s` read only the first 4 MB and `find('mvhd')`, so any
  **non-faststart** MP4 (moov box at END — Windows Game Bar / Unreal editor recorder / OBS default) was
  false-rejected "not a valid MP4/MOV" ⇒ C3 FAIL on all 3 real 14-Jul clips. **Fix:** read head
  (faststart) then, if no mvhd, the last 20 MB (moov-at-end), with a sanity-bounded mvhd read
  (timescale 1..6e6, 0.1 s..12 h) so a stray 'mvhd' in mdat can't false-pass. ⇒ Monaco 96.5 s +
  Turning_Circle 416 s parse, **C3 PASS**.
- **KI-042 (S3) — live COLREGS matrix crashed on a padded file.**
  `verify_colregs.matrix()` did a bare `json.load`; the mount NUL-padded a fresh
  `colregs_head_on_result.json` (valid body + 20×\x00, KI-038 family) ⇒ `JSONDecodeError` aborted the
  whole matrix. **Fix:** `_load_result()` strips trailing NUL/whitespace and recovers an intact body;
  marks a truly unparseable body **CORRUPT** (never crashes). ⇒ matrix 4/4.

## Changed files
- `python/verify_capture_artifacts.py` — robust `parse_mp4_duration_s` + `_mvhd_duration_s` helper (KI-041)
- `python/verify_colregs.py` — `_load_result()` + hardened `matrix()` (KI-042)
- `python/verify_20260714b.py` — NEW self-contained regression gate (synthetic fixtures; stdlib-only)
- Docs: PROGRESS (addendum + D7 ☐→◐ + ledger), Test Log ×5 rows, KI-041/KI-042 (RESOLVED), TC-52,
  Troubleshooting (KI-041 user entry), this packet, closeout runbooks.

## Gates (all PASS this session)
- `python python/verify_20260714b.py` → **4/4 gates + 3/3 neg-controls** → `wp_20260714b_result.json`
- On disk, verified against Session A's live runs:
  - `verify_run_kinematics` run 155234 (D2 SS5) → **8/8** (radius 86 m, reached 360°, no spin)
  - `verify_sensor_suite --run …153701` → **4/4** (G_AIS/G_RADAR/G_CAMERA)
  - `verify_capture_artifacts --film-dir Demo/film` → **C2 PASS + C3 PASS** (C1 stills 0 — see below)
  - `verify_colregs --matrix` → **4/4**, no crash

## What Lemuel still needs (≤20 min, in-engine) — the TRUE remaining closeout
The film + D2 + sensor/traffic gates are DONE. Only these remain (all in `NaviSense_Monaco`, no rebuild):
1. **D6 beauty stills (0 on disk):** during a framed PIE run, run the editor-Python
   `Phase5_Systems/08_capture_demo_stills.py` (burst `HighResShot 3840x2160`, ≥3 shots), then
   `python python/verify_capture_artifacts.py --latest --film-dir "Demo\film"` → C1 PASS closes G_CAPTURE_UE (D6) + G_FILM_UE (D7).
2. **3 LIVE COLREGS runs** (head_on already live today): `python run_colregs.py --crossing-giveway`,
   `--crossing-standon`, `--overtaking` (each presses Play, auto-verifies). Then
   `python python/verify_colregs.py --matrix` → 4 LIVE run dirs closes G_COLREGS_UE.
3. **Session closeout:** `python python/verify_demo_session.py --film-dir "Demo\film"` (TC-49).
4. **D8 clean box** (separate ~30 min, any day) per the Gate Closeout Guide, Session B.

## Rollback
Test-tooling + docs only; raw run logs and all C++ untouched. Backups at `/tmp/vca_backup.py`,
`/tmp/vc_backup.py` (this session); `git checkout` on Windows reverts any file.
