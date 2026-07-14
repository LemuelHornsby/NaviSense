# Regulatory Mapping Annex — NaviSense evidence artifacts ↔ IMO MASS Code ↔ DNV AROS

**Version 0.1 · 14 July 2026 · Ships inside every evidence pack as `regulatory_mapping.md`.**
Vocabulary rule: use the Code's own terms everywhere — *operational context*, *function*, *functional requirement*, *expected performance*, *verification evidence*.
References: IMO MASS Code, res. MSC.595(111), voluntary effect 1 Jul 2026; Experience-Building Phase framed at MSC 112 (Dec 2026); DNV AROS notations (eff. Jan 2025) on DNV-CG-0264; DNV-RP-0513.

## 1. Mapping table

| # | NaviSense artifact | Status | MASS Code touchpoint | DNV AROS / CG-0264 touchpoint |
|---|---|---|---|---|
| 1 | Scenario definition YAML (vessel, environment, traffic, sea-state schedule) | EXISTS | Operational context / ODD; risk-assessment scenario basis | ConOps description; NAV operational envelope |
| 2 | COLREGS encounter matrix + conformance scoring (Rules 8, 13–17; CPA/TCPA) | EXISTS | Safety of navigation — functional requirements & expected performance | AROS-NAV mode qualification (DS/SA); collision-avoidance testing |
| 3 | IMO maneuvering KPIs (turning circle, zig-zag vs MSC.137(76)) | EXISTS | System design / safety-of-navigation capability baseline | Vessel maneuvering characterization |
| 4 | Run logs, canonical clock, health gates K1–K8, integrity manifest | EXISTS | Software principles; management of safe operations; auditability | Simulation-testing traceability; RP-0513 verification evidence |
| 5 | Evidence pack + single-file HTML report (provenance, verdicts) | EXISTS | Approval-process documentation; EBP data-submission candidate | Assessor-facing test report; AiP dossier input |
| 6 | `sensor.v1` stream (GPS/IMU/AIS/radar/camera) + fidelity gates | EXISTS | Connectivity; remote-ops situational awareness (future) | ROC data-quality demonstration (future) |
| 7 | Repro doctor + one-command runner + negative controls | EXISTS | Software principles (quality, reproducibility) | RP-0513 supplier-maturity signal |
| 8 | Requirements-trace table (scenario ↔ functional requirement) | **NEW — template in Evidence_Pack_Templates.md** | Goal-based Part III traceability | Function-by-function qualification evidence |
| 9 | Uncertainty & validity statement per KPI | **NEW — template in Evidence_Pack_Templates.md** | Risk-assessment confidence | RP-0513 required-confidence justification |
| 10 | Sim-vs-real residual chapter (per pilot) | PLANNED (V3) | EBP experience data; risk-assessment confidence | RP-0513 validation-against-reality |

## 2. How to cite this mapping in a customer dossier

State per chapter: "This section provides *verification evidence* toward [function] under the applicant's *operational context* defined in §[x]; simulator credibility per the NaviSense Simulation Credibility File v[n]." Never state or imply approval, certification, or acceptance — those belong to the administration/class alone. Permitted: "MASS-Code-mapped", "aligned to", "structured for assessor review".

## 3. National-pathway slot (fill per customer — usually the real gate)

| Customer | Governing document (their answer, discovery Q3) | Mapping owner | Status |
|---|---|---|---|
| [pilot 1] | e.g. UK MCA workboat code / MGN MASS guidance / NO sandbox | — | ☐ |

## 4. Watch triggers that force a revision

MSC 112 (Dec 2026) EBP framework + data formats → align evidence-pack export. AROS/CG-0264 revisions → re-check table col. 5. Any customer flag/class feedback → new row or correction. Log changes below.

## 5. Revision log

| Ver | Date | Change |
|---|---|---|
| 0.1 | 2026-07-14 | Initial annex from strategy report §V.3 |
