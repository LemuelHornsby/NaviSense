# DIANA 2027 — Short Proposal Draft v3 (submission-prep)
## Challenge: Multidomain Autonomy of Uncrewed Systems
**Applicant:** NaviSyn Marine Solutions · **Contact:** Lemuel · navisynmarinesolutions@gmail.com
**Deadline:** 3 July 2026, **12:00 UTC** — **submit by Tue 30 June (buffer)**
**Format:** 5 pages max · English · **Eligibility floor: TRL 4+**, SME registered in a NATO nation, own/control the technology
**Status:** Draft **v3** (26 Jun 2026, W3). Carries v2 forward and **upgrades the maturity case with real artifacts logged 21–26 Jun** — several capabilities crossed from "in build" to "working today" this week (turning-circle IMO KPIs from an in-engine run, AIS/COLREGS encounter analysis, validated GPS/IMU, single-file evidence report, clean-machine repro). Two human fills still remain (CFD campaign §4, team bio §5) — both marked **[FILL IN]**. Honesty flags from `DIANA_v2_internal_review.md` are preserved; see also `DIANA_submission_checklist.md`.

---

## 1 · Problem (1/2 page)

Uncrewed surface vessels (USVs) and autonomous ships must be assured to navigate safely in exactly the conditions that physical sea trials can least afford to stage repeatably: degraded or denied GNSS, dynamic and uncooperative traffic, and contested or uncertain environments. Sea trials are scarce, weather-bound, internationally fragmented, and impossible to repeat identically — yet both the commercial and defence assurance pathways now demand *repeatable, scenario-based evidence* that an autonomy stack behaves correctly across these conditions.

On the commercial side, the IMO MASS Code (voluntary effect 1 July 2026) and its Experience-Building Phase establish simulation-based evidence as a required component of any risk-based assurance case. On the defence side, USV test & evaluation needs the same thing — repeatable scenario rehearsal, sensor-stack validation, and rules-of-the-road conformance under contested conditions — before and between scarce range slots.

The tools that could close this gap are split badly for the innovation base actually writing the algorithms: enterprise platforms (Applied Intuition) are priced beyond startups and labs (<EUR 100k/yr is not served), while research-grade simulators carry unvalidated physics, no scenario scoring, and no assessor-readable evidence output. The organisations with the most to contribute — autonomy SMEs, university marine-robotics labs, USV builders — have no affordable, validated tool to generate the evidence that class societies, flag states, and test centres are beginning to require.

---

## 2 · Solution (1 1/2 pages)

**NaviSense** is an open-core simulation and evidence platform for maritime autonomy development and test & evaluation. It is a working system today, not a concept. It delivers:

- **Standard-method maneuvering physics, on a path to CFD validation.** Vessel dynamics use the MMG standard method (Yasukawa–Yoshimura 2015, 3-DOF + bow thruster) and compute the IMO standard manoeuvre KPIs — turning-circle advance/transfer/tactical diameter and zig-zag overshoot angles — from a documented, version-controlled coefficient set. The present coefficients are derived from established empirical regression (Kijima–Yoshimura); a CFD captive-test campaign is underway to replace them with vessel-specific validated values [FILL IN §4]. The architectural point is decisive: physics is an auditable, replaceable module — *"our turning circle matches our CFD"* is a sentence the platform is built to back with data, which no black-box game-engine demo can claim.

- **Photoreal georeferenced environments.** Real port geometry via Cesium + Google Photorealistic 3D Tiles (Monaco / Port Hercule live), rendered in Unreal Engine 5.7 with dynamic water and a deterministic, replayable sea-state field (10 presets) that drives 6-DOF vessel response (roll, pitch, heave) via an analytic hydrostatics model. The world is navigable at true WGS-84 coordinates — GPS output is real lat/lon matching chart position.

- **Synthetic sensor suite, validated against ground truth.** GPS (true lat/lon via geo-origin), IMU (heading, yaw-rate, accelerations), camera frames to disk, and scripted AIS traffic targets. The GPS/IMU bundle is now **objectively validated against the simulator's own ground-truth vessel state** (speed/yaw-rate/heading correlation 1.0000, GPS position median residual 0.18–0.43 m across two real runs). Because every sensor is synthetic and scripted, the platform can stage precisely the conditions the challenge names — **GNSS degradation and denial**, **uncertain position fixes**, **dynamic obstacles** — repeatably, with ground truth, at zero range cost.

- **Scenario runner, traffic analysis, and evidence output — working now.** Scenarios run headless from a **single command**; a run auto-produces a **self-contained evidence report** (one HTML file, plots embedded, emailable to an assessor) plus machine-readable logs. Scripted **AIS traffic with CPA/TCPA and COLREGS encounter classification** (Rules 13–15: head-on / crossing / overtaking, with give-way / stand-on duty) is generated and written into the evidence pack today. The remaining step — quantitative **rule-conformance scoring** (a pass/fail grade per encounter) and the full 10-encounter pack — is the next build milestone (community-alpha timeframe).

