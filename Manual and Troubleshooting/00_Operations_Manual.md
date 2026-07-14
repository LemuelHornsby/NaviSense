# 00 · NaviSense Operations Manual

**Scope:** how to install, launch, drive, and read the NaviSense Simulator (UE5 build).
**Audience:** Lemuel + future collaborators/testers. **Last updated:** 12 July 2026 (WP_20260712 staleness sweep: baseline GO gate `verify_20260711.py` documented; demo-date slip noted; content verified current through the 9-Jul terminal COLREGS runner + `verify_demo_session.py` closeout). Prior: 25 June 2026.

> Golden rule: **start the Python listener first, then press Play in Unreal.** Unreal connects
> out to the listener as a TCP client. (Since WP-3 the order is forgiving — UE auto-reconnects —
> but starting the listener first is still the clean habit.)

---

## 1 · System overview

NaviSense has three parts that talk over one link:

```
  Unreal Engine 5.7 (visuals + sensors)         Python (plant + control)
  ┌─────────────────────────────┐   TCP :5005   ┌──────────────────────────┐
  │ ANaviSenseShipPawn          │  state.v1  →  │ MMG plant (DOLPHIN.yaml)  │
  │  Bridge ─ Sensors ─ Actuators│  ← sensor.v1  │ scenario / autopilot ctrl │
  │ NaviSense_Monaco level      │  newline-JSON │ python_listener.py        │
  └─────────────────────────────┘               └──────────────────────────┘
```

- **Python is authoritative** for ship motion in the parity path: it integrates the dynamics and
  sends pose (`state.v1`) to Unreal ~30 Hz. Unreal renders it and returns sensor data (`sensor.v1`) ~5 Hz.
- **Canonical run command lives at the workspace root:** `python_listener.py`.
- **Coordinate/sign convention** is owned by `NaviSense_UE5/Source/NaviSense/Core/NaviSenseCoords.h`.

---

## 2 · Prerequisites

| Need | Version / note |
|---|---|
| Unreal Engine | **5.7** (project `NaviSense_UE5/NaviSense_UE5.uproject`) |
| Visual Studio | 2022 (v14.4x toolchain) with C++ / "Game development with C++" workload — for recompiles |
| Python | 3.12 (a `.venv` in the workspace root is the convention) |
| Cesium ion token | Required for the Google Photorealistic 3D Tiles in Monaco — your own token (BYO) |
| GPU | Discrete GPU recommended (Lumen + Water + tiles are heavy) |

---

## 3 · First-time setup (once per machine)

```powershell
cd "D:\Marine Autonomy\NAVISENSE\NaviSense Simulator with Unreal Engine"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt          # numpy, pyyaml, matplotlib (+ optional autopilot extras)
```

- **Readiness check (new, WP-20260625):** `python python/repro_doctor.py` prints a clean-machine readiness verdict (deps, core-tool integrity, UE project, DA_DOLPHIN assets incl. un-pulled Git-LFS stubs, Cesium token) and writes `Saved/NaviSense_Reports/repro.json`; add `--strict` for the demo-day gate. Full clone→demo walkthrough: **`SETUP.md`** at the workspace root.

- **Cesium token:** open the project, Cesium panel → sign in / paste your ion token so the tiles stream.
- **Project build:** double-click `NaviSense_UE5.uproject`. If prompted to rebuild modules, click **Yes**.
- Confirm the module is live: open `NaviSense_Monaco`, *Tools → Execute Python Script* →
  `Content/NaviSense/Python/Phase1to3_Foundation/00_preflight_report.py` → Output Log shows
  `navisense_module_compiled: true`.

---

## 4 · Run the closed loop (the normal daily flow)

1. **Terminal** (venv active, at the workspace root):
   ```powershell
   python python_listener.py --plant mmg --controller turning_circle --target unreal --verbose
   ```
   Wait for: `Waiting for Unreal to connect on 127.0.0.1:5005 …`
2. **Unreal:** open `NaviSense_Monaco`, press **Play (PIE)**.
   - On-screen banner should read **CONNECTED** (or `RECONNECTING…` until the listener is up).
   - The DOLPHIN begins moving. The verbose terminal prints per-tick `x z yaw u rud mode`.
