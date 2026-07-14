# WP-20260629 — Canonical run-clock `t_mono` (closes KI-024)

**Date:** 2026-06-29 (Mon) · **Author:** Claude (autonomous session) · **Type:** pure-Python,
log-schema add (append-only) — **NO wire / DTO / schema / C++ change, NO recompile, NO new
mandatory in-engine gate.** · **Demo gates:** hardens **D4** (sensor fidelity) + **D6** (evidence
pack) data integrity. · **Verdict:** `verify_20260629.py` **6/6 + 3/3 controls = PASS**.

## Goal
Close **KI-024**: `state.csv t` (Python plant clock) and `sensor.csv t` (UE engine clock) advance
at different rates (3.0× vs 1.0× wall under high PIE FPS), so anything that fuses the two logs by
`t` gets badly misaligned data. The 22-Jun mitigation joined on `wall_time` (an absolute epoch
float) inside `verify_sensors_fidelity` only — leaving a trap for any future fuser and a fragile
join key (epoch floats aren't guaranteed monotonic across NTP steps).

**Fix:** the single `RunLogger` process now stamps one **monotonic, run-relative** clock
`t_mono = time.monotonic() - run_start` onto **every row of BOTH logs** (and `events.csv`), plus a
`timeBase` block in `manifest.json`. `t_mono` is now THE canonical join key; `verify_sensors_fidelity`
prefers it and falls back to `wall_time` for legacy (pre-`t_mono`) runs. `t` stays as the raw
per-side reference clock. Because both rows are stamped from one process-wide monotonic source, they
share one timeline regardless of plant/engine clock skew.

## Changed files
- `python/run_logger.py` — add `t_mono` to `SENSOR_COLUMNS`, `STATE_COLUMNS`, the `events.csv`
  header, and each row; new `_mono_start` field + `_t_mono()` helper; `manifest.timeBase`
  (`joinKey=t_mono`). **Append-only** — existing column order unchanged (zero risk to positional
  readers; consumers use name-based `DictReader`).
- `python/verify_sensors_fidelity.py` — new `_col_ok()` / `_join_key()`; `_join_to_plant` joins on
  the canonical key (`t_mono` when both logs carry it, else `wall_time`); `C1` reports the key used.
  **Legacy runs are byte-for-byte identical** (fall back to `wall_time`).
- `python/verify_20260629.py` — **NEW** gate (6 gates + 3 negative controls).

## Acceptance gates — `python python/verify_20260629.py` → **6/6 + 3/3 PASS**
- **G1** `t_mono` present in sensor.csv, state.csv, events.csv + `manifest.timeBase.joinKey=t_mono`.
- **G2** `t_mono` monotonic non-decreasing and run-relative (starts ≤ 50 ms) in BOTH logs.
- **G3** the two logs' `t_mono` lie on ONE timeline (spans agree, overlap) **while raw `t` diverges
  3×** (sensor 5.90 s vs state 17.70 s) — KI-024 reproduced and bypassed.
- **G4** `verify_sensors_fidelity` prefers `t_mono` on a fresh run **and** falls back to `wall_time`
  on a legacy run (`…_055244`).
- **G5** canonical (`t_mono`) join recovers the plant speed ramp vs the faithful sensor with
  rms = 0.0001 m/s.
- **G6** a `t_mono`-stripped run still loads + joins via `wall_time` (no crash) — back-compat.
- **N1** a backwards `t_mono` is caught (monotonic check fails). **N2** a desynced/rescaled `t_mono`
  is caught (span/overlap check). **N3** the bug the fix prevents: a **raw-`t` join is ~3000× worse**
  (rms 0.580 vs 0.0001 m/s) than the canonical join.

## Regression (current disk, headless) — all green
- `verify_compile_readiness` (Z0) **16/16** (C++ untouched).
- `verify_run_kinematics` `…_055244` **8/8**.
- `verify_sensors_fidelity` `…_055244` **8/8** (wall_time fallback — identical; C1 still flags the
  3.0× vs 1.0× divergence).
- `run_demo.py --scenario imo_turning_circle --selftest` → **DEMO COMPLETE, health 8/8, DT 158.2 m
  IMO PASS**; the produced run carries `t_mono` in both logs + manifest; fidelity gate confirms
  *"join uses 't_mono', NEVER raw t"*.
- `verify_20260623` run_demo e2e **5/5 + 3/3** (27.0 s).

## Lemuel's steps (≤ 5 min, optional — nothing blocks)
1. Pull, then (optional) `python python/verify_20260629.py` → expect `6/6 + 3/3 PASS`.
2. Next in-engine PIE run: open the new run's `state.csv`/`sensor.csv` and confirm a `t_mono`
   column on both — that is now the column to fuse sensor↔plant on. No editor/recompile change.

## Rollback
Restore `python/run_logger.py` and `python/verify_sensors_fidelity.py` from git
(`git checkout -- python/run_logger.py python/verify_sensors_fidelity.py`) and delete
`python/verify_20260629.py`. The change is additive: old runs and all other tooling are unaffected
either way (legacy runs never had `t_mono`; consumers fall back to `wall_time`).

## Honesty / scope
This makes the canonical join key robust and enforced; it does **not** make the two raw `t` clocks
themselves identical (that is the deterministic engine sim-clock work, **KI-012**, which is
in-engine). `build_evidence_pack` does not currently fuse sensor.csv (it reads `state.csv` for the
IMO KPIs), so KI-024 was a latent risk — this packet removes it before any sensor-overlay / WP-15B
AIS fuser is added, and upgrades the only live fuser (`verify_sensors_fidelity`).
