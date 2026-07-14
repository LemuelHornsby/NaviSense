# LinkedIn — Build-in-Public Post (draft, for handle warm-up)
**Status:** DRAFT. Post only once your LinkedIn handle/brand is live (per calendar, W2 carryover). This is a warm-up post, not the soft launch — the launch post with the film is 11 Jul.
**Voice check:** plain, direct, specific numbers, no hype words. All claims below trace to real repo artifacts (21–26 Jun).
**Suggested media:** `Development/Development images/Yachtscene.png` (vessel under way) + `logs/unreal-test-run_20260624_055244/evidence_pack/turning_circle.png` (the IMO turning-circle plot). Two images, no carousel needed.

---

## Option A — short (recommended)

Three weeks ago NaviSense was a closed loop I could only describe. This week it measured itself.

A Python script drives a 38 m vessel through a photoreal, georeferenced Monaco in Unreal Engine. I ran a turning circle and the simulator produced the IMO standard maneuver numbers from the run log:

- Advance 155 m (4.09 x ship length)
- Tactical diameter 158 m (4.16 x ship length)

Both inside the IMO limits. The whole run also writes a single self-contained evidence report — one file you can email — with the plots, a health check, and the AIS/COLREGS encounter analysis next to it.

One honest caveat, because it matters: those numbers come from a standard-method maneuvering model (MMG), not yet from CFD of this exact hull. The CFD validation is the work I'm doing now. The point of the architecture is that the physics is a replaceable module — so "our turning circle matches our CFD" becomes a sentence I can back with data, not a slogan.

Building this open-core, part-time, in public. More soon.

---

## Option B — even shorter (if A feels long)

This week NaviSense went from "a vessel moves in Monaco" to "the vessel measures its own turning circle."

A Python script drives a 38 m ship through photoreal Monaco in Unreal Engine; the run log produces the IMO maneuver KPIs — advance 155 m, tactical diameter 158 m, both inside IMO limits — and a single-file evidence report you can email.

Honest caveat: those are standard-method (MMG) numbers, not yet CFD of this hull. CFD validation is what I'm building next. The physics is a replaceable module by design, so the validation slots straight in.

Open-core, part-time, in public.

---
## Why this is safe to post
- "IMO numbers, both inside limits" = real (`unreal-test-run_20260621_163148` evidence pack: A/Lpp 4.09, DT/Lpp 4.16, both PASS).
- "single self-contained evidence report" = real (WP-20260626, evidence_report.html).
- "AIS/COLREGS encounter analysis" = real (WP-20260624).
- The CFD caveat is the KI-019 honesty correction, stated plainly — it pre-empts the one question an engineer would ask.
- No competitor named, no customer named, no metric invented.