3. **Stop:** press **Stop** in PIE, then **Ctrl-C** the listener. Logs are flushed on exit. *(Since WP-10 the listener **re-accepts**: press **Stop** then **Play** again and it reconnects with a fresh run — no relaunch. Ctrl-C only when you're fully done; use `--once` for a single-shot run.)*

Both `-v` and `--verbose` work. `--target unreal` only affects labelling; the protocol is identical to Unity.

---

## 5 · Controllers & run recipes

All controllers run through the same command; swap `--controller`.

| `--controller` | What it does | Notes |
|---|---|---|
| `turning_circle` | 60 s straight "approach", then holds hard rudder (±35°) → carves a circle | **Best for a clear, obvious visual + sign check.** Open-loop. |
| `zigzag10` | IMO 10°/10° zig-zag after the 60 s approach | Needs heading feedback — now fed from the plant, so it always runs. |
| `zigzag20` | IMO 20°/20° zig-zag | More visible heading swings than zigzag10. |
| `demo` | Straight-ish demo sweep (sinusoidal rudder) | Quick "is it moving?" check. |
| `transit` | **Straight steady course** (constant RPM, zero rudder) | Own-ship for the **AIS / COLREGS** scenarios (head-on / crossing / overtaking) so the encounter geometry stays clean. |
| `waypoint` | LOS waypoint following | Needs `--path-file <waypoints.json>`. |
| `nmpc` | NMPC approach/docking | Needs `--goals-file` + `--active-goal`; optional `casadi`. |
| `ppo` | PPO collision-avoidance policy | Needs `--policy-file`; optional `torch`. |
| `keyboard` / `gamepad` | Manual control from the listener side | For interactive driving. |

**Important — the 60-second "approach" phase:** `turning_circle`, `zigzag10`, `zigzag20` first run
~60 s straight to reach steady speed, *then* begin the maneuver. If "nothing turns," wait past 60 s
(or speed it up with `--time-scale`). This is by design (IMO maneuver procedure), not a bug.

Useful flags: `--time-scale 10` (run 10× faster than real time), `--duration 120` (auto-stop after N real s),
`--no-log` (skip logging), `--once` (single-shot: exit after the first client — default is to re-accept so the listener survives a UE PIE Stop/Play), `--hz 30` (state send rate), `--run-id <name>` (log folder prefix),
`--wind-mps` / `--current-mps` (environment), `--plant-config DOLPHIN.yaml`,
`--sea-state 0–9` (wave-driven **heave + roll/pitch** on the hull — the hull bobs *and* rolls with a beam swell / pitches into a head swell; 0 = calm/flat), `--wave-heading-deg` (also sets which way the swell rolls vs pitches the hull), `--wave-seed` (replayable wave field), `--scenario <name>` (one-flag demo preset: controller + sea state; `--scenario list` lists them), `--sea-state-schedule "t:ss, …"` (**runtime-varying** sea — the sea builds/eases during ONE run, e.g. `"0:1, 90:4, 180:6"` = SS1 ramping to SS6; cross-faded so it's smooth; overrides `--sea-state`). `--ais <preset>` (**scripted AIS traffic** — `head_on` / `crossing` / `overtaking` / `harbor_mix` / `monaco_capture`; `--ais list` lists them; recorded in the manifest, the evidence pack then reports each target's range/bearing + **CPA/TCPA** + the **COLREGS** encounter **and a per-encounter COLREGS conformance verdict** (give-way/stand-on, Rules 8/13-17; WP-20260627) — gate D4/WP-15). **WP-15B (29 Jun):** the contacts are now also **rendered in-engine** — the listener emits each target's pose in `state.v1 traffic[]` and the pawn drives the placed *Traffic* ships. One-time setup: `Tools → Execute Python Script → Phase5_Systems/07_setup_traffic_ships.py` (Movable + tag + assign the 3 props); needs the WP-20260629B C++ rebuild. New 3-ship capture scenario: `--scenario monaco_capture`.

---

## 6 · Motion modes (on the ship pawn)

Set on `ANaviSenseShipPawn` → **MotionSource**:

- **PoseReceive** (default, parity path) — Python pose is authoritative; the hull tracks `state.v1`.
- **NativePhysics** — offline; forces from the actuator component (in development).
- **Manual** — offline; keyboard (W/S throttle, A/D rudder) or the **bridge dashboard** → actuators.
  Toggle with **`M`** at runtime (works even with the bridge connected — `bAllowManualToggleKey`).

### 6.1 · Bridge Dashboard control (WP_20260701, needs the UMG/Slate rebuild)

`ANaviSenseShipPawn` exposes three `BlueprintCallable` entry points that drive the SAME manual-drive
path as the keyboard, so a UMG widget (or any Blueprint) can helm the ship:

- `SetHelm(float Rudder01)` — `[-1,1]`, + = starboard.
- `SetThrottle(float Throttle01)` — `[-1,1]`, + = ahead.
- `SetBowThruster(float Norm01)` — `[-1,1]`, + = bow-to-starboard; works at any speed (unlike the
  rudder, which needs way — `SpeedFrac`), via a dedicated `BowThrusterMaxYawRateDeg` yaw term.

All three clamp their input and set `IsDashboardControlActive()` true; from then on `UpdateManual`
takes its throttle/rudder targets from these calls instead of polling W/S/A/D (the widget must keep
calling them every tick it's visible, e.g. from its own `Event Tick`, or the ship coasts on the last
value). Still requires `MotionSource = Manual` (press `M`) and `GM_NaviSense` as the active GameMode
(already set, KI-021) so the placed yacht is possessed.

Nineteen `BlueprintPure` getters (rudder/RPM/thruster; heading/speed/yaw-rate/roll/pitch/heave/lat/lon;
motion-mode/plant-mode/rolling-advance/peak-heading-deviation; traffic-count/nearest-range/name) feed
the dashboard's four panels — see `Documents/NaviSense_BridgeDashboard_Recipe.md` for the full getter
list, the navy theme palette, and the in-editor UMG build steps (`WBP_BridgeDashboard`). Requires a
full C++ rebuild first (`NaviSense.Build.cs` now enables `UMG`/`Slate`/`SlateCore`, previously
commented "Phase 10 — HUD").

For all bridge-driven runs, keep **PoseReceive**.

---

## 7 · Reading the outputs

**On-screen HUD / banner:** connection state (CONNECTED / RECONNECTING / STALE), and (as wired)
heading, speed, rudder, RPM, sea state.

**Logs** are written to the workspace root at:
```
logs/<run-id>_<YYYYMMDD_HHMMSS>/
  ├─ state.csv     # per-tick own-ship state (the truth record)
  ├─ sensor.csv    # inbound sensor packets from UE
  ├─ events.csv    # run_started / mode_change / run_ended marks
  ├─ manifest.json # run metadata: plantKind, controllerKind, tickHz, seaState, waveHeadingDeg, waveSeed, durations, row counts, timeBase(join key), sensorRawLines
  └─ sensor_raw.jsonl # sampled RAW sensor.v1 packets (rich blocks: ais.targets[], radar.contacts[], camera{}) — WP-20260708C
```

The active **sea state** is recorded per run in `manifest.json` (`seaState`/`waveHeadingDeg`/`waveSeed`), in the
`events.csv` `run_started` line, and as a `sea_state` column in the project-level `logs/runs.csv` index (WP-9, D3 evidence).

`state.csv` columns (authoritative for analysis):
`wall_time, t, mode, x, y, z, yawDeg, u, v, r, portRpm, starboardRpm, rudderDeg, bowThrusterNorm,
portRpmCmd, starboardRpmCmd, rudderCmdDeg, bowThrusterCmdNorm, speed_mag, rudder_error_deg, rollDeg, pitchDeg, heaveM, t_mono`
(`rollDeg/pitchDeg/heaveM` — visual 6-DOF pose, maneuvering + wave-coupled — added WP-9, 18 Jun.)

**`t_mono` (added WP-20260629, KI-024)** — a single monotonic, run-relative clock (seconds from run start) stamped by the one logger onto **both** `state.csv` and `sensor.csv` (and `events.csv`). It is the **canonical key to fuse sensor↔plant rows — join on `t_mono`, never on `t`** (sensor `t` = UE engine clock, state `t` = Python plant clock; they diverge under high PIE FPS). `manifest.json` records this in `timeBase.joinKey`.

**`sensor_raw.jsonl` (added WP-20260708C)** — a sampled raw copy of the inbound `sensor.v1` packets (every packet for the first 300, then 1-in-10 ≈ 6 Hz @ 60 fps). The flat `sensor.csv` drops the rich blocks; this file is the on-disk evidence for them. Each line is `{"wall_time":…, "t_mono":…, "msg":<wire packet, byte-intact>}`. Gate it objectively after a run:
```powershell
python python/verify_sensor_suite.py --latest            # G_AIS_SENSOR_UE + G_RADAR_UE + G_CAMERA_UE
python python/verify_sensor_suite.py --latest --require camera   # run without traffic (no AIS/radar to see)
```
PASS writes `Saved/NaviSense_Reports/sensor_suite_result.json` (TC-43). Runs made before 8 Jul 2026 have no `sensor_raw.jsonl`. `--latest` ignores `_`-prefixed log dirs (`_selftest`/`_rehearsal`).

Quick sanity reads: `mode` should leave `approach` after ~60 s for maneuver controllers; `rudderCmdDeg`
should be non-zero during a maneuver; `yawDeg`/`r` should change when rudder is applied.

**Analyse a run** (IMO KPIs + plots):
```powershell
python python\analyse_zigzag.py            # 1st/2nd overshoot angles vs IMO criteria
python python\analyse_turning_circle.py    # advance / transfer / tactical diameter
python python\analyse_actuators.py
python python\verify_run_kinematics.py    # objective run-log health gate (K1-K8); exit 0/1 for nightly
python python\verify_sensors_fidelity.py  # D4: GPS/IMU fidelity vs plant ground truth (D1-D8); add --selftest for negative controls; exit 0/1 for nightly
python python\build_evidence_pack.py      # D6: writes logs\<run>\evidence_pack\ (kpis.json + EVIDENCE.md + evidence_report.html + plots, IMO KPIs; --no-html skips the HTML)
                                          #     P0 gate (13 Jul, KI-038): refuses (exit 3) if state.csv rows < final manifest stateRows
                                          #     or manifest.json is unreadable — i.e. a stale/partial run-dir view. --allow-partial =
                                          #     watermarked forensic pack only. LIVE-run packs: always (re)build on Windows.
python python\colregs_score.py --ais head_on   # D4: COLREGS conformance verdict per encounter (give-way/stand-on, Rules 8/13-17); also surfaced IN the evidence pack when --ais is set
python run_demo.py --scenario imo_turning_circle  # D6: ONE command end to end — preflight + listener + scenario + AUTO evidence pack (add --selftest to run with NO Unreal; --list for the menu; --preflight for the env check only)
python demo_rehearsal.py                           # D6/D8: headless DEMO-READINESS rehearsal — runs the whole demo storyline (--selftest) and prints ONE DEMO READY / NOT READY verdict (--fast = 2-scenario smoke; --report-only = re-aggregate latest runs; report -> logs\_rehearsal\DEMO_READINESS.md)
python preflight_demo.py                           # DEMO GO/NO-GO — run right BEFORE the in-engine rebuild+PIE session: re-confirms rebuild-safety (Z0 + stacked link audit) AND storyline DEMO READY, prints ONE GO / NO-GO (--report-only = fastest; --full = 4-scenario). GO = headless safe to rebuild; NOT the in-engine confirm. -> Saved\NaviSense_Reports\demo_preflight_result.json
```

---

## 8 · Wire contract — quick reference

Authoritative field list: `NaviSense_UE5/Source/NaviSense/Bridge/NaviSenseBridgeTypes.h`
(`FNaviSenseState`) and the listener's `build_state_packet`.

- **Python → Unreal — `navisense.state.v1`** (~30 Hz): `t, x, y, z, yawDeg, u, v, r,
  portRpm, starboardRpm, rudderDeg, bowThrusterNorm` (+ commanded values), `mode`.
  Frame: Unity wire frame (x=East, y=Up, z=North, metres; yaw CW from North).
  - **rev 1.2 (16 Jun):** also `rollDeg` (+ = starboard-down) and `pitchDeg` (+ = bow-up) — a visual heel/trim proxy derived from motion (plant stays 3-DOF). Default 0; v1.1 receivers ignore them. Sign/axis mapping lives only in `Core/NaviSenseCoords.h` (`WireAttitudeToUE`).
  - **rev 1.3 (17 Jun):** also `heaveM` (+ = up, metres) — a deterministic sea-state wave-field vertical bob (plant stays 3-DOF; SS0 ⇒ 0), applied as a Z offset on the pawn. Enable with `--sea-state 1–9`. Sign/axis mapping lives only in `Core/NaviSenseCoords.h` (`WireHeaveToUE`).
  - **rev 1.4 (18 Jun):** the **same** `rollDeg`/`pitchDeg` keys now also carry a **wave-induced** roll/pitch from the sea-state field's surface slope, composed on top of the maneuvering heel/trim (beam swell ⇒ roll, head swell ⇒ pitch; SS0 ⇒ unchanged). **No new wire key, no DTO change** — same `Core/NaviSenseCoords.h` mapping (`WireRollToUE`/`WirePitchToUE`). Composed attitude is clamped (12° roll / 6° pitch).
  - **rev 1.5 (29 Jun, WP-15B):** optional `traffic` array — one entry per scripted AIS contact `{id, name, x, y, z, yawDeg, sogKn, cogDeg}` in the SAME wire frame as own-ship, so the pawn renders the placed *Traffic* ships with the same `NaviSenseCoords` conversion + spawn anchor. Absent by default (no schema-string bump; a no-traffic sender is byte-identical). Emitted automatically for any `--ais`/traffic scenario.
- **Unreal → Python — `navisense.sensor.v1`** (~5 Hz): `sensors.{ gps, imu, ais, camera, radar, … }`.
  GPS carries real `worldPosition`, `speed`, and **true `latDeg`/`lonDeg`** (Monaco geo-origin, `RefLatDeg/RefLonDeg` on the sim subsystem); IMU carries `headingDeg`, real `yawRateDegPerSec`, and finite-difference `acceleration`. **AIS (rev 1 Jul, WP-20260701B):** `ais.targets[]` now carries one record per scripted contact `{mmsi, name, rangeM, trueBearingDeg, relBearingDeg, cogDeg, sogKn, latDeg, lonDeg}` — identity/course/speed from the contact plus **receiver-computed** range & true/relative bearing from own-ship (empty `[]` when no traffic). This is the own-ship AIS **receiver view of scripted contacts** — not a live receiver, and `rangeM`/bearing are geometry, not the CPA/TCPA/COLREGS verdict. (WP-SENSOR-1 / WP-20260701B)
  - **Camera (rev 1 Jul, WP-20260701C):** `camera{fovDeg, resX, resY, headingDeg, frameIndex, frameRef, pose{x,y,z}}` — still-frame **capture metadata** (chase-rig pose in the wire frame + heading + FOV + 4K resolution) plus a deterministic `frameRef` (`NaviSense_00000.png` …) naming the HighResShot still on disk. **NOT** a live in-band pixel feed — a consumer joins the metadata to the PNG by `frameRef` (KI-026). Toggle `bEmitCamera` on `USensorBundleComponent`.
  - **Radar (rev 2 Jul, WP-20260702 — Sensor Suite Roadmap Pt 1, NEW scope beyond D4):** `radar{maxRangeM, sweepDeg, contacts[]}` — each contact is an **anonymous blip** `{rangeM, trueBearingDeg, relBearingDeg, radialSpeedKn, closing}` for a scripted contact within `RadarMaxRangeM` (default **22224 m = 12 NM**, full **360°** sweep). Range/bearing reuse the AIS geometry; `radialSpeedKn` is the range-rate from own (speed+heading) + target (cog/sog) velocity (**+ve = opening**, so `closing = radialSpeedKn < 0`); beyond-range contacts are dropped; no traffic ⇒ `contacts: []`. **HONESTY (KI-027):** a **geometric radar model derived from the known contact set — NOT** an EM-propagation / RCS radar simulation (no clutter, false positives, or detection of un-scripted geometry). Toggle `bEmitRadar` / `RadarMaxRangeM` on `USensorBundleComponent`. Design decisions for Radar/LiDAR/Sonar: `Documents/NaviSense_Sensor_Suite_Roadmap.md`.
- Transport: newline-delimited JSON over TCP `127.0.0.1:5005`. One JSON object per line.

---

## 9 · Shutdown / cleanup

Stop PIE first, then Ctrl-C the listener (so it flushes logs and appends to `logs/runs.csv`).
If port 5005 is "already in use," see `01_Troubleshooting_Guide.md` → Bridge.

---

## 10 · Cheat-sheet

```powershell
# activate env
.\.venv\Scripts\Activate.ps1
# obvious visual + sign check (wait past 60 s)
python python_listener.py --plant mmg --controller turning_circle --target unreal --verbose
# IMO zig-zag, 10x speed, auto-stop at 30 s real
python python_listener.py --plant mmg --controller zigzag10 --target unreal -v --time-scale 10 --duration 30
# 6-DOF water ride: turning circle in a rough sea (SS5)
python python_listener.py --plant mmg --controller turning_circle --target unreal -v --sea-state 5
# D3 runtime sea-state build: the sea grows SS1->SS6 during ONE continuous run
python python_listener.py --target unreal -v --scenario building_sea_transit
# D6 one-command demo scenario (list them all: --scenario list)
python python_listener.py --target unreal -v --scenario imo_turning_circle
# D6 ONE-COMMAND demo: preflight + listener + scenario + AUTO evidence pack on Stop (--selftest = no Unreal)
python run_demo.py --scenario imo_turning_circle
# D4/WP-15 AIS traffic + CPA/TCPA + COLREGS encounter (evidence pack lists the target + risk metrics)
python run_demo.py --scenario head_on_transit --selftest   # also: crossing_transit / overtaking_transit / harbor_traffic
python python/build_evidence_pack.py --run-dir logs/<run> --ais head_on   # add AIS analysis to ANY existing run's pack
#   ^ the pack then also scores COLREGS conformance per encounter (give-way/stand-on verdict, Rules 8/13-17); standalone: python python/colregs_score.py --run-dir logs/<run> --ais head_on (WP-20260627)
# evidence_report.html is a SINGLE self-contained file (every plot embedded as base64, 0 external refs) —
# email it / attach to a pilot proposal or grant app; it is the shareable D6 artifact. --no-html skips it (WP-20260626).
# D8 clean-machine readiness verdict (deps/tools/UE project/data-assets/LFS/Cesium token) -> repro.json; full guide = SETUP.md
python python/repro_doctor.py            # add --strict for the demo-day gate
# Demo-readiness rehearsal: run the WHOLE demo storyline headless and reduce it to one DEMO READY / NOT READY verdict (WP-20260704) — nightly drift guard for the demo (target was 11 Jul; SLIPPED — live session pending)
python demo_rehearsal.py                 # full storyline; --fast = turning-circle + head-on smoke; --report-only = aggregate the latest runs without re-running
python preflight_demo.py                 # GO/NO-GO preflight before the demo-critical PIE session (rebuild-safety + storyline READY -> one GO/NO-GO)
# TC-50 baseline GO gate (WP-20260711): Z0 16/16 + link audit + preflight GO + run-sheet currency + pytest, with 3 fixture neg-controls -> wp_20260711_result.json
python python/verify_20260711.py         # re-run any day to prove the frozen tree is still demo-ready (sandbox/CI note: needs pytest installed)
# D6/D7 capture: take >=3 4K beauty stills in PIE, then GATE them headless (WP-20260630)
python run_demo.py --scenario monaco_capture        # COLREGS traffic; or rough_turning_circle (SS5 seakeeping)
# Double-click launchers (12 Jul, for screen-driven sessions): DEMO_1..7_*.bat at the workspace root wrap the commands above
# (run_demo monaco_capture / rough_turning_circle, run_colregs x4, verify_demo_session) — same behavior, window stays open (pause).
#   ^ press Play, then in-editor: Tools > Execute Python Script > Phase5_Systems\08_capture_demo_stills.py (burst HighResShot 4K)
python python/verify_capture_artifacts.py --latest   # C1 >=3 full-res stills + C2 run kinematic-health -> PASS = G_CAPTURE_UE
# offline protocol self-test (no Unreal needed)
cd Development\bridge_harness ; python mock_listener_selftest.py   # terminal 1
python ue5_client_sim.py --seconds 8                               # terminal 2
```


## 11 · Run start position (spawn anchoring) — added 2026-06-21 (KI-020)

Bridge-driven runs now START and stay wherever `BP_ShipPawn_Yacht` is **placed in the level**, instead of snapping to the wire origin (Port Hercule). Position the yacht in open water, **save the level**, and every PIE run plays out from that location and heading. The pose is applied as an offset from the placed transform; the hull always rides the water surface (placed Z is ignored for height). Controlled by the pawn property **`Anchor Pose To Spawn`** (category *NaviSense*, default **on**). Turn it **off** only for absolute-world navigation (waypoint/NMPC autopilots that steer to fixed Monaco coordinates). Requires the C++ build that includes KI-020 (full rebuild).


## 12 · Hydrostatics (6-DOF water ride) — added 2026-06-21 (WP-20260621_HYDRO)

The yacht's heave/roll/pitch are produced by an analytic **hydrostatics** component that samples the rendered water surface and integrates the DOLPHIN buoyancy/GM/damping model — so the hull settles at the real waterline and rides waves (Python still drives X/Y/yaw). Setup: create a `NaviSenseHydrostaticsConfig` data asset (`DA_DOLPHIN_HydrostaticsConfig`, defaults already DOLPHIN) and assign it to the pawn's **Hydrostatics → Config**. Tune **WaterlineOffsetCm** so the waterline sits at the surface. Toggle **Use Hydrostatics** off on the pawn to fall back to the wire visual proxy (no recompile). Requires the build with the Water module (WP-20260621_HYDRO).


## 13b · COLREGS encounters — pick one, score compliance — added 2026-07-03 (WP-20260703)

Run a single, unambiguous COLREGS encounter (one target ship; the other two hidden) with a scripted own-ship maneuver, then read the scored verdict.

Scenarios (listener `--scenario`): `colregs_head_on` (Rule 14) · `colregs_crossing_giveway` (Rule 15, target from the starboard bow) · `colregs_crossing_standon` (Rule 17, target from the port bow, own-ship holds) · `colregs_overtaking` (Rule 13). Own-ship runs a scripted give-way (early starboard alteration) or a hold (stand-on) through its MMG model; `python/colregs_score.py` scores conformance into the evidence pack. New flag **`--initial-speed <m/s>`** gives a running start (0 = from rest; the stand-on scenario sets it so Rule-17 'keep speed' is measured on a steady vessel).

**Since WP-20260709/B (9 Jul):** the four `colregs_*` scenarios auto-select `--plant mmg`
(an explicit `--plant` wins — the kinematic stub cannot depict an avoidance maneuver). ALL four
default to ONE target ship, **`marine_rescue_boat`** (imported world-aligned — no roll fix
needed). Swap the ship per run with the listener's **`--target-name <Outliner label>`** (the
editor picker passes it automatically from its `TARGET_SHIP` setting / `pick(enc, ship=…)`);
the name + ship type flow to the wire, logs and the run manifest (`aisTargetName`). Traffic
actors keep their PLACED pitch/roll at run time (KI-034 — recompile once after pulling the fix).

