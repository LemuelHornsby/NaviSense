# NaviSense UE5 — Analytical Review & Strategic Assessment

> **Status 14 Jul 2026 (WP_20260714B):** **Demo closeout Session A COMPLETE** — `verify_demo_session` **SESSION PASS** (TC-49): 28 HighResShot 3840×2160 stills + 5 demo clips ⇒ capture gate **3/3** (D6+D7), all **4 COLREGS scenarios ran live** ⇒ matrix **4/4 live**, sensors **4/4**; D2 + KI-034 eye-confirmed earlier today. Two closeout-tooling bugs found+FIXED this session — **KI-041** (film gate false-rejected moov-at-end recordings — was on the C3 critical path) + **KI-042** (COLREGS matrix crashed on a NUL-padded result), `verify_20260714b` 4/4+3/3. Burndown now **D1–D7 ✅ · D8 ◐** (only the ~30-min clean-box Session B remains): see `Documents/NaviSense_UE5_Gate_Closeout_Guide.md`.

**Project:** NaviSense Simulator (Unreal Engine 5.7) · **Owner:** Lemuel, NaviSyn Marine Solutions
**Prepared by:** Claude (co-developer) · **Date:** 11 June 2026
**Scope:** The Unreal build (`NaviSense_UE5`), assessed against the full repository heritage (Unity build, Python stack, CFD program) and against the marine-autonomy industry as of June 2026.
**Companion document:** `NaviSense_UE5_Master_Execution_Plan.md` (the how/when; this document is the what/why).

---

## Status update — 14 June 2026 (read first)

> **12 Jul 2026 update (WP_20260712) — demo date SLIPPED, tree frozen-green:** the 11 Jul target passed without the live session (no PIE since 8 Jul, film dir empty; Step-0 KI-034 Live Coding recompile pending). No product change; TC-50 baseline re-proved 5/5+3/3 on 12 Jul (`wp_20260712_result.json`). The freeze holds — the next action is Lemuel's ONE live session (`PENDING_EDITOR_GATES.md`, Steps 0→1→3→5→6, ends `verify_demo_session.py`), which alone closes D2/D4/D6/D7.
>
> **28 Jun update (WP-20260628) — D5 wake & spray VFX feed (first in-engine packet in a week):** the wake is
**driven by speed** (the hull is kinematically posed — no fluid sim, KI-025): a Niagara system reads two 0..1
user floats (`WakeIntensity`/`Spray`) and scales bow wave / stern wash / spray. Shipped the whole authorable
stack — the curve (`python/wake_model.py`), a minimal additive C++ feed (kinematics getters → `UFUNCTION(BlueprintPure)` + `GetWakeIntensity01/Spray01` mirroring the Python exactly; no wire/schema change,
Z0 16/16), the attach script + the build recipe (with a no-recompile fallback), and the gate
(`verify_20260628.py` **6/6 + 3/3**, C++↔Python curve parity). Advances **D5 ☐→◐** and unblocks **D7** (the
film needs a wake); remaining = the NS_Wake Niagara art + the in-engine **G_WAKE_UE** eye-check. New **TC-29**,
new **KI-025** (honesty: speed-responsive visual proxy, not a CFD wake).

