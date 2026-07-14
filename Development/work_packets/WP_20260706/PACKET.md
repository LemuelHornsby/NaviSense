# WP-20260706 — Demo-week hold-the-line (T-5) + Monday Week-5 metrics

**Date:** 2026-07-06 (Monday) · **Model:** Opus 4.8 · **Type:** verification + docs only.
**NO C++ / wire / DTO / schema / Python-behavior change → no rebuild (Z0 stays 16/16).**

## Context — 5 days to the 11 Jul demo
The headless frontier is exhausted. **Every** remaining demo gate (D2 SS5 wave-ride,
D4 AIS/camera sensors, D6 stills, D7 film) is behind the ONE shared C++ rebuild + ONE
PIE/capture session in `Development/work_packets/PENDING_EDITOR_GATES.md`. The last five
packets each flagged that adding more headless code this close is the real **drift** risk.
So today is deliberately NOT a new feature: it is a fresh GO re-confirm on today's disk,
the Monday Week-5 metrics, and a tightened brief on the single critical-path action.

## What was done (no new product code)
- Re-ran the demo preflight on today's disk → **GO**
  (`preflight_demo.py --report-only`): `Z0` compile-readiness **16/16**, stacked
  pre-rebuild link audit (`verify_20260702b`) **5/5+3/3**, `demo_rehearsal` → **DEMO
  READY** (fresh run generated 2026-07-06T11:30, health 7/7, COLREGS COMPLIANT).
  → `Saved/NaviSense_Reports/demo_preflight_result.json`.
- Regression sweep green on today's disk: `verify_20260702b` 5/5+3/3, `verify_20260704`
  5/5+3/3 (demo-readiness rehearsal harness).
- `python/verify_20260706.py` re-derives the GO verdict + regression rc's into
  `Saved/NaviSense_Reports/wp_20260706_result.json` (below).
- Documents/PROGRESS.md: Monday **Week-5** dev-metrics block + a ledger line.

## Acceptance gates — `python python/verify_20260706.py`
G1 preflight verdict on today's disk == **GO** (reads `demo_preflight_result.json`
`verdict`, freshly written today) ·
G2 regression: `verify_20260702b` exit 0 AND `verify_20260704` exit 0 ·
G3 result json `wp_20260706_result.json` written with `{go, checks[], regression{}}`.
(Pure read/aggregate — re-derives nothing, cannot drift from the tools it reads.)

## Deliverable run today
**GO** on today's disk. D-gate burndown unchanged (no in-engine session occurred):
D1 ✅ · D3 ✅ · D5 ✅(mechanic, 28 Jun) · **D2 / D4 / D6 / D7 / D8 all still gated on
the ONE rebuild + PIE/capture session** — now T-5.

## Lemuel's steps — the single critical-path action (unchanged, now urgent)
This is the ONLY thing between the current build and a green demo. Budget ~40 min:
1. `python preflight_demo.py` → expect **GO** (confirmed today).
2. `PENDING_EDITOR_GATES.md` **Step 0**: close the editor, full `Build.bat` rebuild
   (NOT Live Coding — WP-20260701 added UMG/Slate/SlateCore modules). Look for
   `Link UnrealEditor-NaviSense.dll` + `Result: Succeeded`.
3. **Step 1** PIE `monaco_capture` → read the `-v` log: traffic moves,
   `ais.targets[] / radar.contacts[] / camera{}` populate.
4. **Step 2** Bridge dashboard (panels live + helm/throttle/thruster drive the ship).
5. **Step 3** capture: SS5 `rough_turning_circle` wave-ride re-check (D2) +
   `08_capture_demo_stills.py` (D6 stills) + MRQ film pass (D7).
6. Reply with the short result lines from `PENDING_EDITOR_GATES.md` — each flips its
   gate + adds the Test-Log row the same session.

## Honesty (KI-019 family)
**GO = the HEADLESS tree is rebuild-safe + the storyline is green.** It does NOT confirm
the in-engine demo; the `G_*_UE` eye-checks remain. Nothing in-engine was verified today.

## Docs updated this session (Documentation Update Protocol)
- `Documents/PROGRESS.md` — Monday Week-5 metrics block + ledger line.
- `Manual and Troubleshooting/05_Test_Log.md` — today's GO re-confirm + regression rows.
- No new KI (no defect found); no D-gate status change; no command/flag change → no
  Operations-Manual / QA-Test-Plan edit needed.

## Rollback
Pure-additive: delete `Development/work_packets/WP_20260706/` +
`python/verify_20260706.py` and revert the doc lines. No product code touched.
