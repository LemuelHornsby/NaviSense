# NaviSense — Launch Strategy & Business Playbook

**Company:** NaviSyn Marine Solutions · **Product:** NaviSense Simulator (UE5 flagship)
**Prepared by:** Claude (co-developer) · **Date:** 11 June 2026
**Companions:** `NaviSense_UE5_Analytical_Review.md` (market/technical analysis) · `NaviSense_UE5_Master_Execution_Plan.md` (build plan) · `NaviSense_Traction_Calendar.md` (week-by-week GTM execution)

**Locked operating constraints (your answers, 11 Jun 2026):** part-time founder · pilot-revenue + grants before any raise · open-core · Europe/UK base · content-led inbound with few high-value calls · defense-open from year 1 · full-time trigger = first meaningful revenue (~€2–3k MRR or one paid pilot). Every recommendation below is shaped by these seven facts.

---

## 1 · Executive summary (the seven answers)

> **Status — 14 June 2026:** The closed loop is **LIVE** in Monaco (demo gate D1) — a concrete, demoable proof point for outreach and grant applications. The codebase is now a self-contained Unreal workspace (see `NaviSense_UE5_Master_Execution_Plan.md` status banner). Launch dates and the plan below are unchanged.


> **STATUS (12 Jul 2026, WP_20260712):** the 11 Jul soft-launch date passed without the film/stills existing (demo live session slipped; warm list 0/10). Ladder below stays valid as a sequence — dates shift right; re-planning belongs to the Friday GTM session (see `PIPELINE.md`, PROGRESS GTM notes).

**When to launch?** Three times, not once. Soft launch the *story* on 11 July 2026 with the 30-day demo film; launch the *community edition* late August once a stranger can install it in under 30 minutes; launch the *product* commercially in the first week of September 2026, riding SMM Hamburg (1–4 Sep) and the Eurostars deadline (10 Sep). Before any of that: the NATO DIANA 2027 short proposal is due **3 July 2026** — a 5-page document worth €100k non-dilutive. That is your first launch act, three weeks from today.

**What must the MVP do?** Not everything — one complete loop, brilliantly: a researcher installs NaviSense in under 30 minutes, drives a CFD-grounded vessel through photoreal Monaco from 30 lines of Python, runs a 10-scenario COLREGS pack, and walks away with a scored evidence report and auto-labeled sensor data. That single workflow — *install → control → test → evidence* — is the product. Section 3 gives the precise cutline.

**What is the competitive advantage?** Not UE5 visuals (copyable) and not code (AI is deflating code moats industry-wide). It is the *stack*: CFD-validated physics + real georeferenced ports + auto-labeled sensors + COLREGS scoring, open at the core, at a price tier Applied Intuition structurally won't serve — compounding into the real moats: community, scenario/data assets, and regulatory timing (MASS Code evidence window 2026–2030).

**Sales/income strategy?** An open-core ladder (free Community → Pro seats → Lab licenses → paid design-partner pilots → defense programs) fed by a content engine, with grants as the bridge financing. First euros come from one €8–15k design-partner pilot — which alone trips your full-time trigger.

**How to scale?** People last: automation-first (you already run a daily packet system), then full-time at the revenue trigger, then one applied engineer after the first grant/pilots, then a seed raise in 2027 *from traction, not promises*.

**How to stay adaptive?** A quarterly signals review with explicit kill/pivot criteria, a 70/20/10 effort split, and the discipline of treating the wedge as a hypothesis the market is allowed to amend.

**How do you succeed?** The pattern across every company studied in §7: pick one workflow, make a small group love it, attach distribution to every artifact you build anyway, charge early, and let evidence — not claims — do the selling. Part-time is survivable precisely because you've automated your own development; the same systems thinking applied to GTM is the plan.

---

## 2 · Launch timing: the three-stage ladder

A "launch" is a moment of concentrated attention. Solo and part-time, you cannot afford one big bang that either lands or dies; you stack three smaller, compounding moments — each gated by readiness, not bravado, and each already aligned with the build plan's D-gates.

