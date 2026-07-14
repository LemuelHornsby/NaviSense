# NaviSense UE5 — Gate Closeout Guide (complete)

**Date:** 14 July 2026 (WP_20260714) · **Owner steps:** Lemuel · **Doc updates on your word:** Claude
**Scope:** every gate still open across D1–D8 + the linked eye-checks. Follow top to bottom.
**Budget:** Session A (in-engine) ≈ 60 min · Session B (clean-box, D8) ≈ 30 min, any day.

> **Update 14 Jul (WP_20260714B — closeout scope SHRANK):** Session A already closed **D2** (SS5 run 155234) + **KI-034**, and the **film is captured** (`Demo/film`: Turning_Circle / Monaco / Head_on). The film gate had been false-failing on those clips — **KI-041 FIXED** (the parser now reads moov-at-end recordings), so **A3's C3 film check now PASSES** (2 clips parse). **What actually remains:** **(A3)** ≥3 **beauty stills** only (films done) → `08_capture_demo_stills.py` then `verify_capture_artifacts --latest --film-dir "Demo\film"`; **(A4)** only **3 live COLREGS runs** (head_on already ran live today) → `run_colregs.py --crossing-giveway|--crossing-standon|--overtaking`; **(Step 6)** `verify_demo_session --film-dir "Demo\film"` (TC-49). Also fixed **KI-042** (COLREGS `matrix()` crashed on a NUL-padded result file). Details: `Development/work_packets/WP_20260714B/PACKET.md`. **UPDATE 20:07 — Session A COMPLETE:** stills + all 4 live COLREGS done; `verify_demo_session` = **SESSION PASS** (TC-49). Only **D8 (Session B, clean box)** remains.

---

## 0 · Where you stand (nothing here needs redoing)

| Gate | Status | Evidence |
|---|---|---|
| D1 closed loop + signs | ✅ 21 Jun | 493° continuous turn post-rebuild, KI-018 resolved |
| D3 runtime sea states | ✅ 21 Jun | SS1→SS6 sweep, 6 transitions logged |
| D4 real sensors (scoped) | ✅ 12 Jul | Live run 125800: TC-23 6/6 · TC-43 4/4; full-view re-proof 14 Jul (639/639 envelopes, fidelity resid 0.01 m). Cesium live-GPS deliberately OUT (KI-014) |
| D5 wake VFX | ✅ 28 Jun | G_WAKE_UE confirmed; C++↔Python curve parity |
| D6 evidence pack (data half) | ✅ 14 Jul | Run-125800 pack **COMPLETE**: `view_complete: true`, 23,393/23,393 rows, health 6/6, AIS 3 targets/2 alerts, `evidence_report.html` |
| Baseline | ✅ 13 Jul | TC-50 5/5+3/3 · TC-51 (P0 anti-partial gate) 6/6+2/2 |

**Still open → this guide:** D2 (SS5 eye-word) · D6 (≥3 stills) · D7 (film) · D8 (clean box) ·
G_TRAFFIC_UE/KI-034 (upright word) · G_COLREGS_UE (live matrix) · TC-49 (one-command closeout).

---

## Session A — ONE in-engine sitting (~60 min)

### A0 · Prep (5 min)

1. Terminal at the workspace root:
   `cd "D:\Marine Autonomy\NAVISENSE\NaviSense Simulator with Unreal Engine"`
2. Sanity gate (should be GO — it was GO on 13 Jul):
   `python preflight_demo.py`
3. Open `NaviSense_Monaco` in the editor. If the water reads neon-cyan / "No Loaded
   Region(s)": re-open the level so the WaterZone reloads (known capture note, WP-20260628).
4. **No rebuild needed.** The KI-034 fix is already in the 9-Jul DLL. Only rebuild if C++
   changed since (it has not).
5. Have Game Bar ready (**Win+Alt+R** starts/stops recording → clips land in
   `%USERPROFILE%\Videos\Captures`).

### A1 · monaco_capture run — traffic eye-check + film beat 1 (15 min)

> ⚠ Keep `--plant mmg` on every demo-evidence run: only the COLREGS scenarios force MMG;
> everything else defaults to the stub plant (found 14 Jul on run 153701 — sensor gates
> unaffected, but footage/KPIs should come from MMG runs).

