# NaviSense — Landing Page Copy (draft, W2)
**Status:** DRAFT for review · staged, not published · go-live target W4 (with the 11 Jul soft launch)
**Voice:** plain, direct, no hype words. Every claim below is true today or clearly marked as a target.
**Build note:** keep the page link out of LinkedIn posts during handle warm-up; the waitlist form can be a simple email capture (Tally/Formspark/Carrd) — no backend needed for soft launch.

---

## Above the fold

**Headline:**
> Turn autonomy code into regulatory-grade evidence.

**Sub-headline:**
> NaviSense is the open-core marine-autonomy simulator: a standard-method maneuvering model, photoreal real ports, synthetic sensors, and scored COLREGS scenarios — at a price the people writing the algorithms can actually pay.

**Primary CTA:** `Join the waitlist` (email capture)
**Secondary CTA:** `Watch the 30-day demo` (links to the 11 Jul film once live)

---

## Positioning sentence (Strategy §4.2 — use verbatim somewhere on the page)

> For marine-autonomy developers and researchers, NaviSense is the open-core simulator that turns autonomy code into regulatory-grade evidence — CFD-validated physics, photoreal real ports, auto-labeled sensors, scored COLREGS scenarios — at a price the people actually writing the algorithms can pay. Applied Intuition sells to programs; NaviSense belongs to engineers.

*(Honesty note: the positioning sentence says "CFD-validated physics" as the product vision. On the proof section below, describe the CFD work as in progress — do not present validation as finished until the campaign data exists. See KI-019.)*

---

## The loop (what you actually do)

**install → control → test → evidence**

1. **Install** — packaged build + `pip install navisense-bridge`. Target: a stranger reaches "vessel moving in Monaco" in under 30 minutes.
2. **Control** — connect your autopilot over a ~30-line Python script. Documented, versioned JSON/TCP wire.
3. **Test** — drive a CFD-grounded vessel through photoreal Monaco; run a COLREGS encounter pack headless.
4. **Evidence** — get a scored report: IMO maneuver KPIs, COLREGS conformance, plots, screenshots.

---

## Proof (what's real today — 19 Jun 2026)

- Closed loop is **live**: a Python autopilot drives the vessel through photoreal Monaco (Cesium + Google 3D Tiles), at true WGS-84 coordinates — GPS output is real lat/lon.
- Maneuvering uses the **MMG standard method** and computes the IMO turning-circle and zig-zag KPIs. The CFD captive-test campaign to replace the empirical coefficients with validated, vessel-specific values is **in progress** — that validation pipeline is the point of the platform.
- Full **6-DOF** vessel response (roll, pitch, heave) in a deterministic, replayable **sea-state** field; logged per run.
- Open, versioned **Python/JSON bridge** — no proprietary SDK, no lock-in.

*(Coming for the community alpha: scored COLREGS-10 pack, one-page evidence report, auto-labeled dataset export. Shown on the roadmap, not claimed as shipped.)*

---

## The deal (open-core, stated once)

- **Community — €0, forever.** Full closed-loop sim, one vessel, Monaco, manual scenarios. Bring your own Cesium token.
- **Pro — €119/mo.** COLREGS scoring, evidence reports, dataset export, priority support.
- **Lab — €4,900/yr.** Teams/universities, 5 seats, classroom use.
- **Design-partner pilot.** We build your vessel profile + scenario suite + evidence report in 8 weeks.

The bridge, schema, and scenario format are open (Apache-2.0). The simulator core is source-available. Pro modules are proprietary. We choose this once and don't change the deal later.

---

## Waitlist block

**Heading:** Be first to run it.
**Body:** We go public with the demo film on 11 July 2026, and the free community edition follows in late August. Join the waitlist to get the install link, the sample dataset, and an early look at the evidence reports.
**Field:** email · **Button:** Join the waitlist
**Microcopy:** No spam. One note at each launch milestone.

---

## Footer one-liner
NaviSyn Marine Solutions · built in public · [LinkedIn] · [YouTube] · [GitHub — opens 25 Aug]
