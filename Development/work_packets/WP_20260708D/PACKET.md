# WP-20260708D -- Preflight stale rebuild-guidance fix (KI-032)

*Manual on-demand session, 8 Jul 2026 (outside the normal 07:00 schedule), run after
WP-20260708 / WP-20260708B / WP-20260708C already closed earlier today.*

## State at session start

Everything headless was already DEMO READY (T-3, target 11 Jul):

- `Z0` compile-readiness **16/16**, stacked link audit green.
- `preflight_demo.py --report-only` -> **GO** (rebuild-safety + `demo_rehearsal` DEMO READY
  4/4, gates D1/D2/D3/D4/D6 covered headless).
- `PENDING_EDITOR_GATES.md` (refreshed this morning, WP-20260708B) already states **Step 0
  (the full C++ rebuild) is CLEARED 7 Jul** and re-scopes the one remaining human session to
  Steps 1-4 (PIE + capture + dashboard + film) -- "Do NOT rebuild again."

Re-running today's regression (`verify_compile_readiness.py`, `preflight_demo.py
--report-only`) to confirm nothing drifted since WP-20260708C surfaced a real, if small,
problem: **`preflight_demo.py`'s own GO-branch guidance was stale.**

## Goal

Fix `preflight_demo.py` so a GO run doesn't tell Lemuel to do something that could waste the
one remaining PIE/capture slot three days before the demo.

## Bug (KI-032)

`preflight_demo.py` (authored 5 Jul, WP-20260705) hardcodes its "next steps" line:

```
next : proceed with PENDING_EDITOR_GATES.md Step 0 (full C++ rebuild, editor CLOSED)
       -> Steps 1-3 (PIE + capture).
```

That was accurate on 5 Jul. It has been **wrong since 7 Jul**, when Lemuel cleared Step 0
(`Build: 53 succeeded, 0 failed`) and WP-20260708B re-scoped the run sheet to Steps 1-4. The
preflight script never re-reads `PENDING_EDITOR_GATES.md` -- it just prints the same
hardcoded string every time it says GO. Left as-is, a demo-week GO run actively tells Lemuel
to redo a rebuild he already completed, burning time and re-opening rebuild risk for no
reason, three days out.

No one hit this yet only because WP-20260708B/C both ran the underlying tools directly
rather than reading the preflight's printed guidance -- but the next `preflight_demo.py
--report-only` Lemuel runs before his PIE session would have shown it.

## Fix

`preflight_demo.py`, GO branch only (`_print()`, ~line 126): the hardcoded step-count string
is replaced with a pointer to `PENDING_EDITOR_GATES.md` as the single source of truth, plus
an explicit instruction to check its header for Step 0's status before rebuilding again. This
also makes the message evergreen -- it can't go stale again the next time a step is cleared,
because it no longer encodes step numbers.

The NO-GO branch (`"FIX the flagged check BEFORE the PIE session..."`) is untouched (proven
by gate N3 below).

## Changed files

- `preflight_demo.py` (workspace root) -- GO-branch guidance text only. No logic change: the
  `decide()` aggregation, the three underlying checks (Z0, link audit, `demo_rehearsal`), and
  the NO-GO branch are byte-identical. Edited via shell (`python3` heredoc + assert-guarded
  `str.replace`), per the CLAUDE.md D: truncation guard -- never the editor tool. Verified
  156 lines (was 154), `py_compile` clean, `(`/`)` balanced (79/79).
- `python/verify_20260708d.py` (new) -- acceptance gate, see below.

No C++/wire/DTO/schema/product-behavior change. No rebuild required or triggered.

## Acceptance gates -- `python/verify_20260708d.py`

**4/4 gates + 3/3 negative controls, PASS:**

| Gate | Result |
|---|---|
| G1 stale text gone | the old hardcoded string is no longer anywhere in the file |
| G2 new text present | live `--report-only` stdout references `PENDING_EDITOR_GATES.md`, no fixed step count |
| G3 parses | `py_compile` clean |
| G4 regression | `Z0` 16/16 AND `preflight_demo.py --report-only` still exits 0 (GO) |

Negative controls (prove the checks actually discriminate, not rubber-stamp):
N1 a fixture still containing the old string is caught by the same detector; N2 a fixture
missing the `PENDING_EDITOR_GATES.md` reference is caught; N3 the NO-GO branch text is
verified byte-identical to before the edit.

Evidence: `NaviSense_UE5/Saved/NaviSense_Reports/wp_20260708d_result.json`.

## Lemuel's in-editor/terminal steps

**None required for this packet** -- it is a text-only fix to a headless script, already
verified on disk. Nothing to run.

This does **not** change what's on `PENDING_EDITOR_GATES.md`: the one remaining action is
still your single PIE/capture session (Steps 1-4, ~40-50 min), unchanged from this morning's
WP-20260708B refresh.

## Rollback

`preflight_demo.py`'s GO-branch print statement reverts to the WP-20260705 original (restore
the two-line hardcoded string quoted under "Bug" above); no other file is touched by rollback.
