# NaviSense Sensor Suite Roadmap — Radar / LiDAR / Sonar (design record)

**Status banner (12 Jul: demo target slipped; rule below unchanged — LiDAR/Sonar still must NOT eat live-session prep):** Radar = SHIPPED (headless, WP-20260702, 2 Jul 2026); LiDAR / Sonar = DESIGN
RECORDED, not yet implemented. **Scope flag:** these three sensors are NEW scope beyond the D4 demo
gate (`03_QA_Test_Plan.md` D4 = GPS/IMU/camera/AIS only). They are valuable roadmap work and MUST NOT
be treated as blocking the 11 Jul 2026 demo, nor divert effort from the last concrete D4 item (live
`CesiumGeoreference` GPS). Tracked as a separate "Sensor Suite Roadmap" line in `PROGRESS.md`.

This document resolves the §5 design decisions the 1-Jul directive requires **before** any
Radar/LiDAR/Sonar C++ is written. Radar's decisions are now realised in code; LiDAR/Sonar decisions
are recorded here so their implementation packets start from an agreed design, not a blank page.

## Honesty discipline (KI-019 family — applies to all three)

None of these are physically-validated sensor simulations at first pass. They are geometric / derived
models over the known scene. Label them as such in the Ops Manual, dashboard, and any GTM material —
the same discipline already applied to wake VFX (KI-025), the attitude proxy, AIS scoring, and the
still-frame camera (KI-026). New honesty issue for radar: **KI-027**.

---

## 1 · Radar — SHIPPED headless (WP-20260702)

| Decision | Choice | Rationale |
|---|---|---|
| Model | Geometric marine navigation radar; anonymous blips derived from the scripted contact set (`state.v1 traffic[]`) — NOT EM-propagation/RCS | Reuses the AIS receiver geometry already validated; zero new trace cost |
| Range | `RadarMaxRangeM` default **22224 m (12 NM)**; contacts beyond are not reported | Typical marine X-band nav-radar range scale |
| FOV / scan arc | **360° azimuth** (`sweepDeg=360`) | Marine radar rotates a full circle |
| Scan rate | Per-call snapshot of currently-detected contacts (the physical 24 rpm sweep is **not** simulated per-spoke) | Matches how the bridge samples `sensor.v1`; documented limitation |
| Noise / clutter | **Perfect** first pass (no jitter, no sea clutter, no false positives) | Honest baseline; a noise UPROPERTY can be added later like the GPS/IMU noise knobs |
| Wire output | `radar{maxRangeM, sweepDeg, contacts[]}`; each contact `{rangeM, trueBearingDeg, relBearingDeg, radialSpeedKn, closing}` — **no identity** (a blip is anonymous) | Contact-list shape (like AIS/traffic) ⇒ **no new USTRUCT**, built as raw JSON, so the B1 top-level wire-parity guard + Z0 stay 16/16 |
| Performance | O(N contacts) over the in-memory list, **no ray traces**; contacts naturally bounded by the scripted target count | Negligible per-tick cost; safe for the 40-fps in-engine budget |
| Radial speed | Range-rate along the line of sight from own (speed+heading) + target (cog/sog) velocity; **+ve = opening**, `closing = radialSpeedKn < 0` | Gives the bridge a closing-target cue without a full tracker |

Realised in: `Sensors/SensorBundleComponent.{h,cpp}` (radar block, `bEmitRadar`/`RadarMaxRangeM`),
reusable mirror `python/radar_sensor.py`, gate `python/verify_20260702.py` (5G/3N),
`Z0` 16/16. In-engine gate **G_RADAR_UE** (blips visible on the wire during PIE) pending the shared
C++ rebuild that also covers the dashboard/AIS/camera work.

---

## 2 · LiDAR — DESIGN RECORDED (not implemented)

| Decision | Choice | Rationale |
|---|---|---|
| Model | Sampled/reduced range-ring representation, NOT a raw dense point cloud | Raw point clouds are the most performance-sensitive of the three; a reduced representation is required for real-time |
| Range | ~200 m default (short-range obstacle sensing) | LiDAR is short-range vs radar |
| FOV | 360° azimuth × a **narrow vertical FOV** (e.g. ±15°) | Marine spinning-LiDAR style |
| Scan rate | ~10 Hz, **decoupled from render tick** (fixed sample budget per emit) | Prevents frame-rate coupling |
| Noise | Perfect first pass | Honest baseline |
| Wire output | A compact fixed-length **range array** (e.g. N azimuth bins → nearest hit distance) or a summary min-range scalar; NOT per-point XYZ | Bounds wire size and DTO shape; likely its own header if it needs a struct, to keep B1 scoped |
| Performance | **Hard per-tick trace-count ceiling decided up front** (e.g. ≤ N_bins line traces against nearby colliders), not discovered via a regression | These are the heaviest sensors; budget first |
| Honesty | "sampled LiDAR (reduced range bins)", never "full point-cloud LiDAR" | KI-019 family |

**Open prerequisite:** decide whether LiDAR traces real level geometry (needs colliders on the
obstacles it should see) or a reduced synthetic set. Recommend real traces against nearby traffic +
shoreline colliders, capped by the trace ceiling above.

## 3 · Sonar — DESIGN RECORDED (not implemented)

| Decision | Choice | Rationale |
|---|---|---|
| Model | Single-beam depth-below-keel (down) + optional forward-looking depth | Simplest useful sonar for a surface-vessel bridge |
| Range | 0–200 m depth default | Harbour/coastal depths |
| FOV / beam | Narrow down-beam (e.g. 20°); forward beam optional | Standard echo-sounder |
| Scan rate | ~5 Hz | Echo-sounder ping cadence |
| Noise | Perfect first pass | Honest baseline |
| Wire output | Summary scalar(s): `depthBelowKeelM` (+ optional `forwardDepthM`) | Simplest DTO shape; may not need a struct |
| Performance | 1–2 traces per emit — cheapest of the three | Trivial once a surface exists to trace against |
| Honesty | Flag clearly whichever source is used (see prerequisite) | KI-019 family |

**Prerequisite gap (must be resolved before Sonar code):** there is currently **no seabed /
bathymetry mesh** in `NaviSense_Monaco` to trace against below the water surface. Decide: (a) add a
real seabed mesh and trace it (physically grounded, needs level work), or (b) return a **synthetic
depth function** (faster to ship, less grounded — must be flagged honestly per KI-019). Recommend (b)
for the first pass, clearly labelled, with (a) as the roadmap upgrade.

---

## Sequencing note

Radar shipped first because it is the natural extension of the validated AIS receiver geometry
(contact list, no new engine feature). LiDAR and Sonar each need the level-side prerequisite above and
a firm per-tick trace budget before implementation — do not start their C++ until those are resolved
in this document. None of the three block the 11 Jul demo.