**Run a scenario from the terminal (WP-20260709C — the standard flow).** One-time setup in the
editor first: Tools → Execute Python Script → `Phase5_Systems/10_colregs_encounter.py` (assigns
`marine_rescue_boat` as the driven traffic slot, scenery mode — other ships stay visible), then
save the level. After that, per scenario:
```powershell
python run_colregs.py --head-on            # or --crossing-giveway | --crossing-standon | --overtaking
#   → listener starts in THIS console; press PLAY in the editor; stop PIE to end the run
#   → the run is AUTO-VERIFIED (health + COLREGS verdict + target identity, per-scenario result file)
python run_colregs.py --head-on --ship Yacht_with_interior   # per-run ship swap
python run_colregs.py --list / --dry-run / --no-verify / --selftest   # utilities
python python/verify_colregs.py --matrix   # roll-up: all four scenarios green side by side
python python/verify_demo_session.py --film-dir "%USERPROFILE%\Videos\Captures"
#   → ONE-command SESSION closeout (WP-20260709D): sensor-suite + capture/film + COLREGS matrix
#     in one shot → Saved/NaviSense_Reports/demo_session_result.json (gates_closed / gates_failed
#     + the remaining eye-checks). --skip sensors,capture,colregs narrows; omit --film-dir to skip C3.
```
⚠ Never launch the listener from editor Python (KI-036: the editor's `sys.executable` is
UnrealEditor.exe — it opens a new editor window). Editor scripts print commands only.
Each scenario writes its own `Saved/NaviSense_Reports/colregs_<scenario>_result.json`.
After a picker session, run the picker's `reset_all()` before any 3-ship scenario
(monaco_capture / harbor_traffic) — it un-hides the ships and clears `TrafficActors`
so the pawn's tag-scan re-binds all three.

