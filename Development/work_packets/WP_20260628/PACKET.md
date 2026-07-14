# WP-20260628 — Speed-driven wake & spray VFX (D5 / WP-16)

**Goal:** stand up demo gate **D5** — a wake that grows with the own-ship's speed
(bow wave + stern wash + spray bursts) and is *off* when moored. The hull is
kinematically posed (no fluid sim), so the wake is **driven by speed**: a Niagara
system reads two 0..1 user floats (`WakeIntensity`, `Spray`) and scales itself.
This packet delivers the **whole authorable stack** — the curve, the C++ feed, the
attach script, the build recipe, and the headless gate — so the only in-editor work
left is the Niagara art + the eye-check.

**Type:** first **in-engine** packet in a week (the six prior were pure-Python; the
headless frontier was exhausted — D2/D5/D7 are in-engine, per WP-20260627's own
rationale). **Minimal additive C++** (BlueprintPure getters + two tiny scalar
functions — no wire/DTO/schema change, no coordinate/sign work, brace-verified Z0
16/16), folded into the engine-closeout recompile, **plus a no-recompile fallback**
so D5 can progress before the rebuild.

## Why this packet now (28 Jun, demo 11 Jul = 13 days)
- D1 ✅, D3 ✅; the headless-advanceable items (D4 intelligence, D6 evidence
  richness, D8 readiness) are mature. The **unstarted** gates are **D5 (wake) and
  D7 (film)** — both in-engine, and **D7 depends on D5** (the film needs a wake).
- The pawn was architected for this: `BodyVelCmPerSec` is computed every tick
  "for wake/VFX (Phase 11)"; the getters just weren't Blueprint-readable yet.
- Starting D5 now leaves runway for the Niagara art + D6 beauty screenshots + the
  D7 MRQ film before the freeze.

## What shipped
**New**
- `python/wake_model.py` — the single source of truth for the speed→VFX curve
  (`intensity01`, `spray01`, `ribbon_width_cm`, `spawn_rate`, `spray_rate`,
  `params`, a CLI table). Grounded in DOLPHIN's speed range (spray onset ≈ hull
  speed ~15 kn; saturates ≈ 20 kn design top speed). Stdlib-only, deterministic.
- `NaviSense_UE5/Content/NaviSense/Python/Phase5_Systems/04_setup_wake_vfx.py` —
  editor-Python: finds the placed yacht, adds a `WakeViz` NiagaraComponent at the
  stern, assigns `NS_Wake` if present, seeds the user floats from the pawn
  (created by **script**, not the right-click menu — KI-013).
- `Documents/NaviSense_Wake_VFX_Recipe.md` — the authoritative build: NS_Wake
  emitters (ribbon stern-wash + sprite spray), the live-intensity binding, the
  acceptance checklist, **and a no-recompile fallback** (BP position-delta speed).
- `Development/work_packets/WP_20260628/verify_20260628.py` — the gate.

**Edited (additive)**
- `NaviSense_UE5/Source/NaviSense/Vessel/NaviSenseShipPawn.h` — the three
  kinematics getters become `UFUNCTION(BlueprintPure)` (Niagara/HUD-readable);
  new `WakeFullSpeedMS=10.3 / WakeSprayOnsetMS=7.7 / WakeMinSpeedMS=0.3` UPROPERTYs
  (*NaviSense | VFX*, tune without recompiling) + `GetWakeIntensity01()` /
  `GetWakeSpray01()` declarations.
- `NaviSenseShipPawn.cpp` — the two getter bodies, **mirroring `wake_model.py`
  exactly** (verify G4 asserts the constants + logic match). Uses only `FMath`
  (already included). No hot-path, no coordinate/sign change (invariant #1 intact).

### The curve (`python python/wake_model.py`)
| kn | m/s | WakeIntensity | Spray |
|---:|----:|--------------:|------:|
| 0 | 0.00 | 0.000 | 0.000 |
| 6 | 3.09 | 0.279 | 0.000 |
| 12 | 6.17 | 0.587 | 0.000 |
| 15 | 7.72 | 0.736 | 0.000 |
| 18 | 9.26 | 0.896 | 0.600 |
| 20 | 10.29 | 1.000 | 1.000 |

## Acceptance gates
- **G_WAKE (auto, this packet):** `verify_20260628.py` → **6/6 + 3/3**. ✅
  - G1 intensity 0-at-rest, monotone, clamped, =1 at full · G2 spray gated below
    the onset then ramps to 1 · G3 ribbon/spawn/spray-rate in bounds + monotone ·
    **G4 C++ defaults == Python constants** + each getter uses the right constant +
    clamps (rendered curve == gated curve) · G5 deterministic · G6 editor-script
    parses + recipe references the user params + edited C++ brace-balanced (KI-004).
  - Controls fire: N1 a flat curve is rejected · N2 a wake-at-rest is rejected ·
    N3 a tampered C++ constant is detected by parity.
- **G_WAKE_UE (in-engine, Lemuel):** wake scales with speed, spray ≈ >15 kn, none
  when moored, reads right at all camera modes, `stat GPU` wake < 2 ms. (Closes D5.)

## Verified (sandbox, headless)
Evidence: `NaviSense_UE5/Saved/NaviSense_Reports/wp_20260628_result.json`
- **G_WAKE 6/6 gates PASS, 3/3 controls FIRE.**
- Regression on current disk green: Z0 compile-readiness **16/16**,
  `verify_run_kinematics` **8/8** (run `…_055244`), `verify_sensors_fidelity`
  **8/8** (morning run), `verify_20260623` run_demo e2e **5/5 + 3/3** (27.4 s).

## Lemuel's steps (≤ 20 min; full detail in the recipe)
1. **Recompile** (editor closed, `Build.bat` — Live Coding does not relink the base
   DLL, KI-018). *Optional:* skip and use the no-recompile fallback for a first look.
2. **Tools → Execute Python Script →** `Phase5_Systems/04_setup_wake_vfx.py`
   (adds WakeViz at the stern, ~2 min).
3. **Build `NS_Wake`** per `Documents/NaviSense_Wake_VFX_Recipe.md` §3 (ribbon
   stern-wash + sprite spray, GPU sim, fixed bounds), re-run the script to assign it.
4. **Bind** `User.WakeIntensity = GetWakeIntensity01`, `User.Spray = GetWakeSpray01`
   on `BP_ShipPawn_Yacht` Event Tick (recipe §4).
5. **PIE** a transit/turning-circle → confirm **G_WAKE_UE**; drop 1–2 screenshots
   into `Development/Development images/` (also feeds D6).

## Rollback
All additive. To revert: delete `python/wake_model.py`, the editor script, the
recipe, this WP folder; in `NaviSenseShipPawn.h/.cpp` remove the `// Wake / spray
VFX feed` blocks and restore `FORCEINLINE` on the three getters (drop the
`UFUNCTION` lines). No data/wire/asset migration involved; the wake is purely
visual.
