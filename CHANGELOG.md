# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: schema/spec changes per `Documents/Spec/NaviSense_Bridge_Protocol_Spec.md` §5; `navisense-core` adopts SemVer at the core/view split. Entries begin at the first externally visible baseline; deep history lives in `Documents/PROGRESS.md` and `Development/work_packets/`.

## [Unreleased]

### Added
- Documents gap-set: Simulation Credibility File v0.1, Regulatory Mapping Annex v0.1, Evidence-Pack Templates (requirements trace + uncertainty/validity), Bridge Protocol Spec v0.1, Legal templates (IP letters, license audit, pilot SOW), discovery-call kit, continuity note, watch logs (2026-07-14).
- Strategy: `NaviSense_Strategy_Validation_Report_2026-07-14.docx` (red-team report; MVS, MASS Code/AROS playbook, V0–V5 validation ladder, kill criteria).

### Planned (from strategy report Part XI)
- `navisense-core` / `navisense-view` split + CI on push; requirements-trace + uncertainty sections wired into `build_evidence_pack.py`; V1 benchmark-hull replication.

## [baseline] — 2026-07-13

### Added
- Evidence-pack view/manifest integrity gate v2.1: refuses partial run views (exit 3), `--allow-partial` watermark, `view_complete` provenance in KPIs (TC-51). Rule: live-run packs are (re)built on Windows.

### Fixed
- KI-037 cp1252 encoding issue (live, 12 Jul); KI-038 stale sandbox-mount view detection.

## [baseline] — 2026-07-12

### Added
- First full live MMG demo session: run `demo-monaco_capture_20260712_125800` (13 min, SS2, 3 AIS targets); Windows-side gates TC-17 6/6 (23,393 rows), TC-23 6/6, TC-43 4/4 ⇒ D4 closed (scoped).
