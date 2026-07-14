# WP_20260711 — DEMO DAY (T-0): final GO gate + session run card

> **SLIP NOTE (12 Jul, WP_20260712):** this run card did NOT run on 11 Jul — it remains the valid instruction set for the pending live session (see `PENDING_EDITOR_GATES.md` slip banner; baseline re-proved green 12 Jul, TC-50 5/5+3/3).

**Date:** 2026-07-11 · **Type:** verification + docs only — **NO C++ / wire / DTO / schema /
product change, NO rebuild.** By design: nothing new lands on demo day; today re-proves the
baseline and hands Lemuel the one live session.

## Goal
1. Re-prove, fresh on the day, that the headless tree is GO (`verify_20260711.py`, TC-50).
2. Give Lemuel the condensed demo-day run card (below). `PENDING_EDITOR_GATES.md` stays the
   single source of truth for step detail (KI-032 lesson — this card does not restate it).

## Changed files
- `python/verify_20260711.py` (NEW, 158 lines) — T-0 GO gate: G1 Z0 16/16 · G2 link audit ·
  G3 preflight GO · G4 run-sheet currency markers · G5 pytest 10/10; N1–N3 fixture controls.
  Writes `Saved/NaviSense_Reports/wp_20260711_result.json`.
- Docs per protocol (PROGRESS ledger, Test Log, QA plan TC-50).

## Result (this session, headless)
`verify_20260711.py` **PASS 5/5 + 3/3** → `wp_20260711_result.json`. Also run raw this
session: Z0 16/16, `verify_20260702b` 5/5+3/3, `preflight_demo --report-only` **GO**
(rehearsal DEMO READY), pytest **10/10**.

## Lemuel's demo-day session (~45–60 min, ONE sitting)
Full detail per step: `Development/work_packets/PENDING_EDITOR_GATES.md`.

| # | Action | Time | Closes |
|---|--------|------|--------|
| 0 | **Live Coding recompile** (Ctrl+Alt+F11) — KI-034 traffic-roll fix. Anything stale → full Build, editor closed | 2–5 min | unblocks G_TRAFFIC_UE |
| 1 | Start recorder (Win+Alt+R) → listener `--scenario monaco_capture -v` → PIE. Eye-check 3 traffic ships upright + moving. Stop → `verify_sensor_suite --latest` | 10 min | G_TRAFFIC_UE (eye) + film beat (a) |
| 3 | `--scenario rough_turning_circle` SS5 pass, recorder on. Eye-check wave-ride at the boot-top. Stills: `08_capture_demo_stills.py` → `verify_capture_artifacts --latest` | 10 min | D2 SS5 (eye), G_CAPTURE_UE, film beat (b) |
| 5 | One-time scenery: `10_colregs_encounter.py` in editor, save. Then 4× `run_colregs.py --<scenario>` (each auto-verifies) → `verify_colregs --matrix` | 15–20 min | G_COLREGS_UE |
| 6 | **ONE command:** `python python/verify_demo_session.py --film-dir "%USERPROFILE%\Videos\Captures"` | 1 min | rolls up G_AIS/RADAR/CAMERA + G_CAPTURE + G_FILM + G_COLREGS → `demo_session_result.json` |
| 2 | (optional, any time) Bridge Dashboard per `NaviSense_BridgeDashboard_Complete_Guide.docx` | when ready | G_DASHBOARD_UE |

Then reply with the results per the "After the session" block in PENDING_EDITOR_GATES.md —
each line flips its gate + docs the same session.

## Acceptance gates
- `python python/verify_20260711.py` exits 0 (5/5 + 3/3) — **met this session**.
- The live-session gates above are Lemuel's; they close on his confirmation + result files.

## Rollback
Tooling/docs only: delete `python/verify_20260711.py` + `wp_20260711_result.json` and revert
the doc lines. No product surface touched.
