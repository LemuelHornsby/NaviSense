# WP-8 — 6-DOF schema v1.3: heave (vertical) + sea-state wave field   ·   2026-06-17

**Theme (F1 part 2):** complete the 6-DOF wire schema. WP-7 gave the hull *attitude*
(heel/trim, v1.2); this packet gives it *vertical motion*. The plant stays 3-DOF; the
listener samples a small, deterministic **sea-state wave field** at the ship's horizontal
position and sim-time, and ships a **heave** (`heaveM`) inside `state.v1` (rev 1.3). Unreal
applies it as a Z offset so the boat **rides the swell** — the second half of demo gate
**D2** (6-DOF water ride) — and the `--sea-state` knob seeds gate **D3** (sea states).
Sampling the *rendered* UE water surface is **F1 part 3** (deferred: needs a UE
water-height source; can't be verified headless).

## Why this packet today
Every prior packet (WP-3…WP-7, SENSOR-1, ACTUATOR-RIG) is auto-verified and waiting on
**one** in-editor recompile + PIE pass — none have a *failing* gate, so there is nothing to
"fix". The highest-value autonomous work is to advance the next backlog item, F1, in its
fully head-less-verifiable form. Heave as a deterministic wave-field proxy is exactly that:
replayable (no RNG at sample time; uses the WP-4 sim clock), the natural partner to the v1.2
attitude, and the sea-state index is the same knob D3 needs.

## Changed files
- **`python/sea_state.py`** (NEW) — deterministic `WaveField(sea_state, heading_deg, seed)`;
  `elevation(east, north, t)` sums a few Pierson-Moskowitz-weighted sinusoids (phases/dirs
  seeded once), realized **Hs == target** by construction, clamped at ±4 m. SS0 ⇒ 0 everywhere.
- **`python_listener.py`** — imports the field; attaches `plant._wave_field`; `build_state_packet`
  samples `heaveM = field.elevation(s.x, s.z, t)` and adds `"heaveM"` **inside** `state.v1`.
  New CLI: `--sea-state 0–9` (default 0 = calm = identical to v1.2), `--wave-heading-deg`, `--wave-seed`.
- **`NaviSense_UE5/Source/NaviSense/Bridge/NaviSenseBridgeTypes.h`** — `FNaviSenseState`
  gains `double heaveM = 0.0` (default 0 ⇒ a v1.2 sender renders identically).
- **`Core/NaviSenseCoords.h`** — `WireHeaveToUE(double)` — the *only* place the heave Z
  sign/axis mapping lives (invariant #1).
- **`Vessel/NaviSenseShipPawn.h/.cpp`** — `TargetHeaveCm` (set in `ApplyOwnShipState`),
  smoothed `CurrentHeaveCm` (lerped in Tick), added to `Loc.Z` beside the freeboard; frozen
  on stale-hold (no drift). Zero heave ⇒ byte-identical Z to v1.2.

## Acceptance gates
| Gate | Type | Status | Evidence |
|---|---|---|---|
| H1–H12 wave model + wire emission + DTO/wire parity + single-source + backward-compat | auto | ✅ PASS 12/12 | `wp_20260617_heave_seastate_result.json` |
| Compile-readiness still green after the C++ edits (Z0 + **B1 now 22/22**) | auto | ✅ PASS 16/16 | `wp_20260615_compile_audit_result.json` |
| pytest plant/contract suite unbroken by the listener change | auto | ✅ PASS 10/10 | `bridge_harness/tests` |
| **G_UE8 — hull rises/falls on the swell, smooth, no jitter @ stable FPS; flat at SS0** | **manual (PIE)** | ☐ pending | Lemuel — folded into PENDING_EDITOR_GATES "Session A" |

## Lemuel's steps (≤ ~5 min, folds into the existing editor pass)
1. **Recompile** (Ctrl+Alt+F11). Picks up `heaveM` + `WireHeaveToUE` + the pawn Z-lerp
   (and the WP-7 attitude fields, still pending the same recompile).
2. Start the listener with a sea state, e.g.
   `python python_listener.py --plant mmg --controller turning_circle --target unreal -v --sea-state 5`,
   press **Play**.
3. **Watch the hull vertically:** it should rise and fall on the swell smoothly (no vertical
   jitter). Re-run with `--sea-state 0` and confirm it sits flat. Then **tell Claude:
   "WP-8 G_UE8 — heave: pass/fail (and whether it sinks or lifts on a crest)."**

## Decisions made autonomously (no user present)
- **Synthetic wave field, not engine water sampling.** A deterministic listener-side field is
  replayable (pairs with the WP-4 clock), needs no UE water-height source, and is
  head-less-verifiable. Reading the *rendered* water surface stays F1 pt3.
- **Sea-state midpoints** (WMO/Douglas Hs/Tp); **±4 m heave clamp**; mean wave heading default
  0 (waves travel north). All tunable in `sea_state.py`.
- **`heaveM` is a separate wire field** (not folded into `z`), exactly like `rollDeg/pitchDeg`,
  so a v1.2 sender is byte-identical and `z` stays the plant's (zero) vertical.

## Tooling incident (KI-004 recurrence) — logged, resolved same session
The editor file-tool **truncated every file it wrote** this session (the 22 KB listener and
all 5 edited C++ files, incl. the 2.3 KB `NaviSenseBridgeTypes.h`). Each was caught by the
post-edit brace/line check and rebuilt via the shell (intact prefix + re-appended tail), then
re-verified (`Z0` 16/16). KI-004 updated; CLAUDE.md hardened to "all D: writes via the shell."
No defect shipped.

## Rollback
- Python: `--sea-state 0` (default) ⇒ heave 0 ⇒ identical to v1.2. To remove entirely, delete
  `python/sea_state.py`, the `_wave_field`/`heave_m` lines + the three CLI args.
- C++: set `heaveM` to 0 on the wire, or revert the 3 files (edits are small, additive,
  brace-verified). No other code depends on heave.
