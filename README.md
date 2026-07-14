# NaviSense Simulator — Unreal Engine 5.7 (canonical workspace)

Flagship marine-autonomy simulator by **NaviSyn Marine Solutions**. This folder is the
**single, self-contained codebase** for the Unreal build. The original `D:\Marine Autonomy\NAVISENSE`
folder (Unity project + originals) is kept untouched as a backup.

## Layout
- `NaviSense_UE5/` — the Unreal Engine 5.7 project (`.uproject`, `Source/`, `Content/`, `Config/`).
- `python_listener.py` — **canonical** Python bridge/plant/control listener. Run this.
- `python/` — plant adapters, scenario + autopilot controllers, run logger, analysis tools.
- `Maneuvering/maniobrabilidad/mmg/` — validated MMG maneuvering dynamics (DOLPHIN.yaml).
- `Development/bridge_harness/` — offline protocol/CI tests only (not the run listener).
- `Development/work_packets/` — dated co-dev packets (daily build + weekly traction).
- `Documents/` — strategy + technical docs. `Image References/` — brand art.

## Run the closed loop
```
python -m venv .venv && .venv\Scripts\activate      # first time
pip install -r requirements.txt                      # first time
python python_listener.py --plant mmg --controller zigzag10 --target unreal --verbose
```
Then press **Play** in `NaviSense_Monaco`. Useful controllers: `turning_circle` (big obvious turn),
`zigzag10` / `zigzag20` (IMO zig-zag), `straight`. Both `-v` and `--verbose` work.

## Sign / maneuver note
Scenario controllers are fed the **plant's own heading**, so a zig-zag/turning-circle runs even if
the frontend sensor echo lacks IMU heading. Coordinate/sign convention lives in ONE place:
`NaviSense_UE5/Source/NaviSense/Core/NaviSenseCoords.h::WireYawToUE` — fix sign issues only there.

## Git / backup
This workspace has its own git repo. Binary assets use Git LFS (see `.gitattributes`) — run
`git lfs install` once, then commit `Content/` deliberately. Heavy UE dirs (Binaries, Intermediate,
Saved, DerivedDataCache, Cesium cache) are git-ignored.
