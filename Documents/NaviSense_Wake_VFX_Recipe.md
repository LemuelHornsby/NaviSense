# NaviSense — Wake & Spray VFX recipe (D5 / WP-16)

**Goal:** a speed-responsive wake — bow wave + stern wash + spray bursts — that
grows with the own-ship's speed and is *off* when moored. The hull is
kinematically posed (no fluid sim), so the VFX is **driven by speed**, not by
fluid interaction.

**Single source of truth for the curve:** `python/wake_model.py` (headless,
gate-checked by `verify_20260628.py`) **==** `ANaviSenseShipPawn::GetWakeIntensity01()`
/ `GetWakeSpray01()` (C++). A Niagara system reads two 0..1 user floats —
`WakeIntensity` and `Spray` — and scales itself. Do **not** re-derive the curve
inside Niagara; just consume the two scalars.

| kn | m/s | WakeIntensity | Spray | ribbon width (cm) |
|---:|----:|--------------:|------:|------------------:|
| 0 | 0.00 | 0.000 | 0.000 | 50 |
| 6 | 3.09 | 0.279 | 0.000 | 134 |
| 12 | 6.17 | 0.587 | 0.000 | 226 |
| 15 | 7.72 | 0.736 | ~0.00 | 271 |
| 18 | 9.26 | 0.896 | 0.600 | 319 |
| 20 | 10.29 | 1.000 | 1.000 | 350 |

Anchors (pawn UPROPERTYs, *NaviSense | VFX*; tune without recompiling):
`WakeMinSpeedMS = 0.3` (dead-band), `WakeSprayOnsetMS = 7.7` (~15 kn hull speed),
`WakeFullSpeedMS = 10.3` (~20 kn). Print the full table any time with
`python python/wake_model.py`.

---

## Step 1 — Recompile (folds into the engine-closeout rebuild)
The wake feed adds `BlueprintPure` getters + `GetWakeIntensity01/Spray01` to the
pawn. Build once (editor **closed**) per the Maintenance Guide — Live Coding does
**not** relink the base DLL (KI-018 lesson):
```
"<UE>\Engine\Build\BatchFiles\Build.bat" NaviSenseEditor Win64 Development -Project="<...>\NaviSense_UE5\NaviSense_UE5.uproject" -waitmutex
```
*(If you want zero recompile for a first look, skip to the **No-recompile fallback** at the bottom.)*

## Step 2 — Attach the WakeViz component (script, ~2 min)
Open `NaviSense_Monaco`, then **Tools → Execute Python Script →**
`Content/NaviSense/Python/Phase5_Systems/04_setup_wake_vfx.py`.
It adds a `NiagaraComponent` named **WakeViz** at the stern
(`(-1800, 0, -150)` cm — tune Z so spawns sit on the sea), assigns `NS_Wake` if
it exists, and seeds the user floats from the pawn. (Created by script, not the
right-click menu — KI-013.)

## Step 3 — Build NS_Wake (the minimal demo-grade system)
Content Browser → `/Game/NaviSense/Niagara/` → right-click → **FX → Niagara System
→ New system from emitters** (or empty), name it **`NS_Wake`**. Add user
parameters first: **User.WakeIntensity (float)**, **User.Spray (float)**.

**Emitter A — Stern wash (Ribbon)** — start from the **Ribbon** template:
- Emitter Update → **Spawn Rate**: bind to a *scratch* `SpawnRate = User.WakeIntensity * 600`.
- Particle Spawn → **Ribbon Width**: `lerp(50, 350, User.WakeIntensity)` (cm).
- Render → Ribbon Renderer, a translucent/foam material; align to the water plane.
- Sim target **GPUCompute**; **Fixed Bounds** on (e.g. 6000 cm) so it never culls.

**Emitter B — Spray (Sprites)** — start from a **sprite burst/fountain**:
- Emitter Update → **Spawn Rate**: `User.Spray * 400` (so it is silent below ~15 kn).
- Particle Spawn → small upward + outward velocity, short lifetime; soft sprite/foam.
- Render → Sprite Renderer, additive; **GPUCompute**; **Fixed Bounds** on.

Keep it cheap (`stat GPU` budget **< 2 ms**). Save `NS_Wake`, then re-run Step 2 to
assign it.

