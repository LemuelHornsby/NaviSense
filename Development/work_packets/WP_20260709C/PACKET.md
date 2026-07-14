# WP-20260709C — terminal COLREGS runner + editor-spawn fix (T-2)

**Trigger (Lemuel):** executing the picker via Tools → Execute Python Script
opened a NEW blank Unreal editor window. **Root cause (KI-036):** inside editor
Python, `sys.executable` IS `UnrealEditor.exe` — the picker's best-effort
auto-launch `Popen([sys.executable, python_listener.py, …])` therefore spawned
another editor. **Directive:** runs come from Python in a terminal, like
before; scenario chosen in code (`--overtaking`, `--head-on`, …); rescue boat
default. Decisions (asked + answered): unused ships stay VISIBLE as scenery ·
auto-verify ON when the run ends · picker kept as a setup utility.

## What shipped
- **`run_colregs.py` (workspace root, NEW)** — one terminal command per scenario:
  `python run_colregs.py --head-on | --crossing-giveway | --crossing-standon | --overtaking`
  → prints the plan, launches the canonical listener in the FOREGROUND
  (`--once -v`, plant=mmg via the scenario), you press Play, stop PIE →
  **auto-verifies THAT run dir** (`verify_colregs`) and writes the per-scenario
  result file. Options: `--ship LABEL` (per-run swap → `--target-name`),
  `--no-verify`, `--selftest` (headless: isolated in `logs/_selftest`, 25×,
  `colregs-<scenario>-selftest` run-id — never shadows a real run), `--dry-run`,
  `--list`.
- **`10_colregs_encounter.py` (fixed + repurposed)** — auto-launch REMOVED
  (KI-036); default `__main__` action is now the ONE-TIME
  **`setup_scenery_target()`**: assigns `marine_rescue_boat` as
  `TrafficActors[0]`, hides nothing (scenery mode), tells you to save the level
  and prints the run_colregs commands. `pick()` (hide-others flow) and
  `reset_all()` (restore 3-ship scenes) remain, now print-only.
- **`verify_20260709b.py`** — G4 swap-e2e now writes to a temp out-dir so it can
  never clobber the canonical per-scenario result file (found by today's gate).

## Acceptance — `python/verify_20260709c.py` **4/4 + 3/3 PASS** (9 Jul)
G1 runner-mapping (4 flags → 4 scenarios; dry-run cmd correct incl. `--ship`) ·
G2 e2e-selftest (fresh isolated selftest run auto-verified — THAT run dir) ·
G3 picker-fixed (no child-process launch; scenery-setup default; pick/reset kept) ·
G4 regression (verify_20260709b 5/5+3/3). Neg: no-flag rejected (rc 2) ·
two-flags rejected (rc 2) · the old auto-launch pattern is detected on a tmp copy.

## Lemuel — the new workflow
**One-time (editor, ~1 min):** Tools → Execute Python Script →
`Phase5_Systems/10_colregs_encounter.py` (runs `setup_scenery_target()`), then
**save the level**. (And Ctrl+Alt+F11 once if the KI-034 recompile is still pending.)

**Per scenario (terminal):**
```
cd "D:\Marine Autonomy\NAVISENSE\NaviSense Simulator with Unreal Engine"
python run_colregs.py --head-on          # then press PLAY; stop PIE to end
python run_colregs.py --crossing-giveway
python run_colregs.py --crossing-standon
python run_colregs.py --overtaking
python python/verify_colregs.py --matrix # all four green = G_COLREGS_UE evidence
```
Swap ship for a run: `python run_colregs.py --head-on --ship Yacht_with_interior`.

## Rollback
Delete `run_colregs.py`, `python/verify_20260709c.py`; revert the picker + the
one-line verify_20260709b change.
