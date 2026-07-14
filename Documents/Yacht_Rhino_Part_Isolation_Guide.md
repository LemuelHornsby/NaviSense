# Yacht Part Isolation in Rhino — for Unreal Actuators

**Goal:** Turn the single Archmodels yacht FBX into **5 clean, separately-pivoted parts** that Unreal can
actuate — **Hull, Rudder, Propeller_Port, Propeller_Stbd, BowThruster** — instead of one fused mesh or
4,812 fragments.

**Source file:** `D:\Marine Autonomy\NAVISENSE\NaviSense Simulator\Assets\shipmodels\unity_yacht_model.fbx`
**Known facts about the source (from the UE import dialog):** binary FBX 7.7.0, **units = millimeter**,
axis **Z-UP (right-handed)**. Named nodes seen include *Hull, Main Deck, MainDeck Rail, Propeller*. The model
is an Archmodels library asset built from thousands of small surfaces.

---

## Why we do this in Rhino (not re-import settings)

The FBX was authored as thousands of tiny surfaces. Re-importing with "Combine" off gives 4,812 unusable
fragments; with it on gives one rigid block you can't animate. Neither is what a sim needs. Rhino lets you
**group the thousands of surfaces into the 5 functional parts** and, critically, **set each moving part's
pivot to its real rotation axis** (rudder stock, prop shaft) before export — which is what makes them rotate
correctly in Unreal with zero extra fiddling.

---

## Part 0 — Setup & orientation (5 min)

1. **Open Rhino.** File → Open (or Import) → select `unity_yacht_model.fbx`.
   - If asked about units on import, keep the file's **millimeters** for now; we'll handle scale at export.
2. **Set up views:** use the **Front**, **Right**, **Top**, and **Perspective** viewports (the 4-view layout).
   You'll identify parts by their location on the hull.
3. **Turn on shaded display** in Perspective so you can see solid shapes, not just wireframe.
4. **Find your bearings on the hull:**
   - **Bow** = front (pointed end). **Stern** = back (flat/transom end).
   - **Rudder & propellers** are at the **stern, below the waterline** (low Z, near the back).
   - **Bow thruster** (if present) = a **transverse tunnel through the hull near the bow**, low down.

> Tip: The rudder is usually a single flat blade hanging vertically behind/below the props. Propellers are
> the multi-blade screws on shafts. If you rotate the Perspective view to look at the stern from behind and
> below, all of these become obvious.

---

## Part 1 — Isolate each moving part (the core work)

You'll do this once per moving part: **Rudder, Propeller_Port, Propeller_Stbd, BowThruster.** Work on a copy
mindset — selecting and exporting doesn't destroy the original until you choose to delete.

### 1.1 Select the part's surfaces
- Zoom to the stern in Perspective. **Window-select** (drag a box) around just the rudder geometry, or click
  its surfaces while holding **Shift** to add to the selection.
- Because the model is many small surfaces, a part may be several surfaces — select them all.
- Use **Right/Front viewports** to box-select precisely without grabbing hull geometry behind it.
- Verify your selection: everything selected highlights. If you grabbed hull by mistake, **Shift+click** to
  deselect those surfaces.

### 1.2 Put the part on its own layer (keeps things organised)
- With the part selected, in the **Layers** panel create a layer (e.g. `Rudder`) and **change the selected
  objects to that layer** (right-click the layer → "Change Object Layer", or select layer then
  Edit → Layers → Change). Repeat per part. This lets you show/hide parts cleanly while working.

### 1.3 (Recommended) Join the part into one object
- With the part's surfaces selected, run **`Join`** (type it in the command line). This welds the surfaces
  into a single polysurface/mesh so it imports into Unreal as ONE component, not many.

### 1.4 Set the pivot — THE most important step
This is what makes the part rotate about the correct axis in Unreal.

- **Rudder:** its rotation axis is the **vertical rudder stock** (the line it hinges about, usually the
  leading edge / the post). 
  1. Select the rudder object.
  2. Run **`ChangeBasePoint`** (or use **Gumball** — see note) and place the base point **on the rudder
     stock axis, at the waterline or hull attachment point.**
  3. The goal: the object's origin sits exactly on the vertical hinge line.
- **Propellers:** rotation axis is the **shaft centerline** (horizontal, fore-aft).
  1. Select the propeller object.
  2. Set its base point **at the center of the prop hub, on the shaft axis.**
- **Bow thruster:** axis is the **transverse tunnel centerline** (port-starboard). Base point at the tunnel
  center.

> **Gumball method (easier):** Turn on **Gumball** (bottom toolbar). Select the object. Hold a modifier and
> drag the Gumball's origin (the white dot) to relocate the pivot, OR right-click the Gumball origin →
> "Relocate Gumball" → snap it to the stock/shaft. Use **Osnap** (End, Mid, Center, Point) to snap exactly
> to geometry. Where the Gumball origin sits = where the part will rotate in Unreal.

### 1.5 Note the world position
Before export, note (or keep) the part's **world location** — Unreal needs each part placed correctly
relative to the hull. Easiest approach: **don't move parts from their world position**; only move the
*pivot/base point*. Then on export, keep world coordinates so everything lines up when reassembled.

