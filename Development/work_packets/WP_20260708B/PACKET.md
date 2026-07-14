# WP-20260708B — D7 film gate + in-engine run-sheet refresh · T-3

**Date:** 2026-07-08 (second packet of the day) · **Type:** capture tooling + docs.
**NO C++ / wire / DTO / schema / product-behavior change → no rebuild (Z0 stays 16/16).**

## Why this packet
1. **The run sheet was stale.** `PENDING_EDITOR_GATES.md` (2 Jul) — and this morning's
   WP-20260708 brief — still told Lemuel to run the Step-0 full rebuild, but that rebuild was
   **confirmed done 7 Jul** (`Build: 53 succeeded, 0 failed`, DLL relinked). At T-3, sending
   Lemuel into a redundant ~10-min rebuild wastes the one PIE/capture slot.
2. **D7 had no path.** The 11 Jul soft-launch kit needs a 60–90 s demo film; D7 was ☐ with no
   step in the session sheet and no objective gate. GTM already flags the launch AT RISK on
   exactly this (no film/stills).

## What was done
1. **`PENDING_EDITOR_GATES.md` refreshed (WP-20260708B):** Step 0 marked **CLEARED 7 Jul**
   ("do NOT rebuild again — no C++ changed since"), session re-scoped to Steps 1–4,
   new **Step 4 — D7 soft-launch film**: screen-record the Step-1/Step-3 PIE runs with
   Windows Game Bar (Win+Alt+R → `%USERPROFILE%\Videos\Captures`) or OBS — no MRQ setup at T-3.
   **Honesty:** a screen recording, NOT an MRQ cinematic render (MRQ = post-demo polish);
   GTM copy must say "demo capture".
2. **`python/verify_capture_artifacts.py` extended additively** with optional **C3 FILM**
   (only when `--film-dir` is given): ≥ `--min-films` clips, each ≥ `--min-film-bytes` (5 MB),
   structurally valid (MP4/MOV `ftyp` + duration parsed from the `mvhd` box, stdlib-only;
   MKV EBML; AVI RIFF) and ≥ `--min-film-secs` (20 s) for MP4/MOV; `--since-epoch` applies.
   C1/C2 behavior byte-for-byte unchanged when `--film-dir` is absent → **G_FILM_UE** gate:
   `python python/verify_capture_artifacts.py --latest --film-dir "%USERPROFILE%\Videos\Captures"`
3. **New `python/verify_20260708b.py`** — G1 a valid 30 s/6 MB fixture MP4 is accepted ·
   G2 back-compat (no `--film-dir` ⇒ exactly the old C1/C2 checks) · G3 run-sheet markers
   (Step 0 CLEARED / Step 4 / G_FILM_UE / no-rebuild) · G4 regression (`preflight_demo.py
   --report-only` live → rc 0 + **GO**, morning `wp_20260708_result.json` still pass) ·
   N1 undersized / N2 5-s / N3 no-ftyp `.mp4` all REJECTED.

## Acceptance gates — `python python/verify_20260708b.py`
**Result: PASS 4/4 + 3/3.** → `Saved/NaviSense_Reports/wp_20260708b_result.json`.

## Lemuel's steps (≤20 min of *your* attention; the session itself ≈40–50 min)
Everything is in the refreshed `PENDING_EDITOR_GATES.md` — **skip the rebuild**, go straight to:
1. Step 1 PIE `monaco_capture` (start Game Bar recording FIRST — Win+Alt+R).
2. Step 2 dashboard · Step 3 SS5 re-check + stills (record the SS5 pass too).
3. Step 4 gate: `python python/verify_capture_artifacts.py --latest --film-dir "%USERPROFILE%\Videos\Captures"`
4. Reply with the result lines (sheet bottom) — they flip D2/D4/D6/**D7** at once.

## Rollback
- Run sheet: previous version is in git history (2 Jul revision); content-identical Steps 1–3.
- `verify_capture_artifacts.py`: C3 is additive — omitting `--film-dir` reproduces the old tool
  exactly (proven by G2). Delete `python/verify_20260708b.py` to remove the gate.

## Session note (tooling integrity, KI-004 family)
A sandbox patch script with a bad `io.open(newline=...)` arg truncated
`verify_capture_artifacts.py` to 0 bytes mid-session (the "w" open truncates before the arg
validates). Caught immediately by the line-count check; file rebuilt in full from the read copy
+ `py_compile`/CLI-verified (334 lines). Lesson recorded: validate args before opening "w", or
write to a temp file + rename.
