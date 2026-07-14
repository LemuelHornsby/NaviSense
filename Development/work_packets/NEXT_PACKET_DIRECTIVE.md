# ▶ NEXT PACKET (directed by Lemuel, 1 Jul 2026) — Full Sensor Suite + Finish Bridge Dashboard UI

**Supersedes** the 30-Jun dashboard directive (that packet, WP-20260701, shipped its headless half
1 Jul — see `Documents/PROGRESS.md` ledger). Lemuel's 1 Jul direction has three parts. **This is
realistically several work packets, not one** — see the sequencing in §4 before picking a start
point.

## 1 · What Lemuel asked for

1. **Fully integrate the sensor suite** — explicitly including **Radar, LiDAR, and Sonar**, not just
   the gaps already flagged in GPS/IMU/AIS (Lemuel chose the largest of three scoped options when
   asked).
2. **Finish the Bridge Dashboard UI** started 1 Jul (`WBP_BridgeDashboard` — see the in-progress
   state below).
3. **Update all documentation** — Documentation Update Protocol (`CLAUDE.md`), same session as
   whatever ships.

## 2 · Honesty / scope flag (read before sequencing)

The original **D4** demo gate (`03_QA_Test_Plan.md`, target 11 Jul 2026) only requires
**"GPS (true lat/lon via Cesium), IMU, camera frames; AIS ≥1 target."** It does **not** mention
Radar, LiDAR, or Sonar. Those three are genuinely new scope beyond any existing demo gate — valuable
roadmap work, but they must not be treated as blocking the 11 Jul demo, and effort should not be
diverted from D4-closing work under time pressure. Sequence accordingly (§4).

## 3 · Current sensor status (as found 1 Jul 2026)

- **GPS** (lat/lon, speed, position) — done, validated against the plant (`verify_sensors_fidelity.py`,
  corr 1.0000). Gap: lat/lon comes from a manual flat-earth projection off `RefLatDeg`/`RefLonDeg` on
  `NaviSenseSimSubsystem`, **not** a live `CesiumGeoreference` component.
- **IMU** (heading, yaw-rate, finite-difference acceleration) — done, validated.
- **AIS** — scripted contacts are rendered in-engine (WP-15B) and fully analysed (CPA/TCPA/COLREGS,
  `python/colregs_score.py`), but `USensorBundleComponent::BuildSensorsJson()`'s own `ais.targets`
  block is still hardcoded to an **empty array** — the mmsi/cog/sog fields were never wired from the
  scripted `ais_traffic.py` field into the actual `sensor.v1` wire feed. This is a small, concrete,
  headless-buildable gap.
- **Camera** — not built at all (WP-14, never started). Needs an actual in-engine capture pipeline
  (e.g. `USceneCaptureComponent2D` to a render target), not just wire-level data — meaningfully
  bigger than GPS/IMU/AIS.
- **Radar / LiDAR / Sonar** — do not exist. Net-new sensor types. Each needs its own design pass
  BEFORE code (see §5) — do not start implementation without these decisions recorded.

## 4 · Recommended sequencing (do not treat as one packet)

1. **Finish `WBP_BridgeDashboard`** (mostly manual/in-editor, see
   `Documents/NaviSense_BridgeDashboard_Recipe.md` + the session-memory tracker
   `project_navisense_dashboard_ui_build` for exact per-field status: layout done, 1/19 getters
   bound as of 1 Jul, sliders + Add-to-Viewport + toggle key pending). Closes **G_DASHBOARD_UE**.
2. **AIS → `sensor.v1`** (small, headless C++ + Python, closes a concrete **D4** gap). Wire
   `ais_traffic.py`'s field into `BuildSensorsJson()`'s `ais.targets` array (mmsi/id, cog, sog, range,
   bearing) instead of the hardcoded empty array. Update the wire-key parity guard (B1) if new nested
   fields are added (own header, same pattern as `FNaviSenseTrafficTarget`, so B1 keeps scanning only
   top-level `state.v1`/`sensor.v1` keys).
3. **GPS via live `CesiumGeoreference`** (moderate C++, closes the other concrete **D4** gap). Replace
   the flat-earth `RefLatDeg`/`RefLonDeg` projection in `SensorBundleComponent.cpp` with a real
   `ACesiumGeoreference::TransformUnrealPositionToLongitudeLatitudeHeight` call (or equivalent 5.7
   API) once `CesiumRuntime` is enabled in `NaviSense.Build.cs` (already stubbed, same pattern as the
   `UMG` line this session uncommented). Keep the existing math as a no-Cesium-reference fallback so
   headless/no-georeference runs still work.
4. **Camera capture (WP-14)** — closes the last concrete **D4** item. Needs a design decision first:
   still-frame capture (reuses the WP-20260630 `HighResShot` pattern) vs. a live `SceneCaptureComponent2D`
   feed exposed as a sensor. Recommend still-frame first (smaller, reuses existing capture tooling).
5. **Radar** (beyond D4, roadmap). Needs §5 decisions resolved first.
6. **LiDAR** (beyond D4, roadmap). Needs §5 decisions first; likely the most performance-sensitive of
   the three (raw point clouds are expensive) — a sampled/reduced representation is almost certainly
   required for real-time use in this project.
7. **Sonar** (beyond D4, roadmap). **Prerequisite gap:** there is currently no seabed/bathymetry mesh
   in `NaviSense_Monaco` to trace against below the water surface — decide whether Sonar traces a
   real seabed mesh (needs one to be added to the level) or returns a synthetic depth function (faster
   to ship, less physically grounded — flag honestly per the KI-019 pattern if chosen).

## 5 · Design decisions needed before Radar/LiDAR/Sonar code (do not skip)

For EACH of the three, resolve and record before writing any C++:
- **Range & FOV** (max detection range, scan arc/beam angle)
- **Scan rate** (Hz — independent of the render/tick rate for performance)
- **Noise/clutter model** (perfect vs. noisy; false positives for Radar in particular)
- **Output format on the wire** (a contact list like `traffic[]`, a raster/heightmap, or a summary
  scalar — this determines the DTO shape and whether it needs its own header file to keep the B1
  wire-key-parity guard scoped correctly, same reasoning as `FNaviSenseTrafficTarget`)
- **Performance budget** (these are the most trace-heavy sensors in the project — decide a per-tick
  trace-count ceiling up front, do not discover it via a frame-rate regression later)
- **Honesty labeling** (KI-019 family): none of these will be physically validated simulations at
  first pass — label them as such in the Ops Manual / dashboard / any GTM material, same discipline
  already applied to wake VFX, attitude proxies, and AIS scoring.

## 6 · Documentation Update Protocol reminder

Whichever piece ships: `PROGRESS.md` ledger line (always) + burndown update if a **D4** sub-item
closes (AIS-feed / Cesium / Camera only — Radar/LiDAR/Sonar do NOT move D4, they're new scope, note
them separately e.g. as a new "Sensor Suite Roadmap" line, not folded into the existing D4 wording
without flagging the scope difference); `05_Test_Log.md` row for any verify run; new `KI-NNN` for any
bug found, `TC-NNN` for any new test; `00_Operations_Manual.md` if a run flag/control changes;
Known Issues Register update for **KI-009** (sensors) reflecting whichever sub-item closes.
