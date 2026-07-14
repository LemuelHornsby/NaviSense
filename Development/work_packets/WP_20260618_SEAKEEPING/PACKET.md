# WP-9 (2026-06-18) — Wave-coupled roll/pitch + 6-DOF / sea-state run evidence

**Theme (Week 2, F1 part 3a):** the hull now **rolls and pitches with the swell**, not just heaves,
and the active **sea state is recorded in the run log**. Pure-Python; rides the existing
`rollDeg`/`pitchDeg`/`heaveM` wire keys. **No DTO/schema change, NO new recompile gate.**

## Why this packet (not another C++ feature)
Every Week-1 packet + WP-7 (v1.2 attitude) + WP-8 (v1.3 heave) is auto-verified but the whole
in-engine queue is blocked behind **one unconfirmed recompile** (see `PENDING_EDITOR_GATES.md`).
Adding more recompile-gated C++ would only deepen that backlog. WP-9 instead makes real D2/D3
progress **without touching C++**: it improves the *content* of wire fields the UE pawn already
consumes, so it folds into the SAME pending recompile rather than adding a new one.

## What changed (all in the canonical workspace)
- **NEW `python/wave_response.py`** — `wave_attitude_deg(field, east, north, yaw, t)`: projects the
  sea-state field's surface slope (`WaveField.slope_rad()`, already present, previously unused on the
  wire) into the hull body frame → wave-induced roll/pitch. Beam sea ⇒ roll, head/following sea ⇒
  pitch. `FOLLOW_GAIN 0.80`; clamps 6° roll / 4° pitch. SS0/None ⇒ (0,0). Dependency-free, pure.
- **`python_listener.py` `build_state_packet`** — composes the wave attitude **onto** the maneuvering
  heel/trim (`attitude_proxy`), each contributor clamped at source and the **sum** capped at
  `TOTAL_ROLL_CLAMP_DEG 12°` / `TOTAL_PITCH_CLAMP_DEG 6°`. Rides the existing `rollDeg`/`pitchDeg`
  keys — **no new wire key** (B1 parity stays 22/22). No field / SS0 ⇒ byte-identical to rev 1.3.
- **`python/run_logger.py`** — `state.csv` now also logs `rollDeg,pitchDeg,heaveM` (appended; the
  6-DOF pose was on the wire but not in the evidence). `manifest.json` records `seaState`,
  `waveHeadingDeg`, `waveSeed`; `runs.csv` index gains a `sea_state` column; the `run_started` event
  notes the sea state. (`python_listener.run()` passes the params through.) **Closes the D3
  "recorded in the run log" half.**
- **NEW `verify_20260618.py`** — 9 checks (W1–W9), writes `wp_20260618_result.json`.

Wire-schema sketch (for reference; no code change required by it): this is "rev 1.4" only in the
sense that `rollDeg`/`pitchDeg` now carry maneuvering **+** wave components; the JSON keys, the DTO
(`FNaviSenseState`), and `NaviSenseCoords.h` are all unchanged.

## Acceptance gates
**Automated (PASS now, sandbox — `wp_20260618_result.json`, 9/9):**
- W1 back-compat: SS0/None ⇒ wave attitude (0,0) **and** full `state.v1` packet byte-identical to rev 1.3.
- W2 maneuvering heel/trim preserved exactly (composition adds 0 at SS0).
- W3 deterministic / replayable (no RNG at sample time).
- W4 directional: head sea ⇒ pitch≫roll; beam sea ⇒ roll≫pitch.
- W5 clamps: wave term ≤6°/4°; **composed** ≤12°/6° even at SS9 + hard turn.
- W6 **no schema drift**: exactly the 22 rev-1.3 wire keys (invariant #3 guard).
- W7 composition active: SS6 beam sea swings composed `rollDeg` on the wire.
- W8 logger logs the 6-DOF pose columns; W9 logger records the sea state (manifest + `runs.csv`).
- Regression re-run green on current disk: compile-readiness **16/16** (Z0 + B1 22/22), schema-v13 **12/12**, pytest **10/10**.

**Manual (folds into the already-pending recompile — NO new recompile):** `G_UE7/G_UE8+`
With the recompile done and the listener on `--controller turning_circle --sea-state 5`: confirm the
hull now **rolls** toward/with a beam swell and **pitches** into a head swell (smooth, no jitter), on
top of the heave bob; sits flat again at `--sea-state 0`.

## Lemuel's steps (≤5 min — only when you next do the pending recompile)
There is **nothing extra to compile** for WP-9. When you run the already-queued Step-0 recompile +
Session-A PIE (see `PENDING_EDITOR_GATES.md`), just also watch the hull's roll/pitch on the swell:
1. (Optional, no engine) `python3 Development/work_packets/WP_20260618_SEAKEEPING/verify_20260618.py` → expect `9/9`.
2. In Session-A, add a beam swell: `python python_listener.py --plant mmg --controller turning_circle --target unreal -v --sea-state 5 --wave-heading-deg 90`. Watch for roll with the swell + pitch through the turn.
3. Tell Claude: **"G_UE7/8+ swell attitude — hull rolls/pitches with the sea: pass/fail."**

## Rollback
Pure-Python, isolated: delete `python/wave_response.py` and revert the `build_state_packet`
composition block + the `run_logger.py` column/manifest additions. The wire schema, the DTO, and all
C++ are untouched, so rollback cannot affect the in-engine build. Truncated-original guard: this
packet was authored entirely via the shell (KI-004) and brace/parse-verified.
