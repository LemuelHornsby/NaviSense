# Pending in-engine gates — consolidated for ONE session (refreshed 2026-07-08, WP-20260708B)

> **14 Jul (WP_20260714): evidence side DONE — only the in-engine sitting remains. Follow `Documents/NaviSense_UE5_Gate_Closeout_Guide.md` (supersedes the step order below; the step details remain valid).** Run-125800 pack rebuilt COMPLETE (`view_complete: true`, health 6/6, AIS 3/2) + suite 4/4 + fidelity 6/6 on the full view; `runs.csv` row present; KI-038 view healed. The sitting (~60 min): Step 3 stills + D2 SS5 eye-word · Step 4 film · Step 5 COLREGS matrix · Step 6 `verify_demo_session.py --film-dir` (TC-49) . D8 clean-box pass (~30 min) can be a separate day. **A1 DONE 14 Jul:** suite 4/4 on run 153701; **KI-034 upright-word CONFIRMED ⇒ RESOLVED, G_TRAFFIC_UE ✅** (film beat 1 still to record — fold into A2/COLREGS). **A2 DONE 14 Jul: D2 CLOSED** (SS5 run 155234 eye-confirmed; SS5 clip in `Demo/film`). Left: stills + beat-1 in the first COLREGS run (KI-040 recompile DONE + wire-confirmed; staged-close encounters selftest-proved 4/4 — head-on pass 236 m at t≈145 s) → matrix → A3/A5 closeout. *(13 Jul status: Step 1 ✅ ran 12 Jul PM — run 125800: TC-17 6/6 on 23,393 rows, TC-23 6/6, TC-43 4/4; KI-037 fixed live.)*

> **14 Jul (WP_20260714B, scheduled):** film CAPTURED (3 clips in `Demo/film`) and the closeout verifiers re-run on Session A's live runs. Fixed **KI-041** (film gate false-rejected moov-at-end clips ⇒ **C3 now PASS**) + **KI-042** (COLREGS `matrix()` crashed on a padded result). `verify_20260714b` 4/4+3/3. **Remaining = D6 ≥3 stills (Step 3) + 3 live COLREGS (Step 5: crossing-giveway/standon/overtaking — head_on done) + `verify_demo_session` (Step 6/TC-49) + D8.** Follow the Gate Closeout Guide. **UPDATE 20:07: Session A COMPLETE — SESSION PASS (TC-49); only D8 (clean box) remains.**

> **SLIP NOTE (12 Jul, WP_20260712):** the 11 Jul demo-day target passed without this
> session running (no PIE run since 8 Jul, film dir still empty). Everything below is
> UNCHANGED and re-proved green on 12 Jul (TC-50 5/5 + 3/3, `wp_20260712_result.json`).
> Run the session at the first free slot; it still ends with `verify_demo_session.py`.

> Supersedes the 2026-07-02 version. **Step 0 (the full C++ rebuild) is CLEARED — Lemuel ran it
> 7 Jul: `Build: 53 succeeded, 0 failed`, `Link UnrealEditor-NaviSense.dll` relinked,
> `Result: Succeeded` (~56 s).** Everything below is written + auto-verified headless
> (`verify_20260702b` 5/5 + 3/3, `Z0` 16/16, preflight **GO** re-confirmed 8 Jul). What remains
> is ONE PIE/capture session (+ a couple of editor-Python runs) — Steps 1–4. **Do NOT rebuild
> again** unless C++ changed since 7 Jul (it has not — 3–8 Jul packets were test-tooling only).

> **Session status (8 Jul, later same day, WP-20260708E):** Lemuel is away from the
> laptop (texting from his phone) -- no screen-control approval possible, and Steps 1/3/4
> need him typing the listener commands + driving PIE live anyway, so none of Steps 1-4
> ran this session. **Steps 1, 3, 4 are QUEUED, unchanged below, awaiting that live
> session.** **Step 2 (Bridge Dashboard) is DEFERRED to Lemuel driving it directly** --
> hand-built UMG graph wiring is not reliable to automate blind; do Steps 1/3/4 first,
> Step 2 whenever Lemuel wants to sit down and build it himself. Everything headless was
> re-confirmed green this session (Z0 16/16, pytest 10/10, preflight GO, a genuinely
> interrupted rehearsal run correctly did NOT shadow-mask the verdict -- KI-030 fix holds
> live) and one real tooling bug was found+fixed (KI-033, `verify_sensors_fidelity.py`
> D4 false-FAIL on straight-course runs) -- neither changes anything below.

Canonical run listener (workspace root):
```
cd "D:\Marine Autonomy\NAVISENSE\NaviSense Simulator with Unreal Engine"
python python_listener.py --target unreal --scenario <name> -v
```
(`Development/bridge_harness/python_listener.py` is the offline CI mirror only.)

---

## ⚠ Step 0 — RE-OPENED 9 Jul: ONE recompile needed (WP-20260709 / KI-034)

