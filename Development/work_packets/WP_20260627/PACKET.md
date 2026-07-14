# WP-20260627 — COLREGS conformance scoring (V&V differentiator)

**Goal:** turn the scripted-AIS encounter layer (WP-20260624) into an actual
*capability*: an automated **COLREGS conformance scorer** that, for each traffic
encounter on a logged run, asks **did the own-ship maneuver that occurred conform
to the COLREGS duty for that encounter?** and returns a per-target verdict
(COMPLIANT / NON_COMPLIANT / NOT_APPLICABLE) with the underlying rule checks and
metrics. This is the literature-standard V&V differentiator the Master Execution
Plan calls out as *"the V&V differentiator"* (§5.1, weeks 5–6) — delivered early,
headless, as the scoring/measurement half.

**Type:** pure-Python analysis layer. **NO wire / DTO / schema / C++ change, NO
recompile, no new mandatory in-engine gate.** One new module + two additive,
guarded hooks into the evidence pack. Nothing on the bridge hot path is touched.
Read-only over `state.csv` (own-ship truth) + the deterministic `ais_traffic`
model ⇒ same numbers headless as live.

## Why this packet now
- WP-20260626 (D6 HTML report) closed green (6/6 + 3/3). Of the open demo gates,
  the headless-advanceable frontier is the **D4 intelligence half** and evidence
  richness — D2 (HYDRO float-at-waterline), D5 (wake VFX), D7 (MRQ film) are all
  in-engine and need Lemuel + the GPU.
- WP-20260624 explicitly **seeds** this: its AIS layer computes the encounter +
  CPA/TCPA but only *classifies* the encounter; it never *scores* whether
  own-ship complied. The scorer is the missing rule-conformance layer.
- It is the strongest fully-sandbox-verifiable item for the **30 Jun DIANA**
  submission + the 11 Jul demo: a defensible, differentiating V&V metric a grant
  reviewer / pilot wants to see, surfaced in the same evidence pack.

## What shipped
**New**
- `python/colregs_score.py` — the scorer. `ConformanceCriteria` (documented,
  tunable thresholds with COLREGS rule citations), `score_target` / `score_run`
  (per-target `ConformanceResult` with rule checks + reasons), `summarize` /
  `conformance_to_json`, and a CLI (`python python/colregs_score.py --ais <preset>`).
  Stdlib + `math` only (no numpy), deterministic, mirrors `analyse_ais` for own
  track + field construction so the encounter classification matches that module.
- `Development/work_packets/WP_20260627/verify_20260627.py` — gates the packet.

**Edited (additive, guarded)**
- `python/build_evidence_pack.py` — after computing the AIS block it attaches
  `ais_block["conformance"] = colregs.summarize(...)` (try/except — a scoring
  failure never breaks the pack) and `_write_markdown` renders a **COLREGS
  conformance** sub-table. The IMO KPIs / health / `kpis.json` shape are otherwise
  unchanged.
- `python/evidence_html.py` — `_ais_section` renders the conformance verdicts
  (green/red pills) and the honesty footer notes that conformance scores the
  *logged* maneuver, not autonomy.

### Scoring model (COLREGS Rules 8 / 13–17)
- **Give-way** (head-on / crossing-give-way / overtaking): COMPLIANT iff the
  maneuver was **substantial** (Rule 16/8b: peak alteration ≥ 15° or ≥25% speed
  cut), **early** (Rule 8a: action began with TCPA ≥ 90 s), in the **correct
  direction** (Rule 14/15: net alteration to starboard for head-on/crossing),
  achieved a **safe distance** (Rule 8d: closest pass ≥ 200 m), and did **not
  cross ahead** of a crossing target (Rule 15).
- **Stand-on** (crossing-stand-on / being-overtaken): COMPLIANT iff course +
  speed were **held** through the hold window until close-quarters (Rule 17a-i);
  action taken only after close-quarters onset is permitted (Rule 17a-ii/b).
- **No risk-bearing encounter** (target never closes inside the alert range) ⇒
  NOT_APPLICABLE (a clear pass is not a violation).

### Run it
```
python python/colregs_score.py --ais head_on                 # latest run
python python/colregs_score.py --run-dir logs/<run> --ais crossing
python python/build_evidence_pack.py --run-dir logs/<run> --ais head_on   # pack now carries the conformance table
python run_demo.py --scenario head_on_transit --selftest      # conformance ships in the auto pack
```

