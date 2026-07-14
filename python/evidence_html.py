"""Single-file HTML evidence report for a NaviSense run (D6 / WP-19).

``write_html()`` renders the SAME already-computed structures that
``build_evidence_pack.build_pack`` assembles (meta / health / maneuver /
actuators / ais / plots) into one **self-contained** ``evidence_report.html``:

* every plot is embedded as a base64 ``data:`` URI (NO external file refs), so
  the single .html can be emailed / dropped into a grant portal and still shows
  its trajectory / heading / actuator / CPA plots,
* the IMO maneuvering KPIs carry the same numbers + PASS/FAIL marks as
  ``kpis.json`` (this module formats, it never re-derives — no drift),
* an honest provenance footer states what the numbers are and are NOT
  (visual seakeeping proxy, scripted AIS, MMG standard-method KPIs — KI-019).

Stdlib-only (base64 / html / os / datetime). Plotting/analysis stays in the
single-purpose analysers; this is a pure presentation layer.
"""

from __future__ import annotations

import base64
import datetime as _dt
import html
import os
from typing import Dict, List, Optional

REPORT_NAME = "evidence_report.html"


# --------------------------------------------------------------- formatting
def _esc(v) -> str:
    return html.escape("" if v is None else str(v))


def _fmt(v, suffix: str = "") -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.2f}{suffix}"
    return f"{v}{suffix}"


def _mark(b) -> str:
    return "n/a" if b is None else ("PASS" if b else "FAIL")


def _pill(label: str) -> str:
    u = (label or "").upper()
    if u in ("PASS", "OK", "YES"):
        cls = "ok"
    elif u in ("WARN",):
        cls = "warn"
    elif u in ("FAIL", "NO"):
        cls = "fail"
    else:
        cls = "muted"
    return f'<span class="pill {cls}">{_esc(label)}</span>'


