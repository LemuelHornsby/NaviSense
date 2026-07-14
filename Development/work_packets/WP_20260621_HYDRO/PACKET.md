# WP-20260621_HYDRO — Hydrostatics port (analytic) + twin-propeller drive

**Theme:** port Lemuel's Unity hydrostatics to UE as an **analytic C++ integrator** (decision: analytic,
full port now) so the hull **settles at the real waterline by buoyancy equilibrium and rides waves**
(fixes KI-022 properly, not a placement hack); and port the twin-propeller drive (KI-023).

**Decisions (21 Jun):** analytic integrator (not Chaos) · full port now · propeller is one combined mesh.

## Architecture (matches Unity's hybrid ownership)
- **Python (MMG plant) owns X / Y / yaw** (maneuvering) — unchanged, still anchored to the placed yacht (KI-020).
- **Hydrostatics owns heave (world Z) + roll + pitch** — samples the rendered water surface along hull
  strips (mean → heave target; least-squares slopes → pitch/roll), integrates three damped oscillators from
  the DOLPHIN stiffness/inertia/damping. Pawn stays kinematic (no Chaos body).
- Falls back to the wire visual proxy (`rollDeg/pitchDeg/heaveM` + placed-waterline Z) when hydrostatics is
  off or has no Config.

## New files
- `Source/NaviSense/Vessel/NaviSenseHydrostaticsConfig.h` — data asset (port of `HydrostaticsConfig.cs`);
  DOLPHIN defaults + derived stiffness/period/damping accessors.
- `Source/NaviSense/Vessel/NaviSenseHydrostaticsComponent.h/.cpp` — the analytic integrator + water sampling
  (isolated in `SampleWaterHeightCm`). `Step(Dt, hullWorldXY, yaw)` → heave Z (cm), roll, pitch (deg).
- `Development/work_packets/WP_20260621_HYDRO/verify_hydrostatics.py` — reference model + 9-gate math proof.

## Changed files
- `Source/NaviSense/NaviSense.Build.cs` — enabled the **Water** module dependency.
- `Source/NaviSense/Vessel/NaviSenseShipPawn.h/.cpp` — added the `Hydrostatics` component + `bUseHydrostatics`
  (default on); Tick uses hydrostatics heave/roll/pitch when active; twin-propeller drive (port/stbd RPM,
  counter-rotating, `bInvertStarboardProp=true`) with a single merged-mesh fallback.

## Verified (sandbox, headless) — `verify_hydrostatics.py` **9/9**
DOLPHIN derived periods heave **2.89 s** / roll **6.63 s** / pitch **2.72 s** (physically sane); H2 equilibrium
(heave→eq, pitch→design trim 1.08°, roll→0); H3–H5 free natural periods match analytic to <1%; H6 roll damps;
H7 strip LSQ slope→pitch correct; H8 clamp at 5°; H9 deterministic. C++: Z0 **16/16**, all files brace-balanced.
**Note:** the math is proven headless; the UE Water-sampling call and the kinematic integration are in-engine
unknowns (I can't compile UE) — see the one flagged `SampleWaterHeightCm` API line.

## Lemuel — steps (full rebuild; then editor setup + tuning)
1. **Full rebuild** (Build.bat — adds the Water module + new classes; not Live Coding). Flag any compile
   error (most likely the flagged `QueryWaterInfoClosestToWorldLocation` line — I'll adjust to the 5.7 API).
2. **Create the config asset:** Content Browser → right-click → Miscellaneous → Data Asset →
   `NaviSenseHydrostaticsConfig` → name it `DA_DOLPHIN_HydrostaticsConfig` (defaults are already DOLPHIN).
3. **Assign it:** select `BP_ShipPawn_Yacht` → its `Hydrostatics` component → set **Config** =
   `DA_DOLPHIN_HydrostaticsConfig`. (The WaterBodyOcean auto-resolves; or set WaterBodyActor explicitly.)
4. **Play** `turning_circle`: the hull should **settle onto the water** (no hover) and **heave/roll/pitch with
   the waves**. Tune **WaterlineOffsetCm** on the component until the painted waterline sits at the surface.
5. **Twin props (KI-023):** in Blender, split `propeller.uasset`'s source into **two** prop meshes (port/stbd),
   re-import, add two components to `BP_ShipPawn_Yacht` named e.g. `Propeller_Port` / `Propeller_Starboard`
   placed on the shafts → the code drives them counter-rotating automatically. (Until then the merged mesh
   keeps spinning on one pivot.)

## Acceptance gates
- **G_HYDRO:** post-rebuild + config assigned, the hull floats at the waterline (no hover/sink) and rides the
  waves in heave/roll/pitch with believable periods; `verify_run_kinematics` still 8/8 (maneuvering unaffected).
- **G_PROP:** after the mesh split, the two propellers each spin about their own shaft, counter-rotating.

## Known follow-ups
- Feed the hydrostatics-computed heave/roll/pitch back to the sensors/run-log (so logged seakeeping = the
  physics, not the now-superseded Python proxy). Currently hydrostatics drives the visual; the wire/log still
  carry the proxy.
- Optional later: Chaos-physics version for nonlinear cross-coupling (analytic linear model is enough for now).

## Rollback
Originals in `Development/work_packets/WP_20260621_HYDRO/rollback_originals/`. To revert: restore Build.cs +
NaviSenseShipPawn.h/.cpp; delete the two NaviSenseHydrostatics* files + this packet dir. `bUseHydrostatics=false`
disables it at runtime without a rebuild (falls back to the proxy).
