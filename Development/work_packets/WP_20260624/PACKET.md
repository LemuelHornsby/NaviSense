# WP-20260624 — Scripted AIS traffic + CPA/TCPA + COLREGS encounters (gate D4 / WP-15)

**Goal:** put a real, scripted AIS traffic target on the run with the **correct
range/bearing from own-ship** (the WP-15 gate), and compute the standard
**CPA / TCPA** and the **COLREGS encounter type** (head-on / crossing / overtaking
+ own-ship's give-way / stand-on duty) into the evidence pack. This advances demo
gate **D4** (AIS half) and seeds the week 5-6 **COLREGS-scoring** differentiator
(Master Execution Plan §5.1) with the literature-standard collision-risk metrics.

**Type:** pure-Python. **NO wire / DTO / schema change, NO recompile, NO new
mandatory in-engine gate.** Own-ship truth is read from the existing `state.csv`;
targets are a deterministic function of sim-time, so the same numbers come out
headless as would come out live. The listener's new `--ais` flag only records the
chosen preset in the run **manifest** (metadata) — zero per-tick work on the bridge
hot path. *Rendering AIS targets as UE pawns + carrying `mmsi/cog/sog` on
`sensor.v1` is the separate in-engine follow-up **WP-15B**; this packet delivers and
validates the **data/analysis half** of D4.*

## Why this packet now
- D4 is **◐** (GPS/IMU validated 22 Jun). Its named-but-unbuilt pieces are camera
  (WP-14), **AIS traffic (WP-15)**, and the live CesiumGeoreference. AIS is the one
  fully reachable from the sandbox today — it's math + data over the existing log.
- `verify_sensors_fidelity` D9 already reads `ais_target_count` and says *"0 until
  scripted traffic, WP-15"* — this packet is exactly that target.
- The critical-path **HYDRO** in-engine gates (G_HYDRO float-at-waterline) still
  need Lemuel's in-editor session; not advanceable from the sandbox today.

## What shipped
**New**
- `python/ais_traffic.py` — the core model (dependency-free): `AISTarget` /
  `AISTrafficField` (constant- or piecewise-velocity dead-reckoning), `cpa_tcpa`
  (analytic closed form), `range_bearing` / `relative_bearing` / `target_aspect`,
  `classify_encounter` (COLREGS Rules 13-15 → give-way/stand-on), `project_latlon`
  (same WGS84 projection + Monaco origin as the GPS sensor), AIS Type-18 encoder,
  and a preset library (`head_on`, `crossing`, `overtaking`, `harbor_mix`).
- `python/analyse_ais.py` — reconstructs each scripted target over a logged run's
  own-ship track and computes per-target range/bearing/CPA/TCPA time series, the
  min-CPA + the encounter at the **decision moment** (first CPA alert, else min
  range), and CPA-alert events. Writes `ais.csv` + a range/CPA plot. Has a CLI.
- `Development/work_packets/WP_20260624/verify_20260624.py` — gates the packet.

**Edited (all additive, guarded, byte-identical when AIS is off)**
- `python/build_evidence_pack.py` — `--ais <preset>` (or auto from `manifest["ais"]`)
  → adds an **AIS traffic & COLREGS** section to `EVIDENCE.md`, an `ais.csv`, an
  `ais_cpa.png`, and an `"ais"` block in `kpis.json`. IMO maneuver KPIs + the health
  gate are untouched.
- `python/scenarios.py` — `Scenario.ais` field + 4 scenarios: `head_on_transit`,
  `crossing_transit`, `overtaking_transit`, `harbor_traffic` (steady own-ship +
  traffic). They compose with `run_demo.py` (one-command demo).
- `python/scenario_controllers.py` — `TransitController` (straight steady course =
  the own-ship for a clean COLREGS encounter); `--controller transit`.
- `python/run_logger.py` — records the AIS preset in `manifest.json` (`"ais"`).
- `python_listener.py` — `--ais <preset>` / `--ais list`; resolves a scenario's AIS
  preset; accepts `--controller transit`; passes the preset to the logger.

### Run it
```
python python_listener.py --ais list                       # the traffic presets
python python/analyse_ais.py --run-dir logs/<run> --ais head_on   # analyse a run
python python/build_evidence_pack.py --run-dir logs/<run> --ais head_on
python run_demo.py --scenario head_on_transit --selftest    # one-command, headless (no UE)
python run_demo.py --scenario crossing_transit              # one-command with real UE
```

## Acceptance gates
- **G_AIS_AUTO** (this packet): `verify_20260624.py` → **6/6 gates** + **3/3 negative
  controls fire**. ✅ (see result JSON)
  - **G1** core cpa/tcpa/range/bearing match the analytic closed form · **G2** the
    head_on/crossing/overtaking presets classify correctly (+ own duty) on a
    synthetic steady own-ship · **G3** the *WP-15 gate* — the AIS block lists the
    target with the correct range & bearing from own-ship (vs hand geometry) ·
    **G4** `build_evidence_pack --ais` on a **real run** emits a finite AIS block +
    `ais.csv` + `ais_cpa.png` + an EVIDENCE.md section, with the IMO KPIs + health
    gate **unchanged** · **G5** analysing twice is bit-identical (determinism) ·
    **G6** the listener records the preset in the manifest and the pack **auto-reads**
    it (full chain).
  - Negative controls: **N1** unknown preset → `make_field` raises + listener exits
    !=0 (no fake run) · **N2** a receding target → `no_risk`, **never alerts** (no
    crying wolf) · **N3** a crossing target on the **port** bow → `stand_on` (the
    opposite of the starboard give-way — proves port/starboard discrimination).
- **G_AIS_UE** (optional, Lemuel; **not required to close** — the data half is
  objectively green): run a traffic scenario with real UE and confirm the
  auto-generated evidence pack lists the target with sane range/CPA. (No AIS pawns
  render yet — that's WP-15B.)

## Verified (sandbox, headless)
Evidence: `NaviSense_UE5/Saved/NaviSense_Reports/wp_20260624_result.json`
- **6/6 gates PASS, 3/3 negative controls FIRE.**
- G3 (the WP-15 gate): head-on target reported range **1600.38 m**, bearing **1.25°**
  from own-ship = hand geometry exactly.
- G4 on the real run `unreal-test-run_20260624_055244`: AIS block + `ais.csv`
  (393 rows) + `ais_cpa.png`; turning-circle **DT/Lpp 4.16 IMO PASS** + health
  **8/8** unchanged.
- **Regression (current disk):** `verify_run_kinematics` **8/8** (newest real run),
  `verify_sensors_fidelity` **8/8** (morning run), `verify_20260623` (run_demo
  end-to-end) **PASS** (5/5 + 3/3, 26.5 s).

## Lemuel — steps (≤10 min; all optional, nothing blocks on this)
1. Headless, no Unreal: `python run_demo.py --scenario head_on_transit --selftest`
   then open `logs/<run>/evidence_pack/EVIDENCE.md` — see the AIS / COLREGS table +
   `ais_cpa.png`.
2. With real UE (optional G_AIS_UE): `python run_demo.py --scenario crossing_transit`,
   Play → let it transit → Stop; the evidence pack auto-lists the crossing target +
   CPA/TCPA. (Own-ship transits; AIS targets are not drawn yet — WP-15B.)
3. The real D2 blocker is still the **HYDRO** in-engine session (rebuild +
   `DA_DOLPHIN_HydrostaticsConfig` + WaterlineOffsetCm tune) from
   `WP_20260621_HYDRO/PACKET.md` — unchanged by this packet.

## Demo-gate impact
- **D4 (real sensors):** the **AIS sub-item is now delivered + validated headless**
  — a scripted target with correct range/bearing, CPA/TCPA, and COLREGS encounter
  in the evidence pack. D4 stays **◐** (remaining: camera WP-14, UE AIS rendering
  WP-15B, live CesiumGeoreference).
- **Seeds W5-6 COLREGS scoring (§5.1):** the CPA/TCPA + rule-conformance metrics the
  V&V differentiator needs now exist and are gated.
- Honesty (KI-019 family): targets are **scripted/deterministic**, labelled as such;
  no "AIS receiver" or "validated traffic model" is claimed.

## Rollback
Delete `python/ais_traffic.py`, `python/analyse_ais.py`, and
`Development/work_packets/WP_20260624/`. Revert the five additive edits (each guarded
by a `None`/absent default — with no `--ais`/`ais=` set, every touched file behaves
byte-identically to before). Nothing on the bridge hot path or the wire changed.
