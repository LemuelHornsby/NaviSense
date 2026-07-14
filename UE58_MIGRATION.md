# UE 5.7 → 5.8 Migration Runbook (NaviSense_UE5)

Status: **DO NOT MIGRATE YET** — blocked on one dependency (Step 1). Everything else is ready.
Written: 2026-07-14. Project reviewed: `NaviSense_UE5.uproject` (EngineAssociation 5.7, C++ module `NaviSense`, 22 source files).

---

## Why this order matters (one-way doors)

- **Assets saved in 5.8 can NEVER be opened in 5.7 again.** Opening the project in 5.8 is safe; *saving* any asset is the point of no return. That's why we migrate a COPY and keep the 5.7 original untouched until validation passes.
- **CesiumForUnreal is a C++ marketplace plugin installed into the engine, not the project.** A 5.7 binary cannot run in 5.8 — it needs a build compiled specifically for 5.8. Your Monaco level depends on it; without it the level opens with broken Cesium actors.
- Engine plugins (Water, WaterAdvanced, WaterExtras, PCGWaterInterop, Buoyancy, MovieRenderPipeline, PythonAutomationTest) ship inside UE 5.8 — nothing to install for those.

---

## Step 0 — Finish 5.7 business first (recommended)

Demo closeout (film, D7, KI-034 recompile) is ~20 min of work on 5.7. Do it BEFORE
migrating — a migration mid-demo means re-verifying everything twice.

1. Complete the pending PIE/capture session + `verify_demo_session.py` closeout on 5.7.
2. Run the full gate suite once more and archive the output — this is your **green 5.7 baseline** to compare 5.8 against.
3. Verify your hard-drive backup actually contains, at minimum:
   - `NaviSense_UE5/` → `Content/`, `Source/`, `Config/`, `NaviSense_UE5.uproject`
   - workspace root → `python/`, `Maneuvering/`, `python_listener.py`, `Development/`, `Documents/`, all `.bat`/`.py` runners
   - (`Binaries/`, `Intermediate/`, `DerivedDataCache/`, `Saved/` are regenerable — nice to have, not required)
   - Spot-check: open 2–3 files from the backup; compare `Content` folder size vs original (~2.4 GB).
4. Optional but strongly advised: initialize git per `GIT_SETUP.md` (still not done — no `.git` in the workspace). A tagged commit `pre-5.8-migration` beats any folder copy.

## Step 1 — THE GATE: Cesium for Unreal build for 5.8