| Stage | Date | What ships | Gate to proceed |
|---|---|---|---|
| **0 · DIANA proposal** | by 3 Jul 2026 | 5-page short proposal, "multidomain autonomy of uncrewed systems" challenge | None — submit regardless; outline in Traction Calendar Appendix A |
| **1 · Soft launch (the story)** | 11 Jul 2026 | 30-day demo film (D7) + landing page + waitlist + first build-in-public thread | D1–D8 demo gates from the Execution Plan |
| **2 · Community alpha (the product, free)** | ~25 Aug 2026 | Open-core repo public, quickstart, Discord, docs, sample dataset | A stranger reaches "vessel moving in Monaco" in <30 min, unaided, on a clean machine |
| **3 · Commercial launch (the business)** | 1–10 Sep 2026 | Pro/Lab tiers purchasable, COLREGS pack + evidence reports, pilot offer page | ≥2 design-partner conversations in progress; pricing live; SMM week + Eurostars (10 Sep) used as the news hook |

Two principles govern the ladder. First, *launch the story before the product*: the film and build-in-public threads from 11 July generate the waitlist that makes the September launch land with warm observers instead of strangers — Supabase's playbook of demonstrating adoption before monetizing (§7.4). Second, *never launch into silence*: each stage borrows an external moment (DIANA deadline, SMM Hamburg's ~49,000 attendees, Eurostars) so the niche press and LinkedIn maritime community have a reason to look.

Waiting longer would be a mistake. The MASS Code took voluntary effect 1 July 2026 and MSC 112 frames the Experience-Building Phase in December 2026 — the industry's attention on simulation-based evidence peaks *now*. A part-time pace argues for launching earlier with a tighter scope, not later with more features.

---

## 3 · The MVP: minimum *launchable* product

### 3.1 The defining test

> A maritime-autonomy researcher who has never spoken to you installs NaviSense, drives the DOLPHIN through photoreal Monaco from their own 30-line Python script within 30 minutes, runs the 10-scenario COLREGS pack overnight, and presents the scored evidence report + labeled dataset to their lab the next morning — then tells another lab.

Cursor reached $100M ARR with zero marketing because one power user's "this saved my week" story recruited the next user (§7.3). Your equivalent wow is *time-to-first-evidence*: nothing in the field today goes from `git clone` to a COLREGS compliance report. Every MVP decision optimizes that loop.

### 3.2 Must do (the cutline)

| # | Capability | Already planned as |
|---|---|---|
| M1 | Closed-loop sim: Python drives vessel in Monaco, MMG physics, 6-DOF water ride | D1, D2 (Exec Plan) |
| M2 | Runtime sea states (3 presets) logged per run | D3 |
| M3 | Sensors: GPS (true lat/lon), IMU, camera frames to disk, AIS w/ traffic target | D4 |
| M4 | Scenario runner: YAML in → run → artifacts out, single command | D6 |
| M5 | **COLREGS starter pack:** 10 canonical encounters (head-on, crossing give-way/stand-on, overtaking variants) + CPA/TCPA + rule-conformance scoring | Week 5–6 plan, pulled forward in scope-reduced form |
| M6 | **Evidence report:** IMO maneuver KPIs + COLREGS scores + plots + screenshots → one PDF/HTML | D6 extension |
| M7 | **Dataset export:** auto-labeled camera frames (2D boxes, COCO format), 1k-frame sample downloadable | Week 8 plan, minimal version |
| M8 | Install story: packaged Win64 build + `pip install navisense-bridge` + quickstart ≤30 min + 3 tutorials | D8 extension |
| M9 | Open-core split implemented: Community (free) vs Pro feature flags + license file | New — §5.2 |
| M10 | Community surface: public repo, Discord, docs site, issue templates | New |

### 3.3 Explicitly NOT in the MVP

Multi-vessel swarms, cloud execution, ROS2 bridge (fast-follow, W11 spike), Long Beach polish, radar/LiDAR physics beyond basic, vessel-import wizard, certification claims of any kind, segmentation labels (boxes only), Mac/Linux builds, in-sim editor UX. Each is a roadmap item the community can see — visible roadmap is itself a retention feature.

### 3.4 MVP schedule impact