`NaviSenseShipPawn.h/.cpp` changed 9 Jul (ApplyTraffic now preserves each Traffic
ship's PLACED pitch/roll — the fix for the rolled-mesh "fin"). **Live Coding
(Ctrl+Alt+F11) is sufficient** (additive member + body-only change); if anything
looks stale, do the full Build (editor closed) per the KI-018 lesson. Z0 16/16 +
stacked link audit 5/5 re-verified 9 Jul. History below.

## ✅ (was) Step 0 — full C++ rebuild — **CLEARED 7 Jul (Lemuel)**

`Build: 53 succeeded, 0 failed` · `[14/15] Link UnrealEditor-NaviSense.dll` (base DLL relinked —
a real rebuild, not Live Coding) · `Result: Succeeded`. This compiled the entire 28 Jun → 2 Jul
stacked additive C++ (dashboard getters/setters + UMG/Slate/SlateCore, `sensor.v1`
ais/camera/radar blocks, `traffic[]` render path, wake getters). No C++ has changed since.
If in doubt: `python python/verify_20260702b.py` → PASS means the built DLL is current.

---

## Step 1 — PIE session (scenario `monaco_capture`) — clears the wire/sensor + traffic gates

Start the listener with the 3-ship capture scenario, press **Play**:
```
python python_listener.py --target unreal --scenario monaco_capture -v
```

| Gate | Packet | Confirm in-engine | PASS when |
|------|--------|-------------------|-----------|
| **G_TRAFFIC_UE** ◐ ships MOVE (8 Jul) — re-check orientation after the KI-034 recompile | WP-20260629B | Watch the three *Traffic* ships | excursion_vessel / marine_rescue_boat / Yacht_with_interior (their real Outliner labels — the fictional AIS names were removed 9 Jul, KI-035/WP-20260709) render and MOVE on their scripted courses (overtaking / crossing / head-on); own-ship is give-way to all; placed roll/pitch preserved (KI-034 fix — needs the Step-0 Live Coding recompile first). |
| **G_AIS_SENSOR_UE** ✅ CONFIRMED 8 Jul (run 195058, `verify_sensor_suite` 4/4) | WP-20260701B | `sensor.v1` `ais.targets[]` in the listener log | The array is **populated** (was hardcoded empty) with `{mmsi,name,rangeM,trueBearingDeg,relBearingDeg,cogDeg,sogKn,latDeg,lonDeg}` per contact; range/bearing track the rendered ships. |
| **G_RADAR_UE** ✅ CONFIRMED 8 Jul (run 195058, `verify_sensor_suite` 4/4) | WP-20260702 | `sensor.v1` `radar.contacts[]` in the log | Anonymous blips (no mmsi/name) appear for contacts inside 12 NM with `rangeM`/bearing/`radialSpeedKn`/`closing`; targets beyond range are dropped. |
| **G_CAMERA_UE** ✅ CONFIRMED 8 Jul (run 195058, `verify_sensor_suite` 4/4) | WP-20260701C | `sensor.v1` `camera{}` in the log + stills on disk | The `camera{fovDeg,resX,resY,headingDeg,frameIndex,frameRef,pose}` block emits each tick and `frameRef` names a `HighResShot` still that exists after Step 3. |

*(These four ride the same wire — one `monaco_capture` run exercises all of them.)*

**Objective confirm (NEW 8 Jul, WP-20260708C) — after you stop the run, run ONE command:**
```
python python/verify_sensor_suite.py --latest
```
PASS ⇒ **G_AIS_SENSOR_UE + G_RADAR_UE + G_CAMERA_UE closed with on-disk evidence**
(the run now persists `sensor_raw.jsonl`; result → `Saved/NaviSense_Reports/sensor_suite_result.json`).
Only **G_TRAFFIC_UE** (ships visibly moving on their COLREGS courses) remains an eye-check.
No traffic in the run? Use `--require camera`.

## Step 2 — Bridge Dashboard (editor-Python + manual UMG wiring)

1. Run the scaffold + binding recipe in the editor: `Phase5_Systems/09_build_bridge_dashboard.py`
   (prints the navy theme + full getter/setter binding list; best-effort creates the
   `WBP_BridgeDashboard` stub). Finish the widget per `Documents/NaviSense_BridgeDashboard_Recipe.md`.

| Gate | Packet | Confirm | PASS when |
|------|--------|---------|-----------|
| **G_DASHBOARD_UE** | WP-20260701 | Add to viewport, read the four panels, use the controls | Actuator/sensor/maneuver-KPI/sea-state+AIS panels show live values; **helm / throttle / bow-thruster controls drive the ship** (`SetHelm`/`SetThrottle`/`SetBowThruster` → manual path). Label the maneuver panel a *live proxy*, not the post-run CFD KPI (KI-019). |

## Step 3 — Demo capture (D2 re-check + D6 stills) — clears the capture gates

1. **D2 SS5 wave-ride re-check** (hydrostatics now owns roll/pitch/heave; `WaterlineOffsetCm=-218`):
   run `--scenario rough_turning_circle`, confirm the hull rides the swell (roll/pitch/heave) while
   settled at the boot-top — the remaining D2 item.
2. **D6 beauty stills:** run `Phase5_Systems/08_capture_demo_stills.py` (burst `HighResShot 3840x2160`).
   *(Capture note: if the water reads neon-cyan / "No Loaded Region(s)", re-open `NaviSense_Monaco`
   so the WaterZone reloads the deep-blue material + regions before framing — WP-20260628.)*

| Gate | Packet | Confirm (terminal) | PASS when |
|------|--------|--------------------|-----------|
| **G_CAPTURE_UE** | WP-20260630 | `python python/verify_capture_artifacts.py --latest` | **≥3** full-res (≥3840×2160) stills from this session AND the run passes `verify_run_kinematics` (no spin/NaN). Writes `capture_artifacts_result.json`. |
| **D2 (SS5)** | WP-20260621_HYDRO / 28 Jun | Eye-check the wave ride | Hull rolls/pitches/heaves with SS5 while floating at the boot-top; props/thruster stay submerged. |

## Step 4 — D7 soft-launch film (NEW 8 Jul, WP-20260708B) — screen-record the same session

The 11 Jul soft-launch kit needs a 60–90 s demo clip. Pragmatic path: **screen-record the PIE
runs you are already doing in Steps 1 + 3** — no MRQ setup needed (honesty: this is a screen
recording, not an MRQ cinematic render; MRQ remains the post-demo polish path — the evidence/GTM
copy must say "demo capture", not "cinematic render").

1. **Before pressing Play**, start the recorder: **Win+G** → capture widget → record (or
   **Win+Alt+R**), or OBS if installed. Game Bar saves to `%USERPROFILE%\Videos\Captures`.
   Maximise the viewport (`F11` immersive mode), hide unwanted UI.
2. Record **(a)** the Step-1 `monaco_capture` run — the traffic/COLREGS beat, and
   **(b)** a Step-3 `rough_turning_circle` SS5 pass — the seakeeping beat. Target 60–90 s
   total (2 clips are fine).
3. Stop recording, then gate the session (stills + run health + film in one command):
```
python python/verify_capture_artifacts.py --latest --film-dir "%USERPROFILE%\Videos\Captures"
```

| Gate | Packet | Confirm (terminal) | PASS when |
|------|--------|--------------------|-----------|
| **G_FILM_UE** | WP-20260708B | the command above | **C3**: ≥1 valid clip (MP4/MKV/AVI structurally parsed; MP4 duration from `mvhd` ≥ 20 s; ≥ 5 MB) alongside C1 stills + C2 run health. Flags: `--min-films`, `--min-film-secs`, `--since-epoch` (this session only). |

---

## After the session — what to tell Claude (closes the gates)
Reply with the short results, e.g.:
- "monaco_capture: 3 ships moved; ais.targets + radar.contacts + camera all populated in the log"
- "dashboard: panels live, helm/throttle/thruster drive the ship"
- "capture: verify_capture_artifacts --latest PASS (N stills)"
- "SS5 rough_turning_circle: hull rides the swell at the boot-top"
- "film: verify_capture_artifacts --film-dir ... PASS (clip NN s)"

Each line flips its gate to ✅ (or opens a KI if it failed) with the matching Test-Log row + PROGRESS
burndown update the same session. Nothing here needs new code — only the PIE/capture session +
confirmation. **Total budget ≈ 40–50 min including the recording.**

## Step 5 — COLREGS live matrix (NEW 9 Jul, WP-20260709C) — terminal runner

One command per scenario (listener runs in the FOREGROUND; press Play, stop PIE to end —
each run auto-verifies itself). One-time first: run `Phase5_Systems/10_colregs_encounter.py`
in the editor (scenery setup: rescue boat becomes the target, nothing hidden), save the level.
```
python run_colregs.py --head-on
python run_colregs.py --crossing-giveway
python run_colregs.py --crossing-standon
python run_colregs.py --overtaking
```

| Gate | Packet | Confirm (terminal) | PASS when |
|------|--------|--------------------|-----------|
| **G_COLREGS_UE** | WP-20260709C | `python python/verify_colregs.py --matrix` | All four scenarios PASS from four distinct LIVE run dirs (the headless selftest matrix is already green — the live matrix replaces it as demo evidence). |

## Step 6 — ONE-command session closeout (NEW 9 Jul, WP-20260709D)

After Steps 1 + 3 + 4 + 5, close the whole session with a single command:
```
python python/verify_demo_session.py --film-dir "%USERPROFILE%\Videos\Captures"
```
Runs sensor-suite + capture/film + COLREGS-matrix gates in one shot and writes
`Saved/NaviSense_Reports/demo_session_result.json` (SESSION PASS ⇒ G_AIS/G_RADAR/G_CAMERA +
G_CAPTURE_UE + G_FILM_UE + G_COLREGS_UE all evidenced on disk). Only the eye-checks remain:
G_TRAFFIC_UE orientation + the D2 SS5 wave-ride (the tool lists them in the result file).

---