> **22 Jun update (WP-20260622) — D4 sensors validated:** the in-engine **GPS/IMU bundle is now objectively validated against the plant** by `python/verify_sensors_fidelity.py` — speed/yaw-rate/heading corr **1.0000**, GPS position = plant + spawn offset (median residual **≤0.43 m**), WGS84 geo-origin **43.7350 N / 7.4250 E** consistent. **8/8 on two real runs** (Lemuel's morning `20260622_054815` + the 21-Jun 493° turn) with **5/5 negative controls** firing. Pure-Python, read-only over `logs/`, **no recompile / no schema change / no new in-engine gate**. Advances **D4 ☐→◐** (remaining: camera WP-14, AIS WP-15, live CesiumGeoreference). Found **KI-024**: the plant-log and sensor-log use different `t` clocks (3.0× vs 1.0× wall) — join on `wall_time`.

> **18 Jun — RECOMPILE CONFIRMED (the big unlock):** Lemuel ran Live Coding on the current tree → **8/8 TUs, "Result: Succeeded"**, patch linked (UE 5.7). This is the one recompile that gated the whole in-engine queue; it builds the full week's C++ together (WP-4/5/6/7/8/9 + SENSOR-1 + ACTUATOR-RIG). **KI-016 RESOLVED, KI-015 validated.** The in-PIE gates (G7/G4/G5/C4/G_UE7/8/8+, sensors, actuator rig, WP-6 manual, WP-5 nightly) are now runnable — `Development/work_packets/PENDING_EDITOR_GATES.md`.
>
> **18 Jun update (WP-9):** **wave-coupled roll/pitch** on the existing wire — the hull now **rolls** with a beam swell and **pitches** into a head swell (not just heaves), and the active **sea state is now logged** (`manifest.json` + `runs.csv`). Pure-Python (`python/wave_response.py` projects the field's surface slope into hull attitude), composed onto the maneuvering heel/trim and riding the existing `rollDeg`/`pitchDeg` keys ⇒ **no DTO/schema change, NO new recompile** (it folds into the already-pending G_UE7/8 eye-check). Auto-verified `verify_20260618.py` **9/9**; regression re-run 16/16 + 12/12 + pytest 10/10. Advances **D2** (rolls/pitches with the sea) + **D3** (logging half). New **KI-017**: the canonical listener still lacks the WP-3 auto-reaccept the 14-Jun ledger claimed.
>
> **21 Jun update (WP-20260621):** **runtime sea-state SCHEDULE + named-scenario registry** — pure-Python, rides the existing `heaveM`/`rollDeg`/`pitchDeg` keys (**no DTO/schema change, NO recompile, no new in-engine gate**). One run now sweeps ≥3 sea states via a cross-faded `ScheduledSeaState` (`--sea-state-schedule "0:1,90:4,180:6"`), each crossing logged to `events.csv` — the **D3 runtime-switch** half (logging landed in WP-9). A `python/scenarios.py` registry + `--scenario <name>` makes a demo one flag, and the evidence pack names the scenario/schedule — the **D6 scenario-selection** half. Auto-verified `verify_20260621.py` **10/10** (negative controls fire); regression green (WP-20260620 8/8, Z0 16/16, schema-v13 12/12, WP-9 9/9, re-accept 5/5, pytest 10/10). Advances **D3** + **D6**; the in-engine smooth-build eye-check folds into the pending Session-A recompile.
>
> **17 Jun update (WP-8):** 6-DOF schema **v1.3** — wave-driven **heave** + a deterministic **sea-state** field (`--sea-state 0–9`) wired to the pawn Z (demo gate **D2** heave half; seeds **D3**; plant stays 3-DOF). Water-surface sampling = F1 pt3. Auto-verified (`verify_schema_v13.py` 12/12; compile-readiness 16/16; pytest 10/10); awaiting Lemuel: recompile + heave eye-check. ⚠ KI-004 recurred (the editor file-tool truncated 6 files mid-write); all rebuilt via shell + brace-verified.
>
> **16 Jun update (WP-7):** 6-DOF schema **v1.2** — heel/trim attitude wired to the pawn (demo gate **D2** attitude half; plant stays 3-DOF). Heave + water-surface sampling = F1 pt2. Awaiting Lemuel: recompile + heel eye-check. *(The 16-Jun "recompile Succeeded" Test-Log row was pre-authored 15 Jun and is unconfirmed — see KI-016.)*

This review was written 11 June 2026. The analysis below stays valid as context; current state:

- **Closed loop is LIVE** in `NaviSense_Monaco` — the DOLPHIN is driven by `python_listener.py`. Demo gate **D1 essentially achieved** (final sign confirmation via `turning_circle` in progress).
- **WP-1/2/3 complete:** repo hygiene, closed loop, bridge robustness (auto-reconnect, stale-hold, non-blocking send). UE recompiled — pawn auto-wires its sensor bundle so packets carry heading.
- **Listener bug fixed:** zig-zag stalled in 'approach' (needed a sensor heading the placeholder didn't supply); controllers are now fed the plant's authoritative yaw. `-v` alias added.
- **Codebase consolidated:** `NaviSense Simulator with Unreal Engine/` is now self-contained (Python + MMG + canonical listener brought in); old `NAVISENSE` root = backup. See `../README.md`, `../CLAUDE.md`, `../GIT_SETUP.md`.
- **Findings:** F3 RESOLVED (WP-3). F2 PARTIAL (sensor heading wired; full GPS/IMU/camera pending). F8 PARTIAL (hygiene + LFS config done; off-machine remote still pending — `GIT_SETUP.md`).
- **Next:** WP-4 deterministic clock (F5), then 6-DOF schema v1.2 + water sampling (F1) and real sensors (F2).

---

## 1 · Executive summary

NaviSense is further along than a single-developer project has any right to be. The Unity build proved the entire product concept end-to-end: a full synthetic sensor suite, MMG maneuvering dynamics in Python, NMPC and PPO autopilots, COLREGS traffic, scenarios, replay, and logging. The UE5 build inherits that proven architecture and adds the two things Unity could not deliver at this quality bar: photoreal georeferenced real-world ports (Cesium + Google Photorealistic 3D Tiles over Monaco and Long Beach) and a AAA rendering/physics platform. The ~1,000-line C++ module is small but unusually clean — correct threading discipline, a single source of truth for coordinate conversion, and a wire protocol already validated by an offline harness.

The strategic timing is exceptional. The IMO adopted the first global MASS Code in May 2026; it takes voluntary effect on **1 July 2026 — twenty days from today** — with an Experience-Building Phase beginning December 2026 and a mandatory code targeted for adoption by 2030 (entry into force 2032). Every autonomy developer, classification society, and flag state now needs *simulation-based evidence* of safe behavior, and the research community has a documented shortage of labeled maritime perception data. NaviSense's specific combination — CFD-validated maneuvering physics + photoreal real ports + synthetic sensors + COLREGS scenario testing, all driven from plain Python over an open JSON bridge — does not exist today in any open-source or mid-market product. That is the differentiator to build toward.

The honest counterweight: the UE5 build has not yet closed the loop in-engine (Phase A is staged but unexecuted), the wire protocol is 3-DOF and cannot express the "high physics" visual goal (no roll/pitch/heave), sensors are placeholders, and the development process itself is the biggest risk — one commit of git history, no off-machine backup, no automated in-engine tests, and every editor action done by hand. Sections 5–6 turn each of these into ranked, actionable improvement areas; the Master Execution Plan sequences them.

---

## 2 · Verified current state

### 2.1 What exists and works (evidence-based)

| Layer | State | Evidence |
|---|---|---|
| **UE5 project shell** | UE 5.7, Water/WaterAdvanced/Buoyancy/PCG/MRQ/PythonAutomationTest/Cesium plugins enabled | `NaviSense_UE5.uproject` |
| **Monaco level** | 19 actors verified by live dump: Google Photorealistic 3D Tiles + CesiumGeoreference, Port Hercule hero mesh, WaterBodyOcean + WaterZone, full sky/lighting/post stack, World Partition | `Saved/NaviSense_Reports/monaco_inventory.json`, Component Guide §1 |
| **Long Beach level** | Map + port materials/static mesh exist; **not** inventoried or verified | `Content/NaviSense/Maps/NaviSense_Longbeach.umap` |
| **C++ module** | Compiles clean under 5.7 (V6 targets). Bridge (TCP client + SPSC thread), coords, sim subsystem, ship pawn, actuators, sensor stub — 974 lines | `Source/NaviSense/`, `Binaries/Win64/UnrealEditor-NaviSense.dll` |
| **Wire protocol v1.1** | `state.v1` in (20–50 Hz), `sensor.v1` out (~5 Hz), newline-delimited JSON over TCP :5005 | `NaviSenseBridgeTypes.h`, `Documents/BRIDGE_SCHEMA.md` |
| **Offline validation** | Pure-Python harness passes all checks incl. zig-zag sign test (100%) — protocol proven without Unreal | `Development/bridge_harness/` |
| **Python plant/control stack** | MMG plant adapter, stub plant, zigzag/turning-circle controllers, PID/LOS/NMPC/PPO autopilots + PPO training env, run logger, analysis scripts | `python_listener.py`, `python/`, `python/autopilot/` |
| **Editor automation pattern** | Proven: Phase 4 port-realism and Phase 5 inventory/health scripts built/cleaned the Monaco scene via editor Python | `Content/NaviSense/Python/` |
| **Unity heritage (parity reference)** | Full sensor suite (GPS/IMU/AIS/camera/radar/LiDAR/sonar), actuator rig, hydrostatics (Crest), COLREGS traffic brain, scenarios, waypoints, replay, HUD, wake VFX | `NaviSense Simulator/Assets/Scripts/` |
| **Physics validation program** | StarCCM+ captive CFD tests targeting MMG coefficients for the DOLPHIN hull (in progress) | `Model tests/CFD/` |
| **Documentation** | Component Guide (current-state, 1 Jun 2026), 45-page Master Development Guide (Phases A–K), 23-page tech-spec/business roadmap | `Documents/`, root `Documents/` |

### 2.2 What is NOT yet true in UE5

**Update (14 Jun 2026): the foundation is now live** — `ANaviSenseShipPawn` is placed in Monaco and driven by `python_listener.py` over the bridge (the closed loop runs; final sign confirmation in progress). The original assessment read: The yacht in Monaco is a static prop; `ANaviSenseShipPawn` has never been placed, possessed, and driven by `python_listener.py` in-engine. The in-engine zig-zag sign test — the single gate that proves the foundation — has not been run. Everything downstream (sensors, sea states, traffic, HUD, cinematics) is design-complete on paper (Master Guide Phases B–K) but unbuilt.

---

## 3 · Code-level review of the UE5 module

### 3.1 Strengths worth protecting

These are genuinely good engineering decisions; the execution plan treats them as invariants:

1. **Threading discipline.** The receive thread does pure byte/JSON work and hands complete lines to the game thread via an SPSC queue; UObjects are never touched off-thread (`BridgeSocketRunnable.h` states the rule; the code follows it). This is the pattern that prevents the class of crash that kills most homemade socket integrations.
2. **One conversion authority.** `FNaviSenseCoords` is the only place Unity-wire ↔ Unreal mapping lives, with the zig-zag sign test as its contract and an explicit "never patch the sign elsewhere" rule. This discipline already caught and prevented the most common cross-engine porting bug.
3. **Wire-named DTOs.** `FNaviSenseState` field names match JSON keys exactly, so `FJsonObjectConverter` does the mapping with zero translation code to maintain.
4. **Data-asset tuning.** `UNaviSenseVesselProfile` keeps hull/actuator dynamics editable without recompiles — the right shape for a multi-vessel future.
5. **Harness-first validation.** Proving the protocol with `mock_listener_selftest.py` + `ue5_client_sim.py` before touching the engine de-risked Phase A almost completely.
6. **Docs that match reality.** The Component Guide is anchored to a live actor dump, corrects its own earlier errors, and the cleanup of 19 spent scripts shows real hygiene.

### 3.2 Findings (file-specific)

Ranked by how much they constrain the "high visuals, high physics" goal. F-numbers are referenced throughout the execution plan.

**F1 — The wire protocol is 3-DOF; "high physics" needs 6-DOF.** `FNaviSenseState` carries x, y, z, yawDeg, u, v, r only. No roll, pitch, or heave — so even a perfect MMG plant can only ever slide the hull around a flat plane. The pawn's Tick hard-codes `Loc.Z = TargetLocation.Z + FreeboardCm` (`NaviSenseShipPawn.cpp`), meaning the hull cannot ride waves, heel into turns, or pitch into head seas. This is the single biggest gap between the current build and the stated visual/physics ambition. *Fix: bridge schema v1.2 with rollDeg/pitchDeg (+ optionally heave) from the plant, blended with local water-surface sampling for wave-induced motion. Spec sketched in the execution plan §6.*

**F2 — Sensors are placeholders.** **[PARTIAL 14 Jun 2026 — SensorBundle auto-wired; full models pending.]** `SensorBundleComponent.cpp` emits zeroed lat/lon, `speed: 0.0`, zeroed IMU rates/accels, and an empty AIS array. The Unity build's seven real sensors are the parity bar. GPS lat/lon is nearly free in UE5 — `CesiumGeoreference` converts engine coordinates to WGS84 directly — which makes this high-value, low-cost. Camera/radar/LiDAR are where UE5 should *exceed* Unity (scene captures with auto-labeling, GPU LiDAR), because that is the synthetic-data product (§5).

**F3 — The bridge cannot recover.** **[RESOLVED 14 Jun 2026 — WP-3.]** `Connect()` tries once at BeginPlay; if the listener isn't up first, you must restart PIE. There is no reconnect/backoff, no heartbeat, no stale-data timeout (if Python dies, the pawn glides on forever using the last target), and `SendSensorPacket()` does a blocking `Socket->Send` on the game thread (a stalled peer = frame hitches). Small fixes, big robustness gain.

**F4 — Native-physics and manual modes are stubs.** `ENaviSenseMotionSource::NativePhysics/Manual` exist but Tick has no force path and `SetupPlayerInputComponent` is empty. The Buoyancy plugin is enabled in the uproject but nothing references it. Consequence: the simulator currently *requires* Python running to show anything moving — bad for demos, packaging, and resilience. A minimal in-engine fallback (buoyancy + simple thrust/rudder forces + keyboard) is needed.

**F5 — The sim clock is wall-clock.** `UNaviSenseSimSubsystem::GetSimTime()` returns `FPlatformTime::Seconds() - StartTimeSeconds`. PIE pauses, editor hitches, and frame spikes all corrupt `t`; nothing is fixed-step on the engine side. Determinism and replay (a core product claim for V&V evidence — §4) need a tick-accumulated sim clock, run-scoped, with the plant remaining the stepping authority.

**F6 — No UE-side logging or replay.** Unity has `ReplayManager` + run logging; UE5 has nothing yet. The Python `RunLogger` captures the wire truth, which is the right foundation — but in-engine capture (screenshots, camera frames, event marks) and deterministic replay of a logged run are needed for the evidence-pack product.

**F7 — Zero automated tests in-engine.** The `PythonAutomationTest` plugin is enabled but unused; there are no Automation Spec C++ tests, no functional test maps, and the excellent offline harness covers only the protocol. Nothing currently prevents a regression that compiles fine but breaks the sign convention, the JSON contract, or actor wiring. This compounds with—

**F8 — Version control is one commit, no remote, no LFS.** **[PARTIAL 14 Jun 2026 — hygiene+LFS done; remote pending, see GIT_SETUP.md.]** The entire UE5 work sits in a single local commit (1 June 2026) with **no off-machine backup**. A disk failure today loses the project. The UE5 `.gitignore` is good (Binaries/Saved/Intermediate/Cesium cache correctly excluded), but FBX/uasset binaries need Git LFS, and the repo root has no `.gitignore` (the Unity `Library/` folder would be catastrophic to track accidentally). This is the highest-severity *process* finding in the review.

**F9 — Google Photorealistic 3D Tiles: licensing and quality limits.** The hero realism currently leans on Google's photoreal tileset. Two constraints: (a) commercial-use and offline-caching terms need verification before NaviSense ships as a product or renders marketing footage — the 675 MB request cache is machine-local convenience, not a redistribution right; (b) photogrammetry melts at close range, especially at the waterline where your camera lives. The Port Hercule hero mesh is the correct mitigation pattern — extend it (hero waterfront band + tiles for background) and keep a Cesium World Terrain + OSM fallback profile.

**F10 — Sea-state system not yet real.** WaterBodyOcean exists with default waves; there is no runtime sea-state switch, no spectrum-mapped presets (calm → rough), no wind/current model in UE5, and buoyancy/visual motion don't sample the actual displaced surface yet. The Water plugin's Gerstner-style waves are fine visually but the *parameters* should be set from named sea states (Beaufort/Douglas scale presets) so scenarios are reproducible and reportable.

**F11 — Single vessel, no traffic.** Unity's `ColregsBrain`/`AITrafficVessel`/`TrafficProfile` logic exists as reference; UE5 has no traffic actor, and AIS (F2) has nothing to report. COLREGS scenarios are the core of the V&V product (§5), so the port of this logic is on the critical path — but *after* the closed loop and sensors.

**F12 — No performance baseline or budget.** Photoreal tiles + Lumen + Water + Niagara will fight for frame time. No `stat`/Insights captures exist, no target (e.g., 60 fps at 1440p on the dev GPU) is written down, and packaging (Phase K) has never been attempted — cook failures tend to surface late and ugly. A weekly automated perf snapshot prevents drift.

**F13 — Long Beach is unverified.** Second port exists as assets but no inventory, no health check, no closed-loop test. Fine to defer — but it should either be brought into the verified set or explicitly parked to stop it silently rotting.

**F14 — Level framework gaps.** No GameMode override set; pawn possession will be manual (Auto Possess Player 0) in Phase A. Trivial, already in the Component Guide's runbook — listed for completeness.

---

## 4 · Industry research: the critical need (June 2026)

### 4.1 The regulatory clock just started ticking

The IMO adopted the **first global MASS Code** at MSC 111 (May 2026). It is non-mandatory and takes effect **1 July 2026** for cargo ships, with an Experience-Building Phase (EBP) to be framed at MSC 112 in December 2026, a mandatory code targeted for adoption by ~1 July 2030, and entry into force on 1 January 2032. The code is goal-based: autonomous and remotely operated ships must demonstrate safety equivalent to a conventional ship.

What that means concretely: between now and 2030, every MASS developer, operator, flag state, and class society participating in the EBP needs **evidence** — repeatable, documented demonstrations that an autonomy stack behaves safely across nominal and degraded scenarios. Physical trials are slow, expensive, weather-bound, and can't safely produce near-collision data. Classification societies have already converged on the answer: DNV's published position is that assurance of autonomous navigation requires *large-scale, systematic simulation-based testing* against a digital twin, with COLREGs-compliance-based evaluation, and DNV maintains a recommended practice (RP-0513) for assuring the simulation models themselves. Simulation is becoming the *regulated instrument*, not a convenience.

### 4.2 The market is real and the buyers are funded

Autonomous-shipping market estimates for 2026 cluster around **$6–9B** with ~6–11% CAGR projections through the early 2030s. The defense segment moves faster: USV-specific defense forecasts run at ~17% CAGR, the U.S. Navy merged its large/medium USV efforts into the MASC program with prototyping in FY2026, and DoD allocated ~$1.1B to unmanned maritime RDT&E in FY2025. On the commercial side, situational-awareness and autonomy retrofit vendors are well capitalized — Orca AI raised a $72.5M Series B (May 2025, $111M total; 1,200+ vessels), and Avikus (HD Hyundai) and Sea Machines continue to commercialize. Every one of these autonomy stacks needs somewhere to be tested, and every perception model they train needs data.

### 4.3 The perception-data shortage is documented

The maritime-AI literature in 2025–26 repeatedly flags scarcity of labeled maritime imagery, class imbalance, and regional bias as the limiting factor for ship detection/tracking models — and shows that **synthetic data from high-fidelity simulation measurably closes the gap** (one 2025 study reports >28% improvement over the best real-data baseline when training with simulation-generated maritime imagery; multiple pipelines now combine 3D virtual environments with GAN-based domain transfer). A photoreal, georeferenced, sensor-instrumented simulator is precisely the machine that manufactures this data — with free, perfect labels.

### 4.4 Who else is in the arena (and the gap NaviSense fits)

**Open-source research sims** — Stonefish, HoloOcean (UE-based), MARUS (Unity), DAVE, UNav-Sim: strong on underwater robotics, ROS integration, and sonar; weak on *surface-vessel* photorealism, validated maneuvering hydrodynamics (none ship CFD-derived MMG coefficients), real-world georeferenced ports, and COLREGS scenario tooling. None are products; all are papers with repos.

**Enterprise V&V platforms** — Applied Intuition's Axion entered maritime via defense (adopted by Saronic, Scientific Systems, U.S. Navy/DIU/CDAO; EpiSci acquisition), bringing automotive-grade scenario-based testing to vessels. It validates the category NaviSense plays in — and it is enterprise/defense-priced, closed, and inaccessible to the universities, labs, and autonomy startups in your chosen wedge.

**Training simulators** — Kongsberg K-Sim, Wärtsilä NTPRO, Force SimFlex: certified for *crew* training, not built for *algorithm* development; no Python-in-the-loop APIs, no synthetic-data export, no CI-friendly headless operation; six-figure price points.

**The gap (the differentiator):** an *accessible, developer-first* marine autonomy simulator that combines (1) photoreal georeferenced **real ports** where docking/approach incidents actually happen, (2) **CFD-validated MMG physics** with IMO-standard maneuver KPIs (zig-zag overshoots, turning-circle advance/transfer) as shippable evidence, (3) a **full synthetic sensor suite with auto-labeled data export**, and (4) **COLREGS scenario library + compliance scoring** for repeatable V&V — all controlled from ordinary Python over an open JSON bridge (ROS2 later). Nobody serves that combination below the enterprise tier. The MASS-Code EBP window (2026–2030) is the adoption runway.

### 4.5 Implication for build priorities

The wedge (autonomy devs & researchers) re-ranks the Master Guide's phases. Sensors-with-export, scenario/COLREGS tooling, determinism/logging, and headless operation move *up* (they are the product); cinematics and HUD polish move to demo-support roles (they sell the product). The execution plan encodes this re-ranking.

---

## 5 · The differentiator, stated precisely

> **NaviSense is the evidence-grade marine autonomy simulator: CFD-validated vessel physics, photoreal real-world ports, auto-labeled synthetic sensors, and scored COLREGS scenarios — driven from plain Python, runnable headless, priced for the people actually building marine autonomy.**

Four pillars, each with a moat property:

1. **Validated physics, not pretty physics.** The Model tests/CFD → MMG coefficient pipeline + automated IMO maneuver reports is something no open-source sim and no game-engine demo can claim. "Our turning circle matches our CFD captive tests" is a sentence competitors can't say.
2. **Real ports, not abstract water.** Cesium-georeferenced Monaco/Long Beach means scenarios carry real chart coordinates — outputs are lat/lon tracks a naval architect or port authority can overlay on an ENC. (Mind F9 licensing.)
3. **Sensor data with free labels.** Every camera frame ships with perfect bounding boxes/segmentation; every radar/AIS return has ground truth. Domain randomization (time of day, sea state, weather) multiplies dataset value — directly attacking the documented data shortage (§4.3).
4. **Open control plane.** Newline-JSON over TCP that a grad student can speak from a 30-line script (already true today — the harness proves it). This is the adoption wedge against closed enterprise tools.

---

## 6 · Ranked improvement areas

**P0 — Existential / unblocks everything (week 1):**
- Execute Phase A: pawn in Monaco, possessed, driven by `python_listener.py`, in-engine zig-zag sign test passed (the Component Guide's Steps 1–5).
- Repo safety: private remote + Git LFS + root `.gitignore` + commit discipline (F8). One disk failure currently ends the company.
- Bridge robustness: reconnect/backoff, heartbeat/stale-state failsafe, non-blocking send (F3).

**P1 — The product spine (weeks 2–4):**
- Bridge schema v1.2: 6-DOF state (roll/pitch/heave) + water-surface sampling for visual wave ride (F1) — this is "high physics" made visible.
- Real sensors with Cesium-georeferenced GPS, IMU from pawn kinematics, camera capture; AIS once traffic exists (F2).
- Deterministic sim clock + run lifecycle + UE-side capture hooks (F5, F6).
- Sea-state presets with runtime switch + wind/current hooks (F10).
- In-engine automation: smoke tests via Automation framework, headless editor-python pipelines, nightly rendered snapshot (F7 — detailed in the execution plan).
- Native fallback mode: buoyancy + simple forces + keyboard, so the sim demos without Python (F4).

**P2 — The differentiator features (weeks 4–12):**
- Traffic + COLREGS port from Unity reference; scenario data assets; compliance scoring/report generation (F11).
- Synthetic-data factory: auto-labeled camera/LiDAR/radar export, domain randomization.
- Replay from logs; evidence-pack generator (run → KPIs → PDF/CSV report).
- Performance budget + weekly automated profile; packaging pipeline; Long Beach verification or explicit parking (F12, F13).
- Cinematics/MRQ demo film for the 30-day showable (sells the above).

**Strategic (continuous):**
- Verify Google 3D Tiles commercial terms; maintain a non-Google fallback environment profile (F9).
- Keep the Unity build frozen as the parity reference; port logic, don't maintain two products.
- Publish-ready artifacts (short demo film, KPI report sample, dataset sample) aimed at the autonomy-dev wedge — by day 30.

---

## 7 · Sources

Industry/regulatory: [IMO adopts first global Code for autonomous ships](https://www.imo.org/en/mediacentre/pressbriefings/pages/imo-adopts-mass-code.aspx) · [IMO — Autonomous shipping](https://www.imo.org/en/mediacentre/hottopics/pages/autonomous-shipping.aspx) · [DNV: IMO MSC 111 — new MASS Code adopted](https://www.dnv.com/news/2026/imo-mcs-111-new-mass-code-adopted/) · [Lloyd's Register MSC 111 summary](https://www.lr.org/en/knowledge/regulatory-updates/imo-meetings-and-future-legislation/msc-111-summary-report/) · [Maritime Executive — non-mandatory MASS Code](https://maritime-executive.com/article/imo-passes-non-mandatory-safety-code-for-autonomous-ships) · [gCaptain analysis](https://gcaptain.com/imo-adopts-mass-code-the-autonomous-ship-moves-from-drawing-board-to-regulated-reality/)

Assurance/simulation-based testing: [DNV simulation-based testing (SEAOPS)](https://www.dnv.com/research/review-2020/featured-projects/seaops-ship-operations-simulation/) · [DNV Simulation Trust Center / RP-0513](https://www.dnv.com/research/review-2022/featured-projects/simulation-trust-center-and-dtyard/) · [Towards Simulation-based Verification of Autonomous Navigation Systems](https://www.researchgate.net/publication/337674478_Towards_Simulation-based_Verification_of_Autonomous_Navigation_Systems) · [Review of autonomous collision-avoidance performance testing (JMSE 2025)](https://www.mdpi.com/2077-1312/13/8/1570)

Market: [Fortune Business Insights — autonomous ships](https://www.fortunebusinessinsights.com/industry-reports/autonomous-ship-market-101797) · [Autonomous ships statistics 2026](https://scoop.market.us/autonomous-ships-statistics/) · [MarketsandMarkets — USV market](https://www.marketsandmarkets.com/Market-Reports/unmanned-surface-vehicle-market-220162588.html) · [CRS — Navy large USV programs](https://www.congress.gov/crs-product/R45757) · [TechCrunch — Orca AI $72.5M Series B](https://techcrunch.com/2025/05/06/boosted-by-defense-and-starlink-orca-ai-pulls-in-72-5m-for-its-autonomous-shipping-platform/) · [DefenseScoop — Navy/Saronic $392M OTA](https://defensescoop.com/2025/08/22/navy-buy-saronic-autonomous-maritime-drones-usv-asv-ota/)

Competitive/technical: [Applied Intuition — maritime/Axion](https://www.appliedintuitiondefense.com/maritime) · [Applied Intuition 2025 year in review](https://www.appliedintuition.com/blog/2025-year-in-review) · [HoloOcean simulator](https://www.researchgate.net/publication/383187592_HoloOcean_A_Full-Featured_Marine_Robotics_Simulator_for_Perception_and_Autonomy) · [MARUS simulator](https://www.researchgate.net/publication/366430822_MARUS_-_A_Marine_Robotics_Simulator) · [Stonefish simulator](https://www.researchgate.net/publication/336557181_Stonefish_An_Advanced_Open-Source_Simulation_Tool_Designed_for_Marine_Robotics_With_a_ROS_Interface) · [SMaRCSim — simulator survey](https://arxiv.org/html/2506.07781v1) · [Synthetic maritime imagery for detection (Springer 2025)](https://link.springer.com/article/10.1007/s00521-025-11838-7) · [RT-DETR + synthetic maritime data](https://arxiv.org/html/2510.07346v1) · [AI in Maritime Security — data-scarcity review](https://www.mdpi.com/2078-2489/16/8/658) · [Cesium for Unreal](https://cesium.com/blog/categories/cesium-for-unreal/) · [Cesium digital twins](https://cesium.com/use-cases/digital-twins/)

*Maintained by NaviSyn Marine Solutions. Update §2 whenever the verified scene or module changes; update §4 quarterly (next regulatory checkpoint: MSC 112, December 2026).*
