# Release / demo checklist — <name, date>

## Release gate (BLOCKING — do not git-tag until ALL three are green)

- [ ] **Regression PASS** — every box in `../03_QA_Test_Plan.md` §5 checked **and** logged in `../05_Test_Log.md` (date / build / ref): __________
- [ ] **Zero open S1**, and zero open S2 on the demoed path (`../04_Known_Issues_Register.md`)
- [ ] **QA sign-off** complete (`qa_signoff_checklist.md`)

> Nothing below may be tagged/released until the three boxes above are checked.

## Code & build
- [ ] Latest `Source/` compiles (full rebuild, not just Live Coding) on a clean `Intermediate/`
- [ ] Canonical `python_listener.py` runs from a fresh venv (`requirements.txt` only)
- [ ] Sign convention verified (TC-04) on this build

## QA
- [ ] Regression checklist green (`../03_QA_Test_Plan.md` §5)
- [ ] QA sign-off complete (`qa_signoff_checklist.md`)
- [ ] Evidence pack generated (run CSV + IMO KPIs + screenshots) — for demo D6

## Repro & backup
- [ ] Clean-machine clone reaches "vessel moving in Monaco" (TC-11)
- [ ] Cesium token setup documented; cache excluded
- [ ] Committed + pushed to private remote; milestone **tagged** — *only after the Release gate above is green*
- [ ] External-drive backup refreshed

## Demo assets (if applicable)
- [ ] MRQ cinematic rendered (D7)
- [ ] Key art / one-pager current (`../../Image References/`, `../../Documents/`)

## Docs
- [ ] `PROGRESS.md`, status banners, and this folder's "Last updated" dates refreshed
