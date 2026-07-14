# NaviSense UE5 — Master Execution Plan & Automation Strategy

> **Status 14 Jul 2026 (WP_20260714B):** **Demo closeout Session A COMPLETE** — `verify_demo_session` **SESSION PASS** (TC-49): 28 HighResShot 3840×2160 stills + 5 demo clips ⇒ capture gate **3/3** (D6+D7), all **4 COLREGS scenarios ran live** ⇒ matrix **4/4 live**, sensors **4/4**; D2 + KI-034 eye-confirmed earlier today. Two closeout-tooling bugs found+FIXED this session — **KI-041** (film gate false-rejected moov-at-end recordings — was on the C3 critical path) + **KI-042** (COLREGS matrix crashed on a NUL-padded result), `verify_20260714b` 4/4+3/3. Burndown now **D1–D7 ✅ · D8 ◐** (only the ~30-min clean-box Session B remains): see `Documents/NaviSense_UE5_Gate_Closeout_Guide.md`.

**Project:** NaviSense Simulator (Unreal Engine 5.7) · **Owner:** Lemuel, NaviSyn Marine Solutions
**Co-developer:** Claude (daily scheduled sessions + on-demand) · **Date:** 11 June 2026
**Companion:** `NaviSense_UE5_Analytical_Review.md` (the why; F-numbers below refer to its findings)
**Supersedes nothing:** the 45-page Master Development Guide (Phases A–K) remains the technical encyclopedia; this plan re-sequences it for a 30-day showable demo, adds the product wedge (autonomy devs & researchers), and defines the automation machine that gets it done.

---

## Status update — 14 June 2026 (read first)

