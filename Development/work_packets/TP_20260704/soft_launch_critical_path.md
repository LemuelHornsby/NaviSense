# Soft-Launch Critical Path — refreshed 4 Jul (7 days out from 11 Jul)

Checklist source: Traction Calendar §3.1. Status honestly assessed against the repo as of today.

| Item | Status | What's left / who |
|---|---|---|
| Demo runs clean enough to film | **CLOSE** (unchanged since 26 Jun) | D1/D3 confirmed in-engine; `run_demo.py` + evidence report work; new 3 Jul COLREGS encounters are an extra filmable moment. Wake VFX polish (D5), MRQ cinematic (D7), ≥3 beauty screenshots (D6) — **still not started**, no new capture files found in the repo since 26 Jun. |
| Film uploaded (60–90 s + 15 s clip) | **NOT STARTED** | No capture pipeline run yet. Dev sessions 27 Jun–3 Jul went into the sensor suite (radar, camera-metadata, dashboard) and COLREGS scoring instead of D6/D7 capture work. If 11 Jul is firm, capture needs to be the next dev priority — see brief Action item 5. |
| LinkedIn launch post (story-led, film embedded, waitlist CTA) | **NOT DRAFTED** | Can't draft the launch post around a film that doesn't exist. A COLREGS engineering post exists as a fallback/companion piece (`LinkedIn_COLREGS_scoring_post.md`) but it isn't a substitute for the story-led launch post the calendar calls for. |
| Landing page (positioning, film, waitlist, pilot one-pager link) | **COPY STAGED, unpublished** (unchanged since 19 Jun) | Copy done in `TP_20260619/landing_page_copy.md`. Still blocked on domain + handle reservation — status unconfirmed by Lemuel for 3 weeks. |
| 10 personal warm DMs | **0/10 — now 3 sessions overdue** | Slipped 18 Jun → 25 Jun → 3 Jul. Fill `warmup_contacts_10.md`; DMs get personalized once names exist. |
| PROGRESS.md T1–T5 baseline recorded | **PARTIAL** (unchanged) | T2–T5 tracked; T1 still needs a live handle to count. |

## Critical path to 11 Jul (in order, updated)
1. **Confirm DIANA outcome** (today, 2 min) — not on the launch path but the highest-value open loop; do first so it stops carrying over.
2. **Fill warm-contact list 0/10** (Lemuel, ~20 min) — now the single most overdue item.
3. **Confirm handles/domain status** (Lemuel, 2 min to just tell me yes/no — if not done, ~15 min to do it).
4. **Demo capture: beauty screenshots + film** (dev side, next session priority) — nothing exists yet; this is the actual bottleneck for the launch post and film upload, not GTM drafting.
5. **Launch post + DM personalization** — can only be drafted once #2 and #4 exist.

**Honest read:** unlike 26 Jun ("mostly non-code now"), the film/capture side has now become the
bottleneck again, because dev time went to sensor-suite work instead. If the 11 Jul date is not
movable, next week's dev session should prioritize `Phase5_Systems/08_capture_demo_stills.py` +
an MRQ film pass over further sensor scope (Radar/LiDAR/Sonar are explicitly non-demo-blocking per
`NEXT_PACKET_DIRECTIVE.md` — the same logic should now apply to further sensor work generally,
until D6/D7 close).
