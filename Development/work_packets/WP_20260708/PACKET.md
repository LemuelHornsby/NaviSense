# WP-20260708 — Demo-preflight false-NOT-READY fix (KI-030) · T-3

**Date:** 2026-07-08 (Wednesday) · **Model:** Opus 4.8 · **Type:** test-tooling fix + verify + docs.
**NO C++ / wire / DTO / schema / product-behavior change → no rebuild (Z0 stays 16/16).**
Touches only the headless demo-readiness harness `demo_rehearsal.py` (offline test tooling).

## Context — 3 days to the 11 Jul demo
Today's preflight came back **NO-GO** (a regression from WP-20260707's GO). Root cause was
**not** a broken pipeline: the demo-readiness *report-only* aggregator
(`demo_rehearsal._latest_run`) selected each scenario's **newest run by mtime** and only
then checked for `evidence_pack/kpis.json`. An **interrupted** run (crash / Ctrl-C / killed
mid-evidence-pack) leaves no `kpis.json`, so a single half-finished newer run **shadowed** a
perfectly good earlier complete run and flipped the whole preflight to a **false NOT READY**.
Observed live today: `building_sea_transit` latest=`..._054549` (no kpis) shadowed the
complete `..._054314`; `colregs_head_on` similarly. The `Z0` compile-readiness (16/16) and the
stacked link audit (`verify_20260702b` 5/5+3/3) were green throughout — the tree was always
rebuild-safe; only the storyline check mis-read stale artifacts.

This matters at T-3 because `preflight_demo.py --report-only` is the documented GO/NO-GO
confidence gate before the single in-engine rebuild+PIE slot — a false NO-GO would waste that
slot or stall the demo.

## What was done
1. **Fix `demo_rehearsal._latest_run`** (KI-030): iterate a scenario's runs **newest→oldest**
   and return the **newest run that has a COMPLETE evidence pack** (`kpis.json` present +
   parseable). If NO run is complete, still return the newest with `kpis=None` so an honest
   **NOT READY** is preserved (a genuinely broken pipeline is never masked). Added a small
   `_read_kpis()` helper. No behavior change to the *live* rehearsal path (which builds a fresh
   pack per run); this only hardens the report-only aggregation over existing runs.
2. **New `python/verify_20260708.py`** — proves the fix with an isolated tmp fixture and
   re-derives the disk verdict: **G1** older-complete beats newer-incomplete · **G2** honesty
   fallback (no complete run ⇒ newest,`None`) · **G3** preflight verdict==GO on today's disk ·
   **G4** regression `verify_20260702b`+`verify_20260704` both exit 0. Neg-controls
   **N1** lone incomplete ⇒ (dir,None) · **N2** empty log-dir ⇒ (None,None) · **N3** bad-json
   kpis counts as incomplete. → `Saved/NaviSense_Reports/wp_20260708_result.json`.
3. Re-ran `preflight_demo.py --report-only` → **GO** (verdict DEMO READY 4/4;
   `demo_preflight_result.json` rewritten today).

## Acceptance gates — `python python/verify_20260708.py`
G1 shadow-fix · G2 honesty · G3 preflight GO · G4 regression (2×rc 0) · N1–N3 neg-controls.
**Result: PASS 4/4 + 3/3.** Result file `wp_20260708_result.json` written.

## Deliverable run today
**GO** on today's disk (headless). D-gate burndown **unchanged** (no in-engine session
occurred): D1 ✅ · D3 ✅ · D5 ✅(mechanic) · **D2 / D4 / D6 / D7 / D8 still gated on the ONE
rebuild + PIE/capture session** in `PENDING_EDITOR_GATES.md` — now **T-3**.

## Lemuel's steps — the single critical-path action (unchanged, now urgent)
The ONLY thing between the current build and a green demo. Budget ~40 min:
1. `python preflight_demo.py` → expect **GO** (confirmed today).
2. `PENDING_EDITOR_GATES.md` **Step 0**: close the editor, full `Build.bat` rebuild
   (NOT Live Coding — WP-20260701 added UMG/Slate/SlateCore). Look for
   `Link UnrealEditor-NaviSense.dll` + `Result: Succeeded`.
3. **Step 1** PIE `monaco_capture` → `-v` log: traffic moves; `ais.targets[]` /
   `radar.contacts[]` / `camera{}` populate (G_TRAFFIC/G_AIS/G_RADAR/G_CAMERA_UE).
4. **Step 2** Bridge dashboard (panels live + helm/throttle/thruster drive the ship).
5. **Step 3** capture: SS5 `rough_turning_circle` wave-ride re-check (D2) +
   `08_capture_demo_stills.py` (D6 stills) + MRQ film pass (D7).
6. Reply with the short result lines from `PENDING_EDITOR_GATES.md` — each flips its gate
   + adds the Test-Log row the same session.

## Honesty (KI-019 family)
**GO = the HEADLESS tree is rebuild-safe + the storyline is green.** It does NOT confirm the
in-engine demo; the `G_*_UE` eye-checks remain. Nothing in-engine was verified today. The fix
only stops a *false* NOT READY — it can never manufacture a *false* READY (G2/N1 prove a
pipeline with no complete run still reports NOT READY).

## Docs updated this session (Documentation Update Protocol)
- `Documents/PROGRESS.md` — ledger line.
- `Manual and Troubleshooting/04_Known_Issues_Register.md` — **KI-030** opened + RESOLVED
  (same session, with root cause + fix).
- `Manual and Troubleshooting/05_Test_Log.md` — TC-41 PASS row + today's GO re-confirm.
- `Manual and Troubleshooting/03_QA_Test_Plan.md` — new **TC-41** (aggregator robustness).
- No run command / flag / controller / control changed → no Operations-Manual edit.
- No D-gate status changed → no burndown/status-banner edit.

## Rollback
Pure-additive + one localized function change. Restore `demo_rehearsal.py` from
`/tmp/demo_rehearsal.bak.py` (or revert `_latest_run`/`_read_kpis`) and delete
`Development/work_packets/WP_20260708/` + `python/verify_20260708.py`. No product code touched.
