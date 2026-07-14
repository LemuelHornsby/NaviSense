# Weekly Brief — Saturday 4 July 2026 (W4, one day late — no Friday session ran)

## Where we are
**Calendar week:** W4 (3–11 Jul) — final week before **11 Jul soft launch**, 7 days out.
**Last week's gate (W3, 26 Jun):** "DIANA submitted." **Status: UNKNOWN / likely MISSED.** The repo has no record of a submission (no v4, no confirmation note anywhere in PROGRESS.md or PIPELINE.md since the 26 Jun review). The hard deadline was **3 Jul, 12:00 UTC — yesterday**. I cannot see the DIANA portal, so I cannot confirm either way. **This is the first thing I need from you** — see Action #1 below. Per the calendar's own rule ("adapt rather than guilt-stack"), if it slipped, there's nothing to replan for DIANA itself (the window is shut); the adaptation is to re-point this week's non-dilutive effort at Inception (still open, rolling, ~1 h) and keep Epic MegaGrants (window open to 4 Sep) and Eurostars (10 Sep) on track.

**This week's gate:** soft-launch kit ready by 10 Jul. Status: **behind**. No film capture, no beauty screenshots, and the warm-contact list is still 0/10 (slipped three sessions running: 18 Jun → 25 Jun → 3 Jul). The demo itself is in good shape to film (D1/D3 confirmed in-engine, D4 sensors mostly validated), but nothing in the film/landing-page/DM pipeline has moved since 26 Jun.

Good news from the build side: 3 Jul shipped a genuinely new, real capability — **scripted COLREGS encounters with automated compliance scoring** (WP-20260703), verified 5/5 + 3/3 headless with real numbers (see Action #4 / the drafted post). This is strong, honest content for the content bank — the first concrete "we scored a COLREGS rule" proof point.

## Your ≤2 h actions this week (ranked by conversion value)

| # | Action | Time | Why it ranks here |
|---|---|---|---|
| 1 | **Confirm DIANA status** — did you submit before 3 Jul 12:00 UTC? Reply with the date, or "missed." | 2 min | Determines whether T5 shows 1 submitted or 0, and whether we need to check for a late-submission/appeal path. I cannot see the portal. |
| 2 | **Fill `warmup_contacts_10.md`** — 10 real names, even rough ones | ~20 min | Now genuinely overdue (missed 18/25 Jun and the 3 Jul target). These are the 11 Jul soft-launch DMs — without names, soft launch has no personal outreach, only a public post. Highest-leverage task left this week. |
| 3 | **Reserve domain + LinkedIn/YouTube handles** (if not already done) | ~15 min | Still blocking the landing page publish, T1 audience tracking, and posting anything under a real brand. Please tell me if this is actually done — the session has had no way to confirm it for 3 weeks. |
| 4 | **Review the drafted COLREGS engineering post** (`LinkedIn_COLREGS_scoring_post.md`) | ~10 min | Real, honest, ready-to-post content built from the 3 Jul build (four scored encounters: head-on, crossing give-way, overtaking, stand-on). Bank it for the W6 "Scoring COLREGS" slot, or use as a second soft-launch-week post if you want more substance than the film alone. |
| 5 | **Confirm NVIDIA Inception status** (submitted? date?) — if not, do it (~1 h, rolling, free) | 2 min–1 h | T5. Unconfirmed for 4 weeks running now. |

Mandatory core (#1–#3) ≈ 40 min. #4–#5 fit inside the 2 h if you have it.

## What I prepared this session (in `TP_20260704/`)
- **`LinkedIn_COLREGS_scoring_post.md`** — new build-in-public post drawn entirely from the 3 Jul WP-20260703 headless run: four scripted encounters (head-on, crossing give-way, crossing stand-on, overtaking), each scored against COLREGS Rules 8/13–17, with the real miss distances (238 m / 342 m / 152 m / 295 m) from `wp_20260703_result.json`. Carries the KI-028 honesty caveat (scripted target + pre-planned own-ship maneuver — this measures the conformance metric, not autonomous decision-making) so it can't be read as overclaiming.
- **`soft_launch_critical_path.md`** — refreshed §3.1 status at 7 days out; flags that the film/screenshot side has had zero movement since 26 Jun while dev effort went to the sensor suite instead.
- **Docs updated:** `PIPELINE.md` (DIANA row marked deadline-passed/status-unknown, warm-contacts row marked overdue, no zombie rows), `PROGRESS.md` (T1–T5 W4 update + session note).

## This week's gate
**Soft-launch kit ready by 10 Jul.** Status: at risk. The blocking items are almost entirely yours (warm names, handles) or dev-capture (film/screenshots), not GTM drafting — I can't draft a launch post that embeds a film that doesn't exist yet, or personalize DMs to names I don't have.

## Blockers needing you
1. **DIANA submission status** — confirm today if possible; the deadline has passed either way, so this is now about record-keeping and knowing whether T5 is 1 or 0.
2. **Warm-contact list (0/10)** — 20 minutes, three sessions overdue, directly blocks 11 Jul's personal-DM step.
3. **Handles/domain** — unconfirmed for 3 weeks; blocks the landing page and T1.
4. **NVIDIA Inception** — unconfirmed for 4 weeks.
5. **(Dev side, urgent for 11 Jul)** No film capture and no beauty screenshots exist yet (D6/D7 still open in PROGRESS.md). Recent dev sessions (27 Jun–3 Jul) went into the sensor suite (radar, camera metadata, dashboard, COLREGS scoring) rather than wake VFX polish / MRQ film / screenshot capture. If 11 Jul is a hard date, the next dev session may need to prioritize `Phase5_Systems/08_capture_demo_stills.py` (beauty stills) and the MRQ film pass over further sensor work — that's a build-track call, not a GTM one, flagging it here since it directly threatens this week's gate.

## Next session I will prepare
- Confirm DIANA outcome in the tracker (submitted-date or closed-missed).
- If a film/stills exist by then: assemble the actual soft-launch post + 10 personalized DMs (needs your names first).
- Eurostars: begin PI verification for the shortlisted labs (was slated for W7, can start early since W4/W5 GTM bandwidth is otherwise blocked on your inputs).
- Epic MegaGrants: submission reminder once the window best-fits (post-11-Jul-film, target ~13 Jul).
