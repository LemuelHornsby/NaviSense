# NaviSense_UE5 — Current State & Next Steps

> **Status 14 Jul 2026 (WP_20260714B):** **Demo closeout Session A COMPLETE** — `verify_demo_session` **SESSION PASS** (TC-49): 28 HighResShot 3840×2160 stills + 5 demo clips ⇒ capture gate **3/3** (D6+D7), all **4 COLREGS scenarios ran live** ⇒ matrix **4/4 live**, sensors **4/4**; D2 + KI-034 eye-confirmed earlier today. Two closeout-tooling bugs found+FIXED this session — **KI-041** (film gate false-rejected moov-at-end recordings — was on the C3 critical path) + **KI-042** (COLREGS matrix crashed on a NUL-padded result), `verify_20260714b` 4/4+3/3. Burndown now **D1–D7 ✅ · D8 ◐** (only the ~30-min clean-box Session B remains): see `Documents/NaviSense_UE5_Gate_Closeout_Guide.md`.

**Project:** NaviSense Simulator (Unreal Engine 5.7) · **Owner:** Lemuel, NaviSyn Marine Solutions
**Anchor map:** `NaviSense_Monaco` · **Verified from:** `Saved/NaviSense_Reports/monaco_inventory.json`
**Last updated:** 12 July 2026 (WP_20260712 staleness sweep — catching the banner up to the tree: 8-Jul PIE run 195058 confirmed the `sensor.v1` AIS/radar/camera blocks in-engine (`verify_sensor_suite` 4/4, D4 mostly ✅); 9-Jul KI-034 fix authored in `ANaviSenseShipPawn::ApplyTraffic` (preserves each Traffic ship's PLACED pitch/roll) — **pending ONE Live Coding recompile**; demo **target was 11 Jul 2026 — SLIPPED (12 Jul):** the live session has not run yet; baseline re-proved green 12 Jul (TC-50 5/5+3/3). The ONE pending live session (`Development/work_packets/PENDING_EDITOR_GATES.md`) closes D2/D4/D6/D7.)

**Last updated (prior):** 1 July 2026 (WP-20260701: interactive Bridge Dashboard data + control layer, directed by Lemuel — `NaviSense.Build.cs` now enables `UMG`/`Slate`/`SlateCore` (Phase 10 HUD, previously commented), `ANaviSenseShipPawn` gains 19 `BlueprintPure` telemetry getters across actuators/sensors/maneuver+IMO/sea-state+AIS plus `SetHelm`/`SetThrottle`/`SetBowThruster` control entry points routed into the existing manual-drive path; `verify_20260701.py` 5/5+3/3 headless. UMG widget `WBP_BridgeDashboard` + C++ rebuild + in-engine `G_DASHBOARD_UE` eye-check pending — see PROGRESS.)

**Last updated (prior):** 28 June 2026 (WP-20260628: D5 wake VFX feed authored — speed→Niagara curve `python/wake_model.py` + pawn BlueprintPure `GetWakeIntensity01/Spray01` + `04_setup_wake_vfx.py` + `NaviSense_Wake_VFX_Recipe.md`; `verify_20260628` 6/6+3/3 with C++↔Python parity. Build NS_Wake + G_WAKE_UE eye-check pending — see PROGRESS D5 ◐)

> This is the single source of truth for where the project is **now** and what to do **next**.
> Everything here is verified against the actual `NaviSense_Monaco` level (a real actor dump), not
> inferred. For the long-term phase roadmap, see `NaviSense_UE5_Master_Development_Guide.pdf`.

---

## Status update — 14 June 2026 (read first)

> **26 Jun update (WP-20260626) — D6 evidence pack → one shareable HTML file:** `build_evidence_pack.py` now emits a **self-contained `evidence_report.html`** (every plot embedded as base64, 0 external refs; IMO-KPI table + health verdict + AIS/COLREGS + honest provenance) next to `EVIDENCE.md`/`kpis.json`; `run_demo` ships it automatically. Pure-Python (`python/evidence_html.py` formats the already-computed KPIs — no re-derive/drift; **no recompile, no schema/C++ change**). `verify_20260626.py` **6/6 + 3/3** (self-containment + IMO-KPI parity vs `kpis.json`; controls detect a corrupted image / wrong KPI / external ref). Advances **D6 ◐** (remaining = ≥3 in-PIE beauty shots / MRQ).
>
> **22 Jun update (WP-20260622) — D4 sensors validated:** the in-engine **GPS/IMU bundle is now objectively validated against the plant** by `python/verify_sensors_fidelity.py` — speed/yaw-rate/heading corr **1.0000**, GPS position = plant + spawn offset (median residual **≤0.43 m**), WGS84 geo-origin **43.7350 N / 7.4250 E** consistent. **8/8 on two real runs** (Lemuel's morning `20260622_054815` + the 21-Jun 493° turn) with **5/5 negative controls** firing. Pure-Python, read-only over `logs/`, **no recompile / no schema change / no new in-engine gate**. Advances **D4 ☐→◐** (remaining: camera WP-14, AIS WP-15, live CesiumGeoreference). Found **KI-024**: the plant-log and sensor-log use different `t` clocks (3.0× vs 1.0× wall) — join on `wall_time`.

> **18 Jun — RECOMPILE CONFIRMED (the big unlock):** Lemuel ran Live Coding on the current tree → **8/8 TUs, "Result: Succeeded"**, patch linked (UE 5.7). This is the one recompile that gated the whole in-engine queue; it builds the full week's C++ together (WP-4/5/6/7/8/9 + SENSOR-1 + ACTUATOR-RIG). **KI-016 RESOLVED, KI-015 validated.** The in-PIE gates (G7/G4/G5/C4/G_UE7/8/8+, sensors, actuator rig, WP-6 manual, WP-5 nightly) are now runnable — `Development/work_packets/PENDING_EDITOR_GATES.md`.
>
> **18 Jun update (WP-9):** **wave-coupled roll/pitch** on the existing wire — the hull now **rolls** with a beam swell and **pitches** into a head swell (not just heaves), and the active **sea state is now logged** (`manifest.json` + `runs.csv`). Pure-Python (`python/wave_response.py` projects the field's surface slope into hull attitude), composed onto the maneuvering heel/trim and riding the existing `rollDeg`/`pitchDeg` keys ⇒ **no DTO/schema change, NO new recompile** (it folds into the already-pending G_UE7/8 eye-check). Auto-verified `verify_20260618.py` **9/9**; regression re-run 16/16 + 12/12 + pytest 10/10. Advances **D2** (rolls/pitches with the sea) + **D3** (logging half). New **KI-017**: the canonical listener still lacks the WP-3 auto-reaccept the 14-Jun ledger claimed.
>
> **17 Jun update (WP-8):** 6-DOF schema **v1.3** — wave-driven **heave** + a deterministic **sea-state** field (`--sea-state 0–9`) wired to the pawn Z (demo gate **D2** heave half; seeds **D3**; plant stays 3-DOF). Water-surface sampling = F1 pt3. Auto-verified (`verify_schema_v13.py` 12/12; compile-readiness 16/16; pytest 10/10); awaiting Lemuel: recompile + heave eye-check. ⚠ KI-004 recurred (the editor file-tool truncated 6 files mid-write); all rebuilt via shell + brace-verified.
> **20 Jun update (WP-20260620):** run-log **health gate** (`verify_run_kinematics.py`, K1–K8) + the **D6 evidence-pack generator** (`build_evidence_pack.py` → `logs/<run>/evidence_pack/`: `kpis.json` + `EVIDENCE.md` + IMO-KPI plots) landed — pure-Python, **no recompile, no new in-engine gate**. Demo gate **D6 ☐→◐**. Sample pack on the 18-Jun `turning_circle` run: health **8/8**, Advance A/Lpp **4.09** + Tactical diameter DT/Lpp **4.16** (both IMO PASS). **KI-018 log-side corroboration:** that run's plant is healthy + continuous through 271° (spin is pawn-side visual only). Auto-verified `verify_20260620.py` **8/8** (negative controls fire); regression green. Awaiting Lemuel: post-recompile `turning_circle` rerun → `build_evidence_pack.py` is the D1/D6 artifact.
>
> **21 Jun update (WP-20260621):** **runtime sea-state SCHEDULE + named-scenario registry** — pure-Python, rides the existing `heaveM`/`rollDeg`/`pitchDeg` keys (**no DTO/schema change, NO recompile, no new in-engine gate**). One run now sweeps ≥3 sea states via a cross-faded `ScheduledSeaState` (`--sea-state-schedule "0:1,90:4,180:6"`), each crossing logged to `events.csv` — the **D3 runtime-switch** half (logging landed in WP-9). A `python/scenarios.py` registry + `--scenario <name>` makes a demo one flag, and the evidence pack names the scenario/schedule — the **D6 scenario-selection** half. Auto-verified `verify_20260621.py` **10/10** (negative controls fire); regression green (WP-20260620 8/8, Z0 16/16, schema-v13 12/12, WP-9 9/9, re-accept 5/5, pytest 10/10). Advances **D3** + **D6**; the in-engine smooth-build eye-check folds into the pending Session-A recompile.
>
> **16 Jun update (WP-7):** 6-DOF schema **v1.2** — heel/trim attitude wired to the pawn (demo gate **D2** attitude half; plant stays 3-DOF). Heave + water-surface sampling = F1 pt2. Awaiting Lemuel: recompile + heel eye-check. *(The 16-Jun "recompile Succeeded" Test-Log row was pre-authored 15 Jun and is unconfirmed — see KI-016.)*

The closed loop is **LIVE**: `ANaviSenseShipPawn` is placed in Monaco and driven by the Python listener over the bridge. The "immediate next steps" in §3 below are **done** (kept for reference); final sign confirmation via `turning_circle` is in progress.

Since the original (1 Jun) snapshot:

- WP-1/2/3 complete (repo hygiene, closed loop, bridge robustness); UE recompiled — the pawn auto-wires its `SensorBundle`, so packets carry heading.
- Listener fixed: zig-zag no longer stalls in 'approach' (controllers fed the plant's yaw); `-v` alias added.
- **Codebase consolidated:** this folder is now a self-contained workspace (Python stack + MMG dynamics + canonical `python_listener.py` brought in). The old `NAVISENSE` root is a backup. See `../README.md`, `../CLAUDE.md`, `../GIT_SETUP.md`, and `PROGRESS.md`.

---

## 1 · Verified current state of `NaviSense_Monaco`

The level contains **19 actors** (from the inventory dump). This is the real, confirmed scene —
all built by Lemuel before the code layer was added.

### 1.1 What's in the map

| Group | Actors present | Notes |
|---|---|---|
| **Geospatial (Cesium)** | `Google Photorealistic 3D Tiles` (Cesium3DTileset), `CesiumGeoreference`, `CesiumCameraManager`, `CesiumCreditSystemBP` | **One** tileset (Google photoreal). Georeference present at origin. |
| **Port** | `PortHercule_Monacomap` (StaticMeshActor) @ (0,0,0) | Your imported Port Hercule mesh. |
| **Vessel** | `unity_yacht_model` (StaticMeshActor) @ (20580, −23500, −310) | The DOLPHIN hull — a **plain static mesh**, not yet a pawn (see §3). |
| **Water** | `WaterBodyOcean` @ (27560, 28990, −100), `WaterZone`, `Landscape_WaterBrushManager`, `Landscape` | Ocean + zone + brush manager + landscape all present. |
| **Lighting / sky** | `DirectionalLight`, `SkyLight`, `SkyAtmosphere`, `VolumetricCloud`, `ExponentialHeightFog`, `PostProcessVolume` | Full dynamic sky + post stack. |
| **Framework** | `PlayerStart` @ (1830, 840, 92), `WorldDataLayers`, `WorldPartitionMiniMap` | World Partition enabled. |

### 1.2 Two corrections to earlier notes (now fixed in this doc)

1. **There is only ONE Cesium tileset** (Google Photorealistic 3D Tiles). Earlier drafts and the PDF
   said "two tilesets (Google + OSM Buildings)" — that is **not** true of this level. There is **no
   Cesium OSM Buildings actor** present. Plan accordingly: building shells in the hero area come from
   the photoreal tiles and your `PortHercule_Monacomap` mesh, not an OSM tileset.
2. **The yacht is a `StaticMeshActor`**, confirming it must be *replaced* by the C++ ship pawn to be
   bridge-driven (a static mesh actor cannot simply "become" a Pawn).

### 1.3 What is NOT in the level yet (gaps to fill next)
- **No bridge-driven vessel.** `unity_yacht_model` is a static prop; nothing receives Python pose.
- **No `GameMode`** set for the level (World Settings → GameMode Override = None).
- **No sensors, scenarios, traffic, HUD, or wake VFX** actors — those are later phases.

---

## 2 · What the code layer adds (compiled & ready)

A C++ module (`Source/NaviSense/`) was added and **compiles cleanly** — confirmed by
`Binaries/Win64/UnrealEditor-NaviSense.dll` and a `Result: Succeeded` build. It does **not** change
the scene; it provides classes you place/use.

| Class | What it does | Where used |
|---|---|---|
| `UNaviSenseSimSubsystem` | Run lifecycle: `RunId`, `Mode`, `GetSimTime()` (the bridge `t`). | Auto-created by engine. |
| `FNaviSenseCoords` | Unity-wire ↔ Unreal coordinate conversion (the single source of truth). | Inside bridge/sensors. |
| `UNaviSenseBridgeComponent` + `FBridgeSocketRunnable` | TCP client to `127.0.0.1:5005`; drains `state.v1` on the game thread, emits `sensor.v1`. | Component on the ship pawn. |
| `ANaviSenseShipPawn` | The own-ship; pose-receive (parity) or native/manual. Has Hull, Actuators, Bridge, Sensors, Camera. | **You place this in Monaco (§3).** |
| `UActuatorComponent` | Rudder/RPM/thruster, actual + commanded, rate-limited. | On the ship pawn. |
| `UNaviSenseVesselProfile` | Data asset: hull + actuator dynamics (DOLPHIN defaults). | Assigned to the pawn. |
| `USensorBundleComponent` | Builds the `sensors{}` JSON — **GPS/IMU validated vs plant** (WP-20260622, KI-009 ◐); camera + AIS still placeholder. | On the ship pawn. |

**Supporting (outside the engine):**
- `python_listener.py` (repo root) — the bridge **server**; now has a `--target unreal` flag
  (protocol identical to Unity; flag only affects labelling).
- `Development/bridge_harness/` — `ue5_client_sim.py` + `mock_listener_selftest.py`: a pure-Python
  bridge validator (no Unreal needed). **Verified passing**, incl. the zig-zag sign test (100%).

---

## 3 · First closed loop in Monaco — COMPLETED 14 Jun 2026

> Done: pawn placed in Monaco, driven by the listener, loop live. Steps kept for reference / re-runs.

The goal of the next session: **drive your existing DOLPHIN in `NaviSense_Monaco` with Python over
the bridge.** Because the yacht is a static mesh, you replace it with the bridge-driven pawn that
reuses the same hull mesh and the same spawn position.

### Step 1 — Confirm the module is live (1 min)
Open `NaviSense_Monaco`. **Tools → Execute Python Script… →
`Content/NaviSense/Python/Phase1to3_Foundation/00_preflight_report.py`**.
In the Output Log, confirm `navisense_module_compiled: true`.

### Step 2 — Place the ship pawn, reuse your hull + position (5 min)
1. In the **Content Browser**, navigate to where `ANaviSenseShipPawn` appears under C++ classes
   (Content Browser → Settings → *Show C++ Classes*, then folder `NaviSense → Vessel`), **or** use
   Place Actors → search "NaviSenseShipPawn".
2. **Drag it into the viewport.**
3. With it selected, in **Details → set its transform** to the yacht's current spot:
   **Location `X=20580, Y=−23500, Z=−310`** (matches `unity_yacht_model` in the inventory). Adjust Z
   up slightly if it sits low in the water.
4. **Details → Hull (StaticMeshComponent) → Static Mesh →** assign
   `/Game/NaviSense/Ships/unity_yacht_model/StaticMeshes/unity_yacht_model` (your DOLPHIN mesh).
5. **Details → Vessel Profile →** assign a `UNaviSenseVesselProfile` data asset. If none exists yet,
   create one: Content Browser → right-click → Miscellaneous → Data Asset → pick
   `NaviSenseVesselProfile` → save under `/Game/NaviSense/Settings/Vessels/DOLPHIN_VesselProfile`.
6. **Delete (or hide) the old `unity_yacht_model` static mesh actor** so there's only one yacht.
7. **File → Save** the level.

### Step 3 — Make the pawn the player & set a GameMode (3 min)
- Simplest: select the pawn → Details → **Pawn → Auto Possess Player = Player 0**. (Or create a
  GameMode with this pawn as Default Pawn — optional for now.)
- This ensures the pawn ticks and its bridge component connects on Play.

### Step 4 — Run the closed loop (2 min)
In a terminal:
```powershell
cd "D:\Marine Autonomy\NAVISENSE"
python python_listener.py --controller zigzag10 --target unreal
```
Then press **Play** in Unreal. In the Output Log you should see
`[NaviSense] bridge connected 127.0.0.1:5005`.

### Step 5 — Verify the sign (the key correctness gate)
Watch the yacht run the zig-zag. **When the rudder commands starboard, the bow must swing
starboard.** This matches what the harness already proved. If it swings the wrong way, the fix is in
**one** file — `Source/NaviSense/Core/NaviSenseCoords.h` — never patch it elsewhere.

**When Step 5 passes, the closed loop is live in Monaco** and the foundation (Phases 1–5) is truly
complete in your real scene.

---

## 4 · How to run & debug (reference)

### 4.1 The Python bridge
```powershell
python python_listener.py --target unreal                         # stub plant, demo sweep
python python_listener.py --controller zigzag10 --target unreal   # IMO zig-zag (sign test)
python python_listener.py --plant mmg --controller zigzag10 --target unreal   # full MMG dynamics
python python_listener.py --controller turning_circle --target unreal
```
Start the listener **first**, then press Play (Unreal connects out as the client).

### 4.2 The no-Unreal harness (validate the protocol anywhere)
```powershell
cd "D:\Marine Autonomy\NAVISENSE\NaviSense Simulator with Unreal Engine\Development\bridge_harness"
python mock_listener_selftest.py        # terminal 1
python ue5_client_sim.py --seconds 8    # terminal 2  -> expect ALL CHECKS PASSED
```

### 4.3 Debugging table
| Symptom | Cause | Fix |
|---|---|---|
| UE log: `bridge connect FAILED ... Is python_listener running first?` | Listener not started | Start the listener before pressing Play. |
| Yacht doesn't move but "connected" | Pawn not possessed / not ticking, or MotionSource ≠ PoseReceive | Set Auto Possess Player 0; confirm MotionSource = PoseReceive. |
| Yacht turns the **wrong way** | Coordinate sign | Fix only in `FNaviSenseCoords`; re-run the harness sign test to confirm. |
| Yacht jitters / lags | Pose smoothing | Tune `PoseLerpSpeed` on the vessel profile. |
| `00_preflight` shows `navisense_module_compiled: false` | Module not built | Rebuild from VS (Development Editor / Win64) or reopen the `.uproject` and let it compile. |
| `[WinError 10048] address already in use` | Port 5005 still held | Close the old listener / Ctrl+C the harness mock. |

---

## 5 · What's on disk now (after cleanup)

### 5.1 Kept
- **`Source/NaviSense/`** — the compiled C++ module (essential).
- **`Content/NaviSense/Python/Phase1to3_Foundation/00_preflight_report.py`** — read-only status check.
- **`Content/NaviSense/Python/Phase4_PortRealism/`** — 7 meaningful, reusable scripts:
  `02_create_substrate_masters_and_mis`, `04_place_monacomap_and_wire_tilesets`,
  `05b_water_wave_assets_patched`, `06_pcg_dock_scatter`, `10_final_material_bind`,
  `15b_manual_bollards_grounded`, `99_cesium_connectivity_test`.
- **`Content/NaviSense/Python/Phase5_Systems/`** — `01_dump_monaco_inventory` (re-run anytime to
  refresh the actor dump), `02_fix_yacht_materials`, `03_scene_health_check`.
- **`Development/bridge_harness/`** — the protocol validator.
- **`Documents/`** — this guide + the PDF master plan (long-term roadmap).

### 5.2 Removed in this cleanup
- 16 spent one-shot Phase4 diagnostic/iteration scripts (`01_inspect`, `03`/`03b`,
  `05`/`05a`/`05c`, `07`–`09`, `11`–`14b`, `15`, `16`) — their work is done (port + materials built).
- 3 redundant foundation scripts that duplicated your Monaco work (`01_create_simulatorbase_map`,
  `02_setup_ocean_and_seastate`, `03_place_ship_pawn`).
- `REMOTE_RUNBOOK.md` — superseded by this current-state guide.
- `__pycache__` caches.

### 5.3 Config fixes applied
- `*.Target.cs` build settings **V5 → V6** (made the C++ compile under UE 5.7).
- `DefaultEngine.ini` `GameDefaultMap` repaired to **`NaviSense_Monaco`** (was pointing at a
  non-existent `NaviSense_SimulatorBase`). No SimulatorBase map is needed.

---

## 6 · After the first closed loop (short roadmap)

Once Step 5 passes, the next increments (detail in the PDF master guide), each anchored to Monaco:

1. **Real sensors** — swap the placeholder `USensorBundleComponent` for real GPS (lat/lon via the
   existing `CesiumGeoreference`), IMU, AIS, then camera.
2. **Sea state on the existing ocean** — bind/confirm `WaveAsset_Calm` on the `WaterBodyOcean`
   component already in the level; add a runtime switch.
3. **HUD** — telemetry overlay reading the pawn + bridge.
4. **Scenarios & waypoints** — data-driven runs; export paths to the Python autopilots.
5. **Wake/spray VFX, cinematics, packaging** — the visualization/demo pillar.

*Maintained by NaviSyn Marine Solutions. Re-run `Phase5_Systems/01_dump_monaco_inventory.py` and
update §1 whenever the Monaco level changes materially.*
