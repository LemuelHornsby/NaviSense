# NaviSense nightly automation (WP-5, F7 / Plan §6)

The "machine around the work": every night at 02:00 it runs the tests, renders a
beauty frame, and folds everything into one `summary.json` that the 07:06 Claude
session reads first — so each morning starts from measured truth, not memory.

## One-time setup

1. **Point at your engine.** Either set a permanent env var:
   ```powershell
   setx UE_ROOT "C:\Program Files\Epic Games\UE_5.7"
   ```
   …or edit `$UeRoot` at the top of `automation_config.ps1`.
2. **Python deps** (for the test lane): `pip install pytest`.
3. **Register the schedule** (elevated PowerShell, once):
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\register_nightly_tasks.ps1
   ```

## Run any lane by hand

```powershell
.\nightly_tests.ps1     # pytest + bridge verifies + UE Automation RunTests NaviSense
.\nightly_render.ps1    # one 1080p beauty PNG of NaviSense_Monaco
.\nightly_sweep.ps1     # collect -> summary.json
.\nightly.ps1           # all three, in order (what the scheduler runs)
```

## Outputs (per night)

`NaviSense_UE5\Saved\NaviSense_Reports\nightly\<YYYY-MM-DD>\`
| File | Lane | Meaning |
|------|------|---------|
| `tests.json` | tests | pytest / verify / UE-automation pass map + `green` |
| `ue_tests\index.json` | tests | raw UE Automation report |
| `beauty_monaco.png` | render | nightly visual-regression frame |
| `render.json` | render | render status |
| `summary.json` | sweep | **the morning read** — overall_green, lane status, per-packet results, UE log tail |
| `nightly_console.log` | all | full transcript |

## WP-5 gate

- `RunTests NaviSense` green from the CLI → `tests.json.results.ue_automation == true`.
- One nightly PNG under `nightly\<date>\` → `render.json.green == true`.

## Notes / upgrades

- The render lane uses `HighResShot` now; swap to **Movie Render Queue** (`MRQ_Nightly`
  preset) in WP-20 (D7) for cinematic frames.
- Offline (no engine on PATH) the UE lanes self-skip (`null`) so the Python lane still
  runs and reports — useful on a CI box without the editor.
- CI ladder (Plan §6.5): local Task Scheduler now → self-hosted GitHub Actions runner at W9+.
