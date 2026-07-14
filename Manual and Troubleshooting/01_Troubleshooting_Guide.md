# 01 · NaviSense Troubleshooting Guide

**How to use:** find the area, match the symptom, apply the fix. Entries marked **[seen]** are issues
actually encountered on this project; **[anticipated]** are likely ones with pre-written fixes.
Log anything new in `04_Known_Issues_Register.md`. **Last updated:** 12 July 2026 (WP_20260712 sweep: added §H demo-prep tooling & traffic symptoms — KI-029/KI-030/KI-034/KI-036 — which post-dated the 18 Jun edition). Prior: 18 June 2026.

> First diagnostic move for any "it's not behaving" issue: **read the run log**. `logs/<latest>/state.csv`
> tells you the truth — is `mode` stuck in `approach`? is `rudderCmdDeg` 0? is `yawDeg` changing? The
> picture on screen can mislead (camera, scale); the CSV does not.

---

## A · Bridge / connection

| Symptom | Likely cause | Fix |
|---|---|---|
| **[seen]** `bridge connect FAILED … Is python_listener running first?` | Listener not started, or wrong port | Start `python_listener.py` first. Since WP-3, UE auto-reconnects — wait for the **CONNECTED** banner. |
| **[seen]** `[WinError 10048] address already in use` / port 5005 busy | A previous listener/harness still holding the port | Close the old terminal / Ctrl-C it. Find it: `netstat -ano | findstr :5005` then `taskkill /PID <pid> /F`. |
| Banner stays **RECONNECTING…** forever | Listener crashed on startup (see its terminal), firewall, or wrong `--port` | Read the listener terminal for a traceback; confirm it printed `Waiting for Unreal…`; allow Python through Windows Firewall (loopback). |
| **[seen 18 Jun]** Listener crashes at startup: `ModuleNotFoundError: No module named 'yaml'` (or `numpy`) / `PyYAML is required` | Python deps not installed in the interpreter you launched — `--plant mmg` loads `DOLPHIN.yaml` (needs PyYAML) and integrates with numpy | Install the stack once: `cd "…\NaviSense Simulator with Unreal Engine"` → `python -m venv .venv` → `.\.venv\Scripts\Activate.ps1` → `pip install -r requirements.txt` (numpy + pyyaml + matplotlib). Re-run the listener from the **activated venv** (the nightly automation also prefers `.venv\Scripts\python.exe`). Quick no-install smoke test: `--plant stub` needs no YAML. |
| Pawn moves then **freezes** with "STALE — holding position" | Listener stopped sending `state.v1` (>1 s) | Expected failsafe (WP-3): the pawn holds at last pose, never drifts. Restart the listener; it resumes. |
| Connected but **pawn doesn't move** | Pawn not possessed / wrong MotionSource | Pawn → Auto Possess Player 0; MotionSource = **PoseReceive**. Confirm `state.v1` is flowing (verbose log). |
| Frame **hitches** correlated with sends | (pre-WP-3) blocking socket send | Resolved by WP-3 non-blocking `PumpTx`. If it recurs, trace `NaviSenseBridge_PumpTx` in Insights (should be µs). |

---

## B · Controllers / maneuvers

