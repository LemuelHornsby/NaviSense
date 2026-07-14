# WP-20260625 — Clean-machine reproducibility: environment doctor + repro gate (D8)

**Goal:** make demo gate **D8** ("everything reproducible after `git clone` +
documented setup on a clean machine; Cesium tokens documented") concrete and
testable. Ship a stdlib-only **readiness doctor** that says exactly what a fresh
clone is missing and how to fix it, a documented **SETUP.md**, and a verify that
proves the **headless demo pipeline reproduces** (two self-test runs, identical IMO
KPIs). Moves **D8 ☐ → ◐**.

**Type:** pure-Python + docs. **NO wire / DTO / schema / C++ change, NO recompile,
NO new mandatory in-engine gate.** Nothing on the bridge hot path is touched. The
only in-engine step is the optional one-time "open the project on a clean box and
Play" confirmation that the sandbox cannot self-check.

## Why this packet now
- D8 was the **only fully sandbox-reachable open demo gate**. D2's real blocker is
  the **HYDRO** in-engine session (G_HYDRO float-at-waterline), D5/D7 are engine-side
  VFX/MRQ, and D6's remainder is in-PIE beauty shots — none advanceable headless today.
- `run_demo.py` already "seeds D8" with a 5-check preflight. This packet turns that
  seed into a real, demo-day readiness verdict + a documented clone-to-demo path, and
  proves the data pipeline reproduces deterministically.
- It also hardens against **KI-004** (D: truncation): the doctor parses every core
  Python tool and brace-checks the key C++, so a silently-cut file is caught up front.

## What shipped
**New**
- `python/repro_doctor.py` — STDLIB-ONLY readiness/reproducibility doctor (must run
  *before* `pip install`, so it never imports numpy/pyyaml — it probes them with
  `importlib.util.find_spec`). 12 checks, each OK/WARN/FAIL + an actionable fix +
  a `required` flag; `--strict` (demo-day) also fails on a required WARN. Writes
  `Saved/NaviSense_Reports/repro.json`. Checks: python version, **requirements.txt
  deps importable**, **core tools present + parse-clean (KI-004 guard)**, MMG plant,
  **.uproject parses (engine/Water/Cesium)**, **key C++ brace-balanced (KI-015 guard)**,
  **DA_DOLPHIN data assets present AND not bare LFS pointer stubs**, **Cesium ion token
  (optional, documented)**, git+git-lfs, logs writable, scenario registry, port free.
- `SETUP.md` (workspace root) — the documented clone→demo path: `git lfs pull`, venv +
  `pip install -r requirements.txt`, `repro_doctor`, the **Cesium ion token** (BYO,
  where to set it, why headless doesn't need it — D8's "tokens documented"), the
  headless `run_demo --selftest`, and the in-engine run. Plus a troubleshooting list.
- `Development/work_packets/WP_20260625/verify_20260625.py` — gates the packet.

**Edited:** none. (Purely additive — zero risk to existing gates.)

### Run it
```
python python/repro_doctor.py            # readiness table + repro.json
python python/repro_doctor.py --strict   # demo-day: a required WARN also fails
python run_demo.py --scenario imo_turning_circle --selftest   # the headless demo
```

## Acceptance gates
- **G_REPRO_AUTO** (this packet): `verify_20260625.py` → **6/6 gates** + **3/3
  negative controls fire**. ✅ (see result JSON)
  - **G1** doctor on the real tree → verdict READY, 0 required failures · **G2** deps
    enumerated exactly (3 active, optionals excluded, `pyyaml→yaml`, all import) ·
    **G3** .uproject parses (engine 5.7, Water on) + both data assets present & not
    LFS stubs · **G4** with no token in env, `cesium_token`=WARN+optional, verdict
    still READY, and SETUP.md documents the token · **G5** *the core* — `run_demo
    --selftest` twice → both exit 0 + health PASS + same IMO verdict + DT within 2%
    (observed **158.18 m == 158.18 m**, IMO PASS both) · **G6** doctor writes a
    schema-valid `repro.json` + SETUP.md references git-lfs/run_demo/Cesium.
  - Negative controls: **N1** an absent module + a required `python_deps` FAIL →
    verdict NOT ready (a missing dep can't pass) · **N2** a required WARN is READY by
    default but NOT ready under `--strict` (strict actually bites) · **N3** a 130-byte
    `version https://git-lfs` stub is flagged a pointer while a real binary is not
    (the clean-machine "LFS not pulled" trap is caught).
- **G_REPRO_UE** (optional, Lemuel; **not required to close** — the headless half is
  objectively green): on a clean checkout, complete SETUP.md §6 once (open the project,
  Cesium token, Play a scenario, evidence pack builds). The only step not self-checked.

## Verified (sandbox, headless)
Evidence: `NaviSense_UE5/Saved/NaviSense_Reports/wp_20260625_result.json`
- **6/6 gates PASS, 3/3 negative controls FIRE.**
- Doctor on the real tree: **10 OK / 2 WARN / 0 FAIL → READY** (the 2 WARNs are the
  optional Cesium-token-not-in-env and git-lfs-not-on-sandbox-PATH; neither blocks).
- G5 reproducibility: two independent `run_demo --selftest` turning-circle runs both
  **DT 158.18 m, IMO PASS, health PASS** — the data pipeline reproduces exactly.
- **Regression (current disk):** `verify_run_kinematics` **8/8** (newest real run
  `unreal-test-run_20260624_055244`), `verify_sensors_fidelity` **8/8** (morning run),
  `verify_20260623` (run_demo end-to-end) **5/5 + 3/3** (28.0 s).

## Lemuel — steps (≤10 min; all optional, nothing blocks on this)
1. `python python/repro_doctor.py` — expect **VERDICT: READY** (git-lfs + Cesium-token
   should both flip to OK on your machine vs the sandbox).
2. Skim `SETUP.md` — confirm the clone→demo path matches your real setup; tell me any
   step that's wrong for your box and I'll correct it.
3. *(Optional, the real D8 manual gate, G_REPRO_UE)* on a spare/clean checkout, do
   SETUP.md §6 once and confirm the in-engine demo comes up. Tell me **"D8 clean-box:
   pass/fail."**
4. The real D2 blocker is still the **HYDRO** in-engine session (rebuild +
   `DA_DOLPHIN_HydrostaticsConfig` + WaterlineOffsetCm tune) from
   `WP_20260621_HYDRO/PACKET.md` — unchanged by this packet.

## Demo-gate impact
- **D8 ☐ → ◐:** the documented clone→demo path + an automated readiness verdict now
  exist, and the **headless half reproduces objectively** (gated). Remaining for D8:
  the one-time clean-box in-engine confirmation (G_REPRO_UE) — and it inherits D2/D5/D7
  (you can't reproduce gates that aren't closed yet).
- Honesty (KI-019 family): the doctor checks *prerequisites* and proves the *headless*
  pipeline reproduces; it does **not** claim the in-engine demo runs on a clean box —
  that stays a labelled manual gate.

## Rollback
Delete `python/repro_doctor.py`, `SETUP.md`, and
`Development/work_packets/WP_20260625/`. Nothing else changed — no existing file was
edited, so removal restores the prior tree exactly.
