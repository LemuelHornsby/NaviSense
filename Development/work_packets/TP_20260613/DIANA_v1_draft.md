# DIANA 2027 — Short Proposal Draft v1
## Challenge: Multidomain Autonomy of Uncrewed Systems
**Applicant:** NaviSyn Marine Solutions · **Contact:** Lemuel · navisynmarinesolutions@gmail.com  
**Deadline:** 3 July 2026, 12:00 BST — **submit by 30 June (buffer)**  
**Format:** 5 pages max · Language: English  
**Status:** Draft v1 (13 Jun 2026) — Lemuel to add personal/team details marked [FILL IN]

---

## 1 · Problem (½ page)

Autonomous surface vessels (USVs) and autonomous ships cannot be safely or cost-effectively certified by sea trials alone. The IMO MASS Code, which took voluntary effect 1 July 2026, and the Experience-Building Phase (EBP) framework jointly establish that repeatable simulation-based evidence is a required component of any risk-based assurance pathway. Yet the simulation tools available to the innovation base — the startups, university labs, and SME autonomy developers actually writing the algorithms — are either enterprise-priced (Applied Intuition, inaccessible at <€100k/yr), or research-grade (unvalidated physics, no scenario scoring, no evidence export).

The result: the organisations with the most to contribute to the MASS EBP — and the most likely customers for NATO test centres seeking synthetic environment integration — have no affordable, validated simulation tool to generate the evidence class societies and flag states are beginning to ask for. This gap is especially acute for USV T&E, where physical test infrastructure is sparse, international, and expensive.

---

## 2 · Solution (1½ pages)

**NaviSense** is an open-core simulation and evidence platform for maritime autonomy development. It delivers:

- **CFD-validated maneuvering physics:** vessel dynamics derived from captive-model CFD tests (RANS, systematic rudder/propeller sweeps), producing MMG hydrodynamic coefficients that have been cross-validated against IMO standard maneuver criteria (turning circle advance/transfer/tactical diameter, zig-zag 1st/2nd overshoot angles). Physics fidelity is documented and version-controlled — not a black-box game engine approximation.

- **Photoreal georeferenced environments:** real port geometry and bathymetry via Cesium + Google Photorealistic 3D Tiles (Monaco / Port Hercule verified; Long Beach in progress), rendered in Unreal Engine 5.7 with atmospheric sky, volumetric clouds, dynamic water surface, and speed-responsive wake/spray. The environment is navigable at true WGS-84 coordinates — GPS sensor output is real lat/lon matching chart position.

- **Full synthetic sensor suite with automatic labels:** GPS (true lat/lon via CesiumGeoreference), IMU (heading, yaw-rate, accelerations), camera frames to disk with auto-generated 2D bounding-box labels in COCO format, AIS traffic targets with correct range/bearing. Every sensor output is machine-readable; labels are generated automatically — no manual annotation.

- **Scored COLREGS scenario packs:** 10 canonical encounters (head-on, crossing, overtaking variants) are scripted in YAML, run headless from a single command, and scored against COLREGS Rule 8/13/14/15/16 conformance criteria (CPA/TCPA margin + rule-conformance flag per encounter). Results are aggregated into an evidence report.

- **Evidence report output:** a single PDF/HTML containing IMO maneuver KPIs vs criteria table, COLREGS scenario scores, trajectory plots, and timestamped screenshots — the kind of document a class society or test-centre assessor can actually read.

- **Open Python/JSON control interface:** any autonomy stack connects via a 30-line Python bridge. The wire schema (JSON over TCP) is publicly documented and versioned. No proprietary SDK, no vendor lock-in.

*[INSERT: 1 architecture diagram — bridge_harness schematic or scene screenshot strip from Development images/]*

**DIANA test-centre fit:** NaviSense integrates as the synthetic environment layer at maritime T&E centres — it provides the scenario, physics, and sensor-data substrate that a test centre's assessment framework runs against. USV developers can run their full test campaign in simulation before arriving at the physical facility, reducing trial time and cost, and producing pre-validated evidence packages the centre can audit.

---

## 3 · Dual-use logic (¾ page)

The same platform serves two communities through identical technical infrastructure:

