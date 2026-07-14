# NaviSense Bridge Dashboard — Build Recipe (WP-UI-DASHBOARD / WP_20260701)

> **9 Jul 2026:** for the complete click-by-click build (all 19 bindings, sliders,
> viewport/toggle/mouse setup, troubleshooting), use
> **`NaviSense_BridgeDashboard_Complete_Guide.docx`** in this folder — it supersedes
> the step summaries below.

Companion to `NaviSense_Wake_VFX_Recipe.md` — same pattern: Python/C++ ship the
data + control layer and a build helper; the UMG widget graph itself is laid
out by hand in the editor (UMG widget wiring is not reliably Python-scriptable
in this engine build).

## 1. What this delivers

A **full-screen, interactive** bridge dashboard: navy background, four panels
(actuators / sensors / maneuver+IMO KPIs / sea-state+AIS), with helm/throttle/
bow-thruster controls that drive the ship through the existing manual-drive
path. Locked decisions (Lemuel, 30 Jun 2026) — see
`Development/work_packets/NEXT_PACKET_DIRECTIVE.md`.

## 2. Prerequisite: C++ rebuild

`NaviSense.Build.cs` now has `UMG`, `Slate`, `SlateCore` **enabled** (was
commented "Phase 10 — HUD"). This packet **requires a full C++ rebuild**
(editor closed, `Build.bat`, not Live Coding — see the KI-018 process lesson:
Live Coding does not reliably rebuild the base DLL) before the widget's
getter/setter bindings will resolve in the UMG graph.

## 3. Navy theme palette (single source — matches `09_build_bridge_dashboard.py`)

| Role                       | Hex       | Use                                   |
|----------------------------|-----------|----------------------------------------|
| `background`               | `#0B1F33` | Full-screen dashboard backdrop         |
| `panel`                     | `#132A45` | The four panel card backgrounds        |
| `accent_ok`                 | `#2ECC71` | Green — nominal / compliant / healthy  |
| `accent_caution`            | `#F5A623` | Amber — caution / degraded / stale     |
| `accent_alarm`              | `#E74C3C` | Red — alarm / non-compliant / fault    |
| `text`                      | `#FFFFFF` | Primary text                           |

`verify_20260701.py` parity-checks this table against the `NAVY_THEME` dict in
`09_build_bridge_dashboard.py` — if you change one, change both (or the gate
fails), same discipline as the WP-20260628 wake-curve C++/Python parity gate.

## 4. Build steps (in-editor, ~20 min)

1. Rebuild C++ (Step 2 above). Confirm `Z0` still green
   (`python Development/work_packets/WP_20260615_COMPILE_AUDIT/verify_compile_readiness.py`).
2. Run `Tools > Execute Python Script… > 09_build_bridge_dashboard.py`. This
   prints the theme + the full binding list to the Output Log and best-effort
   creates an empty `WBP_BridgeDashboard` under `Content/NaviSense/UI/` (parent
   class `UserWidget`). If asset creation fails on this engine build, create it
   by hand: Content Browser → Add → User Interface → Widget Blueprint → name it
   `WBP_BridgeDashboard`.
3. In the widget Designer: a full-screen `Canvas Panel` → `Border`
   (Brush Color = `background` navy) filling the screen. Add four child
   `Border` panels (Brush Color = `panel`), one per corner/quadrant:
   - **Top-left — Actuators**: rudder-angle gauge/text, port RPM, starboard
     RPM, bow-thruster bar.
   - **Top-right — Sensors**: heading, speed-over-ground, yaw-rate, roll,
     pitch, heave, lat/lon.
   - **Bottom-left — Maneuver + IMO KPIs**: motion-mode label, plant mode,
     rolling advance (label it "live proxy, not the validated KPI" — KI-019),
     peak heading deviation.
   - **Bottom-right — Sea state + AIS/COLREGS**: sea state / wave height (from
     the run manifest — read once at widget Construct via a Blueprint
     GameplayStatics call, or leave as a static label sourced from the
     scenario name until a live getter is added), traffic contact count,
     nearest-contact range + name.
4. Bind every text/gauge widget's Text/Percent property to the matching
   `ANaviSenseShipPawn` getter (**Bind** button in the Details panel → pick the
   function) — see the exact list Step 2 printed, or `PANEL_BINDINGS` in
   `09_build_bridge_dashboard.py`. Use `accent_ok`/`accent_caution`/
   `accent_alarm` to color-code e.g. `IsBridgeStale()` (caution) or the
   nearest-traffic range crossing a CPA threshold (alarm).
5. Add a **helm slider** (or two buttons ± ) bound to call
   `SetHelm(float)` **On Value Changed**; a **throttle slider** →
   `SetThrottle(float)`; a **bow-thruster slider** → `SetBowThruster(float)`.
   All three are `[-1,1]`, clamped in C++ — the widget does not need to clamp.
   `IsDashboardControlActive()` flips true the first time any of these fires;
   from then on the widget's values (not W/S/A/D) drive `UpdateManual` every
   tick — make sure the widget calls `SetThrottle`/`SetHelm` every tick while
   visible (an `Event Tick` re-issuing the current slider value works), not
   only on change, or the ship will coast on the last command.
6. Add the widget to the viewport: PlayerController (or a small new
   `ANaviSenseShipPawn`-side helper) `Event BeginPlay` → `Create Widget`
   (class `WBP_BridgeDashboard`) → `Add to Viewport`. Bind a key (`Tab` or
   `B`) to toggle its visibility (`Collapsed` ⇄ `Visible`) so it can be
   shown/hidden without leaving PIE.
7. Ensure `GM_NaviSense` is the active GameMode override (it already is,
   KI-021) and `MotionSource` is `Manual` (press `M`) before expecting the
   helm/throttle/thruster to move the ship — the dashboard drives the SAME
   manual-drive path as the keyboard, not `PoseReceive`.

## 5. Acceptance (`G_DASHBOARD_UE`, Lemuel, ≤20 min)

Full-screen navy dashboard visible (toggle key), all four panels show live,
sane values while a run/PIE session is active, and moving the helm/throttle/
thruster sliders visibly turns the rudder / changes RPM+speed / yaws the ship
at rest, exactly like W/S/A/D.

## 6. Honesty labels (KI-019 family — put these ON the dashboard, not just here)

- Maneuver/IMO panel: "Live proxy — not the CFD-validated evidence-pack KPI."
- Sea-state/AIS panel: "AIS contacts are scripted; range is geometry, not the
  logged CPA/TCPA/COLREGS verdict."
- Wake/attitude visuals elsewhere in-scene remain visual proxies (unchanged).
