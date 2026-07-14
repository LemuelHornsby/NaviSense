# WP_20260714C — Off-machine git backup enablement (KI-006)

**Date:** 2026-07-14 (Tue, interactive, Lemuel-directed) · **Type:** config + runbook only — NO product change
**Goal:** settle the full off-machine backup (KI-006, S1 top risk) on the existing remote
`github.com/LemuelHornsby/NaviSense`, replacing its dated history.

## Decisions (Lemuel)
- **Scope:** code + docs + configs + `.uproject` + **UE Content** (blueprints/level/data assets, 2.4 GB) +
  **ship models** (810 MB) via Git LFS. **Demo films (2.4 GB) excluded** (regenerable; HDD/cloud).
- **Remote:** replace the dated history with one clean authoritative snapshot (`--force`).
- **Feasibility:** GitHub Free now includes **10 GiB LFS storage + 10 GiB/mo bandwidth** (metered billing,
  data packs retired; verified on GitHub Docs 14 Jul 2026). ~3 GB LFS fits free.

## Changed files
- `.gitattributes` — LFS now also covers `*.3dm` (+ `*.tif/.tiff/.obj/.blend/.psd/.dds/.bmp/.stl/.3ds/.zip/.7z/.mov/.mkv/.avi/.uexp/.ubulk`).
- `.gitignore` — excludes `Demo/film/` (kept a `.gitkeep`) and `*.3dmbak`.
- `GIT_SETUP.md` — rewritten as a complete Windows runbook.
- Docs: KI-006 → IN PROGRESS, PROGRESS ledger, Test Log row.

## Finding (fixed)
`ship models/dolphin/dolphin.3dm` (339 MB) + its `.3dmbak` were **not** LFS-tracked ⇒ GitHub's **100 MB
non-LFS file limit** would have failed the push. Fixed: `*.3dm`→LFS, `*.3dmbak`→ignored. Sandbox audit
confirmed every remaining >95 MB would-commit file is LFS-patterned (biggest: `marine_rescue_boat.uasset`
494 MB, `excursion_vessel.uasset` 354 MB — both under LFS's 2 GiB/file cap).

## Gate / acceptance (Lemuel, on Windows)
Run `GIT_SETUP.md` §0–§4. **PASS =** the §2 pre-push audit prints only `LFS=True`, `git push … --force`
completes, and `github.com/LemuelHornsby/NaviSense` shows the tree with "Stored with Git LFS" badges.
⇒ then KI-006 RESOLVED (Test Log PASS, tester=Lemuel).

## Rollback
Config + docs only; nothing pushed from the sandbox. `.gitattributes`/`.gitignore` backups at
`/tmp/bak_gitattributes` / `/tmp/bak_gitignore` (this session); `git checkout` on Windows reverts any file.
