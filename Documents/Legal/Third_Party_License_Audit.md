# Third-Party License & Content Audit

**Version 0.1 · 14 July 2026.** Complete before: any paid demo, the community alpha (25 Aug), and any grant that asks about IP. Rule: a row is CLEAR only with a link/quote to the governing terms filed in the notes column; "probably fine" is OPEN.

| # | Asset / dependency | Where used | License / terms | Commercial use | Redistribute in builds | In film/stills/marketing | Status | Action |
|---|---|---|---|---|---|---|---|---|
| 1 | Unreal Engine 5.7 | NaviSense_UE5 | Epic EULA — **which regime applies to a sold tool: royalty vs Unreal Subscription?** | ? | ? | OK for dev media | **OPEN** | Written confirmation from Epic before pricing; affects MegaGrants posture |
| 2 | Cesium for Unreal plugin | Georeferencing | Apache-2.0 (plugin) | OK | OK | OK | CLEAR (plugin only) | file link |
| 3 | Cesium ion (tiles/terrain service) | Monaco world | ion plan tier terms | ? (tier-dependent) | streaming only? | ? | **OPEN** | Confirm tier limits for commercial demos + deliverables |
| 4 | Google Photorealistic 3D Tiles (via ion) | Monaco visuals | Google Maps Platform terms — display restrictions, no offline/derived caching | ? | likely NO | **? for recorded film** | **OPEN — HIGH** | Verify before the demo film ships in marketing |
| 5 | OpenStreetMap extracts (`osm_extraction/`) | Port/world data | ODbL — attribution + share-alike on derived *databases* | OK w/ attribution | check derived-DB clause | OK w/ attribution | **OPEN** | Add attribution; assess whether port models = derived database |
| 6 | DOLPHIN hull geometry + derived data | Plant, content, renders | Design-group consent (see Letter) | pending | pending | pending | **OPEN — HIGH** | Signatures |
| 7 | Marketplace/Fab content in `Content/` (audit each: water, props, textures, audio in `Audio/`) | UE project | per-asset EULA | usually OK in builds | usually NO source redist | usually OK | **OPEN** | Inventory pass: list every non-original asset here |
| 8 | Python deps (`requirements.txt`) | core | mostly MIT/BSD/Apache | OK | OK | n/a | OPEN | Generate `pip-licenses` report, attach |
| 9 | Ship models (`ship models/`, AIS traffic pawns) | traffic visuals | source? | ? | ? | ? | **OPEN** | Identify origin per model |
| 10 | Fonts/logos/brand art (`Image References/`) | marketing | source? | ? | ? | ? | OPEN | Confirm origin/licenses |
| 11 | Real ship names used for AIS targets (KI-035 feature) | demos | not IP, but avoid implying endorsement | — | — | caution | NOTE | Use fictional names in public marketing |

**Standing rules.** New dependency ⇒ new row before merge. The community-alpha repo must carry: LICENSE files (per the open-core split), a NOTICE file with OSM/Cesium attributions, and no Marketplace-sourced content in the open portion. Re-audit at every packaging change.
