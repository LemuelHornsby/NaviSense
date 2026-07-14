# WP-20260708E -- Sensor-fidelity D4 yaw-rate false-FAIL fix (KI-033)

*Fifth session today, run while Lemuel is away from the laptop (no screen-control access
possible, no live PIE session possible). Scope: headless-only regression + tooling fixes.*

## Why this ran

Lemuel asked what else is genuinely headless/scriptable to prep before he's home for the
live PIE/capture session. Rather than invent new feature work, the useful move was to
re-run every verify tool that hadn't run today and see what falls out. Two things fell out
of that:

1. A **real interrupted run** during a fresh `demo_rehearsal.py` full re-run (see Regression
   below) exercised the KI-030 shadow-fix live, for the first time outside a synthetic
   fixture -- confirms it holds under an actual truncation, not just the unit test.
2. A **genuine false-FAIL** in `verify_sensors_fidelity.py`'s D4 (yaw-rate) gate, found by
   running it against a straight-transit run -- this packet.

## Bug (KI-033)

`verify_sensors_fidelity.py` has 8 gates cross-checking the in-engine sensor bundle against
plant ground truth. D5 (heading fidelity) already has a guard: if a run turns less than 5
degrees, there isn't enough signal to correlate, so D5 reports INFO instead of gating.
**D4 (yaw-rate fidelity) never got the same guard.** Run it against a straight-transit run
(`logs/unreal-test-run_20260708_052109`, controller=`transit`, the `monaco_capture` AIS/
COLREGS pattern) and the plant yaw rate never leaves 0.000 deg/s -- both the correlation and
slope helper functions hit their explicit zero-variance branches and return `corr=0.0`,
`slope=0.0`. That's a mathematically degenerate result, not a real sensor defect, but D4 has
no INFO escape hatch, so it hard-FAILs (`6/7 => FAIL`).

This matters beyond one log: `transit`-controller scenarios are exactly the AIS/COLREGS
family (`head_on_transit`, `crossing_transit`, `harbor_traffic`, `monaco_capture` -- the very
scenario Step 1 of today's PIE session uses) and several hold a steady course by design. Any
of them can trip this false FAIL if someone runs the sensor-fidelity gate against the
resulting log.

## Fix

`python/verify_sensors_fidelity.py`:
- New constant `YAWRATE_MIN_RANGE_DEGPS = 0.5` (deg/s), placed next to the existing D4
  thresholds.
- D4 now computes the plant's own yaw-rate range first; below the threshold it reports INFO
  (`"run yaw-rate range only X deg/s (<0.5) -- not enough to gate"`), exactly mirroring D5's
  existing pattern. Above the threshold, behavior is byte-identical to before (same slope/
  corr/rms math, same PASS/FAIL thresholds) -- confirmed on the real turning-circle run
  `unreal-test-run_20260622_054815` (the run WP-20260622 originally validated D4 on):
  still `corr=1.0000`, still PASS, still 8/8.
- D4 never had a negative control (unlike D5's `frozen_heading`). Added `frozen_yawrate`
  (freeze `imu_yawRateDegPerSec` to 0.0) to `run_selftest`, applicable only when the run's
  base D4 isn't already INFO -- same applicability pattern as `frozen_heading`.

No C++/wire/DTO/schema change. No rebuild. Test-tooling only.

## Changed files

- `python/verify_sensors_fidelity.py` -- D4 guard + new negative control. Edited via shell
  (assert-guarded `str.replace` ×3), per the CLAUDE.md D: truncation guard. 573 lines (was
  559), `py_compile` clean.
- `python/verify_20260708e.py` (new) -- acceptance gate, see below.

## Acceptance gates -- `python/verify_20260708e.py`

**5/5 gates + 3/3 negative controls, PASS:**

| Gate | Result |
|---|---|
| G1 flat-run no false FAIL | real flat-transit run: D4=INFO, verdict=PASS (was FAIL pre-fix) |
| G2 turning-run unchanged | real turning-circle run: D4=PASS, corr=1.0000, verdict=PASS (regression-safe) |
| G3 new control has teeth | `frozen_yawrate` FIRES (D4->FAIL) on the turning run |
| G4 new control applicability | `frozen_yawrate` reports N/A on the flat run (mirrors `frozen_heading`) |
| G5 regression + parses | `py_compile` clean; Z0 16/16; `preflight_demo.py --report-only` still GO |

Negative controls: N1 replays the exact pre-fix math against the real flat run and proves it
really did return `corr=0.0/slope=0.0` (the bug was real, not assumed); N2 a synthetic run
with yaw-rate range just *above* the threshold still gates normally to PASS (the guard
doesn't over-suppress real signal near the boundary); N3 a synthetic run with a flat plant
but a wildly corrupted sensor is still INFO (the guard reads the plant, not the sensor --
can't be gamed from the sensor side).

Evidence: `NaviSense_UE5/Saved/NaviSense_Reports/wp_20260708e_result.json`.

## Regression run this session (before this fix was even found)

- `python3 -m pytest Development/bridge_harness/tests/` -- **10/10 passed** (hadn't run today
  until now).
- Fresh full `demo_rehearsal.py --no-plot` (all 4 scenarios re-executed headless, not just
  aggregated): 3 of 4 completed cleanly with fresh evidence packs
  (`imo_turning_circle_141025`, `imo_zigzag10_141039`, `building_sea_transit_141054`); the
  4th (`colregs_head_on_141109`) was interrupted mid-evidence-pack by this session's own
  45-second tool budget -- which is exactly the KI-030 shadow scenario, live. Re-running
  `preflight_demo.py --report-only` afterward confirms the fix holds on the real interruption:
  it correctly skipped the incomplete `141109` run and fell back to the complete
  `colregs_head_on_20260708_051158` run from this morning, verdict stayed **DEMO READY /
  GO**. No cleanup needed -- `logs/_rehearsal/` is disposable scratch space and the tooling
  already ignores the incomplete dir correctly.
- `verify_run_kinematics.py` and `verify_sensors_fidelity.py` re-run against an existing real
  log (`unreal-test-run_20260708_052109`) -- kinematics 6/6 PASS; sensor-fidelity is what
  surfaced KI-033 above.

## Lemuel's in-editor/terminal steps

**None.** Nothing here touches the editor or needs anything typed live. This is pure
headless verification + a tooling bug fix.

## What's still strictly for the live session

Unchanged from `PENDING_EDITOR_GATES.md` (see the new status note added at its top this
session): Steps 1, 3, and 4 (PIE + sensor/traffic gates, capture, film) need Lemuel typing
the listener commands and pressing Play/Stop in the actual editor -- nothing headless
substitutes for that. Step 2 (Bridge Dashboard) is deferred to Lemuel driving it directly
per his instruction (hand-built UMG graph wiring, not reliable to automate blind).

## Rollback

Revert the three edits to `python/verify_sensors_fidelity.py` (drop `YAWRATE_MIN_RANGE_DEGPS`,
restore the unguarded D4 body, drop the `frozen_yawrate` control) -- `verify_20260708e.py` is
additive and can simply be deleted; nothing else references it.
