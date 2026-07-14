# DIANA v2 — Internal Review Against the Published Challenge Wording
**Date:** 19 June 2026 (W2) · **Reviewer:** Claude (Friday traction session) · **For:** Lemuel review before the 30 Jun submit

This is the W2 calendar deliverable: "DIANA v2 + internal review against challenge wording." I pulled the actual 2027 challenge text and graded v1 against it, then edited v2 accordingly. Read this before the draft.

## 1 · What the challenge actually asks for (2027 wording)
"Multidomain Autonomy of Uncrewed Systems" — autonomous systems that operate and collaborate across **land, sea, air, space and cyber**. Named focus: **resilient autonomy and navigation** — navigating safely with **degraded GNSS, uncertain maps/terrain, dynamic obstacles across domains, and adversarial contestation**. €100k, 200+ test centres, 6-month accelerator from Jan 2027. Eligibility: SME registered in a NATO nation, owns/controls the tech, **TRL 4 or above**. 5-page short proposal. Deadline **3 Jul 2026, 12:00 UTC**.

## 2 · Eligibility — confirm before investing more time
| Requirement | Status | Action |
|---|---|---|
| SME registered in a NATO nation | UK is NATO ✓ — confirm NaviSyn's legal registration is current | Lemuel: 1-min confirm |
| Own / control the technology | ✓ (solo-built, no encumbrances) | none |
| **TRL 4+** | Assessed **TRL 4** (working closed loop validated in sim/lab; recompile confirmed 18 Jun). Defensible. | Lemuel: confirm you're comfortable stating TRL 4 |

If any of these fails, stop — but all three look clear.

## 3 · v1 graded against the challenge (the gap that mattered)
v1 was a strong *maritime evidence/certification* pitch but under-served two things the challenge names explicitly:

| Challenge emphasis | v1 coverage | v2 fix |
|---|---|---|
| Resilient navigation under **degraded GNSS** | absent | Added to §2 (synthetic sensors can stage GNSS degradation/denial) + §4 roadmap (GNSS-degraded scenario pack) |
| **Dynamic obstacles / contested** conditions | implicit (COLREGS only) | Made explicit — AIS/own-ship traffic, contested-traffic scenarios, CPA/TCPA |
| **Multidomain** framing | single-domain (sea) | §3 reframed: sea-domain wedge + domain-portable T&E *pattern*; added challenge-fit map |
| **Interoperability** | present | kept + elevated (open versioned bridge, autonomy-agnostic) |
| TRL / maturity proof | vague | §4 now cites concrete artifacts (18 Jun recompile, logged 5-min run, 6-DOF logging) |

Net: v2 leads with *resilient-navigation T&E* — the on-thesis hook — while keeping the MASS-Code regulatory pull as the commercial dual-use leg.

## 4 · Honesty correction applied (important — do not revert)
v1 stated the MMG coefficients "**have been cross-validated against IMO standard maneuver criteria**" and the W1 LinkedIn draft said the "**turning circle and zig-zag numbers match the model test data.**" **Neither is yet true in the repo.** `Maneuvering/.../mmg/DOLPHIN.yaml` states plainly: coefficients are Kijima–Yoshimura **empirical regression** + **[assumed] placeholders**, "Replace with PMM / free-running model / **CFD once available**," and N_r is "**tuned** for a 40 m yacht." The CFD captive-test campaign that would validate them is the in-progress work, not a finished result.

v2 therefore says: standard-method MMG model computing IMO KPIs **now**, with CFD validation **underway** — the architecture is *built to be* CFD-validated. This is still a strong, differentiated story and it is defensible under scrutiny (a grant assessor who asks "show me the CFD correlation" must not catch you out). Logged as **KI-019** so the dev/QA side keeps marketing claims and repo state in sync. The same correction is applied to the LinkedIn v2 draft.

## 5 · Residual human fills (only you can do these)
1. **§4 CFD campaign description** — tool, run count, sweep ranges, outputs, honest status. This is the single most load-bearing paragraph; an assessor will probe it.
2. **§5 team bio** — naval-arch credentials + sim-engineering background.
3. **§2 architecture diagram** — drop in a scene strip (`Cesium layout.png` / `Yachtscene.png`) or a simple bridge schematic.

## 6 · Length
v2 runs slightly long with the challenge-fit map. If the formatted PDF exceeds 5 pages, cut the map first (it's an internal aid), then tighten §2 bullets. Keep §1, §3 (multidomain), and §4 maturity intact — those carry the score.

## 7 · Path to submission
v2 (today) → your two fills + eligibility confirms (≤45 min) → next Friday (W3, 26 Jun) I do a final proof pass against this checklist → **submit 30 Jun**. Buffer holds even if a week slips.
