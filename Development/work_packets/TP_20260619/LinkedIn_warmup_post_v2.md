# LinkedIn Post — Build-in-Public Warm-up (v2, cleared for W2)
**Status:** DRAFT — post once handles are live (LinkedIn handle + domain reserved). Calendar slots this for W2 (19–25 Jun), after the DIANA v2 pass — both done today.
**Format:** text post, no link, no image (warm-up phase — LinkedIn suppresses link posts during the early follower period). Optional single image noted at the end.
**Tone:** plain, direct, no hype words.
**What changed from v1:** the physics paragraph is rewritten to be truthful (see KI-019). v1 claimed the turning-circle and zig-zag numbers "match the model test data" — they don't yet; the coefficients are empirical estimates and the CFD campaign that validates them is the work in progress. Posting the v1 wording would have been an unsupportable claim.

---

## DRAFT POST

30 days ago I set out to find whether one person could build a maritime autonomy simulator that a researcher could actually afford to use.

The bar I set: you install it, connect your Python autopilot, drive a vessel through a real port from about 30 lines of code, run a COLREGS encounter pack, and walk away with a scored evidence report. Under 30 minutes, clean machine.

Where it stands after the first stretch:

— The vessel runs in Monaco. Google Photorealistic 3D Tiles, real coordinates, Cesium georeferencing. The GPS output is true lat/lon, matching the chart position of Port Hercule.

— It moves in six degrees of freedom on a real sea state — roll, pitch, heave from a deterministic wave field you can replay run to run, not a canned animation.

— The maneuvering model is the MMG standard method — the same approach naval architects use to predict turning circles and zig-zag overshoot. It produces those IMO numbers now. The coefficients today are empirical estimates; the next step is the CFD captive-test campaign that replaces them with validated, vessel-specific values. That step is the whole point: "our turning circle matches our CFD" is the sentence that separates evidence tooling from a nice-looking demo, and the architecture is built to back it with data.

— The bridge is about 30 lines of Python over a JSON/TCP socket. The sign convention is documented, versioned, and tested. A +10 degree rudder command swings the bow to starboard. Sounds trivial. It's the first gate, and a surprising number of sims fail it.

Target: 11 July. Demo film, one-page evidence report, waitlist open.

Building this in public from here.

---

*Notes for Lemuel:*
- *Edit the CFD line to match your real campaign status — keep it honest; do not claim validation is finished until the data exists.*
- *Optional image: `Yachtscene.png` or `Cesium layout.png` from Development images. An image trades a little organic reach for more time-on-post — your call.*
- *Hold until the LinkedIn handle is live so the post can carry your brand from day one.*