In-editor picker: **Tools → Execute Python Script → `Phase5_Systems/10_colregs_encounter.py`** with `ENCOUNTER` set (or a 4-button Editor Utility Widget — `Documents/NaviSense_COLREGS_Encounter_Recipe.md`). It hides the two unused Traffic ships, assigns the chosen ship, and launches the listener; then press **Play**. Read `logs/<run>/evidence_pack/evidence_report.html` → COLREGS conformance. Headless dry-run: `python run_demo.py --scenario colregs_head_on --selftest --plant mmg`. Honesty: scripted target + pre-planned maneuver = the conformance METRIC, not autonomous avoidance (KI-028).

## 13 · Demo capture — beauty stills & film frames — added 2026-06-30 (WP-20260630)

> **All pending in-engine gates are batched into ONE ≤20-min session** in `Development/work_packets/PENDING_EDITOR_GATES.md` (refreshed 8 Jul, WP-20260708B — **Step 0 rebuild CLEARED 7 Jul, do NOT rebuild again**): `--scenario monaco_capture` PIE (traffic + AIS/radar/camera on `sensor.v1`) → the Bridge Dashboard → demo capture + the D2 SS5 wave-ride re-check. Run `python python/verify_20260702b.py` first (**5/5+3/3**) — it audits the whole stacked C++ surface so the rebuild is expected to compile+link first try.

