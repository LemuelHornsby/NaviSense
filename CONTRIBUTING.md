# Contributing to NaviSense

**Status: repo is private pre-alpha; this file activates at the community alpha. License split: see LICENSE files (formats/bridge schema/scoring = Apache-2.0; core runners/vessel pipeline = proprietary/source-available — check each directory's LICENSE).**

## The one rule that explains everything else

NaviSense is a verification instrument, so contributions are held to instrument standards: **every behavioral change ships with a gate** — a `verify_*` script (or extension of an existing one) with a pass/fail exit code **and at least one negative control** proving the gate can fail. PRs without gates are not reviewed. Read `Manual and Troubleshooting/03_QA_Test_Plan.md` for the pattern.

## Ground rules

Open an issue before a PR (use the templates); small PRs beat big ones; no new third-party dependency or asset without a row added to `Documents/Legal/Third_Party_License_Audit.md`; sign conventions and wire fields are API — changes require a spec + CHANGELOG entry per `Documents/Spec/NaviSense_Bridge_Protocol_Spec.md` §5; honesty rules apply to docs and claims (nothing is "validated" unless the Credibility File §5 tier says so); Windows is the reference platform for the UE side, headless core must stay OS-portable Python.

## Dev setup

`SETUP.md` (clone → demo) and `python/repro_doctor.py` (12-check readiness). Run the headless self-test before pushing: `python run_demo.py --selftest`.

## Legal

By contributing you agree your contribution is licensed under the license of the directory it modifies, and you certify the Developer Certificate of Origin (developercertificate.org). [Decide before alpha: DCO sign-off vs CLA — default DCO.]
