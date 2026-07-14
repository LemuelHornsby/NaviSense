# Epic MegaGrants — Application Draft (W3)
**Window:** opens **29 Jun 2026**, runs to ~4 Sep 2026 (per grant tracker). **Award:** up to ~$150k, **no equity**, funds open-source tools / real-time 3D / UE projects.
**Fit:** NaviSense is a UE 5.7 + Cesium open-core simulator — squarely what MegaGrants showcases (real-time 3D, open ecosystem, georeferenced worlds).
**Effort for Lemuel:** ~an afternoon inside the window. This draft fills the form fields; you paste + personalize + add links once the landing page / repo / film exist.
**Submit:** any time in the window; **no hard deadline pressure** — do it after the 11 Jul soft launch so you can link the film + landing page (stronger application). Recommended target: **week of 13 Jul**.

---

## Form fields (draft answers)

**Project name:** NaviSense — open-core marine-autonomy simulator & evidence platform

**One-line summary:** A UE5 + Cesium simulator that turns autonomy code into regulatory-grade evidence for uncrewed vessels — CFD-grounded maneuvering physics, photoreal georeferenced ports, synthetic sensors, and scored COLREGS scenarios, open at the core.

**Category:** Tools / open-source / simulation (real-time 3D).

**What you've built (current state, real):**
- Closed-loop simulation: a ~30-line Python script drives a vessel through photoreal Monaco (Cesium + Google Photorealistic 3D Tiles) in UE 5.7, with MMG standard-method maneuvering physics and 6-DOF water response.
- An in-engine turning-circle run produces IMO standard maneuver KPIs (advance, transfer, tactical diameter) with an objective health gate; a single-file HTML evidence report is generated per run.
- Synthetic sensor suite (GPS/IMU validated against ground truth; camera; scripted AIS traffic with CPA/TCPA + COLREGS encounter classification).
- Deterministic, headless, single-command runs; documented clone-to-demo setup that reproduces on a clean machine.

**What the grant enables (use of funds):**
- Harden and document the open-source community edition (public repo, quickstart, docs site, sample dataset) so a researcher reaches "vessel moving in Monaco" in under 30 minutes.
- Expand the photoreal port library beyond Monaco and improve the Cesium BYO-token environment flow.
- Improve UE5-side fidelity: water/wake VFX, vessel rendering, MovieRender Queue cinematic output for reproducible evidence films.
- (Optional, if asked for milestones) 3 milestones over 6 months: M1 community edition public; M2 second photoreal port + sample dataset; M3 cinematic evidence-film pipeline.

**Why it matters / impact:** The IMO MASS Code (in voluntary effect 1 Jul 2026) makes simulation-based evidence part of how autonomous vessels get assured. Existing tools are either enterprise-priced (out of reach for the labs and startups writing the algorithms) or research-grade with unvalidated physics. NaviSense is open-core so the people actually building marine autonomy can generate credible evidence — and it is a flagship example of UE5 + Cesium used for serious georeferenced engineering, not just visualization.

**Open-source commitment:** Community edition is open under a permissive/source-available split (Apache-2.0 for the bridge/schema/scenario format; source-available for the simulator core) — chosen on day 1, written into the first README. (Strategy §5.2.)

**Links to add before submitting (Lemuel):**
- Demo film (11 Jul soft-launch upload) — the single strongest asset; submit after it exists.
- Landing page / waitlist.
- Public repo (or a private preview link if pre-25-Aug).
- Sample evidence report (the self-contained HTML, or its PDF).

**Team:** Solo founder, NaviSyn Marine Solutions (naval architecture + simulation engineering). [Same bio as DIANA §5 — reuse.]

---
## Notes
- **Honesty (KI-019):** physics is MMG standard-method computing IMO KPIs; CFD validation is underway, not complete. Do not write "CFD-validated" in the application — write "CFD-grounded, validation underway," matching the DIANA wording.
- Overlaps cleanly with the **Cesium Ecosystem Grant** (summer 2026, $5k–$50k) — the same open-source + Cesium angle. Prep both together; they are not mutually exclusive.
- This is bridge fuel for the roadmap you already have — it funds the open-source community surface (M8/M10) you are building regardless. (Strategy §5.4 rule: never bend the roadmap to a grant.)
