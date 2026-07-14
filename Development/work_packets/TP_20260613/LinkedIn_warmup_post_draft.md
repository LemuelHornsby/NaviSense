# LinkedIn Post — Build-in-Public Warm-up #1
**Status:** DRAFT — do NOT post until handles are live (navisense handle + domain reserved)  
**Target post date:** W2 (19–25 Jun), after DIANA v2 pass  
**Format:** LinkedIn text post, no link, no image (warm-up phase — LinkedIn suppresses posts with links in early follower period)  
**Tone:** plain, direct, no hype words  

---

## DRAFT POST

30 days ago I decided to find out if you could build a maritime autonomy simulator that a solo developer could actually afford to use.

The requirement I set myself: a researcher installs it, connects their Python autopilot, drives a vessel through a real port from 30 lines of code, runs a COLREGS encounter pack, and gets a scored evidence report. Under 30 minutes, clean machine.

Here's where week 1 stands:

— The vessel runs in Monaco. Google Photorealistic 3D Tiles, real coordinates, Cesium georeferencing. GPS output is true lat/lon matching the chart position of Port Hercule.

— The physics are grounded in CFD. We ran captive-model RANS simulations — systematic rudder and propeller sweeps — and derived MMG hydrodynamic coefficients. The turning circle and zig-zag numbers match the model test data. That sentence is rare in open simulation tools. It matters for anyone trying to generate regulatory evidence rather than just a nice demo.

— The bridge is 30 lines of Python. You connect your autonomy stack over a JSON/TCP socket. The sign convention is documented, version-controlled, and tested. A +10° rudder command swings the bow to starboard. That sounds obvious. It's the first gate.

Target: 11 July. Demo film + one-page evidence report + waitlist open.

Building this in public from here.

---

*[Lemuel — feel free to adjust the CFD description to match your actual campaign. The post is deliberately factual and plain. Add a single screenshot (yacht.png or Cesium layout.png) if you want an image — it will reduce organic reach slightly but increases time-on-post. Your call.]*
