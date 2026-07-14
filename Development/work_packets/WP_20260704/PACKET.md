# WP-20260704 — Headless demo-readiness rehearsal harness

**Date:** 2026-07-04 · **Model:** Opus 4.8 · **Type:** pure-Python orchestration + docs.
**NO C++ / wire / DTO / schema change → no rebuild (Z0 stays 16/16).**

## Goal
With WP-20260703 green and the headless frontier exhausted, **every remaining demo
gate is in-engine behind the one shared C++ rebuild** (7 days to the 11 Jul demo).
The last-week risk is *drift* — a change that quietly breaks one of the scenarios the
live demo will show. `run_demo.py` runs ONE scenario; nothing ran the whole demo
storyline and reduced it to a single, objective readiness verdict. This packet adds
that: a headless **DEMO READY / NOT READY** gate over the demo storyline, runnable
nightly and before every in-engine session.

## What was built
- **`demo_rehearsal.py`** (workspace root) — drives the curated **DEMO STORYLINE**
  headless, each scenario via `run_demo.py --selftest` (no Unreal/GPU), reads each
  run's evidence pack (`health.verdict`, IMO KPI pass flags, COLREGS conformance
  verdict) and aggregates to ONE verdict + a per-scenario / per-gate readiness matrix.
  - Storyline: `imo_turning_circle` (D1/D6) · `imo_zigzag10` (D1/D6) ·
    `building_sea_transit` (D2/D3 runtime sea-state sweep) · `colregs_head_on` (D4).
  - `--fast` = 2-scenario smoke (turning circle + head-on); `--report-only` =
    re-aggregate the latest existing runs without re-running (nightly re-report);
    `--scenarios a,b` override; `--no-plot` for speed.
  - Re-derives nothing itself — it only reads what the already-verified tools wrote,
    so it cannot drift from them. `overall_ready()` is the single aggregation rule.
- **`python/verify_20260704.py`** — gates it (below).

## Deliverable run today (full storyline, `--plant mmg`, headless)
**DEMO READY — 4/4 required scenarios READY, gates D1/D2/D3/D4/D6 covered headless.**
- `logs/_rehearsal/DEMO_READINESS.md` (human matrix)
- `NaviSense_UE5/Saved/NaviSense_Reports/demo_readiness.json` (machine)
Each scenario: health PASS; turning/zig-zag IMO KPIs PASS; colregs_head_on
conformance COMPLIANT.

## Acceptance gates — `python python/verify_20260704.py` → **PASS 5/5 + 3/3**
G1 storyline↔`scenarios.py` parity (4 required, all real, IMO keys well-formed) ·
G2 evaluator correctness (good pack READY; health-FAIL / no-pack NOT ready) ·
**G3 e2e** — the `--fast` rehearsal runs 2 real `--selftest --plant mmg` runs ⇒
DEMO READY 2/2, D1+D4 covered, JSON+MD reports written ·
G4 aggregation (`overall_ready`: one required-fail⇒NOT READY, a non-required fail
does not block, empty⇒NOT READY) ·
G5 regression (`Z0` 16/16 + `verify_20260703` + `verify_20260702b` green).
Controls: N1 unknown scenario detected not-run · N2 a health-FAIL pack scored NOT
ready (no false green) · N3 a conformance mismatch scored NOT ready.

## Lemuel's steps (≤5 min, no rebuild)
Optional — this is a headless QA tool, nothing in-engine is required:
1. `python demo_rehearsal.py` → prints DEMO READY / NOT READY + writes the report.
   (`--fast` for a ~30 s smoke; `--report-only` to re-aggregate the latest runs.)
2. Read `logs/_rehearsal/DEMO_READINESS.md`.
The in-engine eye-checks are unchanged and still tracked in
`Development/work_packets/PENDING_EDITOR_GATES.md` (the one shared rebuild + PIE
session). READY here means the HEADLESS pipeline is green, NOT that the in-engine
demo is confirmed.

## Honesty (KI-019 family)
The verdict is a **headless** readiness check — it confirms the Python pipeline
(plant → listener → evidence pack → health/KPI/COLREGS gates) reproduces green
across the whole storyline. It does NOT confirm the in-engine demo; the `G_*_UE`
gates remain. The report banner states this.

## Docs updated this session (Documentation Update Protocol)
- `Documents/PROGRESS.md` — ledger line + D6 burndown note.
- `Manual and Troubleshooting/05_Test_Log.md` — TC-39 PASS row + the full-storyline
  DEMO READY 4/4 deliverable row.
- `Manual and Troubleshooting/03_QA_Test_Plan.md` — new **TC-39**.
- `Manual and Troubleshooting/00_Operations_Manual.md` — `demo_rehearsal.py` command
  (both command blocks).
- No new KI (no defect found); no D-gate status flip.

## Rollback
Pure-additive: delete `demo_rehearsal.py` + `python/verify_20260704.py` and revert
the doc lines. No C++, wire, asset, or existing tool touched. Removing it cannot
affect a run.