> **12 Jul 2026 update (WP_20260712) — demo date SLIPPED, tree frozen-green:** the 11 Jul target passed without the live session (no PIE since 8 Jul, film dir empty; Step-0 KI-034 Live Coding recompile pending). No product change; TC-50 baseline re-proved 5/5+3/3 on 12 Jul (`wp_20260712_result.json`). The freeze holds — the next action is Lemuel's ONE live session (`PENDING_EDITOR_GATES.md`, Steps 0→1→3→5→6, ends `verify_demo_session.py`), which alone closes D2/D4/D6/D7.
>
> **28 Jun update (WP-20260628) — D5 wake & spray VFX feed (first in-engine packet in a week):** the wake is **driven by speed** (the hull is kinematically posed — no fluid sim): a Niagara system reads two 0..1 user floats (`WakeIntensity`, `Spray`) and scales bow wave / stern wash / spray. The whole authorable stack shipped — the curve (`python/wake_model.py`), a **minimal additive** C++ feed (the kinematics getters become `UFUNCTION(BlueprintPure)` + `GetWakeIntensity01()`/`GetWakeSpray01()` mirroring the Python **exactly**; no wire/DTO/schema change, no coordinate/sign work, Z0 16/16), the attach script (`04_setup_wake_vfx.py`), the build recipe (`Documents/NaviSense_Wake_VFX_Recipe.md`, with a **no-recompile fallback**), and the gate. `verify_20260628.py` **6/6 + 3/3** with **C++↔Python curve parity** (the rendered curve == the gated curve). Advances **D5 ☐→◐** (remaining: the NS_Wake Niagara art + the in-engine eye-check **G_WAKE_UE**) and unblocks **D7** (the film needs a wake). New **TC-29**, new **KI-025** (honesty: speed-driven visual proxy, not a CFD wake). The six prior packets were pure-Python — this restarts the in-engine demo work for the 11 Jul gate.
>
> **27 Jun update (WP-20260627) — COLREGS conformance scoring (the V&V differentiator, §5.1, delivered early/headless):** the scripted-AIS layer now SCORES, per encounter, whether the own-ship maneuver conformed to the COLREGS duty — `python/colregs_score.py` returns a give-way / stand-on verdict (COMPLIANT / NON_COMPLIANT / NOT_APPLICABLE) against **Rules 8 / 13–17** (give-way: early + substantial alteration to starboard to a safe distance; stand-on: keep course/speed until close-quarters), surfaced in the evidence pack (kpis.json + HTML + EVIDENCE.md) and shipped automatically by `run_demo` for any `--ais` scenario. Pure-Python, read-only (**no wire/DTO/schema/C++ change, no recompile, no new mandatory in-engine gate**). `verify_20260627.py` **6/6 + 3/3** — validated **both ways** (a compliant give-way scores COMPLIANT; a held course, a wrong-way turn, and a clear pass are each handled correctly), with encounter-classification parity vs `analyse_ais` and a purely-additive evidence pack (IMO KPIs + health byte-identical). **Honesty:** it *measures* the logged maneuver — the demo own-ship runs a FIXED controller, so a held course into a give-way duty is correctly NON-COMPLIANT; autonomous avoidance is the W5-6 roadmap. Advances **D4** (the AIS/intelligence half) + seeds §5.1. New **TC-28**.
>
> **26 Jun update (WP-20260626) — D6 evidence pack is now a single shareable file:** the evidence-pack generator emits a **self-contained `evidence_report.html`** alongside `EVIDENCE.md`/`kpis.json` — every plot embedded as a base64 `data:` URI (zero external file refs, so the one .html can be emailed / attached to a pilot proposal or DIANA grant and still renders), with the IMO maneuvering-KPI table (PASS/FAIL vs limits), the kinematic-health verdict + checks, the actuator + AIS/COLREGS tables, and an honest provenance footer (MMG standard-method KPIs **not** CFD-validated; roll/pitch/heave = visual proxy; AIS = scripted). Pure-Python presentation layer (new `python/evidence_html.py` *formats* the already-computed KPIs — never re-derives, no drift; **no wire/schema/C++ change, no recompile, no new mandatory in-engine gate**). `run_demo.py` ships it automatically. `verify_20260626.py` **6/6 + 3/3** (incl. self-containment + IMO-KPI parity vs `kpis.json`, with negative controls that detect a corrupted embedded image, a wrong KPI value, and an injected external ref). Advances **D6** (◐ — remaining = ≥3 in-PIE beauty screenshots / MRQ).
>
> **25 Jun update (WP-20260625) — D8 clean-machine reproducibility:** a stdlib-only **readiness doctor** (`python/repro_doctor.py`) reports exactly what a fresh clone is missing — deps, core-tool integrity (KI-004 guard), UE project, DA_DOLPHIN assets incl. un-pulled **Git-LFS** stubs, and the **Cesium ion token** — with a READY/NOT-READY verdict + `repro.json`; **`SETUP.md`** documents the full `git clone`→demo path; and `verify_20260625.py` proves the **headless pipeline reproduces** (`run_demo --selftest` ×2 → **DT 158.18 m IMO PASS** both). Pure-Python + docs (**no wire/schema/C++ change, no recompile, no new mandatory in-engine gate**; zero existing files edited). **6/6 gates + 3/3 negative controls**. Advances **D8 ☐→◐**; the only remaining D8 step is the one-time clean-box in-engine confirm (which also inherits D2/D5/D7). Honesty: the doctor proves prerequisites + the headless half; it does not claim the in-engine demo on a clean box (labelled manual gate G_REPRO_UE).
>
> **24 Jun update (WP-20260624) — D4 AIS traffic (data/analysis half):** a **scripted AIS target** now rides the run with the **correct range/bearing from own-ship** (the WP-15 gate) plus **CPA/TCPA** and the **COLREGS encounter** (head-on / crossing / overtaking → give-way / stand-on), surfaced in the evidence pack (`ais.csv` + `ais_cpa.png` + `kpis['ais']`). Pure-Python (`python/ais_traffic.py` + `analyse_ais.py`; `build_evidence_pack --ais`), read-only over the own-ship track — **no wire/DTO/schema change, no recompile, no new mandatory in-engine gate** (the listener's `--ais` only records the preset in the manifest). `verify_20260624.py` **6/6 + 3/3** negative controls; live e2e via `run_demo --scenario head_on_transit --selftest` (DEMO COMPLETE, health PASS). Seeds the **W5-6 COLREGS-scoring** differentiator (§5.1). UE AIS-pawn rendering + `sensor.v1` mmsi/cog/sog = **WP-15B** (in-engine follow-up). Advances **D4 ◐**.
>
> **23 Jun update (WP-20260623) — one-command demo runner:** `run_demo.py` makes the whole demo a single command — **PREFLIGHT** (python/layout/scenario/free-port/tool-import, the seed of **D8**) → **LAUNCH** the listener with a named scenario → **DRIVE** one run (real PIE, or `--selftest` with a bundled client = **no Unreal/GPU**) → **AUTO-BUILD** the IMO evidence pack + kinematic-health gate. Pure-Python orchestration (**no wire/schema/C++ change, no recompile, no new mandatory in-engine gate**). `verify_20260623.py` gates it END-TO-END headless **5/5** with **3/3 negative controls firing** (incl. *no-vessel → no fake pass*). Advances **D6** (the one-command runner now exists, ◐) + seeds **D8**; only the in-PIE eye-check + ≥3 beauty screenshots/MRQ remain for D6.
>
> **22 Jun update (WP-20260622) — D4 sensors validated:** the in-engine **GPS/IMU bundle is now objectively validated against the plant** by `python/verify_sensors_fidelity.py` — speed/yaw-rate/heading corr **1.0000**, GPS position = plant + spawn offset (median residual **≤0.43 m**), WGS84 geo-origin **43.7350 N / 7.4250 E** consistent. **8/8 on two real runs** (Lemuel's morning `20260622_054815` + the 21-Jun 493° turn) with **5/5 negative controls** firing. Pure-Python, read-only over `logs/`, **no recompile / no schema change / no new in-engine gate**. Advances **D4 ☐→◐** (remaining: camera WP-14, AIS WP-15, live CesiumGeoreference). Found **KI-024**: the plant-log and sensor-log use different `t` clocks (3.0× vs 1.0× wall) — join on `wall_time`.

> **21 Jun update (WP-20260621):** **runtime sea-state SCHEDULE + named-scenario registry** — pure-Python, rides the existing `heaveM`/`rollDeg`/`pitchDeg` keys (**no DTO/schema change, NO recompile, no new in-engine gate**). One run now sweeps ≥3 sea states via a cross-faded `ScheduledSeaState` (`--sea-state-schedule "0:1,90:4,180:6"`), each crossing logged to `events.csv` — the **D3 runtime-switch** half (logging landed in WP-9). A `python/scenarios.py` registry + `--scenario <name>` makes a demo one flag, and the evidence pack names the scenario/schedule — the **D6 scenario-selection** half. Auto-verified `verify_20260621.py` **10/10** (negative controls fire); regression green (WP-20260620 8/8, Z0 16/16, schema-v13 12/12, WP-9 9/9, re-accept 5/5, pytest 10/10). Advances **D3** + **D6**; the in-engine smooth-build eye-check folds into the pending Session-A recompile.
>
> **18 Jun — RECOMPILE CONFIRMED (the big unlock):** Lemuel ran Live Coding on the current tree → **8/8 TUs, "Result: Succeeded"**, patch linked (UE 5.7). This is the one recompile that gated the whole in-engine queue; it builds the full week's C++ together (WP-4/5/6/7/8/9 + SENSOR-1 + ACTUATOR-RIG). **KI-016 RESOLVED, KI-015 validated.** The in-PIE gates (G7/G4/G5/C4/G_UE7/8/8+, sensors, actuator rig, WP-6 manual, WP-5 nightly) are now runnable — `Development/work_packets/PENDING_EDITOR_GATES.md`.
>
> **18 Jun update (WP-9):** **wave-coupled roll/pitch** on the existing wire — the hull now **rolls** with a beam swell and **pitches** into a head swell (not just heaves), and the active **sea state is now logged** (`manifest.json` + `runs.csv`). Pure-Python (`python/wave_response.py` projects the field's surface slope into hull attitude), composed onto the maneuvering heel/trim and riding the existing `rollDeg`/`pitchDeg` keys ⇒ **no DTO/schema change, NO new recompile** (it folds into the already-pending G_UE7/8 eye-check). Auto-verified `verify_20260618.py` **9/9**; regression re-run 16/16 + 12/12 + pytest 10/10. Advances **D2** (rolls/pitches with the sea) + **D3** (logging half). New **KI-017**: the canonical listener still lacks the WP-3 auto-reaccept the 14-Jun ledger claimed.
>
> **17 Jun update (WP-8):** 6-DOF schema **v1.3** — wave-driven **heave** + a deterministic **sea-state** field (`--sea-state 0–9`) wired to the pawn Z (demo gate **D2** heave half; seeds **D3**; plant stays 3-DOF). Water-surface sampling = F1 pt3. Auto-verified (`verify_schema_v13.py` 12/12; compile-readiness 16/16; pytest 10/10); awaiting Lemuel: recompile + heave eye-check. ⚠ KI-004 recurred (the editor file-tool truncated 6 files mid-write); all rebuilt via shell + brace-verified.
>
> **16 Jun update (WP-7):** 6-DOF schema **v1.2** — heel/trim attitude wired to the pawn (demo gate **D2** attitude half; plant stays 3-DOF). Heave + water-surface sampling = F1 pt2. Awaiting Lemuel: recompile + heel eye-check. *(The 16-Jun "recompile Succeeded" Test-Log row was pre-authored 15 Jun and is unconfirmed — see KI-016.)*

Progress against this plan (live ledger: `PROGRESS.md`):

- **WP-1 repo hygiene, WP-2 closed loop, WP-3 bridge robustness — DONE.** Closed loop LIVE in Monaco; demo gate **D1 essentially achieved** (final sign confirmation via `turning_circle` in progress). UE recompiled.
- **Listener consolidated + fixed:** one canonical `python_listener.py` at the workspace root (`-v` works; controllers fed plant yaw so the zig-zag never stalls). `bridge_harness/` is offline-test-only.
- **Workspace self-contained** (Python + MMG brought in); old `NAVISENSE` root = backup. New git repo to be created on Windows per `../GIT_SETUP.md` — off-machine remote is still the top open item.
- **Next:** WP-4 deterministic sim clock (F5); port WP-3 auto-reaccept into the canonical listener; then Week-2 6-DOF + sea states.

---

## 1 · Mission and success criteria

### 1.1 The 30-day showable demo — **target WAS Saturday 11 July 2026 — SLIPPED (12 Jul note)**

> **12 Jul 2026 (WP_20260712):** the 11 Jul target passed without the live session running. Everything headless is green and frozen (TC-50 re-proved 5/5+3/3 on 12 Jul); the demo now closes at Lemuel's first free slot via the unchanged run card (`Development/work_packets/WP_20260711/PACKET.md` → `PENDING_EDITOR_GATES.md`, Steps 0→1→3→5→6, ~45–60 min, ends with `verify_demo_session.py`). The freeze rule stays in force until that session is done.

One sentence: *a Python autopilot drives the CFD-grounded DOLPHIN through photoreal Monaco in selectable sea states, with real sensor output, riding the water in 6-DOF, captured as a cinematic film and a one-page evidence report — reproducible from a single command.*

Demo Definition of Done (every box checkable, no hand-waving):

- [ ] **D1** Closed loop live in `NaviSense_Monaco`: pawn driven by `python_listener.py --plant mmg`, in-engine zig-zag sign test passed.
- [ ] **D2** Hull rides the water: roll/pitch/heave visible (schema v1.2 + wave sampling), heel in turns, no waterline clipping at any sea state.
- [◐] **D3** Sea states switchable at runtime (≥3 presets: Calm / Moderate / Rough) and recorded in the run log. *(21 Jun · WP-20260621: runtime SWITCH done headless — `--sea-state-schedule`/`--scenario` cross-fades one run through ≥3 sea states, each logged to `events.csv`; in-engine smooth-build eye-check folds into the pending recompile.)*
- [ ] **D4** Real sensors on the wire: GPS with true lat/lon via CesiumGeoreference, IMU from pawn kinematics, camera frames captured to disk; AIS carries ≥1 scripted traffic target. **(◐ 22 Jun: GPS/IMU objectively validated vs the plant — WP-20260622/TC-23. 24 Jun: AIS DATA/ANALYSIS delivered — WP-20260624/TC-25 puts a scripted target on the run with correct range/bearing + CPA/TCPA + COLREGS encounter in the evidence pack (6/6 + 3/3). Still pending: camera (WP-14), live CesiumGeoreference, UE AIS-pawn rendering + sensor.v1 mmsi/cog/sog (WP-15B). 27 Jun · WP-20260627/TC-28: the AIS intelligence now also SCORES **COLREGS conformance** per encounter — give-way/stand-on verdict, Rules 8/13–17, in the evidence pack (`verify_20260627.py` 6/6 + 3/3).)**
- [◐] **D5** Wake/spray VFX active and speed-responsive. *(28 Jun · WP-20260628: speed-driven feed authored — the curve `python/wake_model.py` + the pawn's BlueprintPure `GetWakeIntensity01()`/`GetWakeSpray01()` (mirrored 1:1, gate-checked) + `04_setup_wake_vfx.py` + `NaviSense_Wake_VFX_Recipe.md`; `verify_20260628.py` **6/6 + 3/3** with C++↔Python curve parity. Remaining: build the NS_Wake Niagara system + the in-engine eye-check (**G_WAKE_UE**); a no-recompile BP fallback unblocks a first look.)*
- [ ] **D6** One scripted scenario (harbor approach + zig-zag + turning circle) runs end-to-end from one command, producing: run CSV, IMO maneuver KPIs (overshoot angles, advance/transfer), and ≥3 beauty screenshots — the **evidence pack**. *(20 Jun · WP-20260620: the IMO-KPI **evidence-pack generator** `python/build_evidence_pack.py` is built — `kpis.json` + `EVIDENCE.md` + plots, turning-circle/zig-zag KPIs auto-selected, plus a `verify_run_kinematics.py` health gate; **D6 ☐→◐**. Remaining: the one-command **scenario runner** (WP-18) + ≥3 beauty screenshots.)* *(21 Jun · WP-20260621: **scenario selection** done — `python/scenarios.py` + `--scenario <name>` (one-flag demo presets, `--scenario list`); the evidence pack now names the scenario + schedule. Remaining for D6: ≥3 beauty screenshots / MRQ.)* *(23 Jun · WP-20260623: the **one-command runner** `run_demo.py` is built — preflight → listener+scenario → auto evidence pack; gated **5/5 + 3/3** headless. Remaining for D6: in-PIE eye-check + ≥3 beauty screenshots / MRQ.)* *(26 Jun · WP-20260626: the pack now emits a **single self-contained `evidence_report.html`** — plots embedded, IMO-KPI table + health + AIS/COLREGS + honest provenance; gated **6/6 + 3/3** by `verify_20260626.py`; `run_demo` ships it. Remaining for D6: ≥3 in-PIE beauty screenshots / MRQ.)*
- [ ] **D7** A 60–90 s cinematic film rendered via Movie Render Queue from a Sequencer pass.
- [◐] **D8** Everything above reproducible after `git clone` + documented setup on a clean machine (Cesium tokens documented). *(25 Jun · WP-20260625: `python/repro_doctor.py` readiness verdict + `SETUP.md` documented clone→demo path + `verify_20260625.py` **6/6 + 3/3** proving the headless pipeline reproduces (run_demo --selftest ×2 → DT 158.18 m IMO PASS both); **D8 ☐→◐**. Remaining: the one-time clean-box in-engine confirm — which also inherits D2/D5/D7.)*

### 1.2 Beyond day 30 — v1.0 product spine (weeks 5–12, summary in §5)

Traffic + COLREGS scoring, synthetic-data factory with auto-labels, deterministic replay, packaged builds, Long Beach verified, ROS2 bridge spike. v1.0 definition stays aligned with the business spec §13.

### 1.3 Non-goals for the next 30 days

Multiplayer/ROC features, certification-grade radar/sonar physics, Long Beach polish, marketplace/licensing infrastructure, mandatory-code compliance claims (the MASS Code is voluntary until ~2032 — we build evidence *capability*, we do not claim certification).

---

## 2 · Operating model: how we two work

### 2.1 Division of labor

**Claude does (anything not requiring the editor GUI or your judgment):** all C++/Python authoring, editor-Python scripts, config changes, schema/doc maintenance, research, test authoring, log/KPI analysis of your runs, daily planning. Output lands as ready files in the repo.

**Lemuel does (the irreducible human steps):** open editor, run scripts via *Tools → Execute Python Script*, press Play/build, judge visuals, run terminal commands, commit+push, record short screen captures when something misbehaves (drop into `Development/Development videos/` — I read frames from these).

### 2.2 The Work Packet protocol (the core loop)

Each working day produces exactly one **Work Packet** — a folder `Development/work_packets/WP_<YYYYMMDD>/` containing:

1. `PACKET.md` — goal, changed-file list, **your in-editor steps (target ≤ 20 min)**, acceptance gates, rollback note.
2. The actual code/scripts already written into the repo tree.
3. `verify_<date>.py` — an editor-Python or harness script that checks the gates automatically where possible and writes `Saved/NaviSense_Reports/wp_<date>_result.json`.

4. **Doc updates** per the Documentation Update Protocol (`../CLAUDE.md`): at minimum a `PROGRESS.md` line; plus `05_Test_Log.md`, `04_Known_Issues_Register.md`, status banners / burndown as the change dictates.

Rules: one packet = one theme; every packet ends at a *runnable* state; a packet is closed only when its gates pass **and** the Documentation Update Protocol is satisfied; failed gates roll into the next packet — never silently dropped. `Documents/PROGRESS.md` (created today) is the single running ledger: one line per packet — date, theme, gates passed/total, next blocker.

### 2.3 The daily scheduled session (automation of *me*)

A scheduled Claude session runs **every morning at 07:00** and:

1. Reads `PROGRESS.md`, the latest `wp_*_result.json`, `Saved/Logs/` tails, and any new files in `Development/Development videos|images/`.
2. Decides the day's packet against this plan's current week (§4) — or, if yesterday's gates failed, builds the fix packet first.
3. Writes the code + scripts + `PACKET.md`, updates `PROGRESS.md`, and (Mondays) refreshes the plan's week section if reality has drifted.
4. Leaves you a short morning brief: what's ready, what your ≤20 min in-editor steps are, what it needs from you.

You work "as much as you want": the packet is sized so the *mandatory* human part stays tiny; everything beyond it is optional depth. If you skip a day, the next session detects no result file and re-plans instead of piling up.

### 2.4 Cadence summary

| Rhythm | What happens |
|---|---|
| Daily 07:00 | Scheduled session → Work Packet + morning brief |
| Daily (you, any time) | Execute packet steps → run `verify` → commit+push |
| Nightly (machine, §6.4) | Headless tests + render snapshot + log sweep (once set up in week 1) |
| Weekly (Mon session) | KPI review, plan drift correction, perf snapshot review |
| Day 30 | Demo freeze: only D1–D8 gate-closing work |

---

## 3 · Day 0 + Week 1 — Foundation & first closed loop (11–17 Jun)

### Day 0 (today, with this document)

- [x] Both strategy documents written; `PROGRESS.md` seeded; daily session scheduled.
- [ ] **You (15 min) — STILL OPEN:** follow `../GIT_SETUP.md` — delete the broken placeholder `.git`, `git init`, `git lfs install`, scoped commits, then push to a **new private GitHub remote**. Last Day-0 safety step (F8).

### WP-1 (Fri 12 Jun) — Repo safety net *(F8)*

Root `.gitignore` (excludes Unity `Library/`, `.venv/`, logs), `.gitattributes` for LFS (`*.fbx`, `*.uasset`, `*.umap`, textures), commit conventions note, `PROGRESS.md` wired. **Gate:** clean `git status`, LFS tracking verified, repo pushed.

### WP-2 (Sat 13 Jun) — **Phase A: the closed loop** *(Component Guide §3, verbatim)*

Scripted as far as possible: `01_place_ship_pawn_monaco.py` places `ANaviSenseShipPawn` at (20580, −23500, −310), assigns hull mesh + a created `DOLPHIN_VesselProfile` data asset, sets Auto Possess P0, hides `unity_yacht_model`. Your steps: run script, save level, start `python_listener.py --controller zigzag10 --target unreal`, press Play. **Gate (the big one):** in-engine sign test — +10° rudder ⇒ bow swings starboard in HUD log *and* Python log. This closes Master Guide Phase A and unblocks everything.

### WP-3 (Sun 14 Jun) — Bridge robustness *(F3)*

Reconnect with exponential backoff (0.5→8 s), heartbeat/stale-state failsafe (>1 s without state.v1 in PoseReceive ⇒ hold position + on-screen warning), send moved off the hot path (queued, non-blocking check), connection-state Blueprint event for HUD. **Gate:** kill/restart listener mid-Play ⇒ pawn freezes gracefully, auto-reconnects, resumes; zero hitches >5 ms from Send (Insights trace).

### WP-4 (Mon 15 Jun) — Deterministic sim clock + run lifecycle *(F5)*

Tick-accumulated sim clock in `UNaviSenseSimSubsystem` (pause-aware, fixed-step accumulator), run start/stop API stamped by `RunId`, both ends log the same `t`. **Gate:** PIE pause 5 s ⇒ `t` drift < 1 ms vs Python tick count.

### WP-5 (Tue 16 Jun) — In-engine test + nightly automation skeleton *(F7, §6)*

First Automation tests (coords round-trip + sign convention as a C++ Spec; JSON contract golden-file test), `Development/automation/` PowerShell scripts: `nightly_tests.ps1`, `nightly_render.ps1` (MRQ single beauty frame from a fixed cam), `nightly_sweep.ps1` (log/report collector), registered in Windows Task Scheduler at 02:00. **Gate:** `RunTests NaviSense` green from command line; one nightly PNG lands in `Saved/NaviSense_Reports/nightly/`.

### WP-6 (Wed 17 Jun) — Week-1 close: native fallback spike *(F4)*

Minimal Manual mode: keyboard throttle/rudder (Enhanced Input), simple thrust/drag/yaw forces — *not* physical truth, just "sim never demos dead". **Gate:** with no Python running, vessel drivable in Monaco at stable FPS; week-1 retro line in `PROGRESS.md`.

---

## 4 · Weeks 2–4 — The demo build-out

### Week 2 (18–24 Jun) — "High physics": 6-DOF + sea states

| Packet | Theme | Gate |
|---|---|---|
| WP-7/8 | **Bridge schema v1.2** (§7): plant emits rollDeg/pitchDeg/heave; UE consumes; harness + golden files updated; v1.1 kept compatible (absent fields ⇒ zeros) | Harness selftest green on v1.1 *and* v1.2 packets |
| WP-9 | MMG plant augmentation in Python: first-order roll from rudder/turn rate (heel-into-turn), pitch/heave from speed + sea-state proxy — honest *visual* seakeeping, flagged as such in docs | Zig-zag shows plausible heel; magnitudes configurable per vessel profile |
| WP-10 | **Water-surface sampling**: pawn samples WaterBody at bow/stern/port/stbd, blends plant pose with wave-induced roll/pitch/heave; freeboard from profile | Hull rides visible waves at all 3 sea states, no clipping (F1 closed) |
| WP-11 | **Sea-state presets** (F10): DataAsset presets Calm/Moderate/Rough mapped to wave params + wind; runtime switch (key + Python command `env.v1`); logged in run CSV | D3 checkable |
| WP-12 | Camera modes (follow/bridge/orbit/free) + actuator visual rig hookup (rudder/prop visuals from `FActuatorState`) | Bridge-cam horizon behaves; rudder visibly deflects in zig-zag |

### Week 3 (25 Jun – 1 Jul) — Sensors, traffic seed, VFX

| Packet | Theme | Gate |
|---|---|---|
| WP-13 | **GPS via CesiumGeoreference** (engine→WGS84), speed/COG from pawn; **IMU** (heading, yaw-rate, accel via finite difference + noise model port from Unity `IMUSensor.cs`) | sensor.v1 carries true Monaco lat/lon (≈43.73 N, 7.42 E) matching chart position of Port Hercule |
| WP-14 | **Camera sensor**: SceneCapture2D → JPEG to disk at configurable Hz + `camera.v1` manifest (Unity parity) | 10 min run ⇒ ordered frame set + manifest |
| WP-15 | **Scripted traffic vessel** (spline-following stand-in, AIS-emitting) — the COLREGS brain port comes in week 5+, but AIS needs a real target now (F2/F11 seed) | AIS block lists the target with correct range/bearing from own-ship |
| WP-16 | **Wake & spray** Niagara (port Unity wake concepts; UE Water interaction): speed-responsive bow wave, stern wash, spray bursts (D5) — **STARTED 28 Jun (WP-20260628): feed + curve + recipe + gate done (`verify_20260628` 6/6+3/3, C++↔Python parity); NS_Wake art + G_WAKE_UE eye-check remain** | 20 kn pass looks right at all camera modes; <2 ms GPU cost budgeted |
| WP-17 | UE-side run capture (F6 start): screenshots on event marks, run metadata JSON; weekly perf snapshot baseline (F12) — `stat unit`/Insights capture archived | Evidence-pack inputs exist; perf baseline recorded |

### Week 4 (2–11 Jul) — Scenario, evidence pack, cinematics, freeze

| Packet | Theme | Gate |
|---|---|---|
| WP-18 ✅ v0 (23 Jun) | **Scenario runner v0** — `run_demo.py`: one command = preflight + listener + named scenario + auto evidence pack (headless `--selftest`, or real PIE). Gated **5/5 + 3/3** by `verify_20260623.py`. *(scenario source = the `python/scenarios.py` registry, not YAML yet.)* | **D6 single-command run works — headless ✅**; in-PIE eye-check optional |
| WP-19 ✅ HTML (26 Jun) | **Evidence pack generator**: `build_evidence_pack.py` → KPIs (1st/2nd overshoot, advance/transfer/tactical diameter) vs IMO criteria + plots, now rendered to **one self-contained `evidence_report.html`** (plots embedded, 0 external refs; `python/evidence_html.py`). Gated **6/6 + 3/3** by `verify_20260626.py` (incl. IMO-KPI parity vs `kpis.json`). *(PDF export still optional/deferred.)* | **Pack generated from a fresh run, numbers match analysis scripts — ✅ (parity-gated G3).** |
| WP-20 | **Sequencer + MRQ film** (D7): camera pass through approach/zig-zag/turn at golden hour, 60–90 s, MRQ render preset (high AA, Lumen) | Film renders headless via MRQ CLI |
| WP-21–23 | Buffer: gate-closing only (D1–D8 audit), HUD telemetry overlay minimal (speed/heading/rudder/RPM/sea state/connection), clean-machine clone test (D8), demo dry run | All eight D-gates checked |

**Freeze rule (5–11 Jul):** no new systems; only D-gate work. The film and evidence pack are the two artifacts you show.

---

## 5 · Weeks 5–12 — From demo to product v1.0 (the wedge features)

Sequenced summary (each becomes packet-level when its week arrives; Master Guide phases in brackets):

1. **W5–6 · Traffic + COLREGS [F]:** port `ColregsBrain`/`TrafficProfile` from Unity to C++/BP; encounter generators (head-on/crossing/overtaking matrices); **COLREGS compliance scoring** (CPA/TCPA, rule-conformance per encounter — the literature-standard metrics) appended to the evidence pack. *This is the V&V differentiator.* *(27 Jun · WP-20260627: the **scoring metric** is delivered early + headless — `colregs_score.py` scores give-way/stand-on conformance per encounter into the evidence pack, gated `verify_20260627.py` 6/6 + 3/3; the remaining W5-6 work is the avoidance **controller** + `ColregsBrain` port that makes own-ship PASS, plus the encounter-matrix generators.)*
2. **W7 · Logging & replay [G]:** deterministic replay of any run CSV (mode=replay), event marks, multi-run comparison; clock work from WP-4 pays off here.
3. **W8 · Synthetic-data factory:** auto-labels (custom stencil ⇒ instance masks + 2D boxes for vessels/buoys), dataset export (COCO format), domain randomization sweeps (time-of-day, sea state, weather) via headless MRQ/PIE batches. *This is the data-product differentiator (research: simulation-trained detectors +28% over real-only baselines).*
4. **W9 · HUD/UX [H] + packaging [K] first pass:** `BuildCookRun` pipeline in nightly rotation; packaged demo build smoke-tested weekly from here.
5. **W10 · Port realism finishing [I] + Long Beach decision (F13):** verify (inventory + health check + one closed-loop run) or park explicitly.
6. **W11 · ROS2 bridge spike** (adoption lever vs MARUS/HoloOcean users) + Cesium licensing resolution (F9): verify Google tiles commercial terms; build the fallback environment profile (Cesium World Terrain + OSM buildings + hero port mesh).
7. **W12 · v1.0 hardening:** docs for external users, quickstart, sample datasets/evidence packs, demo film v2 — aligns with business-spec §13 release definition.

---

## 6 · Automation strategy (the machine around the work)

### 6.1 Principles

Automate *verification and repetition*, keep *judgment* human; every automated step writes a machine-readable result (`Saved/NaviSense_Reports/`); anything run twice by hand becomes a script the third time; the editor-Python pattern you proved in Phase 4/5 is the backbone.

### 6.2 The four automation lanes

| Lane | Tooling | Cadence |
|---|---|---|
| **Code verification** | UE Automation Spec (C++) for coords/contract/components; `PythonAutomationTest` plugin for editor-level checks; harness selftest + `pytest` for the Python plant/controllers; `ruff` lint | Nightly + before every commit |
| **Scene verification** | Editor-Python: inventory dump, scene health check, material binds (existing scripts, kept current); golden-actor-list diff per map | Nightly headless |
| **Visual regression** | MRQ CLI: fixed 4-camera beauty frames per map nightly → dated folder; weekly side-by-side contact sheet | Nightly render, weekly review |
| **Performance & packaging** | Insights/`stat` capture on a scripted 60 s run (weekly); `BuildCookRun` packaged build (weekly from W9) | Weekly |

### 6.3 Headless command recipes (canonical, scripted in `Development/automation/`)

```powershell
# Editor-Python headless (scene ops, dumps, health checks)
& $UE\UnrealEditor-Cmd.exe $PROJ -ExecutePythonScript="<script.py>" -unattended -nullrhi -nosplash -log

# Automation tests
& $UE\UnrealEditor-Cmd.exe $PROJ -ExecCmds="Automation RunTests NaviSense; Quit" -unattended -nullrhi -log -ReportExportPath="Saved\NaviSense_Reports\tests"

# Movie Render Queue (nightly beauty / film render)
& $UE\UnrealEditor-Cmd.exe $PROJ NaviSense_Monaco -game -MoviePipelineConfig="/Game/NaviSense/Cinematics/MRQ_Nightly" -windowed -resx=1920 -resy=1080 -log

# Packaged build (weekly, W9+)
& $UE\Engine\Build\BatchFiles\RunUAT.bat BuildCookRun -project=$PROJ -platform=Win64 -clientconfig=Development -cook -build -stage -pak -archive -archivedirectory="D:\NaviSenseBuilds"
```

(Exact `$UE` path + Task Scheduler registration ship in WP-5; `-nullrhi` is dropped for render jobs.)

### 6.4 Nightly pipeline (02:00, Windows Task Scheduler)

`nightly.ps1`: git status snapshot → Python suite (harness selftest, pytest, ruff) → UE Automation tests → scene health dump per verified map → MRQ snapshot frames → collect everything + log tails into `Saved/NaviSense_Reports/nightly/<date>/summary.json`. The 07:00 Claude session reads that summary first — so every morning starts from *measured* truth, not memory.

### 6.5 Repo discipline

Conventional commits (`feat(bridge): …`, `fix(coords): …`); push at least daily (the nightly flags unpushed work); LFS for binaries; tag demo milestones (`demo-30day`); `PROGRESS.md` is the ledger, `PACKET.md`s are the diary. CI ladder: local Task Scheduler now → self-hosted GitHub-Actions runner on your machine when packaging stabilizes (W9+) → cloud runners only if/when a team exists.

---

## 7 · Bridge schema v1.2 (6-DOF) — specification sketch

**state.v1 → state.v2 additions** (all optional; absent ⇒ 0.0; v1.1 consumers unaffected):

```json
{
  "schema": "navisense.state.v2",
  "rollDeg": 0.0,     // + = starboard down (heel), wire frame
  "pitchDeg": 0.0,    // + = bow up
  "heaveM": 0.0,      // vertical offset from calm waterline, + up
  "p": 0.0, "q": 0.0, // roll/pitch rates rad/s (optional, HUD/IMU use)
  "envSeaState": "calm"  // echo of active preset for logging
}
```

**Authority split (the design decision):** the *plant* owns low-frequency rigid-body motion (maneuvering surge/sway/yaw + heel-into-turn roll); the *engine* owns high-frequency wave-induced motion (sampled from the actual rendered water so visuals never disagree with the sea). The pawn composes: `FinalPose = PlantPose ⊕ WaveResponse(samples, vesselProfile)`. Logged separately so evidence packs report plant truth, not cosmetic motion. **sensor.v1 → v1.2:** gps gains `latDeg/lonDeg` (true values via Cesium), imu gains `rollDeg/pitchDeg/p/q`, ais targets gain `mmsi/cog/sog`. Golden-file tests in the harness pin both versions.

---

## 8 · Risk register (top 8, live)

| # | Risk | L×I | Mitigation |
|---|---|---|---|
| R1 | **No off-machine backup** (F8) | now-critical | Day-0 push to private remote; nightly flags unpushed commits |
| R2 | Threading regression in bridge | low×high | The SPSC rule is tested in CI (WP-5); rule documented in-code |
| R3 | Coordinate/sign regression | low×high | Sign test in Automation suite + harness; fixes only in `FNaviSenseCoords` |
| R4 | Google 3D Tiles licensing blocks commercial use (F9) | med×high | W11 verification; fallback environment profile maintained from W11 |
| R5 | Perf collapse (tiles+Lumen+water+Niagara) (F12) | med×med | Weekly perf snapshot from W3; budgets in `PROGRESS.md`; Nanite/LOD passes scheduled W10 |
| R6 | Solo-dev bus-factor / burnout | med×high | Work packets keep mandatory daily load ≤20 min; freeze weeks protect the demo; everything scripted = resumable |
| R7 | Scope creep vs 30-day demo | high×med | D1–D8 are the only demo currency; new ideas go to `Documents/ICEBOX.md` |
| R8 | "Visual seakeeping" mistaken for validated seakeeping | med×med | Evidence packs label plant-truth vs cosmetic motion (§7); claims discipline in all marketing |

---

## 9 · Measuring the *development* itself

Weekly in `PROGRESS.md`: packets closed / gates passed (target ≥5/wk), nightly green-rate (target ≥90%), D-gate burndown (8→0 by 11 Jul), perf headline (fps @1440p on dev GPU), evidence-pack generation time (target <10 min from run start). The Monday session reports these five numbers — if two trend red for two weeks, we re-plan instead of pushing harder.

---

## 10 · Daily session charter (the scheduled prompt, for reference)

> Read `Documents/PROGRESS.md`, the newest `Saved/NaviSense_Reports/nightly/*/summary.json` and `wp_*_result.json`, and `Documents/NaviSense_UE5_Master_Execution_Plan.md` §3–4 for the current week. If yesterday's gates failed, build the fix packet; otherwise build the next planned packet: write all code/scripts into the repo, create `Development/work_packets/WP_<date>/PACKET.md` with ≤20 min of human steps and explicit gates, update `PROGRESS.md`, and post a short morning brief (ready work, human steps, blockers). Mondays: also report the five §9 metrics and correct plan drift. Never mark a gate passed without a result file or Lemuel's confirmation.

---

*This plan is a living document — the Monday session amends §3–5 against reality. Edition 1.0, 11 June 2026.*
