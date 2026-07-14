# 02 · NaviSense Maintenance Guide

**Goal:** keep the project healthy, reproducible, and backed up as it grows toward release.
**Last updated:** 12 July 2026 (WP_20260712 sweep: sandbox/CI env note — fresh sandboxes need `pip install pytest --break-system-packages` before `verify_20260711.py`/regression, or G5 false-fails; demo-date slip noted, freeze holds until the live session). Prior: 29 June 2026.

## 1 · Maintenance cadence

| Rhythm | Tasks |
|---|---|
| **Daily** (auto) | The 07:00 scheduled session builds a Work Packet, updates `Documents/PROGRESS.md`. You: run the packet's ≤20-min steps, run its `verify_*.py`, commit. |
| **Daily** (you) | Commit + push at least once (protects against loss). Keep `PROGRESS.md` blockers honest. |
| **Weekly** (Mon) | Review the five GTM metrics + demo-gate burndown; run the full QA regression set (`03_QA_Test_Plan` §Regression); capture a `stat unit`/Insights perf snapshot; prune stale work-packet folders. |
| **Weekly** (Fri, auto) | Traction packet (GTM). |
| **Monthly** | Update Python deps (see §3); review Known Issues for anything gone stale; verify the external-drive backup is current; re-confirm Cesium token validity. |
| **Per release / demo** | Complete `Templates/release_checklist.md` and a QA sign-off (`Templates/qa_signoff_checklist.md`). Tag the git commit (e.g., `demo-30day`). |

## 2 · Backup & version control (highest priority)

- **Off-machine remote is the #1 maintenance duty.** Until it exists, the external-drive backup is the
  only safety net. Set it up via `../GIT_SETUP.md` (new private repo → LFS → commits → push).
- **Commit discipline:** conventional messages (`feat(bridge): …`, `fix(coords): …`, `docs: …`). Push daily.
- **LFS:** binary assets (`.uasset`, `.umap`, `.fbx`, textures, media, PDFs) via `.gitattributes`. Never
  commit `Binaries/`, `Intermediate/`, `Saved/`, `DerivedDataCache/`, or the Cesium cache (all git-ignored).
- **Tags:** tag every demo/release milestone so you can always return to a known-good build.
- **The two repos:** the workspace has its own repo (canonical going forward); the old `NAVISENSE` root
  repo is a frozen backup. Do not develop in the old root.

## 3 · Dependency management

- **Python:** pinned-ish in `requirements.txt` (numpy, pyyaml, matplotlib). Update in the venv, run the
  full QA set, and only then commit the new `requirements.txt`. Heavy optional deps (`casadi`, `torch`,
  `stable-baselines3`) are for `nmpc`/`ppo` only — keep them optional.
- **Unreal engine/plugins:** the project targets **UE 5.7** with Water/WaterAdvanced/WaterExtras/
  PCGWaterInterop/Buoyancy/MovieRenderPipeline/PythonAutomationTest/CesiumForUnreal/ModelingToolsEditorMode.
  Before bumping the engine or Cesium plugin, branch first and re-run the full regression — Cesium has
  hard engine-version floors (check release notes).
- Record any dependency change in `Documents/PROGRESS.md` and, if it caused a fix, in Known Issues.

## 4 · Logs, caches & disk hygiene

- **Run logs** accumulate under `logs/`. Keep representative/validation runs; periodically archive or
  delete throwaway runs. `logs/runs.csv` is the index.
- **Cesium request cache** (`cesium-request-cache.sqlite`, can be hundreds of MB) is machine-local and
  git-ignored — safe to delete to reclaim space; it refills on next run.
- **UE transient dirs** (`Binaries/Intermediate/DerivedDataCache/Saved`) can be deleted to force a clean
  rebuild; never commit them.

## 5 · Configuration & tuning

- **Vessel dynamics:** `Maneuvering/maniobrabilidad/mmg/DOLPHIN.yaml` (MMG coefficients) is the source of
  truth for ship behavior. Keep it under version control; note the CFD/validation provenance of any change.
- **Visual/runtime tuning:** the `UNaviSenseVesselProfile` data asset (freeboard, rate limits, pose-lerp)
  tunes visuals without recompiling. Prefer data-asset edits over code edits for tuning.
- **Invariants (never violate)** — also in `../CLAUDE.md`: coordinate/sign only in `NaviSenseCoords.h`;
  socket RX thread never touches UObjects; DTO field names match JSON keys; controllers fed plant yaw.

## 6 · The automation (scheduled sessions)

- `navisense-daily-work-packet` (~07:00 daily) and `navisense-friday-traction` (Fri) prepare work + GTM
  packets. They run only while the desktop app is open; if missed, they run on next launch.
- Manage them in the app's **Scheduled** panel (pause/resume/edit). Pre-approve their tools once via
  "Run now" so future runs don't pause on permissions.
- **Objective run-log gates for the 02:00 nightly (exit 0/1):** `python/verify_run_kinematics.py` (plant health, K1–K8) and `python/verify_sensors_fidelity.py` (sensor GPS/IMU fidelity vs plant, D1–D8; `--selftest` runs negative controls). Wire both in when the nightly runs on a build.