```
python python_listener.py --target unreal --scenario monaco_capture --plant mmg -v
```
Press **Play**. Start recording (Win+Alt+R), maximise viewport (F11), ~45 s of the
3-ship traffic beat, stop recording. While it runs, eye-check:

- **G_TRAFFIC_UE / KI-034:** are `excursion_vessel` and `Yacht_with_interior` (the two
  roll-corrected hulls) **upright and bow-forward** while moving? `marine_rescue_boat` was
  always fine. → *one sentence to Claude closes KI-034.*

Stop PIE (ends the run cleanly; it auto-logs + the listener re-accepts for the next run).

### A2 · SS5 rough_turning_circle — D2 eye-word + film beat 2 + stills (15 min)

```
python python_listener.py --target unreal --scenario rough_turning_circle --plant mmg -v
```
Press **Play**. Record ~45 s of the seakeeping beat (Win+Alt+R). Eye-check **D2**:

- Hull **rolls/pitches/heaves** with the SS5 swell while staying settled at the boot-top
  (`WaterlineOffsetCm=-218`); props + bow thruster stay submerged, wake trails at speed.

**Stills (D6):** while framed nicely, run in the editor Python console
(`Window → Output Log → Cmd: Python`, or Execute Python Script):
`NaviSense_UE5/Content/NaviSense/Python/Phase5_Systems/08_capture_demo_stills.py`
(burst `HighResShot 3840x2160` — take ≥3: traffic beat, seakeeping beat, close-up).
Stop PIE.

### A3 · Gate stills + film from the terminal (5 min)

Move/copy your 1–2 clips into the repo film folder (evidence lives with the repo):
```
copy "%USERPROFILE%\Videos\Captures\*.mp4" "Demo\film\"
python python/verify_capture_artifacts.py --latest --film-dir "Demo\film"
```
PASS when: **C1** ≥3 stills ≥3840×2160 · **C2** run health (no spin/NaN) · **C3** ≥1 clip
≥20 s ≥5 MB → closes **G_CAPTURE_UE (D6 stills)** + **G_FILM_UE (D7, TC-42)**.
Result: `Saved/NaviSense_Reports/capture_artifacts_result.json`.

### A4 · COLREGS live matrix — G_COLREGS_UE (15–20 min)

> **Staging (14 Jul final, selftest-proved compliant 4/4):** head-on — boat starts **500 m dead
> ahead**, visibly underway (2.3 kn), own **turn at t≈20 s with the boat ~410 m** (sharp 55°
> command, 67° net swing), **port-to-port pass 222 m around t≈100 s**, ~2 min total. This is
> the Rule-8 floor: a later turn cannot achieve the 200-m compliant pass (176/194-m variants
> rejected). Crossing — turn t≈18 s, pass 213 m; overtaking 295 m; standon holds (152 m).
> After the pass the ship **resumes the base course** (head-on/crossing t=130 s, overtaking
> 170 s — on course again ~20 s later): the full filmable arc is approach → turn → pass →
> resume in ~2.5 min. Staging is pure Python — restart the listener to pick it up.

> ⚠ **One listener at a time.** The canonical listener re-accepts after every PIE Stop, so a
> forgotten terminal keeps OWNING port 5005 and steals every later Play — your "COLREGS" run
> then silently logs as the old scenario (seen live 14 Jul: 4 attempts logged monaco_capture/stub,
> encounter never started). **Ctrl+C the previous listener before each `run_colregs.py`**;
> check with `netstat -ano | findstr :5005` (no LISTENING = free). The runner's banner must
> name the avoid scenario + `plant: MMG` **and** `listening on 127.0.0.1:5005` (KI-039: 5502 = the pawn never connects).

One-time scenery prep (editor): Execute Python Script →
`.../Phase5_Systems/10_colregs_encounter.py` (rescue boat becomes the target; save the
level). **Never** launch runs from editor Python (KI-036) — the runner below is terminal-side.

