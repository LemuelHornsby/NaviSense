# WP-20260630 — Demo-capture enablement (D6 stills / D7 frames + one in-engine batch)

**Date:** 2026-06-30 (Tue) · **Author:** Claude · **Type:** pure-Python + editor-Python
(**NO wire / DTO / schema / C++ change, NO recompile** of its own) · **Demo gates:** D6
(≥3 beauty screenshots) + D7 (establishing frames) tooling; batches the pending in-engine
gates **G_TRAFFIC_UE · D2 SS5 · D6 · D7** into ONE session · **Verdict (headless):**
`verify_20260630.py` **5/5 gates + 3/3 controls = PASS**.

## Why
The headless frontier is essentially exhausted (PROGRESS 29 Jun): every remaining demo gate —
**G_TRAFFIC_UE** (the 29-Jun traffic render, pending the rebuild), **D2** SS5 wave-ride re-check,
**D6** ≥3 beauty screenshots, **D7** the film — is now an *in-engine* item that needs you + PIE.
This packet (a) removes the manual fiddliness of capturing stills, and (b) turns "did we get the
shots?" into an objective, repeatable gate, and (c) sequences the four pending in-engine gates into
one ≤20-min sitting so they fall together.

## What changed (all in the WORKSPACE; additive, no recompile)
- **NEW** `python/verify_capture_artifacts.py` — reusable, **stdlib-only** D6/D7 gate:
  - **C1** ≥ `--min-shots` (3) PNG stills under `--shots-dir`, each ≥ `--min-bytes` **and**
    ≥ `--min-width`×`--min-height` (read straight from the PNG **IHDR**; a blank/failed
    HighResShot is a few KB, a low-res grab is rejected). `--since-epoch` ignores stale stills.
  - **C2** the named run (`--run-dir`/`--latest`) passes the kinematic-health gate
    (`verify_run_kinematics` verdict **PASS**) — a pretty frame is never accepted over a spinning/NaN run.
  - Writes `Saved/NaviSense_Reports/capture_artifacts_result.json`, exits 0 iff PASS.
- **NEW** `NaviSense_UE5/Content/NaviSense/Python/Phase5_Systems/08_capture_demo_stills.py` —
  editor-Python (run via **Tools → Execute Python Script**, KI-013). Fires a **burst** of
  `HighResShot 3840x2160` captures on the editor tick (non-blocking — you keep flying the camera),
  `SHOTS`/`INTERVAL_S`/`RESOLUTION` configurable at the top, and writes
  `Saved/NaviSense_Reports/capture_manifest.json` (records the session start epoch + the exact
  verify command, so C1 can be scoped to this session).
- **NEW** `python/verify_20260630.py` — the headless authoring gate (5 gates + 3 controls).
- No existing file edited. No wire/DTO/schema/C++ touched (**Z0 16/16**, C++ untouched).

## Acceptance gates — `python python/verify_20260630.py` → **5/5 + 3/3 PASS** (done, headless)
- **G1** `08_capture_demo_stills.py` parses + really drives `HighResShot` + writes the manifest.
- **G2** the shots check accepts a set of full-res stills (count/size/resolution).
- **G3** the run-health check is wired to `verify_run_kinematics` and PASSES on a real healthy run.
- **G4** the stdlib PNG-size parser reads IHDR right and rejects non-PNG bytes.
- **G5 (e2e)** `evaluate()` = PASS for {3 full-res stills + a healthy run}; the four capture
  scenarios resolve to real controllers; **Z0 16/16** (C++ untouched).
- **N1** only 2 stills → shots FAIL · **N2** a 640×480 grab → shots FAIL · **N3** a spin-on-the-spot
  run → run-health FAIL (so the gate won't rubber-stamp a broken run).

## Your in-engine session (≤ 20 min) — knocks out 4 gates at once
Prereq: the **WP-20260629B C++ rebuild** (adds `FNaviSenseState.traffic` + `ApplyTraffic`). If you
haven't rebuilt since 29 Jun, do the full Build (editor closed) first, then run
`Phase5_Systems/07_setup_traffic_ships.py` once.

1. **G_TRAFFIC_UE + D7 COLREGS footage** — `python run_demo.py --scenario monaco_capture`, press
   **Play**. Confirm the 3 ships move along the encounter (overtake SLOWBELLE, give way to AZURFERRY
   crossing from starboard, meet MERIDIAN head-on). With PIE running:
   **Tools → Execute Python Script → `08_capture_demo_stills.py`** → it grabs 3× 4K stills
   (re-frame the chase cam between them). **This is D6 + the COLREGS film beat in one run.**
2. **D2 SS5 wave-ride re-check (hydrostatics active)** — `python run_demo.py --scenario
   rough_turning_circle` (SS5, beam swell), Play. Confirm the hull **rolls/heaves through the turn**
   with hydrostatics owning roll/pitch/heave (the boot-top stays at the surface, props submerged —
   WaterlineOffsetCm=-218). Run `08_capture_demo_stills.py` again for a seakeeping still.
3. **D7 establishing/seakeeping reel** — optionally `--scenario building_sea_transit` or
   `storm_ride` for the sea-builds-around-the-yacht beauty pass; capture stills the same way.
4. **Gate it (headless, ~2 s):** stop PIE, then
   `python python/verify_capture_artifacts.py --latest`
   → expect **C1 PASS** (≥3 full-res stills) + **C2 PASS** (the run is kinematically healthy) =
   **PASS**, writing `capture_artifacts_result.json`. That is the objective close-out for the
   captured set. (Until you capture, `--latest` correctly reports C1 FAIL = "no stills yet".)

**Capture-readiness note (not a bug):** if the sea reads neon-cyan in a fresh capture (as in the
29-Jun `yacht_with_traffic.png`, which also shows "No Loaded Region(s)"), re-open `NaviSense_Monaco`
so the WaterZone reloads the tuned material — per the 28-Jun ocean-colour fix the MI edits only show
after a level reload. Frame beauty stills with regions loaded + the deep-blue water.

## Acceptance (in-engine) — **G_CAPTURE_UE**
`verify_capture_artifacts.py --latest` returns **PASS** on a real captured set (≥3 4K stills + a
healthy run). This closes the D6 "≥3 beauty screenshots" item and seeds D7.

## Rollback
Delete `python/verify_capture_artifacts.py`, `python/verify_20260630.py`, and
`NaviSense_UE5/Content/NaviSense/Python/Phase5_Systems/08_capture_demo_stills.py`. Fully additive —
nothing else references them; no runtime/wire path is touched.

## Honesty (KI-019 family)
This packet ships **tooling**, not captured footage — it does not itself advance an in-engine gate
to ✅. The capturer reads the live viewport; the gate checks the files + the run's health. No new
claim about fidelity. The COLREGS traffic remains a **scripted** preset rendered as props (WP-15B);
the wake/roll/heave remain visual proxies (KI-025/KI-022 family).