## Step 4 — Drive the two user floats from speed (primary, after recompile)
Open `BP_ShipPawn_Yacht` → **Event Tick**:
```
WakeViz → Set Niagara Variable (Float):  In Variable Name = "User.WakeIntensity"
          In Value = (self) Get Wake Intensity 01            [BlueprintPure C++]
WakeViz → Set Niagara Variable (Float):  In Variable Name = "User.Spray"
          In Value = (self) Get Wake Spray 01                [BlueprintPure C++]
```
That is the whole binding — the C++ getters return the gated curve from live speed.
Compile + Save the BP. (For permanence, also add the WakeViz component in the BP
class, not just the level instance — see KI-023 instance-vs-class note.)

## Step 5 — Acceptance (G_WAKE_UE)
Start the listener and PIE a transit / turning circle, e.g.
`python python_listener.py --scenario imo_turning_circle` then Play. Confirm:
1. **Moored = no wake** (at rest the ribbon/spray are off).
2. **Wake grows with speed** (ribbon widens, spawn rate rises as she makes way).
3. **Spray bursts only at high speed** (appears above ~15 kn, off at cruise).
4. **Reads right at all camera modes** and `stat GPU` wake cost **< 2 ms**.
5. Capture 1–2 screenshots into `Development/Development images/` for the D6 pack.

---

## No-recompile fallback (first look without a rebuild)
If you want a wake before the next rebuild, drive the user floats from a Blueprint
that computes speed from the actor's frame-to-frame movement instead of the C++
getter:
- `BP_ShipPawn_Yacht` Event Tick: `Speed (cm/s) = (GetActorLocation - PrevLoc).Size2D / DeltaSeconds`; store `PrevLoc`.
- `v = Speed * 0.01` (m/s); `WakeIntensity = clamp((v - 0.3)/(10.3 - 0.3), 0, 1)`;
  `Spray = clamp((v - 7.7)/(10.3 - 7.7), 0, 1)` (the same constants).
- Set `User.WakeIntensity` / `User.Spray` on WakeViz as in Step 4.
Slightly noisier than the C++ feed (position-delta vs plant velocity) but visually
fine, and it unblocks the eye-check. Switch to the C++ getters after the rebuild.

---

## Foam-trail tuning — exact module locations (added 2026-06-28)

**Where the "Fountain emitter" is:** open `NS_Wake`. The center tab is **System Overview**. The
teal **NS_Wake** node = the system; the **orange column to its right IS the Fountain emitter** — the
whole vertical stack (`Properties` · `Emitter Spawn` · `Emitter Update` · `Particle Spawn` ·
`Particle Update` · `Render`). Click a **row** in that column to select a module; edit it in the
**Details** panel on the right.

**Why there is no trail behind the ship:** the emitter is in **Local Space**, so particles move
with the boat. Turn it off and they're left in the water = the wake.

Edits (click the row in the Fountain column → set in Details → then **Compile + Save**):
1. **Trail** — click **Properties** (top row, `[CPU]` tag) → uncheck **Local Space**.
2. **Kill the green → white foam** — click **Scale Color** (under *Particle Update*) → set its colour
   to white with alpha fading to 0; also click **Initialize Particle** (under *Particle Spawn*) →
   **Color** = white. (The green is the Fountain template's Scale-Color gradient.)
3. **Flat wash, not a geyser** — click **Add Velocity (In Cone)** (*Particle Spawn*) → drop the
   velocity/speed to ~40–80 and widen the cone slightly; click **Gravity Force** (*Particle Update*)
   → set ~0 (foam shouldn't arc like a fountain).
4. **Long trail** — click **Initialize Particle** → **Lifetime** 4–6 s; **Sprite Size** 100–200.
5. **Density** — the **Spawn Rate** Multiply Float we set (`User.WakeIntensity × 600`): raise the
   constant to ~1500 for a fuller trail.
6. (Optional V-arms) add a second emitter angled outboard, same settings — but a **40 m displacement
   yacht at ~6 kn** makes a clean foam trail that widens slightly aft, NOT the big planing
   rooster-tail in a speedboat photo. Aim for the accurate, calmer look.
