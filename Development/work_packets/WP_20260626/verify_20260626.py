#!/usr/bin/env python3
"""Gate WP-20260626 — the single-file HTML evidence report (D6 / WP-19).

Builds the evidence pack on a REAL logged run, then proves the new
``evidence_report.html`` is (a) a parseable HTML document, (b) genuinely
self-contained — every plot embedded as a *valid* base64 PNG with zero external
file refs, (c) numerically faithful to ``kpis.json`` (the page formats, never
re-derives), (d) carries the health verdict + all checks, (e) shows the AIS /
COLREGS section when traffic is present, and (f) is portable (opens standalone
in a directory containing only the .html).

6 gates + 3 negative controls (a corrupt embedded image is DETECTED, a wrong
KPI value is DETECTED, an injected external <img src> is FLAGGED) so a green
result means the checks actually bite, not just that clean data passes.

Read-only over logs/ + writes only the evidence_pack + the result JSON.
Exit 0 iff 6/6 gates pass AND 3/3 negative controls fire.
"""

from __future__ import annotations

import base64
import datetime as _dt
import html.parser
import json
import os
import re
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_PY = os.path.join(_ROOT, "python")
for p in (_PY, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import build_evidence_pack as bep   # noqa: E402
import verify_run_kinematics as vrk  # noqa: E402

RESULT = os.path.join(_ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports",
                      "wp_20260626_result.json")
DATA_URI_RE = re.compile(r'data:image/png;base64,([A-Za-z0-9+/=]+)')
EXT_REF_RE = re.compile(r'(?:src|href)\s*=\s*"(?!data:|https?:|#)([^"]+\.(?:png|jpg|jpeg|svg|css|js))"',
                        re.IGNORECASE)


# ------------------------------------------------------------ shared checks
def _images(html_text: str):
    """Return (n_found, n_valid_png) for embedded base64 PNG data URIs."""
    found = DATA_URI_RE.findall(html_text)
    valid = 0
    for b64 in found:
        try:
            raw = base64.b64decode(b64, validate=True)
        except Exception:                       # noqa: BLE001
            continue
        if raw[:8] == b"\x89PNG\r\n\x1a\n":
            valid += 1
    return len(found), valid


def _external_refs(html_text: str):
    return EXT_REF_RE.findall(html_text)


def _parses(html_text: str) -> bool:
    class _P(html.parser.HTMLParser):
        pass
    try:
        _P().feed(html_text)
        return True
    except Exception:                           # noqa: BLE001
        return False


def _expected_kpi_strings(kpis: dict):
    """Strings that MUST appear verbatim in the HTML (formatted from kpis.json)."""
    out = []
    mv = kpis.get("maneuver", {}) or {}
    kind = mv.get("kind")
    if kind == "turning_circle":
        if mv.get("tactical_diameter_m") is not None:
            out.append(f"{mv['tactical_diameter_m']:.2f} m")
        if mv.get("tactical_diameter_over_Lpp") is not None:
            out.append(f"{mv['tactical_diameter_over_Lpp']:.2f}")
        if mv.get("advance_m") is not None:
            out.append(f"{mv['advance_m']:.2f} m")
    elif kind == "zigzag":
        if mv.get("first_overshoot_deg") is not None:
            out.append(f"{mv['first_overshoot_deg']:.2f} deg")
    return out


def _parity_ok(html_text: str, kpis: dict) -> bool:
    return all(s in html_text for s in _expected_kpi_strings(kpis))


# ------------------------------------------------------------------ run pick
def _pick_run(log_root: str):
    """Newest real run (excluding _selftest) whose controller has IMO KPIs."""
    runs = []
    if os.path.isdir(log_root):
        for name in os.listdir(log_root):
            d = os.path.join(log_root, name)
            if name.startswith("_") or not os.path.isdir(d):
                continue
            if os.path.exists(os.path.join(d, "state.csv")):
                runs.append(d)
    runs.sort(key=lambda d: os.path.getmtime(d), reverse=True)
    for d in runs:
        rows = vrk._load_state_csv(os.path.join(d, "state.csv"))
        man = vrk._load_manifest(d)
        ctrl = vrk._controller_kind(man, rows)
        if ctrl in ("turning_circle", "turning", "turn") or "zigzag" in ctrl:
            return d
    return runs[0] if runs else None


# ---------------------------------------------------------------------- main
def main() -> int:
    log_root = os.path.join(_ROOT, "logs")
    run_dir = _pick_run(log_root)
    gates, negs = [], []

    def gate(gid, name, ok, detail):
        gates.append({"id": gid, "name": name, "passed": bool(ok), "detail": detail})

    def neg(nid, name, fired, detail):
        negs.append({"id": nid, "name": name, "fired": bool(fired), "detail": detail})

    if not run_dir:
        print("[verify] no usable run under logs/", file=sys.stderr)
        _write({"overall": "FAIL", "error": "no run"}, gates, negs)
        return 1

    # Build the pack with a scripted AIS preset so the AIS section is exercised.
    res = bep.build_pack(run_dir, make_plots=True, ais_preset="head_on", make_html=True)
    pack_dir = res["pack_dir"]
    html_path = res.get("report_html")
    kpis = json.load(open(os.path.join(pack_dir, "kpis.json"), encoding="utf-8"))
    htext = open(html_path, encoding="utf-8").read() if html_path and os.path.exists(html_path) else ""
    plots = kpis.get("plots", []) or []

    # G1 — builds + parses as HTML
    g1 = bool(htext) and htext.lstrip().startswith("<!DOCTYPE html>") \
        and "</html>" in htext and _parses(htext)
    gate("G1", "build_and_parse", g1,
         f"path={os.path.basename(html_path) if html_path else None} bytes={len(htext)} parses={_parses(htext)}")

    # G2 — every plot embedded as a VALID base64 PNG (no broken images)
    n_found, n_valid = _images(htext)
    g2 = n_found >= 2 and n_found == n_valid == len(plots)
    gate("G2", "plots_embedded_valid", g2,
         f"plots={len(plots)} data_uris={n_found} valid_png={n_valid}")

    # G3 — IMO KPI parity vs kpis.json (page formats, never re-derives)
    exp = _expected_kpi_strings(kpis)
    g3 = bool(exp) and _parity_ok(htext, kpis)
    gate("G3", "imo_kpi_parity", g3, f"expected={exp} all_present={g3}")

    # G4 — health verdict + every check id present
    verdict = kpis["health"]["verdict"]
    ids_present = all(c["id"] in htext for c in kpis["health"]["checks"])
    g4 = (f"HEALTH: {verdict}" in htext) and ids_present
    gate("G4", "health_present", g4,
         f"verdict={verdict} badge={'HEALTH: '+verdict in htext} all_check_ids={ids_present}")

    # G5 — AIS / COLREGS section present with the target's geometry + encounter
    ais = kpis.get("ais") or {}
    if ais and not ais.get("error") and ais.get("targets"):
        tg = ais["targets"][0]
        g5 = ("AIS traffic &amp; COLREGS encounters" in htext
              and str(tg.get("encounter_primary")) in htext
              and f"{tg.get('min_range_m'):.2f} m" in htext)
        d5 = (f"preset={ais.get('preset')} target={tg.get('name')} "
              f"encounter={tg.get('encounter_primary')} min_range={tg.get('min_range_m')}")
    else:
        g5 = False
        d5 = f"no AIS block (ais={ais})"
    gate("G5", "ais_colregs_section", g5, d5)

    # G6 — self-contained + portable: zero external refs, opens standalone
    ext = _external_refs(htext)
    portable = False
    try:
        tmp = tempfile.mkdtemp(prefix="navisense_report_")
        lone = os.path.join(tmp, "evidence_report.html")
        shutil.copyfile(html_path, lone)          # copy ONLY the html, no PNG siblings
        re_text = open(lone, encoding="utf-8").read()
        rn, rv = _images(re_text)
        portable = (rn == n_found == rv) and not _external_refs(re_text)
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception as e:                        # noqa: BLE001
        d6err = f"{type(e).__name__}: {e}"
    g6 = (len(ext) == 0) and portable
    gate("G6", "self_contained_portable", g6,
         f"external_refs={ext} portable_standalone={portable}")

    # N1 — a corrupted embedded image is DETECTED. Mutate the first 8 base64
    # chars (still valid base64, so it decodes) so the decoded PNG *magic* is
    # wrong -> proves _images validates the image bytes, not just the substring.
    m = DATA_URI_RE.search(htext)
    b0 = m.group(1)
    bad = ("A" * 8) + b0[8:]            # same length/parity; first bytes -> 0x00
    tampered = htext[:m.start(1)] + bad + htext[m.end(1):]
    tn, tv = _images(tampered)
    neg("N1", "corrupt_image_detected", tv < tn,
        f"after magic-tamper: found={tn} valid={tv} (valid<found => detected)")

    # N2 — a wrong KPI value is DETECTED (parity actually compares values)
    if exp:
        real = exp[0]
        wrong = "9999.99 m" if real.endswith(" m") else "9999.99"
        mutated = htext.replace(real, wrong, 1)
        neg("N2", "wrong_kpi_detected", not _parity_ok(mutated, kpis),
            f"replaced '{real}'->'{wrong}'; parity_now={_parity_ok(mutated, kpis)}")
    else:
        neg("N2", "wrong_kpi_detected", False, "no KPI strings to mutate")

    # N3 — an injected external <img src> is FLAGGED (self-containment guard bites)
    injected = htext.replace("</body>", '<img src="turning_circle.png"></body>', 1)
    neg("N3", "external_ref_flagged", len(_external_refs(injected)) >= 1,
        f"external_refs_after_inject={_external_refs(injected)}")

    passed = sum(1 for g in gates if g["passed"])
    fired = sum(1 for n in negs if n["fired"])
    overall = "PASS" if passed == len(gates) and fired == len(negs) else "FAIL"
    summary = {
        "packet": "WP-20260626",
        "theme": "Single-file HTML evidence report (D6 / WP-19)",
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "run_dir": os.path.basename(run_dir),
        "report_html": os.path.basename(html_path) if html_path else None,
        "report_bytes": len(htext),
        "gates_passed": passed,
        "gates_total": len(gates),
        "all_negative_controls_fired": fired == len(negs),
        "overall": overall,
    }
    _write(summary, gates, negs)

    print(f"[verify] WP-20260626 — run {os.path.basename(run_dir)}")
    for g in gates:
        print(f"  {g['id']} {g['name']:<24} {'PASS' if g['passed'] else 'FAIL'} — {g['detail']}")
    for n in negs:
        print(f"  {n['id']} {n['name']:<24} {'FIRED' if n['fired'] else 'MISS'} — {n['detail']}")
    print(f"[verify] {overall}: {passed}/{len(gates)} gates, {fired}/{len(negs)} controls -> {RESULT}")
    return 0 if overall == "PASS" else 1


def _write(summary, gates, negs):
    summary = dict(summary)
    summary["gates"] = gates
    summary["negative_controls"] = negs
    os.makedirs(os.path.dirname(RESULT), exist_ok=True)
    with open(RESULT, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    sys.exit(main())