## Acceptance gates
- **G_COLREGS** (this packet): `verify_20260627.py` → **6/6 gates** + **3/3
  negative controls fire**. ✅ (see result JSON)
  - **G1** a give-way vessel that alters early + substantially to **starboard** and
    opens a safe CPA → COMPLIANT (4/4 rule checks). · **G2** a give-way vessel
    holding course into a head-on → NON_COMPLIANT (Rule 16 no action / Rule 8d
    unsafe). · **G3** a stand-on vessel that **holds** → COMPLIANT, one that alters
    **early** → NON_COMPLIANT (Rule 17a-i). · **G4** scorer's decision-moment
    encounter/duty **matches `analyse_ais`** on a real run. · **G5** the evidence
    pack carries the verdict (kpis.json + HTML + EVIDENCE.md), it **equals** the
    standalone scorer (parity), and the IMO KPIs + health are **identical** to a
    no-AIS build (purely additive). · **G6** scoring a run twice is bit-identical.
  - Negative controls: **N1** a clear/opening pass is NOT_APPLICABLE, never a false
    violation · **N2** a give-way vessel that turns the **wrong way (to port)** is
    flagged on the starboard check · **N3** a tampered conformance verdict in
    `kpis.json` is **detected** by the parity comparison.

## Verified (sandbox, headless)
Evidence: `NaviSense_UE5/Saved/NaviSense_Reports/wp_20260627_result.json`
- **6/6 gates PASS, 3/3 negative controls FIRE** (real run `unreal-test-run_20260624_055244`).
- Live e2e: `run_demo --scenario head_on_transit --selftest` → DEMO COMPLETE,
  health PASS; the auto pack's COLREGS section honestly scores the held-course
  transit **NON-COMPLIANT** (give-way duty, no avoiding action).
- **Regression (current disk):** `verify_run_kinematics` **8/8**,
  `verify_sensors_fidelity` **8/8**, `verify_20260623` run_demo e2e **5/5 + 3/3**
  (26.6 s), `verify_20260624` AIS **6/6 + 3/3**, `verify_20260626` HTML report
  **6/6 + 3/3** (exercised the edited pack/HTML path).

## Lemuel — steps (≤5 min; all optional, nothing blocks)
1. `python run_demo.py --scenario head_on_transit --selftest` (no Unreal), open
   the printed `…/evidence_pack/evidence_report.html`, and read the **COLREGS
   conformance** table. The transit holds course into a give-way duty, so it is
   correctly scored NON-COMPLIANT — that is the harness working, **not** a claim
   the ship avoids traffic.
2. (Optional) `python python/colregs_score.py --run-dir logs/<run> --ais crossing`
   to score any run against another encounter; `--safe-cpa-m` tunes the safe
   distance.
3. Tell me if you want the safe-distance / early-action thresholds tuned for the
   demo audience, or the scorer wired into the listener's live `--ais` runs.

## Honesty (KI-019 family)
The scorer **measures** whether the maneuver in the log conformed; it does **not**
make own-ship avoid traffic. The demo own-ship runs a FIXED maneuvering controller
(turning-circle / zig-zag / steady transit) — autonomous COLREGS avoidance is the
week 5–6 roadmap. Where own-ship holds course into a give-way duty the verdict is
(correctly) NON-COMPLIANT. The evidence-pack section + HTML footer state this. Do
**not** present a COMPLIANT verdict on a scripted run as "NaviSense obeys COLREGS";
the deliverable is the *scoring metric*, validated both ways (G1/G2/G3).

## Demo-gate impact
- **D4 (◐, unchanged status):** the AIS/intelligence half gains a rule-conformance
  scoring metric (CPA/TCPA was data; this is the V&V verdict). Remaining for D4:
  camera (WP-14), live CesiumGeoreference, UE AIS-pawn rendering (WP-15B).
- Seeds the **week 5–6 COLREGS-scoring differentiator** (§5.1) — the metric now
  exists and is gated; the autonomy controller that makes own-ship PASS is next.

## Rollback
Delete `python/colregs_score.py` and `Development/work_packets/WP_20260627/`, then
revert the additive hooks in `python/build_evidence_pack.py` (the `import
colregs_score`, the `ais_block["conformance"]` block, the markdown sub-section) and
`python/evidence_html.py` (the `conf_html` block + the footer sentence). The
evidence pack then renders exactly as in WP-20260626.
