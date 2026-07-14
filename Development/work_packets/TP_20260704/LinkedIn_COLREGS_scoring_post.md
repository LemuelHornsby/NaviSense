# LinkedIn post — "Scoring a COLREGS encounter in simulation" (draft, review before posting)

**Source artifacts (real, not invented):** `Development/work_packets/WP_20260703/PACKET.md`,
`NaviSense_UE5/Saved/NaviSense_Reports/wp_20260703_result.json` (verify 5/5 gates + 3/3 negative
controls), `Manual and Troubleshooting/04_Known_Issues_Register.md` KI-028.
**Status:** not yet postable under a live handle (T1 still unconfirmed — see brief). Bank this for
the W6 "Scoring COLREGS" content-bank slot (26 Jul–1 Aug), or use sooner once a handle exists.

---

## Post text

This week I rebuilt how NaviSense runs COLREGS encounters — one target ship at a time, instead of
three at once, so the geometry is actually readable.

Four classic encounters, each scored against the actual COLREGS rule that applies:

- Head-on (Rule 14) — own-ship alters to starboard, passes clear at 238 m
- Crossing, give-way duty (Rule 15) — early starboard alteration, passes astern at 342 m
- Crossing, stand-on duty (Rule 17) — holds course and speed, near-miss logged at 152 m
- Overtaking (Rule 13) — starboard alteration, clears at 295 m

Every run gets scored automatically — COMPLIANT / NON-COMPLIANT / NOT-APPLICABLE — against Rules
8 and 13–17, with the miss distance and the maneuver that produced it written into the evidence
pack. I also ran it wrong on purpose three times (held course through a head-on, turned the wrong
way in a crossing, turned early on a stand-on leg) to make sure the scorer actually catches bad
behavior and doesn't just rubber-stamp everything. It did.

To be precise about what this is and isn't: the target ship's track is scripted, and the own-ship
maneuver in these four demo scenarios is a pre-planned response, not a decision the system made by
sensing the target and reacting. What's real and validated is the *scoring* — an automated,
repeatable check of whether a given maneuver conformed to the rule that applied. Autonomous
COLREGS decision-making (own-ship senses the encounter and picks its own response) is the next
piece of work, not this one.

This is the kind of repeatable, scored evidence a MASS-Code / class-society assurance case
actually wants: not "the ship didn't hit anything," but "here is the rule that applied, here is
what the ship did, here is whether that counted as compliant."

#MaritimeAutonomy #COLREGS #SimulationEngineering #MASSCode

---

## Notes for Lemuel
- No film/screenshot attached yet — this is a text-only engineering post. Could pair with a
  screen-capture GIF of one encounter (e.g. the crossing give-way run) if you want a visual; none
  exists yet in the repo.
- Honesty line ("the target ship's track is scripted...") is load-bearing — keep it, don't trim it
  for brevity. It's the KI-028 guardrail and it's what makes the claim defensible if a technical
  reader pushes back.
- Numbers (238 m / 342 m / 152 m / 295 m) come straight from `wp_20260703_result.json` G3 — do not
  round differently or restate from memory.
