# WP-20260705 — Demo GO/NO-GO preflight

**Date:** 2026-07-05 (Sunday) · **Model:** Opus 4.8 · **Type:** pure-Python + docs.
**NO C++ / wire / DTO / schema change → no rebuild (Z0 stays 16/16).**

## Context — why this, not another feature
Six days to the 11 Jul demo. The headless frontier is exhausted: **every** remaining
demo gate is in-engine behind the ONE shared C++ rebuild + ONE PIE session
(`Development/work_packets/PENDING_EDITOR_GATES.md`). The last three packets each
flagged that piling on more headless code this close is the real **drift** risk. The
higher-value move is to protect the single demo-critical in-engine slot: make sure
that when Lemuel sits down to rebuild + capture, the tree will compile+link first try
and the demo storyline hasn't quietly regressed.

## What was built
- **`preflight_demo.py`** (workspace root) — ONE command, run right before the PIE
  session, that re-confirms on TODAY's disk:
  - **A. rebuild-safety** — `Z0` compile-readiness (16/16) + `verify_20260702b`
    (stacked 28 Jun→2 Jul link audit: all 16 pawn UFUNCTION decls defined, Build.cs
    `UMG`/`Slate`/`SlateCore` deps intact) ⇒ the rebuild is expected to compile+link.
  - **B. storyline-READY** — `demo_rehearsal.py` → `demo_readiness.json overall_ready`
    ⇒ the curated demo storyline still scores DEMO READY headless.
  - Aggregates via a pure `decide()` to a single **GO / NO-GO** (GO iff every required
    check passed; empty or any-fail ⇒ NO-GO naming the first failure), writes
    `Saved/NaviSense_Reports/demo_preflight_result.json`, exit 0=GO / 1=NO-GO.
  - It only READS the verdicts of already-verified tools (re-derives nothing) ⇒
    cannot drift from them. Default re-runs the 2-scenario rehearsal fresh so it can't
    false-green off a stale json; `--report-only` (fastest), `--full` (4-scenario).
- **`python/verify_20260705.py`** — gates it (below).

## Deliverable run today
**GO** — `rebuild:Z0_compile_readiness` rc0 (16/16) · `rebuild:stacked_link_audit`
rc0 (verify_20260702b 5/5+3/3) · `storyline:demo_rehearsal` rc0 → **DEMO READY**
(fresh 05 Jul run, health 7/7, COLREGS COMPLIANT). → `demo_preflight_result.json`.

## Acceptance gates — `python python/verify_20260705.py` → **PASS 5/5 + 3/3**
G1 `decide()` GO/NO-GO logic (all-pass→GO; any required fail→NO-GO naming it) ·
**G2 e2e** — a live `--report-only` on the current tree → GO, result json written with
`verdict/go/checks/reason/packet` + exactly 3 checks ·
G3 NO-GO path — an injected failing required check → NO-GO, reason names it (no false
green) ·
G4 aggregation edges — empty checklist→NO-GO, a non-required fail does NOT block ·
G5 regression — `Z0` 16/16 + `verify_20260702b` + `verify_20260704` exit 0.
Controls: N1 one failing required check→NO-GO · N2 empty checklist→NO-GO · N3 a GO
verdict can never carry a failing required check.

## Lemuel's steps (≤2 min, no rebuild)
Right before the in-engine session:
1. `python preflight_demo.py` → expect **GO**. If **NO-GO**, fix the flagged check
   BEFORE the PIE slot (do not burn it on a broken tree).
2. Then proceed with `PENDING_EDITOR_GATES.md` Step 0 (full rebuild, editor CLOSED)
   → Steps 1-3 (PIE `monaco_capture` + dashboard + capture).

## Honesty (KI-019 family)
**GO = the HEADLESS tree is rebuild-safe + the storyline is green.** It does NOT
confirm the in-engine demo — the `G_*_UE` eye-checks remain. The tool's banner + the
result-json `note` state this.

## Docs updated this session (Documentation Update Protocol)
- `Documents/PROGRESS.md` — ledger line (no D-gate flip; tooling only).
- `Manual and Troubleshooting/05_Test_Log.md` — TC-40 PASS + the GO deliverable row +
  a regression row (Z0 / link audit / rehearsal all green on today's disk).
- `Manual and Troubleshooting/03_QA_Test_Plan.md` — new **TC-40**.
- `Manual and Troubleshooting/00_Operations_Manual.md` — `preflight_demo.py` command
  (both command blocks).
- No new KI (no defect found); no D-gate status change.

## Rollback
Pure-additive: delete `preflight_demo.py` + `python/verify_20260705.py` and revert the
doc lines. No C++, wire, asset, or existing tool touched.
