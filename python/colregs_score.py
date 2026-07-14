"""COLREGS conformance scoring — the V&V differentiator (Master Execution Plan §5.1).

WHAT THIS IS
    A deterministic, dependency-free *scoring engine* that takes a logged own-ship
    run (``state.csv``) plus a scripted AIS preset and asks, for each traffic
    encounter: **did the own-ship maneuver that actually occurred conform to the
    COLREGS duty for that encounter?** It returns a per-target verdict
    (COMPLIANT / NON_COMPLIANT / NOT_APPLICABLE) with the underlying rule checks
    and the numeric metrics behind them (alteration magnitude + direction, the
    TCPA at which action began, achieved miss distance vs a safe-distance
    threshold, whether own-ship passed ahead of a crossing target, and — for a
    stand-on duty — whether course/speed were held).

    This is the literature-standard V&V layer the week 5-6 "COLREGS scoring"
    differentiator is built on (it consumes the encounter geometry seeded by
    ``ais_traffic`` / ``analyse_ais`` in WP-20260624). It is the *measurement*
    side, not autonomy: it scores whatever maneuver is in the log.

HONESTY (KI-019 family — important for GTM/grant use)
    The demo own-ship runs a FIXED maneuvering controller (turning-circle /
    zig-zag / steady transit); it does NOT yet run an autonomous COLREGS-avoidance
    controller (that is the week 5-6 roadmap). So where own-ship holds course into
    a give-way duty, this scorer will (correctly) report NON_COMPLIANT — that is
    the harness doing its job, not a claim that the ship avoids traffic. Do not
    represent a COMPLIANT verdict on a scripted run as "NaviSense autonomously
    obeys COLREGS." The deliverable here is the *scoring metric*, validated both
    ways (a synthetic compliant give-way scores COMPLIANT; a held course scores
    NON_COMPLIANT).

PURE / DETERMINISTIC
    Read-only over ``state.csv`` (own-ship truth) + the closed-form ``ais_traffic``
    model. No wire/DTO/schema/C++ change, no recompile. Same numbers headless as
    live. Standard library + ``math`` only (no numpy), matching the rest of the
    stack.

CLI
    python python/colregs_score.py --ais head_on                 # latest run
    python python/colregs_score.py --run-dir logs/<run> --ais crossing
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ais_traffic as ais            # noqa: E402
import analyse_ais as aais           # noqa: E402
import verify_run_kinematics as vrk  # noqa: E402


# ------------------------------------------------------------------ criteria
@dataclass(frozen=True)
class ConformanceCriteria:
    """Thresholds for the rule checks. Defaults are demo-scale (≈1–2 km, 6–14 kn
    encounters off Port Hercule) and are deliberately conservative + documented so
    a reviewer can see exactly what "compliant" means here. All tunable per call.

    Rule references (1972 COLREGs):
      * Rule 8  — action to avoid collision: positive, made in *ample time*,
        *substantial*, and resulting in passing at a *safe distance* (8 a/b/d).
      * Rule 13 — overtaking: keep out of the way.
      * Rule 14 — head-on: alter course to *starboard*, pass port-to-port.
      * Rule 15 — crossing: vessel with the other on her own *starboard* side keeps
        out of the way and *avoids crossing ahead*.
      * Rule 16 — give-way vessel: take *early and substantial* action.
      * Rule 17 — stand-on vessel: *keep course and speed*; may act if the give-way
        vessel is not; *must* act when collision cannot be avoided by her alone.
    """
    action_alteration_deg: float = 15.0   # Rule 8(b)/16: "substantial", readily apparent
    detect_alteration_deg: float = 5.0    # heading change that marks "action has begun"
    early_tcpa_s: float = 90.0            # Rule 8(a)/16: action begun with TCPA ≥ this = ample time
    safe_cpa_m: float = 200.0             # Rule 8(d): achieved miss distance ≥ this = safe
    substantial_speed_drop: float = 0.25  # a ≥25% speed cut also counts as substantial action
    hold_alteration_deg: float = 10.0     # Rule 17(a)(i): stand-on "keep course" tolerance
    hold_speed_frac: float = 0.15         # Rule 17(a)(i): "keep speed" tolerance
    close_quarters_tcpa_s: float = 60.0   # Rule 17(a)(ii)/(b): stand-on action permitted below this
    alert_range_m: float = ais.DEFAULT_CPA_ALERT_M   # defines a risk-bearing encounter
    tcpa_horizon_s: float = ais.DEFAULT_TCPA_HORIZON_S


# ------------------------------------------------------------------ result
@dataclass
class RuleCheck:
    name: str
    rule: str
    passed: bool
    detail: str


@dataclass
class ConformanceResult:
    mmsi: int
    name: str
    ship_type: str
    encounter: str            # at the decision moment (matches analyse_ais.encounter_primary)
    duty: str                 # give_way | stand_on | none
    verdict: str              # compliant | non_compliant | not_applicable
    # metrics
    decision_t_s: float
    decision_basis: str       # alert | min_range | none
    tcpa_at_decision_s: float
    net_alteration_deg: float       # signed: +starboard / -port, decision→CPA
    peak_alteration_deg: float      # max |alteration| over the window
    alteration_dir: str             # starboard | port | none
    tcpa_at_action_s: Optional[float]   # TCPA when |alteration| first ≥ detect threshold
    speed_drop_frac: float
    achieved_miss_m: float          # min actual range over the window (the real closest pass)
    min_predicted_cpa_m: float
    passed_ahead: bool              # own-ship crossed ahead of the target (crossing only)
    held_course: bool               # stand-on only
    held_speed: bool                # stand-on only
    checks: List[RuleCheck] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    def to_json(self) -> dict:
        d = asdict(self)
        for k, v in list(d.items()):
            if isinstance(v, float):
                d[k] = round(v, 3)
        d["checks"] = [
            {**{kk: (round(vv, 3) if isinstance(vv, float) else vv)
                for kk, vv in c.items()}}
            for c in d["checks"]
        ]
        return d


# ------------------------------------------------------------------ helpers
def _unwrap_deg(seq: List[float]) -> List[float]:
    """Unwrap a compass-heading series so course changes accumulate without the
    ±180° fold (lets a >180° turn read as a >180° alteration, not a sign flip)."""
    out: List[float] = []
    off = 0.0
    prev: Optional[float] = None
    for h in seq:
        if prev is not None:
            d = h - prev
            if d > 180.0:
                off -= 360.0
            elif d < -180.0:
                off += 360.0
        out.append(h + off)
        prev = h
    return out


def _alteration_dir(net_deg: float, dead: float = 3.0) -> str:
    if net_deg > dead:
        return "starboard"
    if net_deg < -dead:
        return "port"
    return "none"


# ------------------------------------------------------------------ core scorer
def score_target(track: "aais.OwnTrack", tgt: "ais.AISTarget",
                 criteria: ConformanceCriteria) -> ConformanceResult:
    """Score one scripted target's encounter against the own-ship track."""
    n = len(track.t)
    # per-step own heading (course-made-good), carrying the last valid heading at
    # near-zero speed so a momentary stop doesn't inject a spurious 0°.
    raw_head: List[float] = []
    last = track.heading0_deg
    speeds: List[float] = []
    for i in range(n):
        ve, vn = track.ve[i], track.vn[i]
        sp = math.hypot(ve, vn)
        speeds.append(sp)
        if sp > 0.20:
            last = ais.compass_from_vec(ve, vn)
        raw_head.append(last)
    uhead = _unwrap_deg(raw_head)

    # per-step encounter geometry vs this target
    ranges: List[float] = [0.0] * n
    cpas: List[float] = [0.0] * n
    tcpas: List[float] = [0.0] * n
    aspects: List[float] = [0.0] * n
    snaps: List[ais.EncounterSnapshot] = []
    i_detect: Optional[int] = None
    for i in range(n):
        ti = track.t[i]
        oe, on = track.e[i], track.n[i]
        ove, ovn = track.ve[i], track.vn[i]
        st = tgt.state_at(ti)
        tve, tvn = tgt.velocity_at(ti)
        snap = ais.encounter_snapshot(ti, oe, on, ove, ovn, st, tve, tvn)
        snaps.append(snap)
        ranges[i] = snap.range_m
        cpas[i] = snap.cpa_m
        tcpas[i] = snap.tcpa_s
        aspects[i] = snap.aspect_deg
        if (i_detect is None and snap.closing and snap.cpa_m <= criteria.alert_range_m
                and 0.0 <= snap.tcpa_s <= criteria.tcpa_horizon_s):
            i_detect = i

    i_cpa = min(range(n), key=lambda k: ranges[k]) if n else 0
    min_pred_cpa = min(cpas) if cpas else float("nan")

    # decision moment = first alert, else min-range (mirrors analyse_ais primary).
    if i_detect is not None:
        i_dec = i_detect
        basis = "alert"
    else:
        i_dec = i_cpa
        basis = "min_range"
    dec_snap = snaps[i_dec]
    encounter = dec_snap.encounter
    duty = dec_snap.duty

    base = ConformanceResult(
        mmsi=tgt.mmsi, name=tgt.name, ship_type=tgt.ship_type,
        encounter=encounter, duty=duty, verdict="not_applicable",
        decision_t_s=track.t[i_dec] if n else 0.0, decision_basis=basis,
        tcpa_at_decision_s=tcpas[i_dec] if n else 0.0,
        net_alteration_deg=0.0, peak_alteration_deg=0.0, alteration_dir="none",
        tcpa_at_action_s=None, speed_drop_frac=0.0,
        achieved_miss_m=ranges[i_cpa] if n else float("nan"),
        min_predicted_cpa_m=min_pred_cpa, passed_ahead=False,
        held_course=True, held_speed=True)

    # No risk-bearing encounter (never closed inside the alert range) ⇒ no duty to
    # maneuver; a distant/clear pass is NOT a violation.
    if i_detect is None or duty == "none":
        base.reasons.append("no risk-bearing encounter (target never closed inside "
                             f"{criteria.alert_range_m:.0f} m with TCPA≥0) — no maneuvering duty")
        base.checks.append(RuleCheck("encounter_risk", "Rule 7",
                                     False, "no close-quarters risk detected"))
        return base

    # ---- analyse the maneuver over [decision .. CPA] -----------------------
    lo = i_dec
    hi = i_cpa if i_cpa >= i_dec else n - 1
    if hi <= lo:
        hi = n - 1
    h0u = uhead[lo]
    alt = [uhead[i] - h0u for i in range(lo, hi + 1)]            # signed, unwrapped
    net_alt = alt[-1] if alt else 0.0
    peak_stbd = max(alt) if alt else 0.0
    peak_port = min(alt) if alt else 0.0
    peak_abs = max(abs(peak_stbd), abs(peak_port))
    # earliness: first sample where alteration first exceeds the detect threshold
    tcpa_at_action: Optional[float] = None
    for k, a in enumerate(alt):
        if abs(a) >= criteria.detect_alteration_deg:
            tcpa_at_action = tcpas[lo + k]
            break
    v0 = max(speeds[lo], 1e-6)
    vmin = min(speeds[lo:hi + 1]) if hi >= lo else v0
    speed_drop = max(0.0, (v0 - vmin) / v0)
    achieved_miss = min(ranges[lo:hi + 1]) if hi >= lo else ranges[i_cpa]
    aspect_cpa = aspects[i_cpa]
    passed_ahead = abs(ais.wrap180(aspect_cpa)) < 90.0   # own in target's forward arc at CPA

    base.net_alteration_deg = net_alt
    base.peak_alteration_deg = peak_abs
    base.alteration_dir = _alteration_dir(net_alt)
    base.tcpa_at_action_s = tcpa_at_action
    base.speed_drop_frac = speed_drop
    base.achieved_miss_m = achieved_miss
    base.passed_ahead = passed_ahead

    checks: List[RuleCheck] = []
    reasons: List[str] = []

    if duty == "give_way":
        action_taken = (peak_abs >= criteria.action_alteration_deg
                        or speed_drop >= criteria.substantial_speed_drop)
        checks.append(RuleCheck(
            "substantial_action", "Rule 16 / 8(b)", action_taken,
            f"peak alteration {peak_abs:.1f}° (≥{criteria.action_alteration_deg:.0f}° "
            f"or speed −{speed_drop * 100:.0f}% ≥{criteria.substantial_speed_drop * 100:.0f}%)"))
        early = bool(action_taken and tcpa_at_action is not None
                     and tcpa_at_action >= criteria.early_tcpa_s)
        checks.append(RuleCheck(
            "early_action", "Rule 8(a) / 16", early,
            f"action began at TCPA {tcpa_at_action:.0f} s (≥{criteria.early_tcpa_s:.0f} s)"
            if tcpa_at_action is not None else "no alteration detected"))
        if encounter in ("head_on", "crossing_give_way"):
            correct_dir = net_alt >= 0.5 * criteria.action_alteration_deg
            checks.append(RuleCheck(
                "starboard_alteration", "Rule 14 / 15", correct_dir,
                f"net alteration {net_alt:+.1f}° ({base.alteration_dir}); "
                f"give-way head-on/crossing requires a substantial alteration to starboard"))
        else:  # overtaking_give_way — keep clear, either side acceptable
            correct_dir = peak_abs >= criteria.action_alteration_deg
            checks.append(RuleCheck(
                "keep_clear", "Rule 13", correct_dir,
                f"overtaking: keep well clear (peak alteration {peak_abs:.1f}°)"))
        safe = achieved_miss >= criteria.safe_cpa_m
        checks.append(RuleCheck(
            "safe_distance", "Rule 8(d)", safe,
            f"achieved miss {achieved_miss:.0f} m (≥{criteria.safe_cpa_m:.0f} m)"))
        not_ahead = True
        if encounter == "crossing_give_way":
            not_ahead = not passed_ahead
            checks.append(RuleCheck(
                "avoid_crossing_ahead", "Rule 15", not_ahead,
                "passed astern of the crossing target" if not_ahead
                else "crossed AHEAD of the give-way target (own in its forward arc at CPA)"))
        ok = action_taken and early and correct_dir and safe and not_ahead
        base.verdict = "compliant" if ok else "non_compliant"
        if not action_taken:
            reasons.append("no substantial avoiding action (Rule 16): own-ship effectively held course")
        elif not early:
            reasons.append("action not taken in ample time (Rule 8a): alteration began too late")
        if action_taken and not correct_dir:
            reasons.append("alteration not to starboard / not substantial for the encounter (Rule 14/15)")
        if not safe:
            reasons.append(f"did not pass at a safe distance (Rule 8d): closest {achieved_miss:.0f} m")
        if encounter == "crossing_give_way" and passed_ahead:
            reasons.append("crossed ahead of the give-way target (Rule 15)")

    elif duty == "stand_on":
        # hold window: decision → close-quarters onset (TCPA ≤ close_quarters) or CPA.
        i_hold_end = hi
        for i in range(lo, hi + 1):
            if 0.0 <= tcpas[i] <= criteria.close_quarters_tcpa_s:
                i_hold_end = i
                break
        hold_alt = [uhead[i] - h0u for i in range(lo, i_hold_end + 1)]
        hold_peak = max((abs(a) for a in hold_alt), default=0.0)
        vmin_h = min(speeds[lo:i_hold_end + 1]) if i_hold_end >= lo else v0
        vmax_h = max(speeds[lo:i_hold_end + 1]) if i_hold_end >= lo else v0
        held_course = hold_peak <= criteria.hold_alteration_deg
        held_speed = (max(abs(v0 - vmin_h), abs(vmax_h - v0)) / v0) <= criteria.hold_speed_frac
        base.held_course = held_course
        base.held_speed = held_speed
        checks.append(RuleCheck(
            "keep_course", "Rule 17(a)(i)", held_course,
            f"heading held within {hold_peak:.1f}° before close-quarters "
            f"(≤{criteria.hold_alteration_deg:.0f}°)"))
        checks.append(RuleCheck(
            "keep_speed", "Rule 17(a)(i)", held_speed,
            f"speed held within tolerance before close-quarters "
            f"(≤{criteria.hold_speed_frac * 100:.0f}%)"))
        # Alteration onset over the whole window. A stand-on vessel must keep course
        # and speed UNTIL close-quarters; a maneuver only AFTER close-quarters onset
        # is permitted (Rule 17 a-ii / b) and does not break the hold (the hold
        # window ends at close-quarters), so held_course/held_speed capture it.
        i_onset = None
        for i in range(lo, hi + 1):
            if abs(uhead[i] - h0u) >= criteria.detect_alteration_deg:
                i_onset = i
                break
        if held_course and held_speed:
            base.verdict = "compliant"
            if i_onset is not None and i_onset >= i_hold_end:
                checks.append(RuleCheck(
                    "permitted_late_action", "Rule 17(a)(ii)/(b)", True,
                    f"kept course/speed until close-quarters, then took permitted "
                    f"avoiding action at t={track.t[i_onset]:.0f} s"))
        else:
            base.verdict = "non_compliant"
            if not held_course:
                reasons.append("stand-on vessel altered course before close-quarters "
                               "(Rule 17a-i: keep course and speed)")
            if not held_speed:
                reasons.append("stand-on vessel changed speed before close-quarters (Rule 17a-i)")

    # surface failed-check details as reasons if none captured yet
    if base.verdict == "non_compliant" and not reasons:
        reasons = [f"{c.rule}: {c.detail}" for c in checks if not c.passed]
    base.checks = checks
    base.reasons = reasons
    return base