Then four short runs — for each: command, press **Play**, let the encounter resolve
(~2 min), stop PIE (each run **auto-verifies** itself):
```
python run_colregs.py --head-on               # Rule 14
python run_colregs.py --crossing-giveway      # Rule 15
python run_colregs.py --crossing-standon      # Rule 17
python run_colregs.py --overtaking            # Rule 13
```
Then the matrix gate:
```
python python/verify_colregs.py --matrix
```
PASS = all four scenarios from four distinct LIVE run dirs → **G_COLREGS_UE**.

### A5 · ONE-command session closeout — TC-49 (2 min)

```
python python/verify_demo_session.py --film-dir "Demo\film"
```
Runs sensor-suite + capture/film + COLREGS-matrix in one shot →
`Saved/NaviSense_Reports/demo_session_result.json`. **SESSION PASS** = every disk-provable
gate closed; only your two eye-words (A1 traffic, A2 wave-ride) live outside the tool.

### A6 · Tell Claude (1 min — flips the gates in the docs)

Reply with short lines; each one closes its gate + Test-Log row + burndown same session:
- "traffic: both roll-corrected hulls upright" → **KI-034 RESOLVED, G_TRAFFIC_UE ✅**
- "SS5: hull rides the swell at the boot-top" → **D2 ✅**
- "capture/film/colregs/closeout: PASS (paste the one-line verdicts)" → **D6 ✅ · D7 ✅ · G_COLREGS_UE ✅ · TC-49 ✅**

> After Session A the burndown reads **7✅ · D8 ◐** — demo-ready.

---

## Session B — D8 clean-box repro (~30 min, any day)

Goal: **G_REPRO_UE** — the demo reproduces from a pristine copy, no hidden local state.

1. Fresh copy on another machine or clean folder (no git remote yet — KI-006 — so copy or
   zip the workspace; `SETUP.md` documents the clone→demo path):
   `robocopy "D:\Marine Autonomy\NAVISENSE\NaviSense Simulator with Unreal Engine" "D:\NaviSense_CleanBox" /E /XD Saved logs Intermediate DerivedDataCache .git`
2. In the clean copy: `python python/repro_doctor.py` → expect **12/12** (deps, tools,
   UE project, DA_DOLPHIN assets, Cesium token; flags un-pulled LFS stubs).
3. Headless end-to-end: `python run_demo.py --selftest` → expect IMO PASS (DT ≈ 158 m)
   twice (deterministic).
4. Optional full: open the UE project from the clean copy, one `monaco_capture` PIE pass.
5. Tell Claude the three results → **D8 ✅** (D2/D5/D7 inheritance is already satisfied
   once Session A lands).

---

## Troubleshooting quick refs

- Evidence pack refuses `PARTIAL VIEW (KI-038)` → rebuild where the full log is visible
  (Windows terminal); never use a pack without `meta.view_complete: true`.
- `UnicodeEncodeError` in pack/analyse on Windows → fixed 12 Jul (KI-037, UTF-8); update tree.
- Editor opens a blank second window on script run → you launched a run from editor Python
  (KI-036); use the terminal runners.
- Preflight NO-GO from an interrupted rehearsal → KI-029/KI-030 are fixed; re-run
  `python preflight_demo.py`; a genuinely bad newest run no longer shadows a good one.
- Neon-cyan water in captures → re-open `NaviSense_Monaco` (WaterZone regions), WP-20260628.

## Not gates — queued after closeout (do not let them eat the sitting)

1. **KI-006 (S1, top risk):** no off-machine git remote — 10 min on Windows per
   `GIT_SETUP.md` → push to a private remote (+ Git LFS for `Content/`).
2. **G_DASHBOARD_UE (Step 2, deferred by design):** finish `WBP_BridgeDashboard` by hand per
   `Documents/NaviSense_BridgeDashboard_Recipe.md` (scaffold + binding list:
   `Phase5_Systems/09_build_bridge_dashboard.py`; 1/19 getters bound so far).
3. **KI-014 (S2):** Cesium crash de-risk → unlocks the scoped-out live-GPS half of D4.
4. **UE 5.8 migration:** BLOCKED on the Cesium 5.8 build (runbook `UE58_MIGRATION.md`).
5. **MRQ cinematic render:** post-demo polish path (film gate uses honest screen capture).
6. **KI-012 deterministic sim clock:** WP-4 authored; schedule its in-engine soak.