## 7 · Documentation upkeep

- `PROGRESS.md` is the living ledger — one line per packet, always with the current blocker.
- When the project state changes materially (a gate closes, an architecture decision), update the relevant
  doc's status banner the same day. The doc set is "current" only if a reader who opens any file sees the
  truth at the top.
- This Manual/Troubleshooting/QA folder is itself maintained: every new bug → Known Issues; every release
  → checklist; review the whole folder monthly (update the "Last updated" dates).

## 8 · The D: drive operating rules (learned the hard way)

- **Large file writes can truncate.** When creating/replacing a large file, write via shell redirection
  and verify (line count + parse). Don't trust a silent save of a big file.
- **Git is Windows-only here.** Never run git against the `D:` workspace from non-Windows tooling.
- Both rules are encoded in `../CLAUDE.md` so the automation respects them too.

## 9 · Documentation Update Protocol (keep everything current)

**Canonical spec:** `../CLAUDE.md` → "Documentation Update Protocol". The daily session is bound to it.

The rule in one line: **a change isn't done until its docs are updated the same session.** Concretely:
- Every work packet → a `Documents/PROGRESS.md` ledger line (always).
- Every test/verify run → a row in `05_Test_Log.md`.
- Every bug → a `KI-NNN` in `04_Known_Issues_Register.md` (and a Troubleshooting entry if user-facing); on fix → mark RESOLVED + Test Log PASS.
- Any demo-gate (D1–D8) move → `PROGRESS.md` burndown + the affected doc's status banner.
- New command/flag/feature → `00_Operations_Manual.md` + a new `TC-NNN` in `03_QA_Test_Plan.md`.
- Release/demo → `Templates/release_checklist.md` + QA sign-off + git tag (blocked until regression green).

This is the mechanism that keeps the whole doc set accurate as the project grows.


## Live Coding vs. full rebuild (verify C++ fixes) — added 2026-06-21

Live Coding (Ctrl+Alt+F11) patches the **in-memory** module with `patch_N.dll`; it does **not** rebuild the base `UnrealEditor-NaviSense.dll`, and with Blueprint re-instancing it can silently skip a translation unit even when it reports *Result: Succeeded*. Symptom (KI-018, 21 Jun): a correct on-disk fix had no effect in PIE. **Rule: to VERIFY a C++ fix (esp. a gate), do a full rebuild with the editor CLOSED, then relaunch** — either `Build.bat NaviSense_UE5Editor Win64 Development -Project="...NaviSense_UE5.uproject"` (look for `Link UnrealEditor-NaviSense.dll` in the log) or Visual Studio → Build Solution. Live Coding remains fine for fast iterative *authoring*; just don't trust it as the gate.
## · Wake & spray VFX (D5 / WP-16) — added 2026-06-28

The wake is **speed-driven**, not a fluid sim (KI-025). The speed→VFX curve is single-sourced in
`python/wake_model.py` and mirrored in C++ (`ANaviSenseShipPawn::GetWakeIntensity01()` / `GetWakeSpray01()`);
`verify_20260628.py` (TC-29) asserts the two stay in sync — **if you change the curve, change it in BOTH and
re-run that gate.** Tune speeds without recompiling via the pawn's *NaviSense | VFX* UPROPERTYs
(`WakeFullSpeedMS` / `WakeSprayOnsetMS` / `WakeMinSpeedMS`). Set up / refresh the in-engine VFX with
`Content/NaviSense/Python/Phase5_Systems/04_setup_wake_vfx.py` + `Documents/NaviSense_Wake_VFX_Recipe.md`
(build the `NS_Wake` Niagara system there). Keep the wake under a **<2 ms** `stat GPU` budget (perf risk R5).

## · Scripted traffic ships for COLREGS (WP-15B) — added 2026-06-29

The COLREGS evidence layer is validated against a **deterministic scripted preset**; WP-20260629B renders those contacts in-engine by driving the placed *Traffic* actors from the listener over the wire. **Wire (additive, no schema bump):** `state.v1` gains an optional `traffic[]` array (`FNaviSenseTrafficTarget` in its OWN header `Bridge/NaviSenseTrafficTypes.h` so the B1 wire-parity guard keeps checking the 22 own-ship keys only). **Pawn:** `ApplyTraffic()` drives each mapped actor with the same `NaviSenseCoords` conversion + own-ship spawn anchor (invariant #1), keeps the actor's placed Z, and forces it Movable. **A C++ rebuild is required** (DTO + pawn changed) — full rebuild, editor closed (see the Live-Coding rule above). **One-time in-editor setup:** run `Content/NaviSense/Python/Phase5_Systems/07_setup_traffic_ships.py` (KI-013: script, not the menu) to set the 3 props Movable, tag them `NaviSenseTraffic`, and assign the pawn's `TrafficActors`; it saves the level. **Tune the encounter** in `python/ais_traffic.py → _PRESETS["monaco_capture"]` (4 numbers per ship). Honesty: the ships are visual props on a scripted preset — not a live AIS receiver / not autonomy (KI-009 / KI-019 family).