---

## Part 2 — Build the Hull (everything else)

1. **Select everything** (`Ctrl+A` or Edit → Select All).
2. **Deselect the 4 moving parts** — easiest if you hid them on their own layers: turn those layers **off**,
   then Select All selects only what's left (the hull + all static detail).
3. With the hull selection, optionally **`Join`** the major surfaces (or leave as-is — the hull doesn't move,
   so it can stay multi-surface; Unreal will treat it as one static mesh on import if exported as one file).
4. Put it on a `Hull` layer.

---

## Part 3 — Export the 5 parts

Export **each part as its own FBX** (cleanest for Unreal), OR one FBX with 5 named objects. Per part:

1. Select only that part (or isolate its layer).
2. **File → Export Selected** → choose **FBX** → name it clearly:
   - `Hull.fbx`
   - `Rudder.fbx`
   - `Propeller_Port.fbx`
   - `Propeller_Stbd.fbx`
   - `BowThruster.fbx`
3. **Export location:** put them in a new folder, e.g.
   `D:\Marine Autonomy\NAVISENSE\NaviSense Simulator\Assets\shipmodels\DOLPHIN_parts\`
4. **In the FBX export options:**
   - **Units:** the source is **millimeters**. Either export in **meters/centimeters** so Unreal reads scale
     correctly, OR keep mm and fix it in Unreal with **Import Uniform Scale**. Simplest: if parts import
     ~10× too big/small in Unreal, set Import Uniform Scale to **0.1** (mm→cm is ÷10... actually mm→cm is
     ÷10; verify visually).
   - **Geometry:** export meshes (Rhino will mesh NURBS on export; accept default mesh density or raise it
     for the hull if it looks faceted).
   - Keep **Y-up or Z-up** consistent — Unreal is Z-up; Rhino is typically Z-up too, so leave default and
     verify orientation after import (bow should point along one axis cleanly).

---

## Part 4 — Import into Unreal & assemble

1. In Unreal, import the 5 FBX files into `/Game/NaviSense/Ships/DOLPHIN/` (a fresh folder).
   - Combine Meshes is irrelevant now (each file is one part). Keep **Build Nanite OFF** for the moving
     parts; the hull can use Nanite later if its materials are opaque.
2. **Scale check:** drop `Hull` into an empty level; compare to a known size (~40 m LOA). If wrong, reimport
   with **Import Uniform Scale** adjusted.
3. **Pivot check:** drop `Rudder` in; in the viewport, rotate it (Yaw). It should swing about the stock line,
   not its center. Props should spin about their shaft. If a pivot is off, it's fixable in Unreal with an
   intermediate Scene Component (see the Component Guide), but a correct Rhino pivot avoids that.
4. **Assemble** on `BP_ShipPawn_Yacht` (derives from `ANaviSenseShipPawn`):
   - `Hull` = root Static Mesh Component.
   - `Rudder`, `Propeller_Port`, `Propeller_Stbd`, `BowThruster` = child Static Mesh Components, each at its
     correct position on the hull.
5. The Phase B actuator rig then drives them from `UActuatorComponent.State`:
   - Rudder ← set relative **Yaw** = `RudderDeg`.
   - Props ← add relative **Roll** ∝ RPM each tick.
   - Bow thruster ← trigger wash VFX from `BowThrusterNorm`.

---

## Checklist

```
☐ Rhino: opened unity_yacht_model.fbx, oriented (bow/stern/waterline)
☐ Rudder isolated → joined → pivot on stock axis → exported Rudder.fbx
☐ Port prop isolated → joined → pivot on shaft → exported Propeller_Port.fbx
☐ Stbd prop isolated → joined → pivot on shaft → exported Propeller_Stbd.fbx
☐ Bow thruster isolated (or noted absent) → pivot on tunnel → exported BowThruster.fbx
☐ Hull = everything else → exported Hull.fbx
☐ Unreal: imported all 5 into /Game/NaviSense/Ships/DOLPHIN/
☐ Scale verified (~40 m); pivots verified (rudder hinges, props spin correctly)
☐ Assembled on BP_ShipPawn_Yacht; Phase B rig drives each part
```

---

## Honest notes & gotchas

- **If the bow thruster isn't modeled** (many yacht models omit it), don't worry — skip its mesh and just use
  a Niagara wash effect at the bow location driven by `BowThrusterNorm`. The actuator still works.
- **Pivot is everything.** A part with the pivot at the world origin or mesh center will rotate wildly in
  Unreal. Spend the time in Rhino step 1.4 to get stock/shaft pivots right — it saves much more time later.
- **Keep world positions** during isolation so the parts reassemble aligned. Move pivots, not parts.
- **The hull can stay heavy** (it's static); the moving parts should be lightweight single objects.
- I can't see Rhino or identify the parts visually for you — that hands-on selection is yours. But once the 5
  meshes are in Unreal, I can give you the exact component hierarchy, relative transforms, and the rig code.

*Companion docs: `NaviSense_UE5_COMPONENT_GUIDE.md` (the Phase B rig) and
`NaviSense_UE5_Master_Development_Guide.pdf` (Phase B in context).*
