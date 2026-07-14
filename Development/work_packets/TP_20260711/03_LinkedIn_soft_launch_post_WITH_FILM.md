# LinkedIn post — soft launch, film-led — TEMPLATE, fill in after the capture session

**Do not post until the film exists.** Fields marked `[[...]]` need real values from that session's
`capture_artifacts_result.json` / the actual film file — do not estimate or round from memory.

---

## Post text

Thirty days ago I set out to build one thing: install → control → test → evidence — a
maritime-autonomy researcher drives a CFD-grounded vessel through a photoreal port from their own
Python script, runs a scenario pack, and walks away with a scored evidence report instead of "it
looked fine to me."

Here's the 30-day demo. [[FILM LINK]]

What's in it, all real, none of it staged for the camera:
- A Python autopilot driving the vessel through photoreal Monaco (Cesium/Google 3D Tiles, true
  WGS-84 GPS)
- Full 6-DOF response to sea state — [[one specific number, e.g. roll/pitch/heave range from the
  SS5 re-check]]
- The sensor suite live on the wire: GPS, IMU, AIS, radar, camera — validated against the physics
  plant
- COLREGS encounters scored automatically against the rule that applies — [[one real miss-distance
  number from the matrix run]]

What it isn't (yet): the COLREGS maneuvers are scripted responses, not autonomous decisions — the
validated part is the scoring. CFD-derived (vs. standard-method) maneuvering coefficients are the
next validation milestone, not a finished claim.

Open-core, going public with a free community edition in late August. If you work in maritime
autonomy, USV development, or class-society assurance, join the waitlist — link below — or just
comment/DM, I read everything.

[[WAITLIST LINK]] (only if domain/handle confirmed live — otherwise drop this line)

#MaritimeAutonomy #COLREGS #SimulationEngineering #MASSCode

---

## Notes for Lemuel
- Pull the film-specific numbers straight from that session's `capture_artifacts_result.json` and
  `verify_run_kinematics` output — don't restate from this template or from memory.
- Pair with the 15 s clip cut for a same-day follow-up post/story.
- This is the actual "Soft launch" per Traction Calendar §3.1 — the 10 warm DMs should go out the
  same day this posts, using `TP_20260613/warmup_contacts_10.md` (still needs Lemuel's names).
