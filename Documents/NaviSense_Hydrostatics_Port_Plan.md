# NaviSense — Hydrostatics & Twin-Propeller Port Plan (Unity → UE5)

**Author:** Claude (co-dev) · **Date:** 2026-06-21 · **Status 12 Jul 2026:** twin-prop half RESOLVED in-engine 24 Jun (KI-023); hydrostatics half authored + assigned (DA_DOLPHIN_*), G_HYDRO float-at-waterline eye-check pending the live session; the "11 Jul demo" timing question below is superseded (date slipped). · **Trigger:** Lemuel's in-engine findings —
yacht floats above the waterline; twin propellers spin around one point. Deep investigation of the
Unity heritage (`NaviSense Simulator/Assets/Scripts/`) to port the real hydrostatics, not a proxy.

## 1. What Unity actually does (the model to match)

A **hybrid 6-DOF split** — clean ownership contract:
- **Python (MMG plant) owns** world X, world Z (Unity frame), and **yaw**. `Ship/YachtPoseApplier.cs`
  writes only those onto the Rigidbody each frame, *preserving* the physics-owned Y/roll/pitch.
- **UE/Unity physics owns** heave (world Y), **roll** (about body-forward), **pitch** (about body-right).

Components:
- `Hydrostatics/HydrostaticsConfig.cs` — ScriptableObject with the **DOLPHIN design data**: LOA 40, Lwl 38,
  B 8.11, T 2.177, freeboard 1.80, displacement **366 t**, VCG 3.50, LCG 18.0, design trim 1.08° by stern,
  LCF 17.594, TPc 2.641, Cwp 0.799, **GMt 1.044**, **GMl 68.154**, radii of gyration (roll 0.38·B, pitch
  0.25·LOA), added-mass/inertia fractions, damping ratios (heave 0.30, roll 0.10, pitch 0.30), ρ 1025, g 9.81.
  Derived: heave stiffness ρgAwp, roll/pitch stiffness m·g·GM, natural periods, damping coefficients.
- `Hydrostatics/RigidbodyHydroSetup.cs` — one-shot: real mass, CoM at (0,VCG,LCG), inertia tensor from
  radii of gyration, **freezes world X, world Z, yaw** (Python-owned), leaves heave/roll/pitch free.
- `Hydrostatics/HydrostaticsController.cs` — every FixedUpdate: sample the ocean at **longitudinal strips**
  (mean elevation → heave target; least-squares slope → pitch) and **transverse strips** (slope → roll),
  with short-wave filtering (a 40 m hull ignores 5 m chop). Apply: buoyancy m·g + heave spring
  −ρgAwp·(y−y_wave) − heave damping; pitch restoring −m·g·GMl·sin(θ−θ_target) − damping (torque about
  body-right); roll restoring −m·g·GMt·sin(φ−φ_wave) − damping (torque about body-forward). Rate clamps.
- `Hydrostatics/IWaveSampler.cs` + `CrestWaveSampler.cs` / `FlatWaveSampler.cs` — water-surface height
  query abstraction (Crest ocean or flat).
- `Actuators/ActuatorVisualRig.cs` — **two** propeller pivots `portPropPivot` / `starboardPropPivot`, each
  spun about its shaft axis from `portRps` / `starboardRps`, with **counter-rotation** (`invertStarboard=true`).

**Why this fixes the floating the right way:** the hull finds its own vertical equilibrium from
buoyancy vs. the *actual sampled water surface* — it physically cannot hover or sink; it rides the real
waves in heave/roll/pitch. Realism, not a placement hack.

## 2. UE5 state today (the gap)

- The pawn is **fully kinematic**: `NaviSenseShipPawn::Tick` sets location+rotation from the wire, and Z is a
  hardcoded `FreeboardCm` above world 0 (KI-022) → floats when the water isn't at Z=0.
- Heave/roll/pitch are **visual proxies** computed in Python (`attitude_proxy.py`, `sea_state.py`,
  `wave_response.py`) and carried on the wire — NOT physics, NOT sampling the rendered water.
- **No** hydrostatics component, **no** water-surface sampling. Water plugin is enabled in the `.uproject`
  (`Water`/`WaterAdvanced`/`WaterExtras`) but the `Water` C++ module is commented out in `NaviSense.Build.cs`.
- Propeller is one merged static mesh (`.../dolphin/propeller/StaticMeshes/propeller.uasset`) driven by a
  single `PropellerViz` about one pivot with the **average** RPM.

## 3. Port plan

**A. Hydrostatics (the core).** Two viable implementations (decision pending):
  - **(A1) Chaos-physics parity** — closest to Unity: make the hull (or a child body) simulate physics; lock
    UE X/Y translation + Z(yaw) rotation; bridge pose-applier writes X/Y/yaw only (preserve physics Z/roll/
    pitch) like `YachtPoseApplier`; a `UNaviSenseHydrostaticsController` applies buoyancy/heave-spring/damp
    force + pitch/roll restoring torques sampling `UWaterBodyComponent`. Most faithful; highest risk
    (kinematic→partial-physics pawn rework; needs in-editor tuning; not sandbox-testable).
  - **(A2) Analytic C++ integrator** — port the spring-mass-damper math and integrate it ourselves each tick
    (heave/roll/pitch as damped oscillators driven by sampled water mean/slope), pawn stays kinematic, Python
    still owns X/Y/yaw. Solves floating (buoyancy equilibrium) + realistic seakeeping riding the *real* water,
    **without** the physics rework. Lower risk; the math is headless-verifiable (oscillator/equilibrium unit
    tests). Per-DOF behavior matches the Unity linear model.
  Common to both: enable `Water` in `Build.cs`; port `HydrostaticsConfig` → `UNaviSenseHydrostaticsConfig`
  data asset (DOLPHIN data); sample `WaterBodyOcean` at strip points; hydrostatics becomes the source of
  truth for heave/roll/pitch (the Python visual proxies are then disabled on the pawn / kept as fallback).

**B. Twin propellers.** Asset + code:
  - **Asset:** split the merged prop into two meshes (re-import the source FBX with **Combine Meshes OFF** if
    the source has two prop objects; else split in Blender), placed on the port/stbd shafts with each pivot on
    its shaft axis; add two components to `BP_ShipPawn_Yacht` named so the resolver finds them.
  - **Code:** port `ActuatorVisualRig` twin-prop drive — spin port from `portRpm`, starboard from
    `starboardRpm`, **counter-rotating**, each about its own shaft (replaces the single avg-RPM `PropellerViz`).

## 4. Open decisions (see clarifying questions)
1. Hydrostatics implementation: A1 (Chaos parity) vs A2 (analytic integrator) vs interim-then-port.
2. Timing vs. the 11 Jul demo: full port as the next packet now, or interim placement fix for the demo + port after.
3. Propeller source: are the two props separate objects in the source FBX (re-import fix) or one mesh (DCC split)?

## 5. Interim status
A placement fix is already authored (KI-022): when spawn-anchored, the hull rides at the *placed* waterline +
heave — stops the hover for the demo while the full hydrostatics port is decided/built. It is NOT the
hydrostatics model; it's a stopgap.