| Symptom | Likely cause | Fix |
|---|---|---|
| **[seen]** Ship runs **straight, never zig-zags**; `state.csv` shows `mode=approach`, `rudderCmdDeg=0` for the whole run | Closed-loop controller never left the approach phase because it couldn't read heading from the sensor echo | **Fixed (14 Jun):** the listener now feeds controllers the plant's authoritative yaw, and the pawn auto-wires its `SensorBundle`. Pull latest listener; recompile UE. To verify quickly, `turning_circle` is open-loop and always turns. |
| **[seen]** "Nothing turns for the first minute" | The 60 s **approach** phase (by design — IMO procedure) | Wait past 60 s, or `--time-scale 10` to fast-forward. Not a bug. |
| **[seen 18 Jun]** Hull turns fine, then **spins on the spot** after a long turn (past ~180° of heading) | Pawn smoothed yaw with `FInterpTo` on the raw scalar; actor yaw is [-180,180] but the wire sends [0,360), so past 180° it chases a 360° gap and spins (KI-018). The **log is clean** — `r`/speed bounded — so it's visual only | **Fixed (18 Jun):** pawn now uses `FMath::RInterpTo` (shortest-angle). **Recompile** (Ctrl+Alt+F11) and rerun. NB `turning_circle` then circles **continuously** by design — for turn-then-straighten use `zigzag10`/`zigzag20`. |
| **[seen]** `unrecognized arguments: -v` | Running a listener variant without the short alias | Use the **canonical** listener at the workspace root (now supports `-v`). Don't run a stray copy. |
| Bow turns the **wrong way** for a given rudder | Coordinate sign convention | Fix **only** in `Source/NaviSense/Core/NaviSenseCoords.h::WireYawToUE`. Re-run the harness sign test + an in-engine `turning_circle` to confirm. Never add a local negate elsewhere. |
| `zigzag` overshoots look implausible | Plant tuning or speed | Check `DOLPHIN.yaml` coefficients; confirm steady approach speed reached before the maneuver; compare with `analyse_zigzag.py` vs IMO criteria. |
| `waypoint` / `nmpc` / `ppo` do nothing | Missing input file | `waypoint` needs `--path-file`; `nmpc` needs `--goals-file` + `--active-goal`; `ppo` needs `--policy-file` (and `torch`). |

---

## C · Build / compile (Unreal C++)

| Symptom | Likely cause | Fix |
|---|---|---|
| **[seen]** Need to apply a C++ change | — | **Live Coding:** Ctrl+Alt+F11 in the editor → watch for `Result: Succeeded` / `Live coding succeeded`. |
| **[seen]** Editor **freezes/crashes** on right-click → *Miscellaneous → Data Asset* | Class-picker enumerates all Data Asset classes (incl. Cesium); on a heavy Cesium scene it can hard-freeze the GPU driver | Don't use the menu. Create the asset by script: *Tools → Execute Python Script* → `Content/NaviSense/Python/Phase1to3_Foundation/04_create_vessel_profile.py` (creates `DA_DOLPHIN_VesselProfile` directly). Also let the editor finish loading/shader-compiling first; update the GPU driver. (KI-013) |
| Live Coding warns it can't patch (constructor/UPROPERTY change) | Live Coding can't always patch CDO/reflection changes | Close the editor → build in VS (`NaviSense_UE5.sln`, **Development Editor / Win64**) → reopen. |
| `00_preflight` shows `navisense_module_compiled: false` | Module not built / stale binaries | Rebuild from VS, or delete `NaviSense_UE5/Binaries` + `Intermediate` and double-click the `.uproject` → rebuild. |
| No `.sln` to open | Project files not generated | Right-click `NaviSense_UE5.uproject` → **Generate Visual Studio project files**. |
| Build error after pulling new `Source/` | Header/intermediate mismatch | Delete `Intermediate/`, regenerate project files, rebuild. |

---

## D · Coordinate / sign / units

- **Authority:** all wire↔Unreal conversion lives in `FNaviSenseCoords` (`NaviSenseCoords.h`). Do not
  convert anywhere else. Wire frame = x=East, y=Up, z=North (metres), yaw CW from North; Unreal = cm, Z-up.
- **Sign test (canonical correctness gate):** command +10° rudder ⇒ bow swings **starboard** and `yawDeg`
  increases, in **both** the Python log and the HUD. If wrong, fix once in `WireYawToUE`.
- **Units:** wire positions are metres; UE is centimetres (×100 in `FNaviSenseCoords`). IMU yaw-rate is
  deg/s; wire `r` is rad/s — don't double-convert.

---

## E · Logging / analysis

| Symptom | Cause | Fix |
|---|---|---|
| No `logs/` folder appears | `--no-log` was set, or you're not at the workspace root | Drop `--no-log`; run the listener from the workspace root. |
| Run produced data but analysis script finds nothing | Maneuver never started (stuck in `approach`) | See B (the heading-feed fix); confirm `mode` reaches `zigzag_10`/`coast` in `state.csv`. |
| `matplotlib not installed; skip plot` | Optional dep missing | `pip install matplotlib` (in the venv). |
| Want to compare runs | — | Each run is its own timestamped folder; `logs/runs.csv` indexes them all. |

