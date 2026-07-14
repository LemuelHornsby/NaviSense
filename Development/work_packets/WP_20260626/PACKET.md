# WP-20260626 — Single-file HTML evidence report (D6 / WP-19)

**Goal:** turn the D6 evidence pack from a folder of loose files (`EVIDENCE.md` +
`*.png` + `kpis.json`) into a **single self-contained `evidence_report.html`** —
the thing you actually hand to a pilot customer, a DIANA reviewer, or attach to a
proposal. Every plot is embedded in the file; it renders with **zero external
file dependencies**. Implements **WP-19** (Master Execution Plan §4: "KPIs vs IMO
criteria table + plots → one PDF/HTML"). Moves **D6** forward (still ◐).

**Type:** pure-Python **presentation layer**. **NO wire / DTO / schema / C++
change, NO recompile, no new mandatory in-engine gate.** One existing file edited
additively (`build_evidence_pack.py`, +1 import, +1 call, +1 flag); one new
module. Nothing on the bridge hot path is touched.

## Why this packet now
- The previous packet (WP-20260625, D8) closed green (6/6 + 3/3). Of the open demo
  gates, the only ones advanceable **headless** are D6 polish and evidence
  integrity — D2 (HYDRO float-at-waterline), D5 (wake VFX), D7 (MRQ film) are all
  in-engine and need Lemuel + the GPU.
- D6's deliverable **is** the evidence pack. It existed as scattered files; a
  single shareable artifact is what makes it demo/grant-ready. This is the highest
  -leverage fully-sandbox-verifiable work toward 11 Jul.
- It also reinforces honesty (KI-019 family): the report carries an explicit
  provenance footer stating what the numbers are and are **not**.

## What shipped
**New**
- `python/evidence_html.py` — stdlib-only renderer (`base64`/`html`/`os`). It
  **formats** the dicts `build_pack` already computed (`meta`/`health`/`maneuver`/
  `actuators`/`ais`/`plots`) — it never re-derives a number, so the HTML cannot
  drift from `kpis.json`. Embeds each plot PNG as a base64 `data:` URI (the file
  is self-contained), renders the IMO-KPI table with PASS/FAIL vs limits, the
  kinematic-health verdict + every check, the actuator-correspondence table, the
  AIS/COLREGS table, and a provenance/honesty footer.
- `Development/work_packets/WP_20260626/verify_20260626.py` — gates the packet.

**Edited (additive)**
- `python/build_evidence_pack.py` — imports `evidence_html`; `build_pack(...,
  make_html=True)` writes the report by default and records `report_html` in
  `kpis.json`; `main()` gains `--no-html`; generator tag bumped to **v2**. The
  `EVIDENCE.md` / `kpis.json` / `*.png` outputs are unchanged.
- `run_demo.py` ships the HTML automatically (it calls `build_evidence_pack` —
  no change needed; confirmed live via `--selftest`).

### Run it
```
python python/build_evidence_pack.py --run-dir logs/<run>     # writes evidence_pack/evidence_report.html
python python/build_evidence_pack.py --run-dir logs/<run> --no-html   # skip the HTML
python run_demo.py --scenario imo_turning_circle --selftest   # the report ships in the auto pack
```
Open `logs/<run>/evidence_pack/evidence_report.html` in any browser — it is one
file, no sibling assets required.

## Acceptance gates
- **G_HTML_AUTO** (this packet): `verify_20260626.py` → **6/6 gates** + **3/3
  negative controls fire**. ✅ (see result JSON)
  - **G1** builds + parses as HTML · **G2** every plot embedded as a **valid**
    base64 PNG, count == plot count (no broken images) · **G3** **IMO-KPI parity**
    — DT / DT-Lpp / advance appear verbatim from `kpis.json` (158.18 m / 4.16 /
    155.31 m) · **G4** health verdict PASS + every check id present · **G5**
    AIS/COLREGS section with the scripted target's range + encounter · **G6**
    self-contained + **portable** (0 external refs; copied alone to a temp dir it
    still renders).
  - Negative controls: **N1** a magic-tampered embedded image is DETECTED invalid
    (G2 validates image bytes, not a substring) · **N2** a wrong KPI value is
    DETECTED by the parity check (G3 compares values) · **N3** an injected external
    `<img src="…png">` is FLAGGED (G6 detects external refs).

## Verified (sandbox, headless)
Evidence: `NaviSense_UE5/Saved/NaviSense_Reports/wp_20260626_result.json`
- **6/6 gates PASS, 3/3 negative controls FIRE** on the real run
  `unreal-test-run_20260624_055244` (turning circle, DT/Lpp 4.16 IMO PASS).
- `run_demo --selftest` turning-circle → 201 KB `evidence_report.html`, 2 plots
  embedded, 0 external refs, `report_html` recorded in `kpis.json`.
- **Regression (current disk):** `verify_run_kinematics` **8/8**,
  `verify_sensors_fidelity` **8/8** (C1 KI-024 divergence still flagged / joined on
  wall_time), `verify_20260623` run_demo e2e **5/5 + 3/3** (26.6 s — exercised the
  new HTML path), `verify_20260624` AIS **6/6 + 3/3**, `repro_doctor` **READY** +
  `run_demo --selftest` **DT 158.2 m IMO PASS**.

## Lemuel — steps (≤5 min; all optional, nothing blocks)
1. `python run_demo.py --scenario imo_turning_circle --selftest` (no Unreal
   needed), then open the printed `…/evidence_pack/evidence_report.html` in a
   browser — confirm the KPI table, health badge, and embedded plots look right.
2. Tell me any layout/wording you want changed for the demo/grant audience.
3. The real D2 blocker is still the **HYDRO** in-engine session
   (`WP_20260621_HYDRO/PACKET.md`) — unchanged by this packet.

## Demo-gate impact
- **D6 (◐, unchanged status):** the evidence pack is now a **single shareable
  file**. Remaining for D6: ≥3 in-PIE beauty screenshots / MRQ (engine-side).
- Honesty (KI-019 family): the report only formats verified numbers and labels
  what they are/are-not (MMG standard-method KPIs **not** CFD-validated;
  roll/pitch/heave = visual proxy; AIS = scripted). No new claim is made.

## Rollback
Delete `python/evidence_html.py` and `Development/work_packets/WP_20260626/`, then
revert the 3 additive hooks in `python/build_evidence_pack.py` (the `import
evidence_html` line, the `make_html` block in `build_pack`, the `--no-html` arg).
`EVIDENCE.md` / `kpis.json` / plots are produced exactly as before.

## Note (pre-existing, not introduced here)
The two **oldest** ledger lines at the bottom of `Documents/PROGRESS.md` (the
14 Jun WP-SENSOR-1 + workspace-consolidation entries) are truncated mid-sentence —
a historical KI-004 cut from a prior session, present before this packet. Left
as-is (reconstructing lost text would be fabrication); flagged for awareness.
