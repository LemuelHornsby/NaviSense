# Live in-engine verification session — 2026-06-21 (recompile CONFIRMED)

**Context:** Lemuel ran Live Coding → **Result: Succeeded, 11/11 TUs** (incl. `NaviSenseShipPawn.cpp`
carrying the KI-018 fix), patch linked. This session drives the full PIE gate battery.
**Division of labour:** Lemuel runs the Python listener on Windows (sandbox can't reach UE);
Claude drives UE via computer-use + verifies every run-log from the work folder.
**On failure:** fix Python/config in-place (shell+verify), flag any C++ that needs a fresh recompile.

## Sandbox health battery — ALL GREEN (13:06, pre-PIE)
WP-20260621 10/10 · WP-20260620 8/8 · Z0 16/16 · schema-v1.2 9/9 · v1.3 12/12 · WP-9 9/9 ·
re-accept 5/5 · kinematic-health(18-Jun log) 8/8 (K6/K7 pass → KI-018 spin is pawn-side only).

## Gate battery progress (update after EACH gate so this is resumable)
| Gate | Packet | Status | Evidence / note |
|------|--------|--------|-----------------|
| static review (Output Log, Cesium/KI-014, pawn, FPS) | — | ☐ pending | |
| G7 sign (+rudder⇒starboard) | WP-2 | ✅ PASS | turns starboard (Lemuel obs, run 161455) |
| KI-018 no-spin past 180° | WP-20260621/KI-018 | ✅ PASS (after full rebuild) | run 163148: 493° continuous, 8/8, DT/Lpp 4.16; KI-018 RESOLVED |
| G4 re-accept/STALE across PIE Stop/Play | WP-3/WP-10 | ☐ pending | |
| C4 pause 5s ⇒ t drift <1ms | WP-4 | ☐ pending | |
| G5 Insights no >5ms hitch | WP-3 | ☐ pending | -trace=cpu |
| G_UE7 heel/trim | WP-7 | ✅ PASS | calm run 163148: heel −0.24° into turn, correct sign |
| G_UE8 heave (SS5, flat SS0) | WP-8 | ✅ PASS | run 164358 heave ±2.5 m; SS0 flat 0 |
| G_UE8+ wave roll/pitch (heading 90) | WP-9 | ✅ PASS | run 164358 roll ±6° / pitch ±4°, oscillating |
| D3 schedule smooth build + ≥3 events | WP-20260621 | ✅ PASS | run 171134: 6 states logged t=0..150s, heave RMS 0.14→1.33 m |
| D6 scenario evidence pack | WP-20260621 | ✅ PASS | --scenario ran live; pack from run 163148 DT/Lpp 4.16 IMO PASS; ≥3 screenshots still pending |
| G_UE manual drive (W/S/A/D, M) | WP-6 | ⏸ DEFERRED (KI-021) | default character possesses P0 not yacht; fix=GameMode DefaultPawnClass=None |
| WP-5 nightly (RunTests + PNG) | WP-5 | ☐ pending | nightly.ps1 |

## Resume instructions (if interrupted)
Continue at the first ☐ row. Listener cmd template:
`cd "D:\Marine Autonomy\NAVISENSE\NaviSense Simulator with Unreal Engine"; python python_listener.py --target unreal --controller <ctrl> -v [--sea-state N|--wave-heading-deg D|--scenario NAME]`
After each maneuver run, verify the newest `logs/<run>/` with `python python\verify_run_kinematics.py`.
Docs to update on completion: 05_Test_Log (rows), 04_Known_Issues (KI-018), PROGRESS (burndown+banners).

## UPDATE (driving constraint discovered)
Computer-use screenshots CANNOT capture the Unreal editor viewport (UE's GPU/D3D-rendered
window returns as the desktop wallpaper on all 3 monitors, despite unrealeditor.exe granted
full-tier). Static review confirmed from Lemuel's screenshots: NaviSense_Monaco open, 19/19
actors loaded, BP_ShipPawn_Yacht placed (OwnShip/Dolphin), WaterBodyOcean/WaterZone present,
Cesium signed in + Google Photorealistic 3D Tiles in outliner (KI-014 likely RESOLVED),
FPS ~40. Note: viewport shows grey placeholder blocks + "No Loaded Region(s)" (WP/Cesium
tiles not streamed yet) — cosmetic, not a bridge blocker.
**PIVOT:** Lemuel drives PIE (he can see the viewport); Claude verifies every run OBJECTIVELY
from logs/<run>/ via verify_run_kinematics (K1-K8, incl. K6 no-spin = KI-018, K7 yaw continuity)
+ analyses pasted screenshots for the pure-visual halves (heel/heave direction). This IS the
PENDING_EDITOR_GATES "Tell Claude" protocol, run live with immediate log verification.

## Mid-session fix (KI-020 spawn anchoring)
Lemuel: runs snapped to Port Hercule despite moving the yacht. Fixed `NaviSenseShipPawn` to anchor the bridge pose to the placed transform (`bAnchorPoseToSpawn`, default on). Z0 16/16, braces balanced. **NEEDS FULL REBUILD** (adds a UPROPERTY — Live Coding can't hot-swap class layout) then rerun; confirm run starts at the placed open-water location. **RESOLVED 21 Jun — Lemuel confirmed.**

## Deep investigation (hydrostatics + twin-prop) — 21 Jun
Found Lemuel's Unity hydrostatics (Config+Controller+RigidbodySetup+PoseApplier+WaveSampler) — a portable
hybrid: Python X/Z/yaw, physics heave/roll/pitch (buoyancy+GM+damping, samples Crest). Real fix for the
floating. Twin props: UE imported FBX as one merged mesh (Unity used 2 counter-rotating pivots). Plan doc:
Documents/NaviSense_Hydrostatics_Port_Plan.md. Water plugin already enabled; Build.cs module commented.
AWAITING DECISIONS: (1) Chaos-parity vs analytic integrator; (2) full port now vs interim-for-demo;
(3) propeller source FBX two-objects vs one-mesh. Interim placement fix (KI-022) authored, not yet rebuilt.

## Hydrostatics port built (WP-20260621_HYDRO) — 21 Jun
Analytic integrator authored: NaviSenseHydrostaticsConfig + NaviSenseHydrostaticsComponent; Water module on; pawn uses hydrostatics for heave/roll/pitch (Python X/Y/yaw); twin-prop code (counter-rotating) + single-mesh fallback. verify_hydrostatics 9/9, Z0 16/16. PENDING: full rebuild + config asset + WaterlineOffsetCm tune + Blender prop split. Water-API call (QueryWaterInfoClosestToWorldLocation) flagged to verify on 5.7 compile.