def _img_data_uri(path: str) -> Optional[str]:
    """Read a PNG and return a base64 data URI (None if unreadable)."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    if not raw:
        return None
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{b64}"


# ------------------------------------------------------------------- styles
_CSS = """
:root{--bg:#0f1720;--card:#16212e;--ink:#e7edf3;--muted:#90a2b4;--line:#26384a;
--ok:#1f9d57;--okbg:#0e2c1d;--fail:#d2433b;--failbg:#321413;--warn:#c98a16;
--warnbg:#2e2410;--accent:#3aa0ff;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:32px 24px 64px}
header.top{border-bottom:1px solid var(--line);padding-bottom:18px;margin-bottom:24px}
header.top h1{margin:0 0 4px;font-size:24px;letter-spacing:.2px}
header.top .sub{color:var(--muted);font-size:13px}
h2{font-size:16px;margin:30px 0 10px;letter-spacing:.4px;text-transform:uppercase;
color:var(--accent)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:16px 18px;margin:12px 0}
.verdict{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.badge{font-weight:700;font-size:15px;padding:8px 16px;border-radius:8px;
border:1px solid transparent}
.badge.pass{background:var(--okbg);color:#5fe39a;border-color:#1f6e44}
.badge.fail{background:var(--failbg);color:#ff8a82;border-color:#7a2b27}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px 22px}
.kv{display:flex;flex-direction:column;padding:6px 0}
.kv .k{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.3px}
.kv .v{font-size:15px}
table{width:100%;border-collapse:collapse;margin:6px 0;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);
vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;
letter-spacing:.3px}
td.num{font-variant-numeric:tabular-nums}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;
font-weight:600;border:1px solid transparent}
.pill.ok{background:var(--okbg);color:#5fe39a;border-color:#1f6e44}
.pill.fail{background:var(--failbg);color:#ff8a82;border-color:#7a2b27}
.pill.warn{background:var(--warnbg);color:#f0c46a;border-color:#7a5e1c}
.pill.muted{background:#1b2735;color:var(--muted);border-color:var(--line)}
.note{border-left:3px solid var(--accent);background:#11202f;padding:10px 14px;
border-radius:0 8px 8px 0;color:var(--muted);font-size:13px;margin:10px 0}
figure{margin:14px 0}
figure img{width:100%;border:1px solid var(--line);border-radius:8px;background:#fff}
figcaption{color:var(--muted);font-size:12px;margin-top:6px}
footer{margin-top:36px;padding-top:16px;border-top:1px solid var(--line);
color:var(--muted);font-size:12px}
footer b{color:var(--ink)}
a{color:var(--accent)}
"""


# -------------------------------------------------------------- section bits
def _kv(k: str, v: str) -> str:
    return f'<div class="kv"><span class="k">{_esc(k)}</span><span class="v">{v}</span></div>'


def _run_section(meta: dict) -> str:
    cells = [
        _kv("Controller", f"<b>{_esc(meta.get('controller'))}</b>"),
        _kv("Plant", _esc(meta.get("plant"))),
        _kv("Sea state", _esc(meta.get("sea_state"))),
        _kv("Wave heading", _esc(_fmt(meta.get("wave_heading_deg"), " deg"))),
        _kv("Duration", _esc(_fmt(meta.get("duration_s"), " s"))),
        _kv("Tick", _esc(_fmt(meta.get("tick_hz"), " Hz"))),
        _kv("Lpp", _esc(f"{meta.get('Lpp_m'):.1f} m" if meta.get("Lpp_m") is not None else "n/a")),
        _kv("Est. service speed", _esc(_fmt(meta.get("service_speed_mps_est"), " m/s"))),
    ]
    if meta.get("scenario"):
        cells.insert(1, _kv("Scenario", f"<b>{_esc(meta.get('scenario'))}</b>"))
    if meta.get("sea_state_schedule"):
        cells.append(_kv("Sea-state schedule (D3)",
                         f"<code>{_esc(meta.get('sea_state_schedule'))}</code>"))
    if meta.get("started_local"):
        cells.append(_kv("Started", _esc(meta.get("started_local"))))
    return f'<div class="card"><div class="grid">{"".join(cells)}</div></div>'


def _health_section(health: dict) -> str:
    verdict = str(health.get("verdict", "n/a"))
    is_pass = verdict.upper() == "PASS"
    badge_cls = "pass" if is_pass else "fail"
    rows = []
    for c in health.get("checks", []):
        rows.append(
            f"<tr><td><code>{_esc(c.get('id'))}</code></td><td>{_esc(c.get('name'))}</td>"
            f"<td>{_pill(c.get('status'))}</td><td>{_esc(c.get('detail'))}</td></tr>")
    table = ("<table><thead><tr><th>ID</th><th>Check</th><th>Status</th><th>Detail</th>"
             "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>")
    k = health.get("ki018_corroboration") or {}
    note = ""
    if k:
        note = (f'<div class="note"><b>KI-018 (log-side):</b> entered &gt;180&deg; zone = '
                f'<code>{_esc(k.get("entered_180_zone"))}</code>, plant heading continuous = '
                f'<code>{_esc(k.get("plant_heading_continuous"))}</code>, effective turn radius = '
                f'<code>{_esc(k.get("effective_turn_radius_m"))} m</code>. {_esc(k.get("note"))}</div>')
    return (f'<div class="card"><div class="verdict"><span class="badge {badge_cls}">'
            f'HEALTH: {_esc(verdict)}</span><span class="muted">'
            f'{_esc(health.get("gates_passed"))}/{_esc(health.get("gates_total"))} '
            f'kinematic gates</span></div>{table}{note}</div>')


def _imo_section(maneuver: dict) -> str:
    kind = maneuver.get("kind")
    if kind == "turning_circle":
        rows = [
            ("Advance A", _fmt(maneuver.get("advance_m"), " m"),
             f"A/Lpp {_fmt(maneuver.get('advance_over_Lpp'))} (limit 4.5)",
             _mark(maneuver.get("imo_advance_pass"))),
            ("Transfer T", _fmt(maneuver.get("transfer_m"), " m"), "", ""),
            ("Tactical diameter DT", _fmt(maneuver.get("tactical_diameter_m"), " m"),
             f"DT/Lpp {_fmt(maneuver.get('tactical_diameter_over_Lpp'))} (limit 5.0)",
             _mark(maneuver.get("imo_tactical_diameter_pass"))),
            ("Steady turning radius R", _fmt(maneuver.get("steady_radius_m"), " m"),
             f"drift &beta; {_fmt(maneuver.get('steady_drift_deg'), ' deg')}", ""),
            ("Time to 90&deg; / 180&deg;",
             f"{_fmt(maneuver.get('time_to_90_s'), ' s')} / {_fmt(maneuver.get('time_to_180_s'), ' s')}",
             "", ""),
        ]
        title = "Turning circle &mdash; IMO MSC.137(76)"
    elif kind == "zigzag":
        ang = maneuver.get("angle_deg", 0.0) or 0.0
        rows = [
            ("1st overshoot", _fmt(maneuver.get("first_overshoot_deg"), " deg"), "",
             _mark(maneuver.get("imo_first_overshoot_pass"))),
            ("2nd overshoot", _fmt(maneuver.get("second_overshoot_deg"), " deg"), "",
             _mark(maneuver.get("imo_second_overshoot_pass"))),
            ("Period", _fmt(maneuver.get("period_s"), " s"),
             f"reversals at {[round(x,1) for x in maneuver.get('reversal_times_s', [])]}", ""),
        ]
        title = f"Zig-zag {ang:.0f}/{ang:.0f} &mdash; IMO MSC.137(76)"
    else:
        msg = _esc(maneuver.get("error") or f"no IMO KPI module for controller '{kind}'")
        return (f'<div class="card"><div class="note">No IMO maneuver KPIs for this '
                f'controller. {msg}</div></div>')
    trs = []
    for name, value, crit, mk in rows:
        pill = _pill(mk) if mk else ""
        trs.append(f"<tr><td>{name}</td><td class='num'>{_esc(value)}</td>"
                   f"<td class='muted'>{crit}</td><td>{pill}</td></tr>")
    body = ("<table><thead><tr><th>Metric</th><th>Value</th><th>Criterion</th>"
            "<th>IMO</th></tr></thead><tbody>" + "".join(trs) + "</tbody></table>")
    err = ""
    if maneuver.get("error"):
        err = f'<div class="note">&#9888; analysis note: {_esc(maneuver["error"])}</div>'
    return f'<div class="card"><b>{title}</b>{body}{err}</div>'


def _actuator_section(actuators: dict) -> str:
    if not actuators:
        return ""
    trs = []
    for name, s in actuators.items():
        moved = "yes" if s.get("achieved_changed") else "NO"
        trs.append(f"<tr><td>{_esc(name)}</td><td class='num'>{_esc(s.get('mean_abs_err'))}</td>"
                   f"<td class='num'>{_esc(s.get('max_abs_err'))}</td>"
                   f"<td class='num'>{_esc(s.get('rms_err'))}</td><td>{_pill(moved)}</td></tr>")
    return ('<div class="card"><table><thead><tr><th>Axis</th><th>mean |err|</th>'
            '<th>max |err|</th><th>rms</th><th>moved</th></tr></thead><tbody>'
            + "".join(trs) + "</tbody></table></div>")


def _ais_section(ais: Optional[dict]) -> str:
    if ais is None:
        return ""
    if ais.get("error"):
        return (f'<h2>AIS traffic &amp; COLREGS</h2><div class="card"><div class="note">'
                f'&#9888; AIS analysis note: {_esc(ais["error"])}</div></div>')
    head = (f'Scripted traffic preset <b>{_esc(ais.get("preset"))}</b> &mdash; '
            f'{_esc(ais.get("n_targets"))} target(s); CPA alert range '
            f'{_fmt(ais.get("alert_range_m"))} m. Own-ship start heading '
            f'{_fmt(ais.get("own_heading0_deg"))} deg. Ranges/bearings are from own-ship; '
            f'CPA/TCPA + encounter use the constant-velocity closed form (COLREGS Rules 13-15).')
    trs = []
    for tg in ais.get("targets", []):
        trs.append(
            f"<tr><td>{_esc(tg.get('name'))}</td><td class='num'>{_esc(tg.get('mmsi'))}</td>"
            f"<td>{_esc(tg.get('ship_type'))}</td>"
            f"<td class='num'>{_fmt(tg.get('min_range_m'), ' m')}</td>"
            f"<td class='num'>{_fmt(tg.get('min_cpa_m'), ' m')}</td>"
            f"<td class='num'>{_fmt(tg.get('tcpa_at_min_cpa_s'), ' s')}</td>"
            f"<td>{_esc(tg.get('encounter_primary'))}</td>"
            f"<td>{_esc(tg.get('duty_primary'))}</td>"
            f"<td>{_pill('YES' if tg.get('alerted') else 'no')}</td></tr>")
    table = ('<table><thead><tr><th>Target</th><th>MMSI</th><th>Type</th><th>Min range</th>'
             '<th>CPA</th><th>TCPA</th><th>Encounter</th><th>Own duty</th><th>Alert</th>'
             '</tr></thead><tbody>' + "".join(trs) + "</tbody></table>")
    note = ('<div class="note">AIS targets are scripted, deterministic contacts &mdash; '
            'not a live AIS receiver. Rendering them as UE pawns + carrying mmsi/cog/sog on '
            'sensor.v1 is the in-engine follow-up (WP-15B); this pack delivers the validated '
            'data/analysis half of D4. See <code>ais.csv</code> for the per-target series.</div>')
    conf = ais.get("conformance") if isinstance(ais, dict) else None
    conf_html = ""
    if conf and not conf.get("error"):
        _cls = {"compliant": "ok", "non_compliant": "fail", "not_applicable": "muted"}
        _lbl = {"compliant": "COMPLIANT", "non_compliant": "NON-COMPLIANT",
                "not_applicable": "n/a"}
        crows = []
        for tg in conf.get("targets", []):
            v = tg.get("verdict", "")
            pill = f'<span class="pill {_cls.get(v, "muted")}">{_lbl.get(v, _esc(v))}</span>'
            if v == "compliant":
                finding = "all applicable rule checks passed"
            elif tg.get("reasons"):
                finding = tg["reasons"][0]
            else:
                finding = "no maneuvering duty"
            crows.append(
                f"<tr><td>{_esc(tg.get('name'))}</td><td>{_esc(tg.get('encounter'))}</td>"
                f"<td>{_esc(tg.get('duty'))}</td><td>{pill}</td>"
                f"<td class='num'>{_fmt(tg.get('net_alteration_deg'), ' deg')}</td>"
                f"<td class='num'>{_fmt(tg.get('achieved_miss_m'), ' m')}</td>"
                f"<td>{_esc(finding)}</td></tr>")
        ctable = ('<table><thead><tr><th>Target</th><th>Encounter</th><th>Duty</th>'
                  '<th>Verdict</th><th>Net alteration</th><th>Achieved miss</th>'
                  '<th>Key finding</th></tr></thead><tbody>' + "".join(crows)
                  + "</tbody></table>")
        csum = (f'<p style="margin-top:18px"><b>COLREGS conformance scoring</b> '
                f'(V&amp;V differentiator) &mdash; {_esc(conf.get("compliant"))} compliant / '
                f'{_esc(conf.get("non_compliant"))} non-compliant / '
                f'{_esc(conf.get("not_applicable"))} n/a. COLREGS Rules 8 / 13&ndash;17.</p>')
        cnote = ('<div class="note">An automated check of whether the own-ship maneuver in '
                 'this run conformed to the COLREGS duty for each encounter. The demo '
                 'own-ship runs a FIXED maneuvering controller and does <b>not</b> yet '
                 'perform autonomous COLREGS avoidance (week 5&ndash;6 roadmap), so a held '
                 'course into a give-way duty is correctly scored non-compliant &mdash; this '
                 'is the V&amp;V scoring metric, not an autonomy claim.</div>')
        conf_html = csum + ctable + cnote
    return (f'<h2>AIS traffic &amp; COLREGS encounters</h2>'
            f'<div class="card">{head}{table}{note}{conf_html}</div>')


def _plots_section(pack_dir: str, plots: List[str]) -> str:
    if not plots:
        return ""
    figs = []
    for p in plots:
        uri = _img_data_uri(os.path.join(pack_dir, p))
        if not uri:
            continue
        figs.append(f'<figure><img alt="{_esc(p)}" src="{uri}">'
                    f'<figcaption>{_esc(p)} (embedded)</figcaption></figure>')
    if not figs:
        return ""
    return f'<h2>Plots</h2><div class="card">{"".join(figs)}</div>'


# ----------------------------------------------------------------- assembler
def write_html(pack_dir: str, meta: dict, health: dict, maneuver: dict,
               actuators: dict, plots: List[str], ais: Optional[dict],
               generator: str = "build_evidence_pack.py") -> str:
    """Render the self-contained report and return its path."""
    gen_at = meta.get("generated_at") or _dt.datetime.now().isoformat(timespec="seconds")
    parts: List[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="en"><head><meta charset="utf-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    parts.append(f"<title>NaviSense evidence &mdash; {_esc(meta.get('run_dir'))}</title>")
    parts.append(f"<style>{_CSS}</style></head><body><div class='wrap'>")
    parts.append("<header class='top'>"
                 "<h1>NaviSense &mdash; Maneuvering Evidence Pack</h1>"
                 f"<div class='sub'>Run <b>{_esc(meta.get('run_dir'))}</b> &middot; "
                 f"generated {_esc(gen_at)} &middot; {_esc(generator)}</div></header>")
    parts.append("<h2>Run</h2>")
    parts.append(_run_section(meta))
    parts.append("<h2>Kinematic health (objective gate)</h2>")
    parts.append(_health_section(health))
    parts.append("<h2>IMO maneuvering KPIs</h2>")
    parts.append(_imo_section(maneuver))
    parts.append("<h2>Actuator correspondence (commanded vs achieved)</h2>")
    parts.append(_actuator_section(actuators))
    parts.append(_ais_section(ais))
    parts.append(_plots_section(pack_dir, plots))
    parts.append(
        "<footer><b>Provenance &amp; honesty.</b> The IMO maneuvering KPIs above are "
        "computed by the MMG standard-method plant (Kijima&ndash;Yoshimura empirical "
        "regression for the DOLPHIN 40 m yacht) &mdash; they are <b>not</b> CFD- or "
        "model-test-validated (that campaign is underway). Roll / pitch / heave are a "
        "deterministic <b>visual seakeeping proxy</b>, not a buoyancy/hydrostatics "
        "simulation. AIS targets are <b>scripted</b> deterministic contacts, not a live "
        "receiver; COLREGS conformance verdicts score the maneuver that was "
        "<b>logged</b> &mdash; the demo own-ship does not yet perform autonomous "
        "COLREGS avoidance. All figures are reproduced verbatim from "
        "<code>kpis.json</code>; this "
        "page only formats them. Plots are embedded (this file is self-contained).</footer>")
    parts.append("</div></body></html>")
    out = os.path.join(pack_dir, REPORT_NAME)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts) + "\n")
    return out
