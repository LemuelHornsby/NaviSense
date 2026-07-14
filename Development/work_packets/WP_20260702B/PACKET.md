# WP-20260702B — Pre-Rebuild Integration Audit + consolidated in-engine gate runbook

**Date:** 2026-07-02 · **Model:** Opus 4.8 (autonomous daily session) · **Type:** headless audit +
documentation. **NO new C++, NO wire/DTO/schema change, NO new rebuild risk.**

## Why this packet
With the three headless D4 sensor items (AIS/camera on `sensor.v1`) and the Radar roadmap item all
shipped by 1–2 Jul, the headless frontier is essentially exhausted: **every** remaining demo gate is
in-engine and gated behind **one shared C++ rebuild**. That rebuild is now the single most
demo-critical action (11 Jul, 9 days out) and it carries a week of stacked additive C++ — including a
**rebuild-forcing `Build.cs` module change** (`UMG`/`Slate`/`SlateCore`). If it fails at compile or
link, Lemuel loses an in-engine session. Nothing headless was auditing that combined surface, and the
`PENDING_EDITOR_GATES.md` runbook was 2 weeks stale (14–18 Jun queue). This packet closes both gaps.

## Deliverables (changed files)
- **NEW** `python/verify_20260702b.py` — pre-rebuild integration audit gate (stdlib only, exit 0/1).
- **REWRITE** `Development/work_packets/PENDING_EDITOR_GATES.md` — consolidated ONE-session runbook for
  the current 28 Jun→2 Jul stack (one rebuild → `monaco_capture` PIE → dashboard → capture).
- Docs (Documentation Update Protocol): `Documents/PROGRESS.md` ledger line; `05_Test_Log.md` row;
  `03_QA_Test_Plan.md` new TC-36; `00_Operations_Manual.md` consolidated-session pointer.
- **NEW** `NaviSense_UE5/Saved/NaviSense_Reports/wp_20260702b_result.json` (written by the gate).

## What the gate checks (5 gates + 3 negative controls)
- **G1** Z0 compile-readiness **16/16** (named A1–F1 contracts + KI-004 truncation guard).
- **G2** `Build.cs` module integrity — `UMG`/`Slate`/`SlateCore` present & un-commented AND the bridge's
  `Json`/`JsonUtilities`/`Sockets`/`Networking` survived the edit (the rebuild-forcing change).
- **G3** Pawn UFUNCTION **declaration↔definition parity** — every one of the 16 new non-inline
  getters/setters has a `.cpp` definition (the **link-failure guard Z0 does not perform**) + the
  retained-traffic accessor is present.
- **G4** `sensor.v1` block integrity — `ais`/`camera`(gated `bEmitCamera`)/`radar`(gated `bEmitRadar`)
  all wired, pull from `GetTrafficTargets()`, and both SBC TUs brace-balanced.
- **G5** Regression — `verify_20260701`, `_701b`, `_701c`, `_702`, `_629b` all exit 0.
- **N1** a commented-out `UMG` dep → G2 fails · **N2** a declared-but-undefined UFUNCTION → G3 fails ·
  **N3** the radar block removed → G4 fails. (All three FIRE = the checks have teeth.)

**Result: PASS 5/5 gates + 3/3 controls** → the stacked surface is expected to compile + link first try.

## Lemuel's steps (≤20 min, in-engine) — the payoff
Follow the refreshed `Development/work_packets/PENDING_EDITOR_GATES.md`:
1. **One full C++ rebuild with the editor CLOSED** (NOT Live Coding — module deps changed). Confirm
   `Link UnrealEditor-NaviSense.dll` + `Result: Succeeded`, relaunch.
2. **PIE `--scenario monaco_capture`** → clears **G_TRAFFIC_UE / G_AIS_SENSOR_UE / G_RADAR_UE /
   G_CAMERA_UE** (ships move; `ais.targets` + `radar.contacts` + `camera` populate the `-v` log).
3. **Dashboard** (`09_build_bridge_dashboard.py` + recipe) → **G_DASHBOARD_UE** (panels live; controls
   drive the ship).
4. **Capture** (`08_capture_demo_stills.py`) + `rough_turning_circle` SS5 → **G_CAPTURE_UE** (via
   `verify_capture_artifacts --latest`) + the remaining **D2** wave-ride re-check.

## Acceptance gates (this packet)
`python python/verify_20260702b.py` → **PASS 5/5 + 3/3**, `wp_20260702b_result.json` verdict PASS. ✅

## Rollback
Pure-additive + docs. Delete `python/verify_20260702b.py` and `git checkout` the
`PENDING_EDITOR_GATES.md` / doc edits. No C++, wire, or asset touched — zero runtime impact.
