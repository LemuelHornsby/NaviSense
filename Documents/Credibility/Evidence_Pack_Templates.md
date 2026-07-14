# Evidence-Pack Templates — Requirements Trace & Uncertainty/Validity Statement

**Version 0.1 · 14 July 2026.** Two new mandatory sections for every evidence pack (strategy report §V.3 gaps). Implement as generated artifacts in `build_evidence_pack.py`; these templates define the schema and wording.

---

## A. Requirements-trace table (`requirements_trace.csv` + rendered section)

One row per scenario × requirement exercised. Columns:

`scenario_id, scenario_rev, mass_code_function, mass_code_chapter_ref, aros_function_mode, requirement_paraphrase, metric, acceptance_criterion, result, verdict, evidence_ref, validity_flag`

Worked example rows:

| scenario_id | MASS function | AROS | requirement paraphrase | metric | acceptance | result | verdict | evidence_ref |
|---|---|---|---|---|---|---|---|---|
| imo_turning_circle | Safety of navigation — maneuvering capability | NAV | Vessel meets IMO maneuvering criteria in defined operational context | Advance/Lpp; DT/Lpp | ≤4.5 / ≤5.0 (MSC.137(76)) | 4.09 / 4.16 | PASS | run 163148 pack §KPI |
| colregs_head_on | Safety of navigation — collision avoidance | NAV(SA) | Give-way behavior per Rules 8/14 within encounter envelope | maneuver onset; CPA floor; side of pass | onset ≤ T_a; CPA ≥ X m; starboard | [fill] | COMPLIANT / MARGINAL / NON-COMPLIANT | run [id] |
| building_sea_transit | Operational context — environmental envelope | NAV | Function demonstrated across declared sea-state schedule | SS transitions logged; heave RMS profile | schedule executed; health K1–K8 green | 6 transitions, 0.14→1.33 m | PASS | run 163148 |

Rules: `verdict` vocabulary is fixed (PASS/FAIL for KPIs; COMPLIANT/MARGINAL/NON-COMPLIANT for COLREGS); `validity_flag` = IN-ENVELOPE or EXTRAPOLATION (auto-set from Credibility File §2.4); a row with EXTRAPOLATION can never carry an unqualified PASS.

---

## B. Uncertainty & validity statement (rendered section, one per pack)

**B.1 Model identification.** navisense-core version; vessel profile + revision; coefficient provenance class per group (literature / estimated / CFD / trial-identified — from profile metadata); scenario set + revisions; seed(s).

**B.2 Validity declaration.** "All results in this pack were produced within the declared validity envelope of Credibility File v[n] §2.4, except rows flagged EXTRAPOLATION in the requirements trace." List each extrapolation with one-line justification.

**B.3 Uncertainty bands (coefficient perturbation).** Method: re-run scenario battery with coefficients sampled within provenance-dependent bounds (defaults: literature ±15%, estimated ±20%, CFD ±7%, trial-identified ±4% — revise as V-tiers close), plus sea-state/traffic-timing randomization where relevant. Report per KPI:

| KPI | Nominal | Band (5–95%) | Verdict stability |
|---|---|---|---|
| e.g. DT/Lpp | 4.16 | [4.02, 4.31] | PASS stable |
| e.g. CPA (head_on) | [x] m | [lo, hi] | **MARGINAL if verdict flips within band** |

**B.4 Verdict downgrade rule (binding).** Any COLREGS verdict that changes within its uncertainty band is reported MARGINAL, never COMPLIANT. Any KPI whose band crosses its acceptance threshold is reported PASS(unstable) and highlighted.

**B.5 Exclusions.** Standing text: "Sensor streams are geometric/derived models, not validated sensor physics; no perception-realism inference is supported. No wave-load structural or seakeeping conclusions are supported. This pack is verification evidence for review by the applicant's assessor; it is not an approval, certification, or acceptance."

**B.6 Sign-off block.** Prepared by / date / navisense-core version / Credibility File version / pack integrity hash (from manifest).

---

Implementation notes: B.3 is a scenario-matrix sweep — the existing runner already supports batch scenarios; add a `--perturb coefficients` mode that reads provenance metadata from the vessel profile. Wire A and B into `build_evidence_pack.py` behind a `--regulatory` flag first, default-on once stable. Gate with a new `verify_` script + negative control (a pack missing either section must FAIL).
