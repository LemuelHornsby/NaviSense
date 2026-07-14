# WP-20260701C — Camera sensor (WP-14, still-frame metadata) on `sensor.v1` (D4)

**Date:** 2026-07-01 (Wed) · **Author:** Claude (**Opus 4.8**, autonomous daily session)
· **Type:** C++ wire block (`SensorBundleComponent`) + reusable stdlib Python mirror,
**NO DTO/USTRUCT/schema-struct change, NO controller change** · **Demo gate:** **D4**
(the last concrete headless-buildable sensor gap — camera frames) · **Verdict (headless):**
`verify_20260701c.py` **5/5 gates + 3/3 controls = PASS**, `Z0` 16/16.

## Why (scope + sequencing)
The 1-Jul directive lists four concrete **D4** closers. #2 (AIS→`sensor.v1`) shipped as
WP-20260701B. The two remaining are **#3 live-Cesium GPS** and **#4 Camera (WP-14)**. Per the
directive and the parent brief, **Camera still-frame is the lower-risk of the two**: live-Cesium
GPS routes through `CesiumRuntime`, whose classes are the direct cause of the OPEN S2 **KI-014**
editor-crash — enabling it headless-clean is fine, but the in-engine gate carries real crash risk
against the 11-Jul demo. Camera still-frame instead **reuses the WP-20260630 `HighResShot` capture
pipeline already in the tree** (no new engine plugin, no crash surface) and closes a real D4 item.
So this packet closes **#4** now; **#3 Cesium GPS** remains the last D4 item, deferred behind KI-014
de-risking (see `NEXT_PACKET_DIRECTIVE.md`).

**Chosen approach: still-frame (metadata) camera, NOT a live `SceneCaptureComponent2D` pixel feed.**
Streaming pixels over the `sensor.v1` socket is out of scope for the demo and heavy; instead the wire
carries camera **capture metadata** (pose + heading + FOV + resolution) plus a deterministic
`frameRef` that names the HighResShot still the WP-20260630 burst writes to the Screenshots dir. A
consumer joins metadata → the PNG on disk by `frameRef`. Honest, deterministic, headless-verifiable.

## What changed (all in the WORKSPACE; additive)
- **EDIT** `Source/NaviSense/Sensors/SensorBundleComponent.cpp` — new `// ---------- CAMERA` block
  before `return Sensors;`, gated on `bEmitCamera`. Emits `sensor.v1 camera{}`:
  `{fovDeg,resX,resY,headingDeg,frameIndex,frameRef,pose{x,y,z}}`. Pose = own-ship chase-rig position
  in the wire frame (`Wire.X/Y/Z` = East/Up/North m); heading = the IMU block's `HeadingDeg`;
  `frameRef = Printf("%s%05d.png", CameraFramePrefix, CameraFrameIndex++)` (monotonic per-call index).
- **EDIT** `Source/NaviSense/Sensors/SensorBundleComponent.h` — camera UPROPERTYs
  (`bEmitCamera=true`, `CameraFovDeg=90`, `CameraResX=3840`, `CameraResY=2160`,
  `CameraFramePrefix="NaviSense_"`) + private monotonic `CameraFrameIndex`. Banner updated.
- **NEW** `python/camera_sensor.py` — reusable, stdlib-only mirror of the C++ camera block
  (`camera_record(own_e, own_up, own_n, own_heading_deg, frame_index, ...)` + `frame_ref()`), same
  keys/frameRef naming/defaults, honesty note in the docstring.
- **NEW** `python/verify_20260701c.py` — the headless authoring gate (5 gates + 3 controls); writes
  `NaviSense_UE5/Saved/NaviSense_Reports/wp_20260701c_result.json`, exits 0 iff PASS.
- No DTO/USTRUCT/schema-struct, no controller, no wire-key parity struct touched. The `camera` block
  is nested (like `gps`/`imu`/`ais`), so the B1 top-level `state.v1`/`sensor.v1` key guard is
  unaffected (same reasoning as the AIS `targets[]` nesting).

## Acceptance gates — `python3 python/verify_20260701c.py` → **5/5 + 3/3 PASS** (done, headless)
- **G1** the C++ camera block is wired (gated on `bEmitCamera`, `SetObjectField("camera")`,
  `frameRef`, `pose`, monotonic `CameraFrameIndex++`), carries all keys, uses chase-rig pose +
  `HeadingDeg`, and the header exposes the config fields.
- **G2** parity — the `python/camera_sensor` mirror produces the SAME `frameRef` naming as the C++
  `Printf("%s%05d.png")` (`NaviSense_00000.png` …) and maps pose (East,Up,North) + index exactly.
- **G3** schema / honesty — right keys+types, wire-frame pose, defaults (FOV/res/prefix) match
  between C++ header and mirror, an explicit **"NOT a live … feed"** honesty label is present in
  both, and the frame index is monotonic.
- **G4** determinism — the mirror replays bit-for-bit for a given (pose, frame index).
- **G5 (regression)** `Z0` **16/16** (C++ compile-ready) + `verify_20260701b` (AIS) + `verify_20260701`
  (dashboard) + `verify_20260629b` (traffic) still PASS (additive).
- **N1** an unwired/`bEmitCamera=false` stub is detected as not-wired · **N2** a wrong `frameRef`
  (missing zero-pad / wrong prefix) is caught vs the `%05d` naming · **N3** the metadata tracks
  pose/heading and the frame index advances (not a stub).

## Lemuel's in-engine session (≤ 20 min) — gate **G_CAMERA_UE** (needs the pending C++ rebuild)
Prereq: the pending shared C++ rebuild (this packet's C++ rides the SAME rebuild as WP-20260701 /
WP-20260701B — editor closed, full `Build.bat`).
1. `python run_demo.py --scenario monaco_capture`, press **Play**.
2. Inspect the wire / `sensor.csv`: each `sensor.v1` packet now has a **`camera`** block with
   `fovDeg/resX/resY/headingDeg/frameIndex/frameRef` + `pose{x,y,z}`, `frameRef` counting up
   `NaviSense_00000.png`, `NaviSense_00001.png`, … and `pose`/`headingDeg` tracking the ship.
3. With PIE running, **Tools → Execute Python Script → `Phase5_Systems/08_capture_demo_stills.py`**
   (WP-20260630) to fire the HighResShot burst that produces the PNGs the `frameRef`s point at, then
   `python python/verify_capture_artifacts.py --latest` (C1 stills / C2 run-health).
   ⇒ the `sensor.v1 camera` metadata + the stills on disk together = the D4 camera item.

## Rollback
Revert the two SBC edits (delete the `// ---------- CAMERA` block in `.cpp` and the 5 camera
UPROPERTYs + `CameraFrameIndex` in `.h`); delete `python/camera_sensor.py` +
`python/verify_20260701c.py`. No DTO/schema/controller was touched, so rollback is local to the
camera block; `Z0` and every other gate are unaffected.
