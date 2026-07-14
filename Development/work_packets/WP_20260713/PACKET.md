# WP_20260713 — Post-live-session triage: P0 anti-partial-evidence gate (KI-038)

**Date:** 2026-07-13 (Mon) · **Type:** pure Python + docs — NO C++/wire/DTO/schema change, NO rebuild
**Result file:** `NaviSense_UE5/Saved/NaviSense_Reports/wp_20260713_result.json` (TC-51, **PASS 6/6 + 2/2**)

## What happened (found, not assumed)

You RAN the live session on **12 Jul PM** — `logs/demo-monaco_capture_20260712_125800`
(13 min MMG @ SS2, monaco_capture, 3 AIS targets). Windows-side, on the full log:
TC-17 kinematics **6/6 on 23,393 rows**, TC-23 GPS/IMU fidelity **6/6**, TC-43 sensor
suite **4/4** ⇒ **D4 is closed (scoped)**. KI-037 (cp1252 pack crash) found + fixed live.

**But:** this sandbox still sees a **frozen 47% view** of that run dir ≥20 h later —
`state.csv` 11,117/23,393 rows, `manifest.json` cut at 967 B (invalid JSON), no `runs.csv`
row — and the 12-Jul on-disk evidence pack had been **silently built from that 47% view**
claiming PASS. Worse, the truncated manifest bypassed a naive row check (the forgiving
manifest loader returns `{}`). Opened **KI-038 (S2)**.

## Shipped

- `python/build_evidence_pack.py` (v2.1): **P0 view-completeness + manifest-integrity gate**
  — refuses (exit 3, KI-038 message) BEFORE writing anything when the run-dir view is
  partial; `--allow-partial` builds a clearly-watermarked forensic pack; `kpis.json meta`
  now carries `view_complete` / `state_rows_read` / `state_rows_manifest`.
- `python/verify_20260713.py` — **TC-51: 6/6 gates + 2/2 neg-controls** (G5 reproduces the
  exact live loophole; probe runs on a COPY, never writes into the real run dir).
- On-disk 125800 pack deliberately rebuilt **watermarked PARTIAL** (honest until your rebuild).
- Baseline **TC-50 re-proved 5/5 + 3/3** (`verify_20260711.py`, 13 Jul re-run).
- Docs: PROGRESS (ledger + Monday metrics + burndown D4 ✅ˢ/D6/D7/D2), Test Log ×3,
  KI-038, TC-51, Ops Manual, Troubleshooting §H, PENDING_EDITOR_GATES banner, CG/MP/AR banners.

## Your steps (≤20 min total)

1. **(2 min) Rebuild the live pack on Windows** — terminal at the workspace root:
   `python python\build_evidence_pack.py --run-dir logs\demo-monaco_capture_20260712_125800`
   Expect `view : complete (23393/23393 rows)` + plant `mmg`, SS2, duration ~780 s.
   If it REFUSES on Windows too → stop, tell me (then the full log never hit disk and
   TC-17's 23,393 came from a pre-close buffer — next session investigates).
2. **(1 min)** `type logs\runs.csv | findstr 20260712` — tell me hit or miss (index row).
3. **(≤15 min) Finish list** — `PENDING_EDITOR_GATES.md`, 13-Jul banner: Step 3 stills +
   D2 eye-word (G_UE7/8) · Step 4 screen-record → `Demo\film` · Step 5 COLREGS matrix ·
   Step 6 `python python\verify_demo_session.py --film-dir "Demo\film"` (TC-49).
4. **(1 sentence)** KI-034: in the 12-Jul run, were the two roll-corrected traffic hulls
   (excursion vessel / yacht) upright? Yes ⇒ I close KI-034 next session.

## Acceptance gates

- TC-51 `verify_20260713.py` PASS 6/6 + 2/2 → `wp_20260713_result.json` ✅ (done, this session)
- TC-50 baseline PASS 5/5 + 3/3 ✅ (done, this session)
- Step 1 Windows rebuild shows `view : complete` (⇒ D6 real-run artifact) — yours
- TC-49 closeout PASS after film (⇒ D7) — yours

## Rollback

`git checkout -- python/build_evidence_pack.py` (Windows git), delete
`python/verify_20260713.py` + `WP_20260713/`. The 125800 pack: any rebuild overwrites the
watermarked artifacts in `logs/.../evidence_pack/`; raw run logs were never modified.