D6 needs ≥3 in-PIE beauty screenshots and D7 needs establishing frames. Capture is now one script + one headless gate:

1. Start a run and press **Play**: `python run_demo.py --scenario monaco_capture` (COLREGS traffic) or `--scenario rough_turning_circle` (SS5 seakeeping); also `building_sea_transit` / `storm_ride` for the sea-build reel.
2. With PIE running, **Tools → Execute Python Script → `Phase5_Systems/08_capture_demo_stills.py`**. It fires a burst of `HighResShot 3840x2160` captures on the editor tick (non-blocking — re-frame the chase cam between shots) into `Saved/Screenshots/WindowsEditor/` and writes `Saved/NaviSense_Reports/capture_manifest.json` (session start epoch + the exact verify command). Edit `SHOTS` / `INTERVAL_S` / `RESOLUTION` at the top; re-run for more.
3. Stop PIE, then gate the set headless: `python python/verify_capture_artifacts.py --latest` → **C1** ≥3 PNG stills each ≥ the byte + resolution floor (read straight from the PNG **IHDR**) and **C2** the run passes the kinematic-health gate (`verify_run_kinematics`) → **PASS** writes `Saved/NaviSense_Reports/capture_artifacts_result.json`. That is **G_CAPTURE_UE**, the objective close-out for the captured set. Useful flags: `--shots-dir <dir>`, `--run-dir logs/<run>`, `--since-epoch <epoch>` (only this session's stills — the manifest prints it), `--min-width 1920 --min-height 1080`, `--no-run-health` (shots only).

4. **D7 soft-launch film (WP-20260708B):** screen-record the same PIE runs — start **Win+Alt+R** (Game Bar; saves to `%USERPROFILE%\Videos\Captures`) or OBS *before* Play, capture the `monaco_capture` traffic beat + a `rough_turning_circle` SS5 seakeeping pass (60–90 s total), then gate everything in one command: `python python/verify_capture_artifacts.py --latest --film-dir "%USERPROFILE%\Videos\Captures"` → **C3** ≥1 valid clip (MP4/MOV structure + `mvhd` duration ≥20 s, ≥5 MB; MKV/AVI magic-checked) alongside C1/C2 = **G_FILM_UE**. Flags: `--min-films`, `--min-film-secs`, `--min-film-bytes`; `--since-epoch` restricts to this session. *Honesty: a screen recording, not an MRQ cinematic render (KI-019 family) — say "demo capture" in outward copy.*

**Before framing stills:** if the sea reads neon-cyan (as in the 29-Jun capture, with a "No Loaded Region(s)" notice), re-open `NaviSense_Monaco` so the WaterZone reloads the tuned deep-blue material and the World-Partition regions load (per the 28-Jun ocean-colour fix). The traffic-render scenarios need the WP-20260629B C++ rebuild.
