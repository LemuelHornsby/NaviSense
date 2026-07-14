# NaviSense — clean-machine setup & reproduction (demo gate D8)

This is the documented path from a fresh `git clone` to a running NaviSense demo on
a clean machine. It is the human side of **D8** ("everything reproducible after clone
+ documented setup; Cesium tokens documented"). The headless half is gated
automatically by `Development/work_packets/WP_20260625/verify_20260625.py`; the
in-engine half (open the UE project and press Play on a fresh box) is the one manual
confirmation.

> **One-button readiness check (run this first, and again any time something looks off):**
> ```
> python python/repro_doctor.py            # reports exactly what is missing + how to fix it
> python python/repro_doctor.py --strict   # demo-day: a required WARN also fails the verdict
> ```
> It is stdlib-only, so it runs **before** `pip install`. A `READY` verdict means the
> prerequisites below are satisfied.

## 0 · Prerequisites
- **Windows 10/11** with **Unreal Engine 5.7** (Epic Games launcher).
- **Python 3.10+** on PATH.
- **Git** + **Git LFS** (the `.uasset` binaries are stored via LFS).
- A **Cesium ion** account + token — *only* for the photoreal Google 3D Tiles in the
  in-engine scene. The headless pipeline and the synthetic GPS sensor do **not** need it.
- `CesiumForUnreal` plugin **built for UE 5.7** (older Cesium caps at UE 5.4 — see KI-014).

## 1 · Clone + pull the binary assets
```
git clone <your-remote> NaviSense
cd "NaviSense/NaviSense Simulator with Unreal Engine"
git lfs install
git lfs pull            # REQUIRED: without this, *.uasset are tiny pointer stubs
```
If the doctor reports `data_assets … LFS not pulled (stub)`, run `git lfs pull`.

## 2 · Python environment
```
python -m venv .venv
.\.venv\Scripts\activate        # PowerShell;  source .venv/bin/activate on *nix
pip install -r requirements.txt # numpy, pyyaml, matplotlib (the 3 required deps)
```
Optional advanced autopilots (CasADi/NMPC, Torch/PPO) are commented in
`requirements.txt`; the demo does not need them.

## 3 · Verify readiness
```
python python/repro_doctor.py
```
Expect `VERDICT: READY`. Two WARNs are normal on a box without a Cesium token set or
without git-lfs on PATH after the assets are already pulled — neither blocks the
headless demo.

## 4 · Cesium ion token (BYO; photoreal tiles only)
The Google Photorealistic 3D Tiles need a Cesium ion access token (BYO — commercial
terms are the user's; see KI-010). Provide it either way:
- **In-engine:** Unreal → *Cesium* panel → sign in / paste the ion token, then the
  `NaviSense_Monaco` tileset loads.
- **For the doctor/automation:** set an environment variable so `repro_doctor` reports
  it present:
  ```
  setx CESIUM_ION_TOKEN "<your-ion-token>"     # Windows, persists; reopen the shell
  ```
  (`CESIUM_ION_ACCESS_TOKEN` / `NAVISENSE_CESIUM_TOKEN` are also recognised.)
**Never commit the token.** Without it you still get the full closed loop, sensors,
6-DOF motion, and the evidence pack — just no Google photoreal terrain.

## 5 · Headless demo — no Unreal, no GPU (the reproducible core)
```
python run_demo.py --scenario imo_turning_circle --selftest
```
A bundled pure-Python client plays the vessel, so the **entire** pipeline runs without
the editor: preflight → bridge listener → one run → auto IMO evidence pack +
kinematic-health gate. Expect `DEMO COMPLETE … health=PASS`, with the evidence pack at
`logs/<run>/evidence_pack/` (`EVIDENCE.md`, `kpis.json`, plots). List the demo presets
with `python run_demo.py --list`.

## 6 · In-engine demo (the one manual gate)
1. Open `NaviSense_UE5/NaviSense_UE5.uproject` (let it build on first open;
   `Development > Rebuild` if Live Coding looks stale — see Maintenance Guide / KI-018).
2. Provide the Cesium token (step 4) so `NaviSense_Monaco` loads its tiles.
3. If a data asset is missing, recreate it via **Tools → Execute Python Script →**
   `NaviSense_UE5/.../Scripts/06_create_hydrostatics_config.py` — **never** via the
   right-click Data-Asset menu, which crashes on the Cesium scene (KI-013).
4. In a terminal at the workspace root:
   ```
   python run_demo.py --scenario imo_turning_circle      # waits for PIE
   ```
   Press **Play** in Unreal, watch the turning circle, press **Stop** — the evidence
   pack builds automatically.

## 7 · What "reproducible" is actually verified
- **Headless (gated, automatic):** `verify_20260625.py` runs `run_demo --selftest`
  twice on an isolated path and requires both to pass with consistent IMO KPIs — proof
  the data pipeline reproduces independent of host. `repro_doctor` proves the
  prerequisites are present and the Python tools are intact (KI-004 truncation guard).
- **In-engine (manual, optional):** open the project on a clean box and complete step 6
  once. This is the only step the sandbox cannot self-check.

## Troubleshooting quick hits
- `data_assets … LFS not pulled` → `git lfs pull`.
- `port_free … in use` → another listener is running; stop it or pass `--port`.
- Cesium tiles missing / editor crash on save → KI-014 (token / UE-5.7-compatible
  Cesium build); synthetic GPS is unaffected.
- Full run book: `Manual and Troubleshooting/00_Operations_Manual.md`;
  issues register: `Manual and Troubleshooting/04_Known_Issues_Register.md`.
