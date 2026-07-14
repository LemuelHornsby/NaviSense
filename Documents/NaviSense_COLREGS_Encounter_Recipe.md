# NaviSense — COLREGS encounter picker (WP-20260703)

> **UPDATED 9 Jul 2026 (WP-20260709)** — three fixes from Lemuel's 8-Jul in-engine run:
> 1. **Recompile ONCE before the next PIE run** (Live Coding Ctrl+Alt+F11 is enough):
>    `ApplyTraffic` now drives **yaw only** and preserves each ship's PLACED pitch/roll
>    (KI-034 — your 90° roll correction on `excursion_vessel` / `Yacht_with_interior`
>    no longer gets stomped, so no more hull-sticking-up-like-a-fin).
> 2. **ONE default target ship for all four encounters (WP-20260709B): `marine_rescue_boat`**
>    (imported world-aligned — no roll correction). The wire/logs/evidence name the exact
>    ship driven. Swap per run: `pick("<encounter>", ship="Yacht_with_interior")` in the
>    editor Python console, or edit `TARGET_SHIP` in the picker — `--target-name` flows
>    everywhere automatically.
> 2b. **Standard flow since WP-20260709C — run from a TERMINAL:** one-time editor setup
>    (Execute Python Script → this picker → `setup_scenery_target()`, save level), then per
>    scenario `python run_colregs.py --head-on | --crossing-giveway | --crossing-standon |
>    --overtaking` → press Play → stop PIE → the run AUTO-VERIFIES (per-scenario result file).
>    All four: `python python/verify_colregs.py --matrix`. Per-run swap: `--ship <label>`.
>    KI-036: editor scripts never launch the listener (that opened a new editor window).
>    Back to 3-ship scenes: run the picker's `reset_all()`.
> 3. **No stub footgun:** the four `colregs_*` scenarios now carry `--plant mmg`
>    automatically — `python python_listener.py --target unreal --scenario colregs_head_on -v`
>    is the complete command (an explicit `--plant` still wins).

Pick ONE COLREGS encounter, run it against a SINGLE target ship, and get a scored
conformance verdict. Own-ship runs a **scripted, deterministic avoidance** (give-way)
or **holds course/speed** (stand-on); the other two Traffic ships are hidden so the
scene shows one unambiguous encounter.

## The four encounters
| Scenario | Rule | Target starts | Own-ship (scripted) | Expected verdict |
|---|---|---|---|---|
| `colregs_head_on` | 14 | fine on the **port** bow, reciprocal | early **starboard** alteration (~35°), pass port-to-port | **COMPLIANT** (~238 m miss) |
| `colregs_crossing_giveway` | 15 | crossing from the **starboard** bow | **starboard** alteration (~40°), pass **astern** | **COMPLIANT** (~340 m miss) |
| `colregs_crossing_standon` | 17 | crossing from the **port** bow | **hold** course & speed (running start) | **COMPLIANT** (held; ~150 m near-miss) |
| `colregs_overtaking` | 13 | slow vessel close ahead (port offset) | **starboard** alteration to keep clear | **COMPLIANT** (~295 m miss) |

The own-ship maneuver is a closed-loop heading hold on the plant's authoritative yaw
(`ColregsAvoidController`, `python/scenario_controllers.py`); it is fully scripted and
replays bit-for-bit. Conformance is measured by `python/colregs_score.py` (Rules
8/13–17) and rendered in `logs/<run>/evidence_pack/evidence_report.html`.

> **Honesty (KI-019 family):** the target is a scripted, deterministic contact and
> own-ship runs a *pre-planned* maneuver — this demonstrates the encounter geometry
> + the conformance *metric*, NOT autonomous COLREGS avoidance (that is the W5-6
> roadmap). A COMPLIANT verdict here means "the scripted maneuver conformed," not
> "NaviSense decided to give way."

## One-time setup
Place your three ships under an Outliner folder named **Traffic** (already done:
`excursion_vessel`, `marine_rescue_boat`, `Yacht_with_interior`).

## Run an encounter (fast path)
**Tools → Execute Python Script → `Phase5_Systems/10_colregs_encounter.py`** with
`ENCOUNTER` set at the top of the file to one of `head_on` / `crossing_giveway` /
`crossing_standon` / `overtaking`. The script:
1. hides the two unused ships, shows + preps the chosen target,
2. assigns it as the own-ship pawn's `TrafficActors[0]`,
3. launches the listener (`--scenario colregs_<encounter>`) in a new console (or prints
   the command),
then **press Play**. After the run, open the evidence report for the verdict.

## Turn it into a 4-button picker (Editor Utility Widget)
1. Content Browser → right-click → **Editor Utilities → Editor Utility Widget** →
   name it `EUW_COLREGS_Picker`.
2. Add four buttons: **Head-on**, **Crossing (give-way)**, **Crossing (stand-on)**,
   **Overtaking**.
3. For each button's **OnClicked**, add an **Execute Python Command** node (or a
   Python-call node) that runs, e.g.:
   `import importlib, Phase5_Systems.\x2f... ` — simplest is one line per button:
   `py: import sys; exec(open(r"<WORKSPACE>/NaviSense_UE5/Content/NaviSense/Python/Phase5_Systems/10_colregs_encounter.py").read().replace('ENCOUNTER = "head_on"','ENCOUNTER = "crossing_giveway"'))`
   or, cleaner, `import Phase5_Systems` isn't on the path — instead bind each button to
   the module helpers: run the script once (registers it), then call
   `head_on()` / `crossing_giveway()` / `crossing_standon()` / `overtaking()`.
4. Run the widget (right-click → Run Editor Utility Widget) and click an encounter,
   then press Play.

*(UMG graph wiring isn't reliably Python-scriptable on this engine build — build the
widget by hand as above; the picker logic itself is all in the Python module.)*

## Read the result
`logs/<run>/evidence_pack/evidence_report.html` → the **COLREGS conformance** section
shows the encounter, the duty (give-way / stand-on), the per-rule checks, and the
COMPLIANT / NON_COMPLIANT / NOT_APPLICABLE verdict. `kpis.json` carries the same under
`ais.conformance`.