- **Open, autonomy-agnostic control interface.** Any autonomy stack connects via a ~30-line Python bridge over a documented, versioned JSON/TCP schema. No proprietary SDK, no lock-in — the interoperability the challenge prizes is the default.

*[INSERT: architecture / scene strip — recommended: `Cesium layout.png` (photoreal georeferenced Monaco in UE5+Cesium) + `Yachtscene.png` (the DOLPHIN under way) + `turning_circle.png` (IMO KPI plot from the evidence pack). See `DIANA_submission_checklist.md` step 3.]*

**Headless, deterministic, repeatable.** Runs use a fixed-step sim clock and emit machine-readable logs (state, sensors, events, manifest) per run, and the whole headless pipeline has a **clean-machine readiness check + documented clone-to-demo setup** that reproduces the same IMO result on a fresh box — i.e. the platform already behaves as a test & evaluation substrate, not a viewer. **DIANA test-centre fit:** NaviSense integrates as the synthetic-environment / scenario layer at a maritime T&E centre — a USV developer runs the full campaign in simulation before arriving at the physical facility, cutting range time and producing pre-validated, auditable evidence packages.

---

## 3 · Multidomain & dual-use logic (3/4 page)

The challenge seeks autonomy that operates and collaborates across domains under degraded and contested conditions. NaviSense addresses this **at the sea-surface domain** with an architecture that is deliberately domain-portable: an autonomy-agnostic bridge, a scenario runner, a synthetic sensor model with controllable degradation, and rule-conformance scoring are a *test & evaluation pattern*, not maritime-specific plumbing. The maritime wedge is where the regulatory pull (MASS Code) and the founder's naval-architecture depth make it credible first; the same substrate extends to other uncrewed-system domains a test centre evaluates.

The dual-use logic is structural, not bolted on:

**Commercial MASS developers** use NaviSense to generate COLREGS encounter evidence and IMO manoeuvre documentation for the MASS Code EBP pathway, in a report designed to be read by class-society assessors (DNV, Lloyd's, BV) in their own vocabulary.

**Defence USV T&E** uses the identical platform for scenario rehearsal, perception-stack validation against labelled synthetic data, rules-of-the-road conformance testing, and — most directly on-challenge — **resilient-navigation evaluation under degraded GNSS and contested, dynamic-traffic conditions**. COLREGS is COLREGS; IMO criteria apply to any displacement hull; degraded-GNSS behaviour matters to both markets. No architectural bifurcation is required — the same packaged build, the same scenario YAML, the same evidence output serve both.

This places NaviSense precisely at the challenge's intersection: a dual-use synthetic T&E environment for uncrewed-system autonomy, built by a naval-architecture + simulation-engineering founder, priced and open-licensed to reach the innovation base DIANA exists to accelerate.

---

## 4 · Maturity & roadmap (3/4 page)

**Current maturity (TRL 4 — technology validated in a laboratory/simulation environment).** Concrete, logged artifacts as of 26 Jun 2026:

- **Closed loop working in-engine.** A Python autopilot drives the vessel through photoreal Monaco; a logged in-engine turning-circle run (21 Jun, `unreal-test-run_20260621_163148`) executed a continuous 493 deg turn with an objective kinematic-health gate passing 8/8, and the evidence pack computed the IMO turning-circle KPIs: **Advance 155.3 m (A/Lpp 4.09, IMO limit 4.5 — PASS)** and **Tactical diameter 158.2 m (DT/Lpp 4.16, IMO limit 5.0 — PASS)**. *(These are the geometry of the simulated manoeuvre computed by the standard-method MMG model; the coefficient set is not yet CFD-validated — see the CFD campaign below.)*
- **Sensors validated against ground truth.** GPS/IMU output cross-checked against the authoritative vessel state on two real runs — speed/yaw-rate/heading correlation 1.0000, GPS position median residual 0.18–0.43 m, WGS-84 geo-origin consistent (Monaco, 43.7350 N / 7.4250 E).
- **Traffic & rules analysis.** Scripted AIS targets with analytic CPA/TCPA and COLREGS Rule 13–15 encounter classification, written into the evidence pack (e.g. a head-on encounter correctly flags own-ship give-way duty with a CPA alert).
- **Deterministic sea states.** A replayable wave field sweeps >=3 sea states within one run (in-engine 21 Jun: SS1->SS6, heave RMS 0.14 -> 1.33 m), driving 6-DOF response via an analytic hydrostatics model.
- **Repeatable T&E substrate.** Single-command run -> self-contained HTML evidence report; fixed-step clock; clean-machine readiness doctor + documented clone-to-demo path; the headless pipeline reproduces the same IMO result (DT 158.2 m) on a fresh environment.
- **Engineering backbone.** C++ module architecture (Bridge, Core, Vessel, Sensors) compiling (full rebuild confirmed 22 Jun); open, versioned Python/JSON bridge; Python + in-engine test suites with objective gates run on every change.
- **CFD captive-test campaign underpinning the validated coefficient set:** **[FILL IN — your real campaign: tool (e.g. STAR-CCM+), number of runs, rudder/propeller sweep ranges, outputs feeding the MMG set, current status. Do not overstate completion. This is the single most load-bearing paragraph — an assessor will probe it.]**

**Target — 11 July 2026:** public 30-day demo film — Python autopilot drives the vessel through photoreal Monaco in selectable sea states with live sensor output, plus the single-file evidence report, reproducible from one command. First public evidence of the working platform.

**EUR 100k phase (6 months post-award):**
- Validated vessel library expansion (2 additional hulls: coastal-patrol USV + offshore supply vessel) via CFD captive tests.
- **Resilient-navigation scenario packs:** GNSS-degraded / denied and contested-traffic encounters with scored conformance — directly serving the challenge's resilient-autonomy theme.
- Sensor-model hardening: camera-label quality validation; IMU noise characterisation; GNSS-degradation models.
- Test-centre integration pilot: NaviSense as the synthetic scenario layer at one DIANA facility (centre TBD via the network); evidence-format co-development with a class-society contact.
- Community open-source launch: public repo, docs, Discord, sample dataset.

**Measurable milestones:** M1 (month 2) — 2 validated vessel profiles + COLREGS-10 pack + a GNSS-degraded scenario pack public (community alpha); M2 (month 4) — test-centre integration running at >=1 DIANA facility, evidence format reviewed by a class-society contact; M3 (month 6) — >=3 external teams using NaviSense for documented T&E or research; Eurostars consortium formed.

---

## 5 · Team & edge (1/2 page)

**[FILL IN — only you have this. Suggested structure:]**

*Founder: [name], NaviSyn Marine Solutions.*
- Naval architecture: [degree, institution, year] — hydrodynamics, CFD, vessel manoeuvring theory.
- Simulation engineering: [prior Unity simulator, Python autonomy stack, UE5 development].
- AI-automated development: a daily scheduled AI build system lets one part-time founder ship at small-team pace — a structural cost/velocity advantage, not a dependency.
- [Advisory or collaborative relationships, if any.]

**Why a solo deep-tech founder is fundable here:** near-zero burn (automated development, no payroll); a *working product*, not a proposal; a niche the primes structurally ignore (too small for Applied Intuition, too technical for training-sim vendors); and a regulatory clock (MASS Code EBP 2026–2030) that rewards credible evidence tooling now. DIANA funding accelerates a roadmap already in motion.

**Advisory plan (Phase 1):** recruit one class-society innovation contact (DNV/BV) and one DIANA test-centre technical lead as unpaid advisors — both reachable via the DIANA network post-award.

---

## 6 · Budget & milestones (1/2 page)

**Total request: EUR 100,000 / 6 months**

| Category | Amount | Rationale |
|---|---|---|
| Engineering (platform + vessel models) | EUR 40,000 (40%) | Founder time at market rate, 6 months part-time; vessel CFD expansion |
| Validation campaign | EUR 25,000 (25%) | Independent CFD cross-check / model-test correlation for 2 new hulls; dataset benchmarking |
| Test-centre integration pilot | EUR 20,000 (20%) | Travel + integration engineering at a DIANA facility; evidence-format co-development |
| Compliance, dissemination, IP | EUR 15,000 (15%) | Open-core licensing, export-control review; workshop dissemination; documentation |

**Milestones:** M1 month 2 / M2 month 4 / M3 month 6 (as §4).
**Phase 2 ambition (if invited):** up to EUR 300k — cloud scenario farm (scale-out T&E), ROS2 bridge, additional ports, first defence-program engagement via the DIANA test-centre network.

---

## Challenge-fit map (internal aid — trim if over 5 pages)

| Challenge area (2027 wording) | NaviSense capability | Evidence (repo) |
|---|---|---|
| Resilient autonomy & navigation | Scriptable GNSS degradation/denial + uncertain-fix testing with ground truth | sensor bundle validated vs plant (22 Jun) |
| Dynamic obstacles | AIS / own-ship scripted traffic; COLREGS encounters; CPA/TCPA | evidence pack AIS section (24 Jun) |
| Adversarial / contested conditions | Repeatable contested-traffic scenarios; deterministic, auditable replays | fixed-step clock + manifest per run |
| Interoperability | Open, versioned JSON/TCP bridge; autonomy-agnostic; YAML scenarios | bridge schema v1.3 |
| Multidomain T&E pattern | Sensor-sim + scenario-runner + scoring substrate, sea-domain first | one-command runner (23 Jun) |
| Test-centre integration | Headless single-command runs; machine-readable + emailable evidence | HTML evidence report (26 Jun); repro doctor (25 Jun) |

*Vocabulary alignment: "test & evaluation", "assurance", "interoperability", "dual-use synthetic environment", "resilient navigation", "degraded GNSS", "repeatable simulation evidence", "TRL 4+".*

*[BEFORE SUBMITTING: §4 CFD campaign description; §5 team bio; §2 architecture/scene strip. Everything else is review-ready. Read `DIANA_v2_internal_review.md` (honesty rationale) and `DIANA_submission_checklist.md` (step-by-step) first.]*