As of 2026-07-14 the latest Cesium release is **v2.27.0 (1 Jun 2026) and supports only UE 5.5/5.6/5.7**. 5.8 support is merged (issue #1846 closed via PR #1856) and slated for their **July 2026 release** — imminent but not published yet.

Check before proceeding (either source):
- https://github.com/CesiumGS/cesium-unreal/releases → look for `CesiumForUnreal-58-vX.Y.Z.zip`
- Epic Games Launcher → Fab library → Cesium for Unreal → "Install to Engine" listing 5.8

**If no 5.8 build exists: STOP. Stay on 5.7.** Nothing else in this runbook is time-sensitive.

## Step 2 — Toolchain

1. Update **Visual Studio 2022** to the latest 17.x via VS Installer (workload: *Game development with C++*, incl. latest MSVC v143 + Windows SDK). UE 5.8 requires a newer MSVC than 5.7 did; UBT names the exact minimum if yours is too old.
2. Confirm UE 5.8 is fully installed in the Epic Launcher (you've done this).

## Step 3 — Migrate a COPY (never in place)

In PowerShell:

```powershell
cd "D:\Marine Autonomy\NAVISENSE\NaviSense Simulator with Unreal Engine"

# Copy project, excluding regenerable dirs (fast: copies ~2.5 GB not 10 GB)
robocopy NaviSense_UE5 NaviSense_UE5_58 /E /XD Binaries Intermediate DerivedDataCache Saved /XF cesium-request-cache.sqlite
```

1. Install the Cesium 5.8 plugin into the UE 5.8 engine **before first open** (Fab "Install to Engine 5.8", or unzip the GitHub release into `C:\Program Files\Epic Games\UE_5.8\Engine\Plugins\Marketplace\`).
2. Right-click `NaviSense_UE5_58\NaviSense_UE5.uproject` → **Switch Unreal Engine version…** → 5.8. (This rewrites `EngineAssociation` and regenerates the `.sln`.)
3. Open the new `.sln` in VS → set **Development Editor | Win64** → Build. Expect success with possible deprecation warnings (the module's deps — Core, Json, Sockets, Networking, Water, UMG/Slate — are all stable APIs). Fix any hard errors before opening the editor.
4. Launch the editor by double-clicking the copy's `.uproject`. First open = full shader + DDC recompile (Substrate + ray tracing + Water + Cesium — expect a LONG first load; let it finish).
5. In the editor: Edit → Plugins → confirm Water, WaterAdvanced, WaterExtras, PCGWaterInterop, Buoyancy, MovieRenderPipeline, PythonAutomationTest, Cesium for Unreal all enabled and loaded without errors. Open `NaviSense_Monaco` and confirm Cesium tiles stream.
6. **Do not Save / Save-All / resave anything yet.** Look first.

## Step 4 — Validate with the existing gate suite

The whole point of your verification infrastructure — it IS the migration acceptance test.
Run against the 5.8 copy (listener + editor from the copy):

1. `preflight_demo.py` → GO
2. `python run_demo.py --selftest` (headless, no UE)
3. One real PIE run (MMG, SS2, traffic on) →
   - `verify_run_kinematics.py` K1–K8 green
   - `verify_sensors_fidelity.py` 8/8 (+ neg-controls)
   - `run_colregs.py` scenarios → `verify_colregs --matrix`
   - `verify_demo_session.py` (TC-49)
4. Eye-checks: hull floats at waterline, twin props counter-rotate, sea-state schedule cross-fades, dashboard binds.
5. Compare KPIs vs the Step-0 5.7 baseline (evidence pack diff). Note: 5.8 changed the default Windows audio backend (XAudio2 → WASAPI) and reworked PCG scheduling — neither should touch the MMG/bridge path, but the baseline diff is what proves it.

**Anything red → close the editor WITHOUT saving, fix or abandon; the copy is disposable.**

## Step 5 — Adopt or roll back

Rollback = delete `NaviSense_UE5_58`, keep using the untouched original. Done.

Adopt (only after Step 4 is fully green):
1. Now allow saves in 5.8. If the editor prompts to update assets, or you resave maps, that copy is permanently 5.8.
2. Rename: `NaviSense_UE5` → `NaviSense_UE5_57_frozen` (rollback keepsake), `NaviSense_UE5_58` → `NaviSense_UE5`. (Renames also sidestep the sandbox no-delete rule on D:.)
3. Update version references:
   - `setx UE_ROOT "C:\Program Files\Epic Games\UE_5.8"` (used by `Development\automation\automation_config.ps1` → nightly tasks)
   - `README.md`, `SETUP.md` (three "5.7" mentions incl. the Cesium/KI-014 note), `CLAUDE.md` if applicable
4. Keep UE 5.7 installed + the frozen 5.7 project for at least a couple of weeks of stable 5.8 use. Commit the migrated state to git.
5. Re-run one DEMO_*.bat end-to-end as the final smoke test.

---

## Known post-migration watch-list

- **Shaders/DDC**: first PIE after migration also recompiles PSOs — don't film benchmarks on first run.
- **Audio**: if capture audio behaves oddly, 5.8's WASAPI default is the suspect; XAudio2 remains an opt-in fallback.
- **Editor Python**: unchanged rule applies (KI-036 — never `Popen` from editor Python).
- **Cesium request cache**: excluded from the copy on purpose; it regenerates (KI-014 token rules unchanged).
