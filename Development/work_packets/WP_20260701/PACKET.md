# WP-20260701 — Interactive Bridge Dashboard: data + control layer (WP-UI-DASHBOARD)

**Directed by Lemuel, 30 Jun 2026** (`Development/work_packets/NEXT_PACKET_DIRECTIVE.md`).
This packet ships the headless-authorable half only: BlueprintPure telemetry getters
across all four dashboard panels + interactive helm/throttle/thruster control entry
points routed into the existing manual-drive path, plus the Build.cs rebuild
prerequisite. The UMG widget graph itself (`WBP_BridgeDashboard`) is built in-editor
per the Recipe doc — Python cannot reliably script UMG widget wiring in this engine
build (same constraint as the WP-16 wake VFX recipe).

## Goal

Data + control layer for a full-screen, navy-themed, INTERACTIVE bridge dashboard:
actuators, sensors, maneuver + IMO KPIs, sea state + AIS/COLREGS — with helm/
throttle/bow-thruster controls that actually drive the ship.

## Changed files

- `NaviSense_UE5/Source/NaviSense/NaviSense.Build.cs` — `UMG`, `Slate`, `SlateCore`
  enabled in `PrivateDependencyModuleNames` (was commented "Phase 10 — HUD").
- `NaviSense_UE5/Source/NaviSense/Core/NaviSenseCoords.h` — additive: `METERS_PER_DEG_LAT`
  constant + `MetersPerDegLon`/`NorthMToLatDeg`/`EastMToLonDeg` static helpers (the
  same flat-earth projection `SensorBundleComponent` already uses inline, now
  available to a second caller). `SensorBundleComponent.cpp` itself is **untouched**.
- `NaviSense_UE5/Source/NaviSense/Vessel/NaviSenseShipPawn.h` — 19 new `BlueprintPure`
  getters across the four panels + 3 `BlueprintCallable` control entry points
  (`SetHelm`, `SetThrottle`, `SetBowThruster`) + `IsDashboardControlActive()` +
  `BowThrusterMaxYawRateDeg` + the backing private state.
- `NaviSense_UE5/Source/NaviSense/Vessel/NaviSenseShipPawn.cpp` — getter bodies;
  `ApplyOwnShipState` now stamps `LastPlantMode`; `Tick` calls a new
  `UpdateManeuverTelemetry()` (rolling advance/overshoot proxies); `UpdateManual`
  now sources `ThrTarget`/`RudTarget` from the dashboard commands when
  `bDashboardControlActive`, adds a bow-thruster yaw term, and carries the
  bow-thruster command into `FActuatorState.bowThrusterNorm`.
- **New** `python/verify_20260701.py` — the headless data+control gate (below).
- **New** `NaviSense_UE5/Content/NaviSense/Python/Phase5_Systems/09_build_bridge_dashboard.py`
  — editor-Python build helper (prints the theme + binding list, best-effort
  creates the `WBP_BridgeDashboard` asset stub).
- **New** `Documents/NaviSense_BridgeDashboard_Recipe.md` — the manual UMG
  build/binding/control-wiring recipe (mirrors `NaviSense_Wake_VFX_Recipe.md`).

**No DTO/wire/schema change** — `FNaviSenseState` keeps its 22 wire keys (Z0 B1 stays
16/16 as part of the same 16-check gate); no existing tested `.cpp` (e.g.
`SensorBundleComponent.cpp`) was edited.

## Invariants respected

1. Coordinate/yaw-sign conversion additions (geo-projection helpers) live in
   `NaviSenseCoords.h` only.
2. The bridge RX thread is untouched — the dashboard reads game-thread state only.
3. No DTO field added; wire-key parity unchanged.
4. Vessel tuning stays in the data asset; `BowThrusterMaxYawRateDeg` is a new
   `EditAnywhere` tunable on the pawn, consistent with existing manual-drive tunables.
5. Scenario controllers still fed the plant's authoritative yaw — unaffected.

## Lemuel's in-editor/terminal steps (≤20 min)

1. **Full C++ rebuild** (editor closed, `Build.bat`; Live Coding is not reliable for
   module-dependency changes — KI-018 process lesson). Confirm `Z0` still green.
2. `Tools > Execute Python Script… > 09_build_bridge_dashboard.py`.
3. Follow `Documents/NaviSense_BridgeDashboard_Recipe.md` §4 to lay out
   `WBP_BridgeDashboard` (4 panels, navy theme, bind getters, wire helm/throttle/
   thruster sliders to `SetHelm`/`SetThrottle`/`SetBowThruster`), add it to the
   viewport, bind a toggle key.
4. In PIE: press `M` for Manual, toggle the dashboard, confirm all four panels show
   live values and the sliders turn the rudder / change RPM+speed / yaw the ship at
   rest (`G_DASHBOARD_UE`).

## Acceptance gates

- **Headless (this run):** `python python/verify_20260701.py` — **5/5 gates + 3/3
  negative controls, PASS** (see below).
- **In-engine `G_DASHBOARD_UE`** (Lemuel, ≤20 min, per steps above) — **PENDING**.

### Gate detail (`wp_20260701_result.json`)

- G1 `dashboard_getters_present` — all 19 required getters declared `BlueprintPure`
  across the 4 panels.
- G2 `control_entry_points_clamped` — `SetHelm`/`SetThrottle`/`SetBowThruster` each
  clamp to `[-1,1]` and mark `bDashboardControlActive`.
- G3 `manual_drive_mirrors_dashboard` — `UpdateManual` sources its throttle/rudder
  targets from the dashboard commands when active, the bow-thruster yaw term is
  wired, and the bow-thruster command reaches `FActuatorState.bowThrusterNorm`.
- G4 `build_cs_umg_enabled` — `UMG`/`Slate`/`SlateCore` active (not commented).
- G5 e2e — `Z0` compile-readiness **16/16**; navy-theme palette byte-parity between
  the editor script and the recipe doc; geo-projection constant parity between the
  new `NaviSenseCoords.h` helper and `SensorBundleComponent.cpp`'s existing literal.
- **3/3 negative controls fire**: N1 a commented-out UMG dep is caught; N2 an
  un-clamped control body is caught; N3 a removed getter is caught AND named.

## Rollback

Fully additive except the 3 anchored edits inside `NaviSenseShipPawn.cpp`
(`ApplyOwnShipState` tail, `Tick` tail, `UpdateManual` head/yaw/state-fill) and the
one-line `Build.cs` uncomment. `git diff` these 4 files to review; revert by
restoring the prior `NaviSense.Build.cs` HUD-deps comment and removing the
Dashboard block from `NaviSenseShipPawn.h`/`.cpp` (clearly delimited by the
"Bridge Dashboard data + control layer" banner comments). No other file touched.

## Honesty (KI-019 family)

Live maneuver/IMO panel values are rolling kinematic proxies, not the post-run
CFD-validated evidence-pack KPIs; AIS range is geometry only, not the logged
CPA/TCPA/COLREGS verdict; wake/attitude remain visual proxies. The Recipe doc §6
and the widget itself must label these.

- gates 5/5 auto + 3/3 controls + 1 in-engine (`G_DASHBOARD_UE`, needs C++ rebuild)
- evidence `wp_20260701_result.json`
- authored via shell (KI-004), Z0/AST-verified.
