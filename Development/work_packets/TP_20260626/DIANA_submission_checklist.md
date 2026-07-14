# DIANA — Final Proof Pass + Submission Checklist (W3)
**This is the W3 gate: "DIANA submitted."** Target submit **Tue 30 Jun**; hard deadline **3 Jul 12:00 UTC**.
**Reviewer:** Claude (Friday session, 26 Jun) · **Owner of remaining actions:** Lemuel.

## A · Final proof pass on the draft (done this session)
Graded `DIANA_v3_final.md` against the v2 internal-review checklist and the published challenge wording:

| Check | Verdict |
|---|---|
| Leads with resilient-navigation T&E (degraded GNSS, dynamic obstacles, contested) | OK — §1 problem + §3 + §2 sensor bullet |
| Multidomain framing (sea wedge within a domain-portable T&E pattern) | OK — §3 + challenge-fit map |
| Maturity proven with concrete, dated artifacts (TRL 4 defensible) | OK — §4 now cites the 21–26 Jun logged runs (IMO KPIs, validated sensors, AIS/COLREGS, repro) |
| Honesty: no unproven "CFD-validated / matches model tests" claim (KI-019) | OK — coefficients = standard-method/empirical, CFD "underway"; IMO PASS labelled as simulated-manoeuvre geometry |
| Interoperability emphasised | OK — open versioned bridge, YAML scenarios |
| Budget = EUR 100k, 4 lines, 3 milestones | OK — §6 |
| Vocabulary (T&E, assurance, dual-use, resilient navigation) | OK — map footer |
| Within 5 pages once formatted | RISK — see step 4; cut the challenge-fit map first if long |

**What changed v2 -> v3 (all honest upgrades from real artifacts logged this week):** turning-circle IMO KPIs now come from an actual in-engine run; AIS/COLREGS encounter analysis moved from "next milestone" to "working now"; GPS/IMU "validated against ground truth" added; single-file evidence report + clean-machine repro added to the T&E-substrate claim. COLREGS *scoring* (the pass/fail grade) is still correctly described as the next milestone, not done.

## B · Your residual actions (the only things blocking submit) — approx 45–60 min
1. **§4 — CFD captive-test paragraph [FILL IN].** Tool (e.g. STAR-CCM+), run count, rudder/propeller sweep ranges, outputs feeding the MMG set, honest current status. The load-bearing paragraph. Do not overstate completion — an assessor will probe it. *(There is a separate StarCCM+ captive-test sub-project under Model tests/CFD/ — pull the real status from there.)*
2. **§5 — team bio [FILL IN].** Naval-architecture credentials (degree/institution/year) + sim-engineering background + any advisory relationships.
3. **Eligibility confirms (1 min each):** (a) NaviSyn is a currently-registered SME in a NATO nation (UK = NATO, confirm registration current); (b) you own/control the tech (yes); (c) you are comfortable stating **TRL 4**.

## C · Assembly + submit (approx 30 min)
4. **Insert visuals + export to <=5-page PDF.** Recommended strip for §2:
   - `Development/Development images/Cesium layout.png` — photoreal georeferenced Monaco (UE5 + Google 3D Tiles). The "real ports" proof.
   - `Development/Development images/Yachtscene.png` — the DOLPHIN under way on dynamic water. The "working vessel" proof.
   - `logs/unreal-test-run_20260624_055244/evidence_pack/turning_circle.png` — the IMO turning-circle plot. The "measured manoeuvre" proof.
   If the formatted PDF exceeds 5 pages: cut the challenge-fit map (internal aid) first, then tighten §2 bullets. Keep §1, §3, §4 intact — they carry the score.
5. **Register on the DIANA portal** (diana.nato.int -> 2027 challenges -> "Multidomain Autonomy of Uncrewed Systems"). Allow time — first-time registration + upload is the usual day-of trap.
6. **Submit by Tue 30 Jun.** Then tell me the submission date so PROGRESS.md T5 and PIPELINE.md go from "ready" to "submitted."

## D · Optional strengthener (only if time)
- A one-page PDF of the **HTML evidence report** (`logs/unreal-test-run_20260624_055244/evidence_pack/evidence_report.html`) attached or linked as the "sample evidence package" — it is exactly the assessor-readable artifact §2/§4 describe. Self-contained, so it travels.

**Bottom line:** the proposal is review-ready; the only true blockers are your two fills + three eligibility confirms. Everything else is assembly. Buffer (30 Jun vs 3 Jul) holds even if a day slips.
