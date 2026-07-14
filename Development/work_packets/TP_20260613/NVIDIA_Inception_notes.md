# NVIDIA Inception — Application Notes
**Program:** NVIDIA Inception (free, no equity)  
**URL:** https://www.nvidia.com/en-us/startups/  
**Time to complete:** ~1 hour  
**What you get:** Cloud credits (partner packages up to ~$100–150k), DLI training access, VC introductions, NVIDIA GTM co-marketing opportunities  
**Why now:** Rolling deadline — no reason to delay. NaviSense is an ideal fit: UE5 + real-time rendering + ML-adjacent (synthetic data / perception model training).

---

## Application fields & suggested answers

**Company name:** NaviSyn Marine Solutions

**Product/project name:** NaviSense

**One-line description:**  
> Open-core maritime autonomy simulator — CFD-validated physics, photoreal real ports, auto-labeled synthetic sensors, scored COLREGS scenarios — for marine autonomy developers and researchers.

**Industry:** Automotive & Robotics / Defense & Government (select both if allowed; otherwise Defense)

**Stage:** Pre-seed / Early (working product, pre-revenue)

**What does your startup do? (short paragraph):**  
> NaviSense is an open-core simulation and evidence platform for autonomous vessel development. Built on Unreal Engine 5.7 with Cesium georeferencing, it gives maritime autonomy engineers a complete test loop: install, drive a CFD-validated vessel through photoreal real ports from 30 lines of Python, run scored COLREGS scenario packs overnight, and export a regulatory-grade evidence report with auto-labeled sensor data. It targets the gap between enterprise AV simulation tools (inaccessible to the innovation base) and research-grade open-source simulators (no physics validation, no evidence output). The MASS Code (IMO, in effect 1 Jul 2026) is creating direct demand for exactly this workflow.

**GPU / compute use:**  
> Real-time rendering of georeferenced port environments (Google Photorealistic 3D Tiles via Cesium), Lumen global illumination, Niagara particle systems (wake/spray VFX), SceneCapture2D sensor frames to disk, and Movie Render Queue cinematic film output. NVIDIA cloud credits would be used for headless CI scenario runs and synthetic dataset generation at scale (target: 100k labeled camera frames for perception model benchmarking).

**Technology:** Unreal Engine 5.7, NVIDIA RTX (real-time rendering), Python (bridge/autonomy interface), C++ (UE plugin)

**Website:** [your domain — reserve navisense.io or similar before submitting]

**LinkedIn / GitHub:** [fill in after handles are reserved]

**Funding status:** Bootstrapped / pre-seed; DIANA 2027 application in progress (€100k non-dilutive)

**Number of employees:** 1 (solo founder)

**Location:** [your location — UK or EU]

---

## Notes

- The application is quick — most fields are dropdowns + short text. The paragraph answers above are the main prep needed.
- Do not mention certification or compliance *claims* — NaviSense generates evidence capability, it does not claim to certify vessels.
- If they ask for a deck or additional materials: the `DIANA_v1_draft.md` §2 architecture description can be adapted into 2–3 slides; the `Development images/Cesium layout.png` and `yacht.png` screenshots are usable.
- After approval (typically 1–2 weeks), you'll get access to the Inception portal for cloud credit requests — request GPU compute credits first (A100/H100 for CI renders).