---

## F · Git / backup / the D: drive

| Symptom | Cause | Fix |
|---|---|---|
| **[seen]** A fresh `git init` left a **broken `.git`** (bad config, can't be removed by tools) | The `D:` drive blocks some `.git` lock/unlink ops from non-Windows tooling | Manage git **only from Windows PowerShell**. To clear a broken repo: `Remove-Item -LiteralPath ".\.git" -Recurse -Force` (or `cmd /c rmdir /s /q .git`). |
| **[seen]** A large file "saved" but is **truncated mid-file** (won't compile / parse) | The `D:` drive truncates large editor/tool writes | Re-create large files via shell/redirect and **verify** (line count + parse). Prefer many small edits over one huge write. |
| Need to set up the repo | — | Follow `../GIT_SETUP.md`: delete broken `.git` → `git init` → `git lfs install` → scoped commits → push to a **new private remote**. |
| `git push` rejects large assets | LFS not tracking them | `git lfs install`; confirm `.gitattributes` patterns; `git lfs ls-files` should list `.uasset/.umap/textures`. |
| Worried about losing work | No off-machine remote yet (top open risk) | Create the private remote per `GIT_SETUP.md`; keep the external-drive backup current until then. |

---

## G · Environment / Cesium / visuals

| Symptom | Cause | Fix |
|---|---|---|
| Monaco tiles don't stream / grey world | Missing/expired Cesium ion token | Add your token in the Cesium panel; check network; the request cache is machine-local (git-ignored). |
| Waterline clipping through the hull | 3-DOF pose (no heave yet) + freeboard offset | Known limitation (finding F1). Adjust `FreeboardCm` on the vessel profile; full fix = 6-DOF schema v1.2 (planned). |
| Hull looks like it slides on a flat plane | No wave-surface sampling yet (3-DOF) | Planned: Week-2 6-DOF + water sampling. Not a regression. |
| Commercial use of Google 3D Tiles unclear | Licensing (finding F9) | Keep BYO-token; verify Google tiles terms before shipping marketing footage; maintain the non-Google fallback profile. |
| **[seen]** "Asset … `__ExternalActors__/…NaviSense_Monaco…` failed to save" dialog | A broken Cesium tileset external actor (World-Partition OFPA) that failed to import — same root as KI-014 | Click **Continue** (skips only that asset; everything else saves — pawn/sensors/rig are safe). Never Cancel (aborts all saves). Fix root: Cesium plugin enabled + UE-5.7-compatible + ion token; else delete & re-add the tileset. |

---

## H · Performance

| Symptom | Cause | Fix |
|---|---|---|
| Low FPS in Monaco | Lumen + Water + photoreal tiles + Niagara competing | Capture `stat unit` / Unreal Insights; set a budget (e.g., 60 fps @1440p on the dev GPU); LOD/Nanite pass (planned W10). |
| Stutter while tiles load | Cesium streaming | Pre-warm the area; reduce tile screen-space error for capture; let the cache fill on a first pass. |

---

## I · Python environment

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'mmg'` | Running the listener outside the workspace, or the MMG package missing | Run from the workspace root (the listener adds `Maneuvering/maniobrabilidad` to the path). The package lives at `Maneuvering/maniobrabilidad/mmg`. |
| `ModuleNotFoundError: numpy/yaml` | venv not activated / deps not installed | Activate `.venv`; `pip install -r requirements.txt`. |
| `casadi` / `torch` import errors | Optional autopilot deps not installed | Install only if using `nmpc`/`ppo` (see commented extras in `requirements.txt`). |

---

## Escalation

If a fix isn't here: (1) reproduce with `--verbose` and keep the `logs/<run>/` folder; (2) note the exact
build (Live Coding patch # or VS build), command line, and a screen capture into `../Development/Development videos/`;
(3) open a `KI-NNN` entry in `04_Known_Issues_Register.md` using `Templates/bug_report_template.md`.


## Manual drive (M / WASD) does nothing in PIE — added 2026-06-21 (KI-021)

**Symptom:** pressing `M` shows no cyan `NaviSense motion: MANUAL` message and W/S/A/D don't move the boat; a default character stands on the deck. **Cause:** the GameMode spawned a default pawn that possesses Player 0 instead of the yacht, so the yacht's input polling sees no controller. **Fix:** World Settings → **GameMode Override** → a GameMode with **Default Pawn Class = None** (the placed yacht's Auto Possess Player 0 then takes Player 0). Bridge-driven runs are unaffected by this (they need no possession).


## Editor CRASHES on Miscellaneous > Data Asset — confirmed 2026-06-21 (KI-013)

**Symptom:** right-click > Miscellaneous > Data Asset hard-crashes the project (the class-picker enumerates Cesium classes on a heavy scene). **Rule:** never use that menu in this project. **Create Data Assets via script** instead: Tools > Execute Python Script > `Content/NaviSense/Python/Phase1to3_Foundation/06_create_hydrostatics_config.py` (creates the vessel profile + hydrostatics config, idempotent). New data-asset types should get a similar create-script.

## Twin propellers won't spin, or orbit / wobble — added 2026-06-24 (KI-023)

After splitting a merged prop into separate port/starboard meshes:

- **Don't spin at all** (Output Log `propeller=MISSING` or `single-merged`): the actuator-viz resolver only grabs a component whose name contains **`prop`** *and* a side (`_p`/`port` or `_s`/`stbd`). Name the spun component `prop_port`/`prop_starboard`; the mesh you do **not** want spun must **not** contain "prop".
- **Spin but ORBIT in a big arc:** the spun component's pivot is far from the hub. A static mesh spins about its **asset origin**, and if you exported the prop *at its original position*, that origin is the model's world origin (on the DOLPHIN, ~3.6 m from the hub). Fix without re-export: parent the mesh under an empty **Scene** component placed **at the hub**, named `prop_port`/`prop_starboard` — the code spins the pivot, the blades follow on-axis. (Or re-export with the mesh origin moved to the hub.)
- **Spin but WOBBLE/tumble:** the pivot's local **X** isn't along the shaft. In a side ortho view (Alt+K), rotate the pivot so its red **X arrow lies on the shaft line** (the code spins about local X = Roll).
- **10× too big / too small on import:** unit mismatch. Match the part's FBX export units to the hull — the DOLPHIN hull is **centimeters / UnitScaleFactor 1.0**; an **mm / USF 0.1** export imports 10× oversize. Fix with **Import Uniform Scale 0.1** on (re)import, or re-export in cm.
- **Both spin the same direction:** toggle `bInvertPortProp` / `bInvertStarboardProp` (pawn → *NaviSense | ActuatorViz*). Both backwards: flip `PropellerVisualSign`.
- **Instance vs class:** components added to the **placed pawn in the level** work for that pawn (just **Save the level**, no Compile) but exist in the **Blueprint class** only if added there. For permanence / clean-machine repro, recreate them in `BP_ShipPawn_Yacht`.
## Wake VFX missing or not scaling with speed — added 2026-06-28 (WP-20260628, KI-025)

**Symptom:** no wake/spray behind the yacht, or it doesn't change with speed.
**Checks (in order):**
1. **Component present?** The placed yacht needs a `WakeViz` NiagaraComponent at the stern — run
   `Tools → Execute Python Script → Content/NaviSense/Python/Phase5_Systems/04_setup_wake_vfx.py`.
2. **NS_Wake built + assigned?** If the Output Log says *NS_Wake not found*, build it per
   `Documents/NaviSense_Wake_VFX_Recipe.md` §3, then re-run the script to assign it.
3. **User params bound?** On `BP_ShipPawn_Yacht` Event Tick, `User.WakeIntensity = GetWakeIntensity01`
   and `User.Spray = GetWakeSpray01` (recipe §4). If the getters don't appear, the C++ wasn't rebuilt —
   do a full `Build.bat` (Live Coding won't relink the base DLL, KI-018), or use the **no-recompile
   fallback** (recipe bottom: drive the params from BP position-delta speed).
4. **No wake at all speeds?** Confirm the boat is actually making way (`GetSpeedMetersPerSec` > the 0.3 m/s
   dead-band); in a bridge run the speed comes from the plant. **Spray only above ~15 kn** is correct (KI-025).
## Ship spins on the spot / turns far too tight — added 2026-06-28

**Symptom:** in a `turning_circle` the ship pivots in place (tiny radius, fast yaw, looks like it spins about the stern) instead of tracing a wide natural circle.
**Cause:** the listener ran with the **default `--plant stub`** (a kinematic placeholder that plays back a fixed commanded yaw rate), not the dynamic MMG plant. The stub pins the yaw rate so the radius collapses to a few metres.
**Fix:** always pass **`--plant mmg`** for realistic maneuvering, e.g. `python python_listener.py --plant mmg --scenario imo_turning_circle --sea-state 0 --target unreal --verbose`. Tell-tale in `logs/<run>/state.csv`: the stub logs suspiciously round values (`u=1.500000`, `r=0.420000`); the MMG plant logs messy dynamics (`u=1.279893`, `r=0.018811`) and an ~80 m turn radius. (Optional hardening: change the `--plant` default to `mmg` in `python_listener.py`.)
## Ocean is neon cyan / water-colour edits don't show — added 2026-06-28

**Symptom:** the UE Water plugin ocean renders bright tropical cyan; editing the water material instance's colour appears to do nothing.
**Cause:** (1) the colour is the **SingleLayerWater Absorption/Scattering vector params on the water material INSTANCE** — `MPC_Water` holds only wave/sim data (Gerstner `k*`/`w*`, positions, time), **no colour**; (2) the **WaterZone caches its water materials at level load**, so editing the source MI doesn't update the live sea until a refresh.
**Fix:** set Absorption/Scattering on the MI assigned to the WaterBody (**Water Material** + **Water Static Mesh Material**) — or run `Content/NaviSense/Python/Phase5_Systems/05_set_ocean_water_color.py` — then **RE-OPEN the level (or press Play)** to force the WaterZone to rebuild from the updated MI. Natural Monaco blue ≈ **Absorption (8, 70, 420)**, **Scattering (0, 0.25, 0.40)**. (`06_fix_water_mpc_color.py` confirms MPC_Water carries no colour — useful diagnostic.)

## H · Demo-prep tooling & traffic (added 12 Jul 2026, WP_20260712)

| Symptom | Likely cause | Fix |
|---|---|---|
| **[seen 7–8 Jul]** `preflight_demo.py` / rehearsal says **NO-GO / NOT READY** but nothing changed | KI-029 (self-test run truncated under CPU load) or KI-030 (an interrupted newer run shadowed a good complete run) | Both RESOLVED 7–8 Jul aggregator-side — pull the current tree and re-run; a persisting NO-GO after that is REAL, read the failing gate line. |
| **[seen 8 Jul]** A Traffic ship renders **lying on its side** ("fin") while moving | KI-034: `ApplyTraffic` stomped the PLACED pitch/roll (mesh-import axis correction) with `FRotator(0, wireYaw, 0)` | Fix authored 9 Jul in `NaviSenseShipPawn.h/.cpp` — needs **ONE Live Coding recompile (Ctrl+Alt+F11)**, then re-check in PIE (G_TRAFFIC_UE). |
| **[seen 9 Jul]** Running a COLREGS scenario from editor Python **opens a second editor window** | KI-036: editor Python's `sys.executable` IS `UnrealEditor.exe`, so any `Popen` respawns the editor | RESOLVED 9 Jul: launch scenarios from a **terminal** via `python run_colregs.py --<scenario>`; the in-editor picker is print-only by design. |
| **[seen 12 Jul]** `run_demo` ends with `UnicodeEncodeError: 'charmap' codec can't encode '\u26a0'` while building the evidence pack (Exit code 1, run itself healthy) | KI-037: markdown/kpis writers used the Windows default cp1252 encoding | RESOLVED 12 Jul — writers pinned to UTF-8; pull current tree and re-run `python/build_evidence_pack.py --run-dir logs/<run>` to rebuild the pack. |
| **[seen 12 Jul]** `verify_20260711.py` fails **G5 only** (`No module named pytest`) on a fresh sandbox/CI box | Environment, not the repo — fresh sandboxes ship without pytest | `pip install pytest --break-system-packages`, re-run; the other four gates are unaffected. |

### Evidence pack refuses: `P0 view-completeness FAIL … PARTIAL VIEW (KI-038)` — added 13 Jul 2026 (WP_20260713)

**Symptom:** `build_evidence_pack.py` exits 3 with `PARTIAL VIEW: read N of M manifest rows` or `manifest.json unreadable/truncated`.

**Cause:** the process is looking at a **stale partial view** of the run dir (KI-038) — seen live on run 125800, where the sandbox mount froze `state.csv` at 47% and cut `manifest.json` mid-token for ≥20 h while Windows had the full files. A pack built from such a view silently undersells (or invalidates) the run.

**Fix:** rebuild where the full log is visible — normally a **Windows terminal**: `python python\build_evidence_pack.py --run-dir logs\<run>`. Expect the `view : complete (N/N rows)` line. `--allow-partial` is for forensics only and watermarks every artifact. Never use a pack whose `kpis.json` `meta.view_complete` is not `true` as demo evidence.

### COLREGS run: bridge connects but the encounter never starts / ship idles — added 14 Jul 2026 (Session A)

**Symptom:** `run_colregs.py --<scenario>` + Play: UE connects instantly but the own ship keeps a transit course (or crawls at stub speed) and the rescue boat never moves; afterwards `logs/` shows the run as `scenario=monaco_capture` (or the previous scenario) instead of the COLREGS one.

**Cause:** an earlier `python_listener.py` is still running in another terminal. Since the re-accept fix (KI-017), a listener SURVIVES PIE Stop/Play — it holds port 5005, so UE reconnects to the stale listener and the new runner never receives the connection.

**Fix:** Ctrl+C every old listener terminal; confirm with `netstat -ano | findstr :5005` (no LISTENING line), then start `run_colregs.py` and check its banner names the avoid scenario + `plant: MMG`. Rule: **one listener at a time** — kill the previous one before each new scenario/runner.

### Bridge overlay stuck `RECONNECTING…` while a runner/listener is up — added 14 Jul 2026 (KI-039)

**Symptom:** listener terminal says `listening on 127.0.0.1:<port>` but the PIE overlay never leaves `NaviSense bridge: RECONNECTING…` and the ship never moves.

**Cause:** port mismatch — the UE pawn dials **5005** (`NaviSenseBridgeComponent.Port`). `run_colregs.py` defaulted to 5502 before 14 Jul (KI-039).

**Fix:** update the tree (default is 5005 now) or pass `--port 5005`. Check the runner banner line `listening on 127.0.0.1:5005` before pressing Play.

### AIS/radar report targets at impossible ranges/bearings (e.g. astern when placed ahead) — added 14 Jul 2026 (KI-040)

**Symptom:** the rendered traffic looks right but `sensor.v1 ais.targets[]`/radar contacts (and anything built on them — dashboard, evidence CPA) show the target at a range/bearing shifted by a constant offset; on the head-on preset the boat 'never approaches'.

**Cause:** sensor geometry compared PLANT-frame wire targets against the pawn's WORLD pose (KI-020 spawn anchor) — fixed 14 Jul (KI-040), needs the Live Coding recompile to take effect.

**Fix:** recompile (Ctrl+Alt+F11), re-run the scenario; at t=0 the head-on target must report ~1,600 m, relBearing ~ -1°.

### Soft-launch film clip rejected as "not a valid MP4/MOV (ftyp/mvhd)" — added 14 Jul 2026 (KI-041)

**Symptom:** `verify_capture_artifacts.py --film-dir …` lists your real recording under "rejected" as "not a valid MP4/MOV (ftyp/mvhd)" and **C3 FAILs**, even though the clip plays fine and is hundreds of MB.

**Cause:** Windows Game Bar / the Unreal editor recorder / OBS write **non-faststart** MP4s — the `moov`/`mvhd` box sits at the END of the file. The pre-14-Jul parser read only the first 4 MB, so it never found the duration and rejected the clip (KI-041).

**Fix:** update the tree — the parser now also reads the tail of the file (proven by `verify_20260714b`). If a clip is *still* rejected it is genuinely truncated (a recording stopped mid-write): re-record, or open it in any player and "save/remux" once to rewrite a clean `moov`.
