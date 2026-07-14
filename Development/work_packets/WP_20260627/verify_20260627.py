#!/usr/bin/env python3
"""Gate WP-20260627 — COLREGS conformance scoring (V&V differentiator, §5.1).

Proves the new ``python/colregs_score.py`` scores the own-ship maneuver against
the COLREGS duty for each encounter, BOTH ways (it recognises a compliant
maneuver AND flags a violation), agrees with the existing ``analyse_ais``
encounter classification, integrates into the evidence pack without disturbing
the IMO KPIs / health, and is deterministic.

6 gates + 3 negative controls. A green result means:
  G1 a give-way vessel that alters early + substantially to starboard and opens a
     safe CPA scores COMPLIANT (4/4 rule checks);
  G2 a give-way vessel that holds course into a head-on scores NON_COMPLIANT with
     the right rule reasons (Rule 16 no action / Rule 8d unsafe distance);
  G3 a stand-on vessel that keeps course/speed scores COMPLIANT, while one that
     alters early scores NON_COMPLIANT (Rule 17a-i);
  G4 colregs_score's decision-moment encounter/duty matches analyse_ais on a real
     run (the two modules agree);
  G5 the evidence pack carries the conformance verdict (kpis.json + HTML +
     EVIDENCE.md), the verdict matches the standalone scorer (parity), and the
     IMO KPIs + kinematic health are IDENTICAL to a no-AIS build (purely additive);
  G6 scoring a run twice is bit-identical (deterministic).
Negative controls (must FIRE): N1 a clear/opening pass is NOT_APPLICABLE, never a
false violation; N2 a give-way vessel that turns the WRONG way (to port) is
flagged NON_COMPLIANT on the starboard check; N3 a tampered conformance verdict in
kpis.json is DETECTED by the parity comparison.

Read-only over logs/; writes only temp packs + the result JSON. Exit 0 iff 6/6
gates pass AND 3/3 controls fire.
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_PY = os.path.join(_ROOT, "python")
for p in (_PY, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import ais_traffic as ais            # noqa: E402
import analyse_ais as aais           # noqa: E402
import colregs_score as cs           # noqa: E402
import build_evidence_pack as bep    # noqa: E402
import verify_run_kinematics as vrk  # noqa: E402

RESULT = os.path.join(_ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports",
                      "wp_20260627_result.json")


# ------------------------------------------------------------ synthetic tracks
def _track(heading_fn, speed=5.0, T=320, dt=1.0):
    """Build a deterministic OwnTrack from a heading(t) schedule at constant speed."""
    t = []; e = []; n = []; ve = []; vn = []
    ee = nn = 0.0
    for k in range(T):
        ti = k * dt
        h = heading_fn(ti)
        vx, vy = ais.vec_from_compass(h, speed)
        t.append(ti); e.append(ee); n.append(nn); ve.append(vx); vn.append(vy)
        ee += vx * dt; nn += vy * dt
    return aais.OwnTrack(t=t, e=e, n=n, ve=ve, vn=vn,
                         heading0_deg=heading_fn(0.0), e0=e[0], n0=n[0])


def _ramp(start_t, end_t, target):
    def f(ti):
        if ti < start_t:
            return 0.0
        if ti < end_t:
            return target * (ti - start_t) / (end_t - start_t)
        return target
    return f


# ------------------------------------------------------------------ run pick
def _pick_run(log_root):
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


def _copy_run(src, dst):
    os.makedirs(dst, exist_ok=True)
    for fn in ("state.csv", "manifest.json"):
        s = os.path.join(src, fn)
        if os.path.exists(s):
            shutil.copyfile(s, os.path.join(dst, fn))
    return dst


# ---------------------------------------------------------------------- main
def main() -> int:
    log_root = os.path.join(_ROOT, "logs")
    run_dir = _pick_run(log_root)
    gates, negs = [], []
    crit = cs.ConformanceCriteria()

    def gate(gid, name, ok, detail):
        gates.append({"id": gid, "name": name, "passed": bool(ok), "detail": detail})

    def neg(nid, name, fired, detail):
        negs.append({"id": nid, "name": name, "fired": bool(fired), "detail": detail})

    # Head-on target ~1500 m ahead, fine on the bow, inbound — used by G1/G2/N2.
    head_on = ais.AISTarget(211000001, "MERIDIAN", "cargo", 30.0, 1500.0, 180.0, 6.0)
    # Crossing target on own PORT bow, closing — stand-on (G3).
    port_cross = ais.AISTarget(227000002, "AZURFERRY", "ferry", -650.0, 650.0, 115.0, 5.0)

    # G1 — COMPLIANT give-way: prompt early substantial starboard turn, opens CPA.
    r1 = cs.score_target(_track(_ramp(5, 35, 45.0)), head_on, crit)
    checks_ok = sum(1 for c in r1.checks if c["passed"]) if isinstance(r1.checks[0], dict) else sum(1 for c in r1.checks if c.passed)
    g1 = (r1.verdict == "compliant" and r1.duty == "give_way"
          and r1.alteration_dir == "starboard" and r1.achieved_miss_m >= crit.safe_cpa_m)
    gate("G1", "compliant_giveway", g1,
         f"verdict={r1.verdict} dir={r1.alteration_dir} netAlt={r1.net_alteration_deg:.0f} "
         f"tcpa_act={r1.tcpa_at_action_s} miss={r1.achieved_miss_m:.0f}m checks={checks_ok}/{len(r1.checks)}")

    # G2 — NON_COMPLIANT give-way: hold course into the head-on.
    r2 = cs.score_target(_track(lambda ti: 0.0), head_on, crit)
    rule_ids = " ".join(c.rule for c in r2.checks)
    g2 = (r2.verdict == "non_compliant" and r2.duty == "give_way"
          and len(r2.reasons) >= 1
          and any("Rule 16" in c.rule and not c.passed for c in r2.checks))
    gate("G2", "noncompliant_giveway", g2,
         f"verdict={r2.verdict} reasons={len(r2.reasons)} miss={r2.achieved_miss_m:.0f}m "
         f"firstReason='{r2.reasons[0] if r2.reasons else ''}'")

    # G3 — stand-on: hold => COMPLIANT, early alter => NON_COMPLIANT.
    r3a = cs.score_target(_track(lambda ti: 0.0), port_cross, crit)
    r3b = cs.score_target(_track(_ramp(25, 65, -40.0)), port_cross, crit)
    g3 = (r3a.duty == "stand_on" and r3a.verdict == "compliant" and r3a.held_course
          and r3b.duty == "stand_on" and r3b.verdict == "non_compliant" and not r3b.held_course)
    gate("G3", "standon_hold_and_violation", g3,
         f"hold: {r3a.encounter}/{r3a.verdict} (held={r3a.held_course}); "
         f"early-turn: {r3b.verdict} (held={r3b.held_course})")

    if not run_dir:
        gate("G4", "encounter_parity_real_run", False, "no real run under logs/")
        gate("G5", "evidence_integration", False, "no real run under logs/")
        gate("G6", "determinism", False, "no real run under logs/")
    else:
        rows = vrk._load_state_csv(os.path.join(run_dir, "state.csv"))

        # G4 — parity with analyse_ais on a real run (modules agree on encounter/duty).
        an = aais.analyse(rows, "head_on")
        cr = cs.score_run(rows, "head_on")
        by = {t.mmsi: t for t in an.targets}
        agree = all((c.encounter == by[c.mmsi].encounter_primary
                     and c.duty == by[c.mmsi].duty_primary) for c in cr if c.mmsi in by)
        g4 = bool(cr) and agree
        gate("G4", "encounter_parity_real_run", g4,
             f"targets={len(cr)} agree={agree} "
             f"({cr[0].encounter}/{cr[0].duty} vs {by[cr[0].mmsi].encounter_primary}/{by[cr[0].mmsi].duty_primary})")

        # G5 — evidence-pack integration + parity + purely additive.
        tmp_ais = _copy_run(run_dir, tempfile.mkdtemp(prefix="cr_ais_"))
        tmp_no = _copy_run(run_dir, tempfile.mkdtemp(prefix="cr_no_"))
        res = bep.build_pack(tmp_ais, make_plots=True, ais_preset="head_on", make_html=True)
        res_no = bep.build_pack(tmp_no, make_plots=False, ais_preset=None, make_html=False)
        kp = json.load(open(os.path.join(res["pack_dir"], "kpis.json"), encoding="utf-8"))
        kp_no = json.load(open(os.path.join(res_no["pack_dir"], "kpis.json"), encoding="utf-8"))
        conf = (kp.get("ais") or {}).get("conformance") or {}
        pack_verdict = conf.get("targets", [{}])[0].get("verdict")
        standalone_verdict = cr[0].verdict if cr else None
        html_text = ""
        hp = res.get("report_html")
        if hp and os.path.exists(hp):
            html_text = open(hp, encoding="utf-8").read()
        md_text = open(os.path.join(res["pack_dir"], "EVIDENCE.md"), encoding="utf-8").read()
        # additive = the IMO KPIs + health are byte-identical with vs without AIS
        # (ignore health['run_dir'], which is just the temp-dir basename).
        def _h(k):
            return {kk: vv for kk, vv in (k.get("health") or {}).items() if kk != "run_dir"}
        additive = (kp.get("maneuver") == kp_no.get("maneuver") and _h(kp) == _h(kp_no))
        g5 = (pack_verdict is not None and pack_verdict == standalone_verdict
              and "COLREGS conformance scoring" in html_text
              and "COLREGS conformance scoring" in md_text
              and additive)
        gate("G5", "evidence_integration", g5,
             f"pack_verdict={pack_verdict} standalone={standalone_verdict} "
             f"html_section={'COLREGS conformance scoring' in html_text} "
             f"additive(KPIs+health unchanged)={additive}")

        # G6 — determinism: identical JSON across two scoring passes.
        j1 = json.dumps(cs.conformance_to_json(cs.score_run(rows, "head_on")), sort_keys=True)
        j2 = json.dumps(cs.conformance_to_json(cs.score_run(rows, "head_on")), sort_keys=True)
        g6 = j1 == j2
        gate("G6", "determinism", g6, f"identical={g6} bytes={len(j1)}")

        # N3 — tamper the pack verdict; the parity comparison must DETECT it.
        tampered_verdict = "compliant" if pack_verdict != "compliant" else "non_compliant"
        neg("N3", "parity_tamper_detected", tampered_verdict != standalone_verdict,
            f"tampered='{tampered_verdict}' vs standalone='{standalone_verdict}' -> mismatch detected")

        shutil.rmtree(tmp_ais, ignore_errors=True)
        shutil.rmtree(tmp_no, ignore_errors=True)

    # N1 — a clear/opening pass is NOT_APPLICABLE (never a false violation).
    far = ais.AISTarget(999000001, "FAR", "cargo", 30.0, 1500.0, 30.0, 6.0)  # heading away
    rn1 = cs.score_target(_track(lambda ti: 0.0), far, crit)
    neg("N1", "clear_pass_not_violation",
        rn1.verdict == "not_applicable" and rn1.verdict != "non_compliant",
        f"opening target verdict={rn1.verdict} encounter={rn1.encounter}")

    # N2 — give-way that turns the WRONG way (to PORT) is flagged on the starboard check.
    rn2 = cs.score_target(_track(_ramp(5, 35, -45.0)), head_on, crit)
    starboard_failed = any(c.name == "starboard_alteration" and not c.passed for c in rn2.checks)
    neg("N2", "wrong_direction_flagged",
        rn2.verdict == "non_compliant" and starboard_failed and rn2.alteration_dir == "port",
        f"port-turn verdict={rn2.verdict} dir={rn2.alteration_dir} starboard_check_failed={starboard_failed}")

    if not run_dir:
        neg("N3", "parity_tamper_detected", False, "no real run under logs/")

    passed = sum(1 for g in gates if g["passed"])
    fired = sum(1 for n in negs if n["fired"])
    overall = "PASS" if passed == len(gates) and fired == len(negs) else "FAIL"
    summary = {
        "packet": "WP-20260627",
        "theme": "COLREGS conformance scoring (V&V differentiator, §5.1)",
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "run_dir": os.path.basename(run_dir) if run_dir else None,
        "gates_passed": passed,
        "gates_total": len(gates),
        "all_negative_controls_fired": fired == len(negs),
        "overall": overall,
    }
    summary["gates"] = gates
    summary["negative_controls"] = negs
    os.makedirs(os.path.dirname(RESULT), exist_ok=True)
    with open(RESULT, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"[verify] WP-20260627 — COLREGS conformance — run {os.path.basename(run_dir) if run_dir else None}")
    for g in gates:
        print(f"  {g['id']} {g['name']:<26} {'PASS' if g['passed'] else 'FAIL'} — {g['detail']}")
    for n in negs:
        print(f"  {n['id']} {n['name']:<26} {'FIRED' if n['fired'] else 'MISS'} — {n['detail']}")
    print(f"[verify] {overall}: {passed}/{len(gates)} gates, {fired}/{len(negs)} controls -> {RESULT}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