def score_run(rows: List[dict], preset: str,
              criteria: Optional[ConformanceCriteria] = None) -> List[ConformanceResult]:
    """Score every scripted target in ``preset`` against the own-ship track in
    ``rows`` (state.csv). Mirrors ``analyse_ais.analyse`` for own-track + field
    construction so the encounter classification matches that module exactly."""
    if not rows:
        raise ValueError("no state rows")
    crit = criteria or ConformanceCriteria()
    track = aais._own_track(rows)
    field_ = ais.make_field(preset, track.e0, track.n0, track.heading0_deg)
    return [score_target(track, tg, crit) for tg in field_.targets]


def conformance_to_json(results: List[ConformanceResult]) -> List[dict]:
    return [r.to_json() for r in results]


def summarize(results: List[ConformanceResult]) -> dict:
    """A compact verdict roll-up for the evidence pack / kpis.json."""
    counts = {"compliant": 0, "non_compliant": 0, "not_applicable": 0}
    for r in results:
        counts[r.verdict] = counts.get(r.verdict, 0) + 1
    return {
        "n_targets": len(results),
        "compliant": counts["compliant"],
        "non_compliant": counts["non_compliant"],
        "not_applicable": counts["not_applicable"],
        "targets": conformance_to_json(results),
    }


# ------------------------------------------------------------------ CLI
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--log-root", default="logs")
    p.add_argument("--run-dir", default=None, help="Specific run dir; default = latest.")
    p.add_argument("--ais", default="head_on", help="AIS preset (see analyse_ais --list).")
    p.add_argument("--safe-cpa-m", type=float, default=None,
                   help="Override the safe-distance threshold (Rule 8d).")
    args = p.parse_args()

    root = os.path.dirname(_HERE)
    log_root = args.log_root if os.path.isabs(args.log_root) else os.path.join(root, args.log_root)
    run_dir = args.run_dir or vrk._latest_run(log_root)
    if not run_dir:
        print(f"[colregs] no run dir under {log_root}", file=sys.stderr)
        sys.exit(2)
    if not os.path.isabs(run_dir):
        run_dir = os.path.join(root, run_dir)

    rows = vrk._load_state_csv(os.path.join(run_dir, "state.csv"))
    crit = ConformanceCriteria()
    if args.safe_cpa_m is not None:
        crit = ConformanceCriteria(safe_cpa_m=args.safe_cpa_m)
    results = score_run(rows, args.ais, crit)
    print(f"[colregs] run={os.path.basename(run_dir)} preset={args.ais} "
          f"({len(results)} target(s))")
    badge = {"compliant": "PASS", "non_compliant": "FAIL", "not_applicable": "n/a"}
    for r in results:
        print(f"  {r.name:10s} ({r.mmsi})  {r.encounter:24s} duty={r.duty:9s} "
              f"=> {badge.get(r.verdict, r.verdict):4s}  "
              f"alt={r.net_alteration_deg:+.0f}° miss={r.achieved_miss_m:.0f} m")
        for reason in r.reasons:
            print(f"      - {reason}")
    sm = summarize(results)
    print(f"[colregs] {sm['compliant']} compliant / {sm['non_compliant']} non-compliant / "
          f"{sm['not_applicable']} n/a")


if __name__ == "__main__":
    main()
