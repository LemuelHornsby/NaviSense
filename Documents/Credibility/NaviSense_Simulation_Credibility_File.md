# NaviSense Simulation Credibility File

**Structured after DNV-RP-0513 (Assurance of simulation models). Living document — version 0.1, 14 July 2026.**
Owner: Lemuel (NaviSyn Marine Solutions). Review cadence: every validation-tier closure (see §5) and at minimum quarterly.
Purpose: the single document handed to a class society, assessor, grant reviewer, or pilot customer who asks *"why should I trust this simulator's output?"*

---

## 1. Intended use and required confidence

NaviSense is a simulation-based **verification instrument** for small-vessel surface autonomy. Its outputs (evidence packs) support:

| Use case | Decision influenced | Required confidence (RP-0513 logic) |
|---|---|---|
| U1 Development regression testing of autonomy stacks | Engineering iteration | Low–medium |
| U2 COLREGS conformance evidence for assessor review | Input to risk assessment / approval file | Medium — with declared validity envelope |
| U3 IMO maneuvering KPI characterization | Vessel capability baseline | Medium |
| U4 Perception-stack validation (camera/radar realism) | — | **Out of scope. Not claimed.** |

Claims policy (binding): marketing and dossiers may state only what the *previous* closed validation tier proves (§5). Current permitted phrasing: "standard-method MMG dynamics; validation campaign in progress, method published."

## 2. Conceptual model

**2.1 Vessel dynamics.** Modular MMG (Maneuvering Modeling Group) formulation, 3-DOF horizontal plane (surge u, sway v, yaw r); modules: bare-hull forces, propeller, rudder, bow thruster, environment (`Maneuvering/maniobrabilidad/mmg/`, parameterized by `DOLPHIN.yaml`). Fixed-step integration; canonical run clock `t_mono`.

**2.2 Attitude and seaway.** Roll/pitch/heave are a **spectral proxy ride** driven by sea-state presets (SS0–SS6, runtime-schedulable with cross-fade), plus analytic hydrostatics for floatation. This is a visualization/low-frequency layer, **not** a wave-load force model; wave-drift forces, added resistance in waves, shallow-water and bank effects are **not modeled**.

**2.3 Sensors.** GPS/IMU derived from plant state (WGS84 geo-origin); AIS targets, radar contacts, camera frame metadata are **geometric/derived models, not validated sensor physics** (KI-027). No clutter, dropout, multipath, or weather effects yet.

**2.4 Validity envelope (declared).**

| Dimension | Valid | Flagged extrapolation |
|---|---|---|
| Vessel | DOLPHIN yacht (single hull) | any other hull until profiled |
| Speed regime | maneuvering speeds, calm-to-moderate seaway | planing, extreme sea states |
| Water | deep, unrestricted | shallow water, banks, channels |
| Maneuvers | turning circle, zig-zag, COLREGS-scale evasive | crabbing/DP precision, seakeeping loads |
| Sensors | kinematic truth + geometric derivations | any realism claim (noise, weather, clutter) |

## 3. Parameter provenance

| Coefficient group | Source | Uncertainty class | Status |
|---|---|---|---|
| Hull derivatives | Kijima–Yoshimura-type regression + assumptions; N_r tuned | High (literature-empirical) | CFD captive campaign pending (geometry v2 fix outstanding) |
| Propeller/rudder | Standard-method estimates | High | same |
| Mass/inertia/hydrostatics | Design-group hull data | Medium | document chain of custody (see Legal/) |

Rule: every vessel profile carries per-group provenance metadata (`literature / estimated / CFD / trial-identified`) consumed by the uncertainty engine (see Evidence_Pack_Templates.md).

## 4. Verification (solving the equations right) — status: STRONG

Evidence inventory (all in-repo, re-runnable): ~30 dated `verify_*` gate scripts with pass/fail exit codes and **negative controls**; run-log kinematic health gate `verify_run_kinematics.py` (K1–K8); sensor-vs-plant fidelity gate `verify_sensors_fidelity.py` (corr 1.0000, median position residual 0.18–0.43 m on real runs — internal consistency, not realism); COLREGS scorer validated both directions (compliant give-way scores COMPLIANT; held-course scores flagged); evidence-pack view/manifest integrity gate (refuses partial inputs, watermarks provenance — added after incident KI-038); one-command runner + repro doctor + headless e2e self-test; C++↔Python parity checks (e.g., wake curve). Known verification gaps: engine-clock vs sim-clock divergence in-engine (KI-012); CI not yet wired to pushes (planned Aug 2026).

## 5. Validation (solving the right equations) — status: OPEN, program committed

| Tier | Content | Acceptance criterion | Target | Status |
|---|---|---|---|---|
| V1 | Benchmark hull (KVLCC2, +1 optional) MMG replication vs published tank/free-running data | KPI comparison published openly, tolerances declared, discrepancies discussed | Sep–Oct 2026 | ☐ |
| V2 | DOLPHIN CFD captive → coefficients → before/after KPI delta | Provenance-tagged coefficient set + published case study | Q4 2026 | ☐ (CFD pending) |
| V3 | Pilot-customer full-scale trial logs → system ID → sim-vs-trial residual chapter | Residual metrics signed off by customer; commanded-vs-achieved actuation bias avoided | first pilot | ☐ |
| V4 | Cross-customer anonymized validation registry | ≥3 vessels; per-class error distributions | 2027 | ☐ |
| V5 | Third-party review (class AiP / statement of fact on methodology) + lab-co-authored method paper | Named external artifact | 2027 | ☐ |

Negative-result policy: out-of-tolerance results are published with analysis, not suppressed.

## 6. Known limitations and open items (mirror of KI ledger, assessor-facing)

Engine-time determinism in-engine (KI-012); radar/AIS/camera realism (KI-027, §2.3); no live CesiumGeoreference GPS (KI-014, scoped out); single developer/machine (supplier maturity §7); no full-scale or tank correlation data yet (§5).

## 7. Supplier maturity (honest)

Solo founder-engineer; strengths: gated daily work-packet process, KI ledger with severities, reproducibility discipline, honesty guardrail on claims (KI-019 precedent). Gaps: no independent reviewer, no CI on push (planned), bus factor 1 (mitigation: Ops continuity note; off-machine remote — KI-006).

## 8. Revision log

| Ver | Date | Change |
|---|---|---|
| 0.1 | 2026-07-14 | Initial file created from strategy-report Parts V/VI/IX |
