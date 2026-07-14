# LinkedIn post — soft launch, text-led (no film) — draft, review before posting

**Use only if going with Path B (post today anyway).** Every claim below traces to a real result
already in the repo — no invented numbers, no "coming soon" dressed up as shipped.

**Source artifacts:** `wp_20260703_result.json`, `wp_20260709_result.json`, `sensor_suite_result.json`,
`colregs_matrix_result.json`, KI-028 (honesty caveat on scripted maneuvers).

---

## Post text

30 days ago I set out to build one thing: a maritime-autonomy simulator where you can drive a
CFD-grounded vessel through a photoreal port from your own Python script, and walk away with
scored evidence instead of a "looked fine to me."

Where it stands today:

- A Python autopilot drives the vessel through photoreal Monaco (real Cesium/Google 3D Tiles, true
  WGS-84 GPS output) — the closed loop has been running since mid-June.
- Full sensor suite is live on the wire: GPS, IMU, AIS, radar, and camera, validated against the
  physics plant (GPS/IMU correlation 1.0000 against ground truth).
- Four classic COLREGS encounters — head-on, crossing give-way, crossing stand-on, overtaking —
  each scored automatically against the rule that applies (Rules 8, 13–17), with miss distance and
  verdict written into an evidence pack. I ran it wrong on purpose three times to make sure the
  scorer actually catches bad behavior. It did.

To be precise about what this is: the COLREGS maneuvers above are scripted, pre-planned responses,
not autonomous decisions — the validated part is the *scoring*, not autonomous rule-following.
That's the next piece of work.

Demo film is being captured this week — I'd rather ship the real one late than a placeholder on
time. If you work in maritime autonomy, USV development, or class-society assurance and want an
early look, drop a comment or DM — building this in the open.

#MaritimeAutonomy #COLREGS #SimulationEngineering #MASSCode

---

## Notes for Lemuel
- No waitlist/landing-page link included — don't publish a dead link if the domain/handle isn't live yet. Add it in if confirmed.
- If posting this, treat the eventual film post as "clip #2," not the soft launch itself — keeps the calendar's 3-stage ladder intact.