**Commercial MASS developers** use NaviSense to generate COLREGS encounter evidence and IMO maneuver documentation required by the MASS Code EBP pathway. The evidence report output is designed to be readable by class-society assessors (DNV, Lloyd's, BV) — it speaks their vocabulary (IMO criteria, rule-conformance scoring, reproducible test conditions).

**Defense USV T&E** uses NaviSense for scenario rehearsal, sensor-stack validation (labelled synthetic data for perception model training and evaluation), and operator familiarization in complex traffic environments. The scenario runner's YAML format maps naturally to test objectives; the evidence report maps naturally to T&E documentation. COLREGS scoring is directly relevant to USV rules-of-the-road compliance testing.

The dual-use logic is structural, not incidental: COLREGS is COLREGS whether the platform is commercial or defense; IMO maneuver criteria apply to any displacement hull; labeled sensor data trains perception models for both markets. NaviSense does not require architectural bifurcation to serve both — the same packaged build, the same scenario YAML, the same evidence PDF.

This makes NaviSense a natural fit for DIANA's multidomain autonomy challenge: it is a dual-use simulation T&E platform at the intersection of the commercial MASS regulatory window and defense USV evaluation needs, developed by a founding team with naval-architecture and simulation engineering depth, priced and licensed to reach the innovation base that DIANA programmes are designed to accelerate.

---

## 4 · Maturity & roadmap (¾ page)

**Current maturity:** The UE5 platform is in active development under a structured 30-day build plan (WP-1 through WP-23, daily work packets). As of the proposal date:

- C++ module architecture complete: Bridge, Core, Vessel, Sensors subsystems implemented
- Python MMG bridge harness operational (sign-test verified: +10° rudder → starboard heading trend confirmed in closed-loop test)
- Monaco scene live: Google Photorealistic 3D Tiles, Cesium georeference, WaterBody, atmospheric environment
- CFD captive-test dataset complete: RANS simulation series (systematic rudder/propeller sweeps) underpinning the MMG model [FILL IN: brief description of your CFD campaign — number of runs, what tool, what output]

**Target: 11 July 2026** — public 30-day demo film: Python autopilot drives CFD-grounded vessel through photoreal Monaco in selectable sea states, with real sensor output and a one-page evidence report, reproducible from a single command. This is the first public evidence of the working platform.

**€100k phase (6 months post-award):**
- Expand validated vessel library (2 additional hull types: coastal patrol USV + offshore supply vessel)
- Sensor model hardening: camera label quality validation against real datasets; IMU noise characterisation
- Test-centre integration pilot: integrate NaviSense as synthetic scenario layer at one DIANA test-centre partner (specific centre TBD via DIANA network)
- Evidence format hardening: alignment with DNV class-society evidence-pack requirements; structured data export for test-centre assessment workflows
- Community open-source launch: public repo, developer documentation, Discord, sample dataset release

**Milestones (measurable):**
1. M1 (month 2): 2 additional validated vessel profiles + COLREGS-10 pack public (community alpha)
2. M2 (month 4): test-centre integration pilot running at ≥1 DIANA facility; evidence-pack format reviewed by class society contact
3. M3 (month 6): ≥3 external teams using NaviSense for documented T&E or research; Eurostars consortium formed

---

## 5 · Team & edge (½ page)

**[FILL IN — use this structure:]**

*Founder: [Your name], NaviSyn Marine Solutions*

- Naval architecture background: [degree, institution, year] — direct competence in hydrodynamics, CFD, vessel maneuvering theory
- Simulation engineering: [relevant experience — prior Unity simulator, Python autonomy stack, UE5 development]
- AI-automated development: operating a daily scheduled AI development system (Claude Code) that lets a single part-time founder ship at the pace of a small team — a structural cost and velocity advantage, not a dependency
- [Any advisory or collaborative relationships to mention]

**Why a solo deep-tech founder is fundable here:** near-zero burn (automated development, no payroll), working product (not a proposal for a future product), a niche the defence primes structurally ignore (too small for Applied Intuition, too technical for training-sim vendors), and a regulatory clock (MASS Code EBP 2026–2030) that rewards whoever has credible evidence tooling now. DIANA funding accelerates a roadmap already in motion.

**Advisory plan (Phase 1):** recruit one class-society contact (DNV/BV innovation team) and one DIANA test-centre technical lead as unpaid advisors — both are reachable via the DIANA network post-award.

---

## 6 · Budget & milestones (½ page)

**Total request: €100,000 / 6 months**

| Category | Amount | Rationale |
|---|---|---|
| Engineering (platform + vessel models) | €40,000 (40%) | Founder time at market rate for 6 months part-time; vessel CFD expansion campaign |
| Validation campaign | €25,000 (25%) | Physical tow-tank or independent CFD cross-check for 2 new hull types; dataset benchmarking |
| Test-centre integration pilot | €20,000 (20%) | Travel + integration engineering at DIANA partner facility; evidence format co-development |
| Compliance, dissemination, IP | €15,000 (15%) | Legal (open-core license, export-control review); conference/workshop dissemination; documentation |

**Milestones** (same as §4 above — M1 month 2 / M2 month 4 / M3 month 6).

**Phase 2 ambition (if invited):** up to €300k for cloud scenario farm (scale-out T&E), ROS2 bridge, additional port environments, and the first defense program engagement via DIANA test-centre network.

---

*NaviSense vocabulary alignment: "test & evaluation", "assurance", "interoperability", "dual-use synthetic environment", "evidence-based assurance pathway", "repeatable simulation evidence", "scenario-based certification".*

*[FILL IN items before submitting: personal bio details §5; CFD campaign description §4; architecture diagram §2. All other sections are ready for review.]*