M1–M4, M6, M8 are already the 30-day plan. M5 (COLREGS-10 in scoring-only form), M7 (boxes-only export), M9–M10 add roughly three weeks of packet work — which is exactly the gap between the 11 July demo and the late-August community alpha. The build plan and launch ladder interlock without re-planning.

---

## 4 · Competitive advantage: what the moat actually is

### 4.1 The honest hierarchy

**Not moats (don't rely on):** UE5 visuals (any studio can match in a quarter), the C++/Python code itself (AI assistance is deflating code-replication cost economy-wide), being first (Applied Intuition could ship "Axion Maritime Lite" any time).

**Real, compounding moats (invest deliberately):**

1. **The validation pipeline.** CFD captive tests → MMG coefficients → IMO maneuver KPIs that match the tow-tank numbers. Reproducing this requires naval-architecture competence + months of CFD, not engineering hours. "Our turning circle matches our CFD" is a sentence no open-source sim and no game-engine demo can say. Deepen it: publish the validation method openly (the *method* recruits trust; the *per-vessel service* earns revenue).
2. **The scenario & data asset base.** Every COLREGS encounter authored, every labeled frame generated, every port verified accumulates. Buyers adopt the library, not the renderer — Applied Intuition's 18-of-20-automakers lock-in came from workflow integration, not graphics (§7.1).
3. **Community + standard-setting.** Open-core means grad students cite you, labs standardize on your JSON/scenario schema, and competitors must interoperate with *your* formats. The bridge schema becoming "the way you script a marine sim" is the quiet, durable win (Anduril's Lattice-as-standard logic at micro scale).
4. **Regulatory timing.** The 2026–2030 evidence window (MASS Code EBP) rewards whoever has credible scenario evidence tooling *now*. Timing isn't permanent, but compounding started early is.
5. **Founder economics.** Automated solo development (your packet system) means a cost base near zero. You can survive on revenue that wouldn't feed a five-person startup — out-waiting better-funded entrants is a strategy.

### 4.2 Positioning sentence

> *For marine-autonomy developers and researchers, NaviSense is the open-core simulator that turns autonomy code into regulatory-grade evidence — CFD-validated physics, photoreal real ports, auto-labeled sensors, scored COLREGS scenarios — at a price the people actually writing the algorithms can pay. Applied Intuition sells to programs; NaviSense belongs to engineers.*

### 4.3 Competitive responses to expect

Applied Intuition moving down-market (counter: community love + price floor they can't match without cannibalizing enterprise deals); an open-source sim adding COLREGS scoring (counter: your physics validation + ports + polish — research repos rarely sustain product quality); a training-sim vendor (Kongsberg/Wärtsilä) adding APIs (counter: speed + developer-native UX; their org structure sells to academies, not engineers). The shared counter to all three: *be the default in the community before they notice the niche.*

---

## 5 · Income & sales strategy

### 5.1 The revenue ladder (sequenced, not simultaneous)

| Rung | Offer | Price (founder pricing) | When |
|---|---|---|---|
| 0 | **Grants** (non-dilutive bridge) | DIANA €100k (+€300k phase 2); Eurostars ≤€360k UK share; national programs | DIANA 3 Jul; Eurostars 10 Sep |
| 1 | **Community** (free, open-core) | €0 — full closed-loop sim, 1 vessel, Monaco, basic scenarios, BYO Cesium token | 25 Aug |
| 2 | **Pro** (individual seat) | €119/mo or €1,190/yr — COLREGS scoring, evidence reports, dataset export, priority Discord | 1 Sep |
| 3 | **Lab** (teams/universities) | €4,900/yr, 5 seats + classroom use; citation encouraged | Sep–Oct |
| 4 | **Design-partner pilot** (FDE-lite) | €8–15k fixed-scope, 8 weeks: their vessel profile + their scenario suite + evidence report + roadmap influence; fee creditable toward Lab/Enterprise | Offer from 11 Jul film onward; target 2–3 signed by Oct |
| 5 | **Enterprise/Defense** | from €25k/yr; custom ports, on-prem, test-centre integration | 2027, via DIANA/DASA channels |

The full-time trigger (€2–3k MRR or a paid pilot) is most likely tripped by **one rung-4 pilot** — so the sales motion optimizes for pilots first, seats second. Twenty Pro seats is the slower equivalent path; both are pursued, neither alone is the bet.

### 5.2 Open-core split (the GitLab buyer-based rule)

Decide tier placement by *who pays*, not by feature size: the individual researcher's workflow is free (sim, bridge, manual scenarios); anything a lab lead expenses is Pro (scoring, reports, datasets); anything an institution signs is Lab/Enterprise (multi-seat, support SLA, custom assets). **Choose the license on day 1** — recommendation: Apache-2.0 for the bridge/schema/scenario format (maximize standard-setting) + source-available (BSL/FSL-style) for the simulator core + fully proprietary Pro modules. HashiCorp's 2023 relicense taught the cost of changing terms after a community forms (§7.5); you get to choose *once*, cheaply, now.

### 5.3 The content-inbound engine (your sales team)

Part-time rules out sustained outbound. The engine: every build artifact becomes content (you already produce demo films, evidence packs, KPI plots as *engineering* outputs — publishing them is marginal cost ~zero). Cadence: one flagship post/week (LinkedIn, where maritime lives) + film clips (YouTube/X) + a monthly deep-dive (blog: "How we validate MMG against CFD", "Scoring COLREGS Rule 15 in simulation") + launch-day posts on HN/Product Hunt for the developer audience. Calls are reserved for qualified pilot conversations only — target ≤2 calls/week, booked via the landing page. The Traction Calendar operationalizes this; the weekly Friday traction session prepares every draft so your cost is review-and-post.

### 5.4 The grant stack (researched, deadlines real)

| Program | Amount | Deadline / status | Fit |
|---|---|---|---|
| **NATO DIANA 2027** | €100k + up to €300k phase 2, 200+ test centres | **3 Jul 2026, 12:00 BST** — 5-page short proposal | "Multidomain autonomy of uncrewed systems" challenge: simulation-based T&E for USV autonomy is on-thesis |
| **Eurostars Call 11** | up to ~€360k (UK: Innovate UK funds 60% of SME costs) | **10 Sep 2026** | Needs ≥2 partners from 2 Eurostars countries — recruit a university/SME partner in July (pilot conversations double as partner search) |
| **DASA (UK)** | varies, themed + open calls | rolling cycles — monitor | Autonomy T&E themes recur; defense-open posture fits |
| **NVIDIA Inception** | no cash; cloud credits (partner packages up to ~$100–150k), DLI, VC connect | rolling, free, no equity | Apply immediately — costs an afternoon |
| Epic ecosystem (MegaGrants) / Cesium ecosystem | varies | verify current status | UE5+Cesium flagship demos are exactly what these programs showcase |
| Maritime accelerators (PortXL Rotterdam, Katapult Ocean, national clusters) | varies + network | verify 2026–27 intakes | Port/operator intros for pilots; apply selectively after September launch |

Rule: grants are *bridge fuel for the roadmap you already have* — never bend the roadmap to a grant. DIANA and Eurostars both fund exactly what the Execution Plan already builds; that's why they're in; anything that doesn't is out.

---

## 6 · Scaling path

**Phase 0 — Automated solo, part-time (now → trigger).** Capacity comes from systems, not hours: daily dev packets, Friday traction packets, nightly CI. Revenue target: first pilot. Guardrail: mandatory human workload ≤20 min/day dev + ≤2 h/week GTM.

**Phase 1 — Full-time founder (trigger → ~€100k ARR).** First pilot/MRR trips your stated trigger. Focus shifts 50/50 build/sell; 2–3 concurrent pilots maximum (Palantir's lesson: deep success in few accounts beats shallow presence in many). Convert pilots to Lab/Enterprise licenses.

**Phase 2 — First teammate (after grant + ≥2 pilots).** Hire #1 is an **applied/forward-deployed engineer** (runs pilots, builds customer scenarios — revenue-attached) — not sales, not marketing; your content engine plus the FDE *is* the GTM. DIANA money funds this without dilution.

**Phase 3 — Seed from traction (2027).** Raise only with: 1,000+ community installs, 3+ paying labs, 1 defense program engagement, the open-core metrics dashboard. Commercial open-source companies raise faster and at higher valuations *because* adoption de-risks the round (§7.4). Use the raise for the platform leap: cloud scenario farm (usage-based pricing — the Cursor lesson: charge for the work the machine does), port library expansion, certification partnerships (DNV-class alignment for evidence packs).

**Product scaling order:** depth in one port → more vessels (validation pipeline as the bottleneck asset) → more ports → cloud scale-out → standards/integrations (ROS2, test centres). Never two new dimensions at once.

---

## 7 · Deep research: what the winners actually did (and your translation)

*Method note: companies chosen for relevance to your shape — technical product, developer/engineer buyer, simulation or defense adjacency, recent (2023–2026) results. Each lesson ends with the NaviSense translation.*

### 7.1 Applied Intuition — own the workflow, then the stack
$15B valuation (Jun 2025), $830M ARR (2x YoY), 18 of the top 20 automakers. Started as *simulation tooling* for AV engineers; expanded only after owning that workflow into data, vehicle OS, defense. Lock-in came from being integrated into the customer's daily engineering loop, not from graphics. **Translation:** win the marine-autonomy engineer's *daily test loop* (scenario → run → evidence). Resist platform breadth until the loop is owned. Their existence also *prices the category* for you: enterprises pay millions for this workflow — your €5–25k tiers are not ambitious, they're conservative.

### 7.2 Anduril — product-first defense, standards as gravity
~$1B revenue 2024 (+138%), $30.5B valuation 2025. Broke defense convention by self-funding finished products and demoing working systems instead of bidding studies; Lattice OS became the integration standard others must speak. **Translation:** in every DIANA/DASA interaction, *demo, never slideware* — your packaged build on a laptop is the pitch. Long-game: make the NaviSense scenario/bridge schema the format USV evidence is exchanged in; standards are gravity wells.

### 7.3 Cursor (Anysphere) — the power-user flywheel
$0 → $500M ARR in ~21 months, $0 marketing, ~$2B ARR by early 2026; growth came from individual power users whose visible wins recruited their teams; later priced usage (the agent's work), not seats alone. **Translation:** obsess over time-to-wow (<30 min install gate is sacred); aim the free tier at the *individual researcher* who expenses nothing but influences everything; when cloud runs arrive, price the compute-hours of evidence generated, not just seats.

### 7.4 Supabase — open-core done honestly
10k GitHub stars in 6 months, PMF proven through adoption *before* raising; $5B valuation by Apr 2025. The free tier is genuinely production-capable (self-hostable); paid solves the *next* problem (managed scale, enterprise security). **Translation:** Community NaviSense must be honestly useful — a student must complete real research on €0, forever. Sell what institutions need beyond it: scoring, reports, datasets, support, scale. Adoption metrics become your seed-round evidence.

### 7.5 HashiCorp — the license cautionary tale
Built the category open (MPL), relicensed to BSL in 2023 to stop free-riders → community fork (OpenTofu) and lasting trust damage, though IBM still paid $6.4B (2025). **Translation:** the relicense pain came from *changing the deal late*. You are pre-community: set the split now (§5.2 — Apache the standard, source-available the engine, proprietary the monetized layer), write it into the repo's first README, and never surprise the community.

### 7.6 GitLab — buyer-based open core
Sustained open-core at scale by tiering on *who the buyer is* (IC free → manager → director → exec), not on feature size; same price self-hosted or SaaS. **Translation:** your tier test for every future feature: "who signs?" Researcher → free. Lab lead → Pro. Institution/program → Lab/Enterprise. This single rule prevents the two classic open-core deaths: a crippled free tier (kills adoption) and a too-generous one (kills revenue).

### 7.7 Palantir — forward-deployed engineering as sales
Pilots staffed by embedded engineers convert to long-term contracts; the model is now copied explicitly by OpenAI/Anthropic for enterprise GTM. Complex products need the vendor to *deliver the first outcome*, not hand over a manual. **Translation:** your design-partner pilot *is* FDE-lite — you personally build their vessel/scenarios in 8 weeks. It's simultaneously revenue, the deepest possible user research, casework content, and the conversion path to licenses. Cap concurrency at 2–3; protect the product roadmap from pilot-specific drift by requiring every pilot artifact to generalize into the library.

### 7.8 Cross-cutting pattern (the success formula in one paragraph)
Every company above: (1) picked a *narrow wedge* with an acute, funded pain; (2) made a *small group of practitioners* measurably faster — and let them evangelize; (3) attached *distribution to artifacts* they were building anyway (demos, benchmarks, open repos); (4) *charged early* relative to peers and let pricing communicate seriousness; (5) expanded only after the wedge was undeniably won; (6) rode an *external clock* (AV investment cycles, defense rearmament, AI wave — yours is the MASS Code window). None of it requires being full-time on day 1; all of it requires refusing to do six things at once.

---

## 8 · Staying adaptive (the system, not the slogan)

**Quarterly signals review** (first: w/c 28 Sep 2026, then every quarter — 2 h, output is one page in `PROGRESS.md`): regulatory (MSC 112 Dec 2026, EBP participation lists — each participant is a prospect); competitive (Applied Intuition maritime releases, new OSS sims, K-Sim/NTPRO API moves); technology (UE/Cesium/Google-tiles licensing changes, AI-agent capability jumps that change your own cost structure); commercial (pilot conversion %, content → call rate, tier mix vs this plan's assumptions).

**Effort allocation 70/20/10:** 70% the locked wedge (this plan), 20% adjacent opportunities that arrive via inbound (a port authority wanting a digital twin; a training academy wanting scenarios), 10% wild experiments. Adjacencies are *logged, quoted at full price, and only pursued if they generalize into the library* — the Palantir drift rule.

**Pre-committed pivot triggers (write once, honor later):** if by **31 Dec 2026** there is no paid pilot *and* <300 community installs *and* no grant — the wedge hypothesis is wrong; first fallback is **port digital twins / pilotage visualization** (same asset base, different buyer), second is **defense T&E services** (DIANA network, services-led). If community adoption is strong but conversion is zero, the problem is packaging/pricing, not product — fix tiers before pivoting. Deciding the thresholds now, calmly, prevents both panic pivots and zombie persistence later.

**Moat maintenance in the AI era:** assume any code feature is replicable in months; keep investing where AI doesn't compound for competitors — your CFD/tow-tank validation data, the scenario corpus, community trust, and regulatory relationships. Meanwhile *exploit* AI asymmetrically: your packet system means one part-time founder ships like a small team; that asymmetry widens every quarter you maintain it.

---

## 9 · Business risk register

| # | Risk | Mitigation |
|---|---|---|
| B1 | Part-time stall — GTM dies in busy weeks | Friday traction packets prepared for you; ≤2 h/wk mandatory; calendar has skip-tolerance built in |
| B2 | Open-core misjudged — free tier cannibalizes or repels | Buyer-based rule (§5.6); revisit tier mix at quarterly review with real data |
| B3 | Google 3D Tiles commercial terms restrict product use | BYO-Cesium-token architecture + W11 fallback environment profile (already in Exec Plan) |
| B4 | Solo-founder credibility gap with institutions/defense | Evidence packs + published validation method + university design partner as reference; advisors at Phase 2 |
| B5 | Export-control / dual-use creep | Core stays civil (COLREGS, commercial sensors); defense work only via structured programs (DIANA/DASA) with their compliance rails |
| B6 | DIANA/Eurostars rejection | They're accelerants, not the plan — ladder stands on pilots/seats; reapply next cycle with traction |
| B7 | A funded competitor targets the niche post-launch | Speed + community + validation moats (§4); being acquired-interesting is an acceptable failure mode |
| B8 | Burnout — two jobs, one human | The trigger exists precisely to bound the part-time period; automation carries the load; freeze weeks protect recovery |

---

## 10 · How you succeed — the synthesis

Focus is the strategy: one wedge (autonomy devs), one port (Monaco), one workflow (install → control → test → evidence), one channel (content-led inbound), one conversion (the design-partner pilot) — until the trigger trips. Ship something public every week; in this niche, consistency outcompetes intensity because almost nobody else is showing working software at all. Charge early and confidently — Applied Intuition's prices mean your tiers read as a bargain, and a customer who pays €10k tells you truths a free user never will. Let the regulatory clock do your marketing: every MASS-Code milestone is a news hook for evidence tooling. Protect the moats that compound (validation data, scenario corpus, community trust) and spend freely the things that don't (code, visuals, pride). And keep the machine running: the daily/weekly packet system is, quietly, your deepest advantage — a part-time founder with automated execution and zero burn can simply refuse to die, and in an industry moving on a 2026–2030 regulatory clock, refusing to die is most of winning.

---

## 11 · Sources

Companies: [Applied Intuition Series F / $15B](https://www.appliedintuition.com/press-releases/series-f) · [Applied Intuition ARR (Sacra)](https://sacra.com/c/applied-intuition/) · [Applied Intuition 2025 review](https://www.appliedintuition.com/blog/2025-year-in-review) · [Anduril $30.5B (Fortune)](https://fortune.com/2025/06/05/anduril-palmer-luckey-funding-30-billion-valuation-founders-fund/) · [Anduril strategy (CB Insights)](https://www.cbinsights.com/research/anduril-strategy-map-partnerships-acquisitions/) · [Anduril revenue (Sacra)](https://sacra.com/c/anduril/) · [Cursor growth (Contrary Research)](https://research.contrary.com/company/cursor) · [Cursor $9.9B / $500M ARR (TechCrunch)](https://techcrunch.com/2025/06/05/cursors-anysphere-nabs-9-9b-valuation-soars-past-500m-arr/) · [Cursor growth analysis](https://www.builderlab.ai/p/growth-machines-the-cursor-story) · [OSS economics / Supabase trajectory (PEXT)](https://www.pext.org/research/oss-economics) · [HashiCorp BSL announcement](https://www.hashicorp.com/en/blog/hashicorp-adopts-business-source-license) · [Open-charter critique of BSL switch](https://www.opencoreventures.com/blog/hashicorp-switching-to-bsl-shows-a-need-for-open-charter-companies) · [GitLab buyer-based open core](https://heichat.net/blogs/Xt1kY7EEXb8/Challenges-and-Successes-of-GitLabs-Buyer-Based-Open-Core-Model/) · [Open-core handbook (OCV)](https://handbook.opencoreventures.com/open-core-business-model) · [Palantir FDE model](https://www.mindstudio.ai/blog/palantir-forward-deployed-engineer-model-anthropic-openai) · [FDE hiring (First Round)](https://review.firstround.com/so-you-want-to-hire-a-forward-deployed-engineer/)

Funding/programs: [NATO DIANA — challenges](https://www.diana.nato.int/challenges.html) · [DIANA 2027 topics (Science|Business)](https://sciencebusiness.net/news/r-d-funding/research-infrastructures/funding-radar-nato-diana-announces-2027-challenge-topics) · [DIANA 2027 — six challenges, 3 Jul 2026 deadline](https://thequantuminsider.com/2026/06/02/nato-diana-announces-six-new-challenges-to-tackle-evolving-defense-and-security-needs/) · [DIANA 2026 cohort (NATO)](https://www.nato.int/en/news-and-events/articles/news/2025/12/10/nato-defence-innovation-accelerator-announces-largest-ever-cohort-of-150-innovators-to-work-on-ten-defence-and-security-challenges-in-2026) · [Eurostars Call 11 — 10 Sep 2026](https://www.eurekanetwork.org/programmes-and-calls/eurostars/eurostars-call-for-projects-september-2026/) · [Eurostars UK funding terms](https://iuk-business-connect.org.uk/opportunities/eurostars-call-for-projects-march-2026/) · [NVIDIA Inception](https://www.nvidia.com/en-us/startups/) · [SMM Hamburg, 1–4 Sep 2026](https://www.smm-hamburg.com/)

Market context: carried over from `NaviSense_UE5_Analytical_Review.md` §7 (IMO MASS Code, DNV assurance, market sizing, Orca AI/Saronic, synthetic-data literature).

*Living document — amend at each quarterly signals review. Edition 1.0, 11 June 2026.*
