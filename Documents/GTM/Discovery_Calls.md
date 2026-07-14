# Discovery Calls — Script, Log, and Rules

**Version 0.1 · 14 July 2026.** Target: 10 calls by 15 Aug, 25 by mid-Oct (strategy report §XI). Log every call in `discovery_call_log.csv` (same folder) within 24 h, verbatim quotes preferred. Success metric = filled matrix, not sold product.

## The script (15 minutes, five questions)

1. "Walk me through the last time you had to show a regulator, class surveyor, insurer, or customer that your vessel/stack behaves safely — what did you actually hand over?"
2. "What does your team do today when the autonomy software changes — what gets re-tested, and how long does it take?"
3. "Which document governs you first: national workboat/MASS guidance, class rules, the IMO MASS Code, something else?"
4. "If a tool turned a scenario battery into an assessor-ready evidence dossier overnight, what would that be worth per project — €2k, €10k, €30k — and whose budget pays: R&D, compliance, or the project?"
5. "Who else should I talk to?"

Rules: no pitching before Q5 is answered; never promise features live on a call; ask permission to quote anonymously; book the follow-up on the call if warm. After 10 rows, re-score the Part IV assumptions (pathway distribution, willingness-to-pay, budget line) against the data and record deltas in PROGRESS.md.

## Warm-list seeding (fill to 10 this week — the 4-sessions-overdue item)

Sources: master's/ship-design network; supervisors' industry contacts; Eurostars lab shortlist (5 labs, TP_20260626); LinkedIn 2nd-degrees at EU/UK USV firms (SEA-KIT, Zelim, ACUA Ocean, HydroSurv, Unmanned Survey Solutions, Maritime Robotics, Zeabuz, Robosys, Marine AI); Ocean Autonomy Cluster; One Sea contacts; SMM Hamburg exhibitor list (1–4 Sep).

| # | Name | Org | Segment | Relationship | Ask sent | Call date |
|---|---|---|---|---|---|---|
| 1 | [fill] | | USV dev | | ☐ | |
| 2–10 | … | | | | ☐ | |

## Log schema (`discovery_call_log.csv`)

`date, org, org_size, segment, contact_role, pathway_doc(Q3), current_evidence_practice(Q1), retest_cadence(Q2), wtp_range(Q4), budget_line(Q4), pain_score_1to5, objections, quotes, referrals(Q5), next_step, next_step_date`
