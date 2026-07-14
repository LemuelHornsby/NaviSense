# WP-10 (2026-06-19) — Canonical listener re-accept (close KI-017)

**Theme (Week 2):** make the **canonical** run listener survive a UE PIE stop/restart by
re-accepting a fresh connection, closing **KI-017**. Pure-Python; **no DTO/schema/C++ change,
NO recompile, NO new in-engine gate.**

## Why this packet
The whole in-engine queue is still blocked behind Lemuel's single pending recompile (KI-018
rerun + the Session-A eye-checks). Rather than pile on more recompile-gated C++, this packet
closes a real, code-level defect I can fix **and fully verify headless**:

**KI-017** — the 14-Jun ledger claimed WP-3 re-accept robustness was "propagated into the
canonical root `python_listener.py`," but it wasn't: `run()` did a **single** `server.accept()`
then exited the moment the client dropped. So a UE PIE **Stop/Play** (or any drop) **ended the
listener** instead of it re-accepting — you had to relaunch Python every PIE session. The
`verify_root_reaccept.py` that "proved" it actually resolves three levels up to the **backup**
root, not this workspace (same class of slip as KI-016/KI-019: a claim outran the code).

Demonstrated before the fix: the new verify scored **1/5** against the old listener (R1 streamed,
then R2/R3/R4 failed — process gone after the first client).

## What changed (canonical workspace only)
- **`python_listener.py` — `run()` refactored** (the canonical run listener at the workspace root):
  - Binds/listens **once**, sets `server.settimeout(1.0)` so Ctrl-C stays responsive, then loops:
    `accept → serve one client → (re-accept | exit)`.
  - The entire per-session body (plant/controller/logger build + RX thread + tick loop) moved
    **verbatim** into a nested `_serve_one_connection(conn, addr, run_id)` closure — so every
    bare name (`plant_kind`, `tick_hz`, `sea_state`, …) is still captured from `run()` with **zero
    arg-threading**. Only deliberate deltas: removed the per-session `server.close()` (the server
    now outlives a client), moved `print("[bridge] closed.")` to `run()`'s `finally`, and let
    `KeyboardInterrupt` propagate to `run()` so Ctrl-C stops the **whole** server.
  - `nonlocal log_dir, time_scale` (both are resolved in-place inside the closure).
  - **Each reconnect is a FRESH run:** fresh plant + controller + logger + sim clock (t→0), with a
    `_s2`, `_s3`, … run-id suffix so logs never collide.
  - **New `--once`** flag → `reaccept=False` (the old single-shot CI behaviour). Default = re-accept.
- **NEW `Development/work_packets/WP_20260619/verify_canonical_reaccept.py`** — targets the
  **canonical** listener via the corrected workspace-root path; spawns it on the dependency-light
  `--plant stub --controller demo --no-log` path and checks R1–R5; writes
  `Saved/NaviSense_Reports/wp_20260619_canonical_reaccept_result.json`.

Invariants respected: no coordinate/sign code touched (#1), RX thread still SPSC hand-off (#2),
DTO/wire keys unchanged (#3), tuning still via data asset (#4), controllers still fed the plant's
authoritative yaw (#5 — preserved inside the relocated body).

## Acceptance gates
**Automated (PASS now — `wp_20260619_canonical_reaccept_result.json`, 5/5):**
- **R1** initial stream — first client gets ≥5 `navisense.state.v1`.
- **R2** re-accept after a **hard** drop (RST) — a new client connects + streams ≥5.
- **R3** fresh run — the reconnect's first packet has `t < 0.5 s` (clock reset, new run).
- **R4** second reconnect — a 2nd drop+reconnect also streams (it's a loop, not one-shot).
- **R5** `--once` exits — single-shot mode still terminates after the first client.
- Regression on current disk: compile-readiness **16/16** (incl. KI-018 `RInterpTo` intact, B1 22/22),
  schema-v13 **12/12**, WP-9 **9/9**, pytest **10/10**. MMG+sea-state+logging smoke verified across a
  reconnect (two fresh runs `smoke_*` / `smoke_s2_*` logged with the `sea_state` column).

**Manual (folds into the already-pending recompile — NO new recompile):**
- **G4 (TC-08), improved:** with the listener running and PIE playing, press **Stop** then **Play**
  again **without** touching the listener → the pawn holds **STALE**, and on Play the listener
  **re-accepts** and the pawn resumes. (Previously G4 required you to Ctrl-C + relaunch the listener.)

## Lemuel's steps (≤5 min — optional; none block the recompile queue)
1. (No engine) `python Development/work_packets/WP_20260619/verify_canonical_reaccept.py` → expect **5/5**.
2. In your next Session-A PIE run, after it's streaming, press **Stop** then **Play** again and
   confirm the listener prints `client gone - re-accepting…` then `Unity connected` and the pawn
   resumes — **no listener relaunch**.
3. Tell Claude: **"G4 re-accept across PIE Stop/Play: pass/fail."**

## Rollback
Pure-Python, isolated. Restore `Development/work_packets/WP_20260619/rollback/python_listener.py.bak`
over `python_listener.py`. No C++, DTO, wire-schema, or data-asset change, so rollback cannot affect
the in-engine build. Authored entirely via the shell (KI-004) and `py_compile`/AST-verified.
