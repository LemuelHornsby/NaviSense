"""Consolidated demo evidence-pack generator for NaviSense run logs (D6).

Given one logged run, this produces a single demo-ready bundle under
``logs/<run>/evidence_pack/``:

* ``kpis.json``    — machine-readable: run metadata, the kinematic-health
                     verdict (verify_run_kinematics), the IMO maneuvering KPIs
                     (turning circle OR zig-zag, auto-selected by controller),
                     and actuator-correspondence stats.
* ``EVIDENCE.md``  — a human/demo-facing report of the same, with IMO
                     pass/fail and pointers to the plots.
* ``*.png``        — trajectory / heading / actuator plots (when matplotlib is
                     available; skipped gracefully otherwise).

It orchestrates the existing single-purpose analysers
(``analyse_turning_circle``, ``analyse_zigzag``, ``analyse_actuators``,
``verify_run_kinematics``) rather than re-deriving anything, so the numbers
match those tools exactly. Pure read-only over logs — it never touches the
wire, the listener, or any source of truth.

Usage:
    python python/build_evidence_pack.py                       # latest run
    python python/build_evidence_pack.py --run-dir logs/<run>
    python python/build_evidence_pack.py --run-dir logs/<run> --L-pp 38 --no-plot
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import re
import sys
from typing import Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import analyse_turning_circle as atc      # noqa: E402
import analyse_zigzag as azz              # noqa: E402
import analyse_actuators as aac           # noqa: E402
import verify_run_kinematics as vrk       # noqa: E402
import analyse_ais as aais                # noqa: E402
import colregs_score as colregs          # noqa: E402
import evidence_html                 # noqa: E402

GENERATOR = "build_evidence_pack.py v2.1 (WP_20260713, P0 view gate; prev v2 WP-20260626)"
DEFAULT_LPP = 38.0   # DOLPHIN, matches analyse_turning_circle default


# ----------------------------------------------------------------- helpers
def _latest_run(log_root: str) -> Optional[str]:
    return vrk._latest_run(log_root)


def _f(row: dict, key: str) -> Optional[float]:
    return vrk._f(row, key)


def _service_speed_mps(rows: List[dict]) -> float:
    """Estimate service speed = peak speed magnitude during the approach phase
    (falls back to the whole-run peak, then a sane default)."""
    appr = [(_f(r, "speed_mag") or 0.0) for r in rows
            if (r.get("mode", "") or "").strip().lower() == "approach"]
    if appr and max(appr) > 0.1:
        return max(appr)
    allsp = [(_f(r, "speed_mag") or 0.0) for r in rows]
    if allsp and max(allsp) > 0.1:
        return max(allsp)
    return 6.0


def _zigzag_angle_from(controller: str) -> Optional[float]:
    m = re.search(r"(\d+)", controller or "")
    return float(m.group(1)) if m else None


# ----------------------------------------------------------------- KPI builders
def _turning_kpis(rows: List[dict], L_pp: float) -> Dict[str, object]:
    m = atc.compute_metrics(rows)
    adv_ratio = (m.advance_m / L_pp) if m.advance_m else None
    dt_ratio = (m.tactical_diameter_m / L_pp) if m.tactical_diameter_m else None
    return {
        "kind": "turning_circle",
        "advance_m": m.advance_m,
        "transfer_m": m.transfer_m,
        "tactical_diameter_m": m.tactical_diameter_m,
        "steady_radius_m": m.steady_radius_m,
        "steady_drift_deg": m.steady_drift_deg,
        "time_to_90_s": m.time_to_90_s,
        "time_to_180_s": m.time_to_180_s,
        "advance_over_Lpp": adv_ratio,
        "tactical_diameter_over_Lpp": dt_ratio,
        "imo_advance_pass": (adv_ratio <= 4.5) if adv_ratio is not None else None,
        "imo_tactical_diameter_pass": (dt_ratio <= 5.0) if dt_ratio is not None else None,
        "imo_report": atc.imo_report(m, L_pp),
        "_metrics": m,
    }


def _zigzag_kpis(rows: List[dict], angle_deg: float, V_mps: float, L_pp: float) -> Dict[str, object]:
    m = azz.compute_metrics(rows, angle_deg)
    o1 = m.overshoots_deg[0] if len(m.overshoots_deg) >= 1 else None
    o2 = m.overshoots_deg[1] if len(m.overshoots_deg) >= 2 else None
    imo1 = imo2 = None
    if abs(angle_deg - 10.0) < 1e-3:
        v_kn = V_mps * 1.94384
        lim1 = 10.0 + (5.0 * L_pp / max(v_kn, 0.1))
        imo1 = (o1 <= lim1) if o1 is not None else None
        imo2 = (o2 <= 25.0) if o2 is not None else None
    elif abs(angle_deg - 20.0) < 1e-3:
        imo1 = (o1 <= 25.0) if o1 is not None else None
    return {
        "kind": "zigzag",
        "angle_deg": m.angle_deg,
        "overshoots_deg": m.overshoots_deg,
        "first_overshoot_deg": o1,
        "second_overshoot_deg": o2,
        "period_s": m.period_s,
        "reversal_times_s": m.reversal_times_s,
        "service_speed_mps": V_mps,
        "imo_first_overshoot_pass": imo1,
        "imo_second_overshoot_pass": imo2,
        "imo_report": azz.imo_report(m, V_mps, L_pp),
        "_metrics": m,
    }


def _actuator_kpis(rows: List[dict]) -> Dict[str, dict]:
    axes = [
        ("rudder", "rudderCmdDeg", "rudderDeg"),
        ("port_rpm", "portRpmCmd", "portRpm"),
        ("starboard_rpm", "starboardRpmCmd", "starboardRpm"),
        ("bow_thruster", "bowThrusterCmdNorm", "bowThrusterNorm"),
    ]
    out: Dict[str, dict] = {}
    for name, ck, ak in axes:
        cmd = [(_f(r, ck) or 0.0) for r in rows]
        ach = [(_f(r, ak) or 0.0) for r in rows]
        mean_e, max_e, rms_e, changed = aac.stats(cmd, ach)
        out[name] = {"mean_abs_err": round(mean_e, 4), "max_abs_err": round(max_e, 4),
                     "rms_err": round(rms_e, 4), "achieved_changed": changed}
    return out


# ----------------------------------------------------------------- plots
def _make_plots(rows: List[dict], maneuver: Dict[str, object], pack_dir: str) -> List[str]:
    made: List[str] = []
    try:
        import matplotlib       # noqa: F401
    except ImportError:
        print("[evidence] matplotlib not installed; skipping plots.", file=sys.stderr)
        return made
    kind = maneuver.get("kind")
    try:
        if kind == "turning_circle":
            p = os.path.join(pack_dir, "turning_circle.png")
            atc.make_plot(rows, maneuver["_metrics"], p)
            made.append(os.path.basename(p))
        elif kind == "zigzag":
            p = os.path.join(pack_dir, "zigzag.png")
            azz.make_plot(rows, maneuver["_metrics"], p)
            made.append(os.path.basename(p))
    except Exception as e:                       # noqa: BLE001 - plotting must never break the pack
        print(f"[evidence] maneuver plot failed: {e}", file=sys.stderr)
    try:
        p = os.path.join(pack_dir, "actuators.png")
        aac.make_plot(rows, p)
        made.append(os.path.basename(p))
    except Exception as e:                       # noqa: BLE001
        print(f"[evidence] actuator plot failed: {e}", file=sys.stderr)
    return made


# ----------------------------------------------------------------- markdown
def _fmt(v, suffix=""):
    return "n/a" if v is None else (f"{v:.2f}{suffix}" if isinstance(v, float) else f"{v}{suffix}")


def _imo_mark(b):
    return "n/a" if b is None else ("PASS" if b else "FAIL")


def _write_markdown(pack_dir: str, meta: dict, health: dict, maneuver: dict,
                    actuators: dict, plots: List[str], ais: Optional[dict] = None) -> str:
    L: List[str] = []
    L.append(f"# NaviSense evidence pack — {meta['run_dir']}")
    L.append("")
    L.append(f"*Generated {meta['generated_at']} by {GENERATOR}.*")
    L.append("")
    if meta.get("view_complete") is False:
        L.append("> \u26a0 **PARTIAL VIEW (KI-038)** - built with `--allow-partial`: "
                 f"{meta.get('view_note')}. NOT demo evidence; rebuild where the "
                 "full run log is visible.")
        L.append("")
    L.append("## Run")
    L.append("")
    L.append(f"- Controller: **{meta['controller']}** · plant: {meta['plant']} · "
             f"sea state: {meta['sea_state']} · wave heading: {_fmt(meta['wave_heading_deg'],' deg')}")
    if meta.get("scenario"):
        L.append(f"- Scenario: **{meta['scenario']}**")
    if meta.get("sea_state_schedule"):
        L.append(f"- Runtime sea-state schedule (D3): `{meta['sea_state_schedule']}` "
                 f"(t:ss set-points, cross-faded)")
    L.append(f"- Duration: {_fmt(meta['duration_s'],' s')} · tick: {_fmt(meta['tick_hz'],' Hz')} · "
             f"Lpp: {meta['Lpp_m']:.1f} m · est. service speed: {meta['service_speed_mps_est']:.2f} m/s")
    L.append("")
    L.append("## Kinematic health (objective gate)")
    L.append("")
    L.append(f"**Verdict: {health['verdict']} ({health['gates_passed']}/{health['gates_total']} gates).**")
    L.append("")
    for c in health["checks"]:
        L.append(f"- `{c['id']}` {c['name']} — **{c['status']}**: {c['detail']}")
    k = health["ki018_corroboration"]
    L.append("")
    L.append(f"> **KI-018 (log-side):** entered >180 deg zone = `{k['entered_180_zone']}`, "
             f"plant heading continuous = `{k['plant_heading_continuous']}`, "
             f"effective turn radius = `{k['effective_turn_radius_m']} m`. {k['note']}")
    L.append("")
    L.append("## IMO maneuvering KPIs")
    L.append("")
    if maneuver.get("kind") == "turning_circle":
        L.append("Turning circle (IMO MSC.137(76)):")
        L.append("")
        L.append(f"- Advance A = **{_fmt(maneuver['advance_m'],' m')}** "
                 f"(A/Lpp = {_fmt(maneuver['advance_over_Lpp'])}, limit 4.5 — "
                 f"**{_imo_mark(maneuver['imo_advance_pass'])}**)")
        L.append(f"- Transfer T = {_fmt(maneuver['transfer_m'],' m')}")
        L.append(f"- Tactical diameter DT = **{_fmt(maneuver['tactical_diameter_m'],' m')}** "
                 f"(DT/Lpp = {_fmt(maneuver['tactical_diameter_over_Lpp'])}, limit 5.0 — "
                 f"**{_imo_mark(maneuver['imo_tactical_diameter_pass'])}**)")
        L.append(f"- Steady turning radius R = {_fmt(maneuver['steady_radius_m'],' m')} · "
                 f"steady drift beta = {_fmt(maneuver['steady_drift_deg'],' deg')}")
        L.append(f"- Time to 90 deg = {_fmt(maneuver['time_to_90_s'],' s')} · "
                 f"to 180 deg = {_fmt(maneuver['time_to_180_s'],' s')}")
    elif maneuver.get("kind") == "zigzag":
        L.append(f"Zig-zag {maneuver['angle_deg']:.0f}/{maneuver['angle_deg']:.0f} (IMO MSC.137(76)):")
        L.append("")
        L.append(f"- 1st overshoot = **{_fmt(maneuver['first_overshoot_deg'],' deg')}** "
                 f"(**{_imo_mark(maneuver['imo_first_overshoot_pass'])}**)")
        L.append(f"- 2nd overshoot = **{_fmt(maneuver['second_overshoot_deg'],' deg')}** "
                 f"(**{_imo_mark(maneuver['imo_second_overshoot_pass'])}**)")
        L.append(f"- Period = {_fmt(maneuver['period_s'],' s')} · "
                 f"reversals at {[round(x,1) for x in maneuver['reversal_times_s']]}")
    else:
        L.append(f"_No IMO maneuver KPIs for controller '{meta['controller']}'._")
    if maneuver.get("error"):
        L.append("")
        L.append(f"> ⚠ maneuver analysis note: {maneuver['error']}")
    L.append("")
    L.append("## Actuator correspondence (commanded vs achieved)")
    L.append("")
    L.append("| Axis | mean \\|err\\| | max \\|err\\| | rms | moved |")
    L.append("|---|---|---|---|---|")
    for name, s in actuators.items():
        L.append(f"| {name} | {s['mean_abs_err']} | {s['max_abs_err']} | {s['rms_err']} | "
                 f"{'yes' if s['achieved_changed'] else 'NO'} |")
    if ais is not None:
        L.append("")
        L.append("## AIS traffic & COLREGS encounters (gate D4 / WP-15)")
        L.append("")
        if ais.get("error"):
            L.append(f"> ⚠ AIS analysis note: {ais['error']}")
        else:
            L.append(f"Scripted traffic preset **{ais['preset']}** — {ais['n_targets']} "
                     f"target(s); CPA alert range {ais['alert_range_m']:.0f} m. Own-ship "
                     f"start heading {ais['own_heading0_deg']:.0f} deg. Ranges/bearings "
                     f"are from own-ship; CPA/TCPA + encounter use the constant-velocity "
                     f"closed form (COLREGS Rules 13-15).")
            L.append("")
            L.append("| Target | MMSI | Type | Min range | CPA | TCPA | Encounter | Own duty | Alert |")
            L.append("|---|---|---|---|---|---|---|---|---|")
            for tg in ais["targets"]:
                L.append(
                    f"| {tg['name']} | {tg['mmsi']} | {tg['ship_type']} | "
                    f"{_fmt(tg['min_range_m'],' m')} | {_fmt(tg['min_cpa_m'],' m')} | "
                    f"{_fmt(tg['tcpa_at_min_cpa_s'],' s')} | {tg['encounter_primary']} | "
                    f"{tg['duty_primary']} | {'YES' if tg['alerted'] else 'no'} |")
            L.append("")
            L.append("> AIS targets are scripted contacts (deterministic). Rendering them "
                     "as UE pawns + putting mmsi/cog/sog on sensor.v1 is the in-engine "
                     "follow-up (WP-15B); this pack delivers the validated data/analysis "
                     "half of D4. See `ais.csv` for the full per-target time series.")
            conf = ais.get("conformance")
            if conf and not conf.get("error"):
                L.append("")
                L.append("### COLREGS conformance scoring (V&V differentiator)")
                L.append("")
                L.append(f"Automated rule-conformance verdict for the own-ship maneuver in "
                         f"this run: **{conf['compliant']} compliant**, "
                         f"**{conf['non_compliant']} non-compliant**, "
                         f"{conf['not_applicable']} n/a (no risk-bearing encounter). "
                         f"COLREGS Rules 8 / 13-17.")
                L.append("")
                L.append("| Target | Encounter | Duty | Verdict | Net alteration | "
                         "Achieved miss | Key finding |")
                L.append("|---|---|---|---|---|---|---|")
                _verd = {"compliant": "COMPLIANT", "non_compliant": "NON-COMPLIANT",
                         "not_applicable": "n/a"}
                for tg in conf.get("targets", []):
                    if tg["verdict"] == "compliant":
                        finding = "all applicable rule checks passed"
                    elif tg.get("reasons"):
                        finding = tg["reasons"][0]
                    else:
                        finding = "no maneuvering duty"
                    L.append(f"| {tg['name']} | {tg['encounter']} | {tg['duty']} | "
                             f"{_verd.get(tg['verdict'], tg['verdict'])} | "
                             f"{_fmt(tg['net_alteration_deg'],' deg')} | "
                             f"{_fmt(tg['achieved_miss_m'],' m')} | {finding} |")
                L.append("")
                L.append("> **What this is:** an automated check of whether the own-ship "
                         "maneuver in this run conformed to the COLREGS duty for each "
                         "encounter (give-way: early + substantial alteration to a safe "
                         "distance; stand-on: keep course/speed until close-quarters). The "
                         "demo own-ship runs a FIXED maneuvering controller and does **not** "
                         "yet perform autonomous COLREGS avoidance (week 5-6 roadmap), so a "
                         "held course into a give-way duty is correctly scored non-compliant. "
                         "This is the V&V *scoring* metric, not an autonomy claim.")
    if plots:
        L.append("")
        L.append("## Plots")
        L.append("")
        for p in plots:
            L.append(f"![{p}]({p})")
    L.append("")
    md = "\n".join(L) + "\n"
    out = os.path.join(pack_dir, "EVIDENCE.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    return out


# ------------------------------------------------- P0 view-completeness gate
class PartialViewError(RuntimeError):
    """state.csv visible rows << manifest stateRows on a FINAL run (KI-038)."""


def _view_completeness(rows, manifest) -> dict:
    """Compare the rows actually read from state.csv with the row count the
    FINAL manifest declares. Guards against building demo evidence from a
    stale / truncated file view (KI-038: the 12-Jul live pack silently used
    11,117 of 23,393 rows - the sandbox mount served a frozen mid-run
    snapshot). Skips (complete=True) when the manifest is not final or does
    not declare stateRows (e.g. a genuinely in-flight run)."""
    declared = manifest.get("stateRows")
    final = bool(manifest.get("final"))
    read = len(rows)
    if not final or not isinstance(declared, int) or declared <= 0:
        return {"complete": True, "rows_read": read, "rows_manifest": declared,
                "note": "no final stateRows in manifest - gate skipped"}
    ok = read >= int(declared * 0.98)
    if ok:
        note = f"complete ({read}/{declared} rows visible)"
    else:
        note = (f"PARTIAL VIEW: read {read} of {declared} manifest rows "
                f"({read / declared:.0%}) - stale/truncated state.csv view (KI-038)")
    return {"complete": ok, "rows_read": read, "rows_manifest": declared, "note": note}


# ----------------------------------------------------------------- driver
def build_pack(run_dir: str, L_pp: float = DEFAULT_LPP, make_plots: bool = True,
               ais_preset: Optional[str] = None, make_html: bool = True,
               allow_partial: bool = False) -> dict:
    state_path = os.path.join(run_dir, "state.csv")
    if not os.path.exists(state_path):
        raise FileNotFoundError(f"no state.csv in {run_dir}")
    rows = vrk._load_state_csv(state_path)

    # KI-038 second failure mode (caught live 13 Jul): the stale mount can also
    # TRUNCATE manifest.json itself -> invalid JSON -> vrk._load_manifest()
    # forgives it and returns {} -> the P0 gate would silently SKIP. Parse the
    # manifest strictly first: an unreadable manifest on disk is itself proof
    # of a broken run-dir view.
    manifest_broken = None
    man_path = os.path.join(run_dir, "manifest.json")
    if os.path.exists(man_path):
        try:
            with open(man_path, encoding="utf-8") as f:
                json.load(f)
        except Exception as e:                   # noqa: BLE001
            manifest_broken = f"{type(e).__name__}: {e}"
    manifest = vrk._load_manifest(run_dir)

    # P0 view-completeness gate (WP_20260713 / KI-038): refuse to bake demo
    # evidence from a partial view of a FINAL run. Runs BEFORE anything is
    # written, so an existing evidence_pack/ is never clobbered.
    if manifest_broken:
        p0 = {"complete": False, "rows_read": len(rows), "rows_manifest": None,
              "note": (f"manifest.json unreadable/truncated ({manifest_broken}) "
                       "- stale run-dir view (KI-038)")}
    else:
        p0 = _view_completeness(rows, manifest)
    if not p0["complete"] and not allow_partial:
        raise PartialViewError(
            p0["note"] + " - refusing to build demo evidence from a partial "
            "view. Rebuild where the full log is visible (Windows terminal: "
            "python python/build_evidence_pack.py --run-dir logs/<run>), or "
            "pass --allow-partial for a clearly-watermarked forensic pack.")

    controller = vrk._controller_kind(manifest, rows)
    V = _service_speed_mps(rows)

    health = vrk.analyse(rows, manifest)
    health["run_dir"] = os.path.basename(run_dir.rstrip("/"))

    maneuver: Dict[str, object]
    try:
        if controller in ("turning_circle", "turning", "turn"):
            maneuver = _turning_kpis(rows, L_pp)
        elif "zigzag" in controller or controller.startswith("zz"):
            angle = _zigzag_angle_from(controller) or 10.0
            maneuver = _zigzag_kpis(rows, angle, V, L_pp)
        else:
            maneuver = {"kind": controller, "error": "no IMO KPI module for this controller"}
    except Exception as e:                       # noqa: BLE001
        maneuver = {"kind": controller, "error": f"{type(e).__name__}: {e}"}

    actuators = _actuator_kpis(rows)

    # Scripted AIS traffic (gate D4 / WP-15). Preset comes from the CLI override
    # or the run manifest (written by the listener for a traffic scenario). Pure
    # read-only over the own-ship track + the deterministic ais_traffic model.
    ais_preset = ais_preset or manifest.get("ais")
    ais_block = None
    ais_analysis = None
    if ais_preset:
        try:
            ais_analysis = aais.analyse(rows, ais_preset)
            ais_block = ais_analysis.to_json()
            # COLREGS conformance scoring (V&V differentiator, §5.1) — score the
            # own-ship maneuver against the duty for each encounter. Additive +
            # guarded: a scoring failure never breaks the pack.
            try:
                ais_block["conformance"] = colregs.summarize(
                    colregs.score_run(rows, ais_preset))
            except Exception as ce:                  # noqa: BLE001
                ais_block["conformance"] = {"error": f"{type(ce).__name__}: {ce}"}
        except Exception as e:                   # noqa: BLE001 - never break the pack
            ais_block = {"preset": ais_preset, "error": f"{type(e).__name__}: {e}"}

    pack_dir = os.path.join(run_dir, "evidence_pack")
    os.makedirs(pack_dir, exist_ok=True)
    plots = _make_plots(rows, maneuver, pack_dir) if make_plots else []
    if ais_analysis is not None:
        # write the AIS log + a range/CPA plot into the pack
        try:
            aais.write_ais_csv(pack_dir, rows, ais_preset)
        except Exception as e:                   # noqa: BLE001
            print(f"[evidence] ais.csv failed: {e}", file=sys.stderr)
        if make_plots:
            cpa_png = aais.make_cpa_plot(ais_analysis, os.path.join(pack_dir, "ais_cpa.png"))
            if cpa_png:
                plots.append(os.path.basename(cpa_png))

    meta = {
        "run_dir": os.path.basename(run_dir.rstrip("/")),
        "controller": controller,
        "plant": manifest.get("plantKind", "?"),
        "sea_state": manifest.get("seaState", "?"),
        "sea_state_schedule": manifest.get("seaStateSchedule"),
        "scenario": manifest.get("scenario"),
        "wave_heading_deg": manifest.get("waveHeadingDeg"),
        "tick_hz": manifest.get("tickHz"),
        "duration_s": manifest.get("durationSeconds"),
        "started_local": manifest.get("startedAtLocal"),
        "Lpp_m": L_pp,
        "service_speed_mps_est": V,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "generator": GENERATOR,
        "view_complete": p0["complete"],
        "state_rows_read": p0["rows_read"],
        "state_rows_manifest": p0["rows_manifest"],
        "view_note": p0["note"],
    }

    # Strip the un-serialisable dataclass before writing JSON.
    maneuver_json = {k: v for k, v in maneuver.items() if not k.startswith("_")}
    kpis = {"meta": meta, "health": health, "maneuver": maneuver_json,
            "actuators": actuators, "ais": ais_block, "plots": plots}
    _write_markdown(pack_dir, meta, health, maneuver, actuators, plots, ais_block)
    html_path = None
    if make_html:
        try:
            html_path = evidence_html.write_html(
                pack_dir, meta, health, maneuver, actuators, plots, ais_block, GENERATOR)
            kpis["report_html"] = os.path.basename(html_path)
        except Exception as e:                   # noqa: BLE001 - never break the pack
            print(f"[evidence] html report failed: {e}", file=sys.stderr)
    with open(os.path.join(pack_dir, "kpis.json"), "w", encoding="utf-8") as f:
        json.dump(kpis, f, indent=2)

    return {"pack_dir": pack_dir, "kpis": kpis, "report_html": html_path}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--log-root", default="logs")
    p.add_argument("--run-dir", default=None, help="Specific run dir; default = latest.")
    p.add_argument("--L-pp", type=float, default=DEFAULT_LPP, help="Lpp in metres (default 38).")
    p.add_argument("--no-plot", action="store_true")
    p.add_argument("--no-html", action="store_true",
                   help="Skip the self-contained evidence_report.html.")
    p.add_argument("--ais", default=None,
                   help="AIS traffic preset override (default: read from the run "
                        "manifest). head_on / crossing / overtaking / harbor_mix.")
    p.add_argument("--allow-partial", action="store_true",
                   help="Build even if state.csv shows fewer rows than the final "
                        "manifest declares (KI-038). The pack is watermarked "
                        "PARTIAL VIEW and must not be used as demo evidence.")
    args = p.parse_args()

    root = os.path.dirname(_HERE)
    log_root = args.log_root if os.path.isabs(args.log_root) else os.path.join(root, args.log_root)
    run_dir = args.run_dir or _latest_run(log_root)
    if not run_dir:
        print(f"[evidence] no run dir under {log_root}", file=sys.stderr)
        sys.exit(2)
    if not os.path.isabs(run_dir):
        run_dir = os.path.join(root, run_dir)

    try:
        res = build_pack(run_dir, L_pp=args.L_pp, make_plots=not args.no_plot,
                         ais_preset=args.ais, make_html=not args.no_html,
                         allow_partial=args.allow_partial)
    except PartialViewError as e:
        print(f"[evidence] P0 view-completeness FAIL: {e}", file=sys.stderr)
        sys.exit(3)
    k = res["kpis"]
    print(f"[evidence] pack -> {res['pack_dir']}")
    print(f"  view       : "
          f"{'complete' if k['meta']['view_complete'] else 'PARTIAL (KI-038)'} "
          f"({k['meta']['state_rows_read']}/{k['meta']['state_rows_manifest'] or 'n/a'} rows)")
    print(f"  controller : {k['meta']['controller']}")
    print(f"  health     : {k['health']['verdict']} "
          f"({k['health']['gates_passed']}/{k['health']['gates_total']})")
    mv = k["maneuver"]
    if mv.get("kind") == "turning_circle":
        print(f"  turning    : DT={_fmt(mv['tactical_diameter_m'],' m')} "
              f"(DT/Lpp={_fmt(mv['tactical_diameter_over_Lpp'])}, IMO {_imo_mark(mv['imo_tactical_diameter_pass'])})")
    elif mv.get("kind") == "zigzag":
        print(f"  zigzag     : 1st OS={_fmt(mv['first_overshoot_deg'],' deg')} "
              f"(IMO {_imo_mark(mv['imo_first_overshoot_pass'])})")
    if k.get("ais"):
        a = k["ais"]
        if a.get("error"):
            print(f"  ais        : {a['preset']} (error: {a['error']})")
        else:
            alerted = sum(1 for t in a["targets"] if t["alerted"])
            print(f"  ais        : {a['preset']} ({a['n_targets']} target(s), "
                  f"{alerted} alert(s))")
    print(f"  plots      : {', '.join(k['plots']) if k['plots'] else 'none'}")
    if res.get("report_html"):
        print(f"  report     : {os.path.basename(res['report_html'])} (self-contained HTML)")


if __name__ == "__main__":
    main()
