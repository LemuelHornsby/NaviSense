# WP-20260623 — Scenario Runner v0 (one-command demo)

**Goal:** make the demo a **single command**. `run_demo.py` preflights the
environment, launches the bridge listener with a named scenario, drives ONE run
(your Unreal PIE session, or a headless self-test client), then **auto-builds the
IMO evidence pack + the kinematic-health verdict** — the demo's headline promise
("reproducible from a single command"). Advances gate **D6** (single-command run)
and seeds **D8** (clean-machine reproducibility).

**Type:** pure-Python **orchestration**, read-only over the existing tools.
**NO wire / schema / C++ change, NO recompile, NO new mandatory in-engine gate.**
(Plant + listener + evidence pack are unchanged; this only composes them.)

## Why this packet now
- The last open Python-side piece of **D6** is the *one-command scenario runner*
  (plan §4 WP-18). Scenario *selection* landed in WP-20260621 (`--scenario`); the
  evidence-pack *generator* landed in WP-20260620. This packet ties them into one
  command and adds the missing pre-flight + auto post-run steps.
- The critical-path **HYDRO** in-engine gates (G_HYDRO/G_PROP) still need Lemuel's
  rebuild + config asset + Blender prop split — not advanceable from the sandbox
  today — so this session pushed the other reachable gate (D6) forward instead.

## What shipped
- **NEW `run_demo.py`** (workspace root, sibling of `python_listener.py`):
  1. **PREFLIGHT** — python version, workspace layout, the named scenario (from
     `python/scenarios.py`), a free TCP port, and that the analysis tools import.
     (This is also the seed of the **D8** clean-machine check.)
  2. **LAUNCH** the listener `--once` with the scenario's controller + sea state.
  3. **DRIVE one run** — interactive (waits for your PIE session to connect and
     for you to Stop PIE) **or** `--selftest` (a bundled `ue5_client_sim.py` plays
     the vessel, so the whole pipeline runs with **NO Unreal / NO GPU**).
  4. **POST-RUN** — auto-runs `build_evidence_pack.py` (→ `logs/<run>/evidence_pack/`)
     and the `verify_run_kinematics.py` health gate, then prints a one-line summary.
  Exit 0 **iff** preflight passed, a run was produced, AND the health gate PASSed.
- **NEW `Development/work_packets/WP_20260623/verify_20260623.py`** — drives
  `run_demo.py` end to end and gates it (writes `wp_20260623_result.json`).

### Run it
```
python run_demo.py --scenario imo_turning_circle              # real UE
python run_demo.py --scenario imo_turning_circle --selftest   # headless (no UE)
python run_demo.py --list            # the scenario menu
python run_demo.py --preflight       # environment check only
```

## Acceptance gates
- **G_DEMO_AUTO** (this packet): `verify_20260623.py` returns **5/5 gates** and
  **3/3 negative controls fire**. ✅ (see result JSON)
  - G1 preflight passes · G2 `--list` matches the registry · G3 end-to-end headless
    turning-circle produces a run + `kpis.json` + `EVIDENCE.md` + plots + health PASS
    · G4 the runner's KPIs equal a standalone `build_evidence_pack` on the same run
    (no fudging) · G5 a second controller (zig-zag) also works (overshoot KPI).
  - Negative controls: **N1** invalid scenario → preflight FAIL; **N2** busy port →
    preflight FAIL; **N3** no vessel ever connects → "no run logged", **no fake pass**.
- **G_DEMO_UE** (optional, Lemuel): `python run_demo.py --scenario imo_turning_circle`
  with real Unreal — press **Play**, let the turn run, press **Stop**; confirm the
  runner prints `DEMO COMPLETE … health=PASS … (IMO PASS)` and an `evidence_pack/`
  drops under the new `logs/<run>/`. *(Not required to close the packet — the
  headless gate already proves the orchestration; this just exercises it with UE.)*

## Verified (sandbox, headless)
Evidence: `NaviSense_UE5/Saved/NaviSense_Reports/wp_20260623_result.json`
- **5/5 gates PASS, 3/3 negative controls FIRE** (run in ~27 s, no Unreal).
- G3 turning-circle: DT **158.18 m (DT/Lpp 4.16, IMO PASS)**, 2 plots, EVIDENCE.md.
- G4 KPI parity: runner DT == standalone `build_evidence_pack` DT (exact).
- G5 zig-zag: `kind=zigzag`, first overshoot **2.04°** (different controller path).
- **Regression on current disk (unaffected — this packet only ADDS two files):**
  `verify_run_kinematics` **7/7** + `verify_sensors_fidelity` **8/8** on the real
  morning run `unreal-test-run_20260622_054815`.

## Lemuel — steps (≤5 min; all optional, nothing blocks on this)
1. Try the headless demo (no Unreal): `python run_demo.py --scenario imo_turning_circle --selftest`
2. Try it with Unreal (G_DEMO_UE): `python run_demo.py --scenario imo_turning_circle`,
   then **Play → run the turn → Stop**; watch it auto-emit the evidence pack.
3. (Optional) add `run_demo.py --selftest` (or `verify_20260623.py`) to the nightly.
The HYDRO in-engine steps (rebuild + `DA_DOLPHIN_HydrostaticsConfig` + WaterlineOffsetCm
tune + Blender prop split) from `WP_20260621_HYDRO/PACKET.md` remain the real D2 blocker.

## Demo-gate impact
- **D6 (one-command run): the runner now exists** — one command preflights, runs a
  scenario, and produces the evidence pack. Stays **◐** until the in-engine
  `G_DEMO_UE` is eye-checked once with real UE and the ≥3 beauty screenshots / MRQ
  (D7) land. The headless half is **objectively green**.
- **D8 (clean-machine repro): seeded** — the preflight is the first executable
  clean-machine check (deps, layout, scenario, port). Full D8 = documented Cesium
  tokens + a post-`git clone` run, tracked for WP-21–23.

## Hardening / finds (fixed in-packet, not shipped broken)
- The **N3** control caught a real bug in the first cut of `run_demo`: a stale-dir
  fallback let it claim success on an *old* run when no new one was produced. Fixed —
  `_new_run_dir` now tracks the pre-existing dirs and returns the genuinely-new one
  only (else None → "no run logged"). The control now fires.
- **Headless `--selftest` runs are isolated in `logs/_selftest/`** (and `--log-dir`
  overrides the target) so a rehearsal never shadows a real UE run for `--latest`
  tooling. Real UE runs land in top-level `logs/` like any other run.
- Confirmed (KI-004 family): the **sandbox cannot unlink files on `D:`** (only
  rename) — so the daily session's headless rehearsals accumulate in `logs/_selftest/`
  (git-ignored, disposable); the verify's self-clean runs on Lemuel's native Windows.

## Rollback
Delete `run_demo.py` and `Development/work_packets/WP_20260623/`. Nothing imports
`run_demo` (no plant/listener references it); removing it cannot affect a run.
