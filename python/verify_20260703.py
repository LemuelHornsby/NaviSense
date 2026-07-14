#!/usr/bin/env python3
"""
verify_20260703.py -- WP-20260703 single-target COLREGS encounters + scripted avoidance

Reconstructs the COLREGS demo the way Lemuel asked for it: ONE target ship per run
(the other two hidden by the editor picker), a COLREGS encounter chosen per run, own-ship
running a SCRIPTED avoidance (give-way) or a course/speed HOLD (stand-on) through its MMG
model, and the encounter scored for conformance.

Gates (5) + negative controls (3). Pure-Python; NO C++/wire change (Z0 unaffected).
 G1 registry: the 4 colregs_* scenarios resolve to the avoid controllers + the correct
    SINGLE-target AIS presets; stand-on carries a running start.
 G2 controller profiles: give-way controllers command a net STARBOARD alteration inside the
    avoidance window and hold the base course before it; stand-on holds ~0 rudder throughout.
 G3 end-to-end compliance: for each of the 4 scenarios the evidence pack scores the intended
    verdict -- give-way => COMPLIANT (starboard, safe miss); stand-on => COMPLIANT (held).
    Uses the latest real logs/_selftest pack per scenario (regenerates via run_demo if absent
    or --fresh).
 G4 picker: the editor picker maps all 4 encounters to a valid scenario + one of the 3 placed
    ships, hides the others, assigns a single TrafficActors target.
 G5 regression: Z0 16/16 (C++ untouched) + verify_20260702b / _701b / _629b still pass.
Negative controls (scorer has teeth, all synthetic + fast):
 N1 a HELD course into a head-on give-way duty scores NON_COMPLIANT.
 N2 a PORT (wrong-way) alteration in a crossing give-way is flagged (starboard check fails).
 N3 a stand-on vessel that alters course early scores NON_COMPLIANT.
"""
import os, re, sys, json, math, glob, subprocess

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WS); sys.path.insert(0, os.path.join(WS, "python"))
REPORTS = os.path.join(WS, "NaviSense_UE5", "Saved", "NaviSense_Reports")
FRESH = "--fresh" in sys.argv

from python import scenarios as SC
from python import ais_traffic as ais
from python.scenario_controllers import make_scenario_controller
from python import colregs_score as cs
from python import analyse_ais as aais

SCEN = {
    "colregs_head_on":          ("avoid_head_on",  "head_on_avoid",    "give_way"),
    "colregs_crossing_giveway": ("avoid_crossing", "crossing_avoid",   "give_way"),
    "colregs_crossing_standon": ("avoid_standon",  "crossing_standon", "stand_on"),
    "colregs_overtaking":       ("avoid_overtaking","overtaking_avoid", "give_way"),
}

def g1():
    for name, (ctrl, preset, _duty) in SCEN.items():
        sc = SC.get_scenario(name)
        if sc.controller != ctrl: return False, f"{name}: controller {sc.controller}!={ctrl}"
        if sc.ais != preset:      return False, f"{name}: ais {sc.ais}!={preset}"
        f = ais.make_field(sc.ais, 0.0, 0.0, 0.0)
        if len(f.targets) != 1:   return False, f"{name}: {len(f.targets)} targets (want 1)"
    if SC.get_scenario("colregs_crossing_standon").initial_speed_mps <= 0:
        return False, "stand-on lacks a running start (initial_speed_mps)"
    return True, "4 scenarios -> avoid controllers + single-target presets; stand-on running start"

def _profile(kind):
    """Step a controller with a simple heading-follows-rudder feedback; return
    (base_hold_ok, avoid_net_starboard, is_hold)."""
    c = make_scenario_controller(kind)
    yaw = 0.0; rudders = {}; head_at = {}
    for i in range(0, 3000):
        t = i * 0.1
        out = c.step(t, {"yawDeg": yaw})
        yaw += 0.02 * out.rudder_cmd_deg * 0.1 * 10   # crude: rudder -> yaw rate
        rudders[round(t)] = out.rudder_cmd_deg
        head_at[round(t)] = yaw
    return rudders, head_at

def g2():
    # give-way: net starboard alteration mid-run, base course held early
    for kind in ("avoid_head_on", "avoid_crossing", "avoid_overtaking"):
        r, h = _profile(kind)
        if abs(h.get(10, 0)) > 3:  return False, f"{kind}: not holding base course early (h10={h.get(10)})"
        if h.get(120, 0) <= 10:    return False, f"{kind}: no substantial starboard alteration (h120={h.get(120):.0f})"
    # stand-on: ~0 rudder throughout (hold)
    r, h = _profile("avoid_standon")
    if max(abs(v) for v in r.values()) > 1e-6:
        return False, "stand-on commands rudder (should hold)"
    return True, "give-way controllers alter starboard mid-run; stand-on holds 0 rudder"

def _latest_pack(scenario):
    ds = sorted(glob.glob(os.path.join(WS, "logs", "_selftest", f"demo-{scenario}_*")),
                key=os.path.getmtime, reverse=True)
    for d in ds:
        k = os.path.join(d, "evidence_pack", "kpis.json")
        if os.path.isfile(k): return k
    return None

def _run(scenario):
    subprocess.run([sys.executable, os.path.join(WS, "run_demo.py"),
                    "--scenario", scenario, "--selftest", "--plant", "mmg"],
                   cwd=WS, capture_output=True, text=True, timeout=180)
    return _latest_pack(scenario)

def g3():
    details = []
    for name, (_c, _p, duty) in SCEN.items():
        k = None if FRESH else _latest_pack(name)
        if k is None: k = _run(name)
        if k is None: return False, f"{name}: no evidence pack", details
        t = json.load(open(k))["ais"]["conformance"]["targets"][0]
        v = t["verdict"]
        ok = (v == "compliant")
        if duty == "give_way":
            ok = ok and t["alteration_dir"] == "starboard" and t["achieved_miss_m"] >= 200.0
        else:
            ok = ok and t["held_course"] and t["held_speed"]
        details.append(f"{name}:{v}(miss {t['achieved_miss_m']:.0f}m,{t['alteration_dir']})")
        if not ok: return False, f"{name}: verdict {v} not the intended {duty} compliant", details
    return True, "all 4 encounters scored intended verdict", details

def g4():
    p = os.path.join(WS, "NaviSense_UE5", "Content", "NaviSense", "Python",
                     "Phase5_Systems", "10_colregs_encounter.py")
    if not os.path.isfile(p): return False, "picker script missing"
    src = open(p).read()
    for enc, sc in [("head_on","colregs_head_on"),("crossing_giveway","colregs_crossing_giveway"),
                    ("crossing_standon","colregs_crossing_standon"),("overtaking","colregs_overtaking")]:
        if sc not in src: return False, f"picker missing scenario {sc}"
    labels = ["excursion_vessel","marine_rescue_boat","Yacht_with_interior"]
    if not all(l in src for l in labels): return False, "picker missing a placed-ship label"
    if "set_actor_hidden_in_game" not in src: return False, "picker does not hide the other ships"
    if "TrafficActors" not in src: return False, "picker does not assign a single target"
    return True, "picker maps 4 encounters -> scenario + 1 of 3 ships, hides others, assigns single target"

def g5():
    z0 = subprocess.run([sys.executable, os.path.join(WS,"Development","work_packets",
                         "WP_20260615_COMPILE_AUDIT","verify_compile_readiness.py")],
                        cwd=WS, capture_output=True, text=True)
    z = (z0.returncode==0 and "16/16" in (z0.stdout+z0.stderr))
    others = {}
    for v in ("verify_20260702b.py","verify_20260701b.py","verify_20260629b.py"):
        r = subprocess.run([sys.executable, os.path.join(WS,"python",v)], cwd=WS,
                           capture_output=True, text=True)
        others[v] = (r.returncode==0)
    ok = z and all(others.values())
    return ok, f"Z0 16/16={z}; " + ", ".join(f"{k}={v}" for k,v in others.items())

# ---- synthetic negative controls -------------------------------------------
def _track(headings_deg, v=3.0, dt=1.0):
    """Build an OwnTrack from a heading schedule fn(t)->deg at speed v."""
    e=[0.0]; n=[0.0]; t=[0.0]
    for i in range(1,320):
        ti=i*dt; h=math.radians(headings_deg(ti-dt))
        e.append(e[-1]+v*math.sin(h)*dt); n.append(n[-1]+v*math.cos(h)*dt); t.append(ti)
    ve=[0.0]*len(t); vn=[0.0]*len(t)
    for i in range(len(t)):
        a=max(0,i-1); b=min(len(t)-1,i+1); d=t[b]-t[a]
        if d>0: ve[i]=(e[b]-e[a])/d; vn[i]=(n[b]-n[a])/d
    return aais.OwnTrack(t=t,e=e,n=n,ve=ve,vn=vn,heading0_deg=0.0,e0=0.0,n0=0.0)

def _score(track, preset):
    f = ais.make_field(preset, track.e0, track.n0, track.heading0_deg)
    return cs.score_target(track, f.targets[0], cs.ConformanceCriteria())

def controls():
    res = {}
    # N1: held course into head-on give-way -> NON_COMPLIANT
    r = _score(_track(lambda t: 0.0), "head_on")
    res["N1"] = (r.verdict == "non_compliant")
    # N2: crossing give-way turned to PORT (wrong way) -> starboard check fails
    def port_turn(t): return 0.0 if t<45 else (-40.0 if t<220 else 0.0)
    r2 = _score(_track(port_turn), "crossing")
    n2 = (r2.verdict == "non_compliant") and any(
        (not c.passed and "starboard" in c.name) for c in r2.checks)
    res["N2"] = n2
    # N3: stand-on that alters course early -> NON_COMPLIANT
    def early_turn(t): return 0.0 if t<30 else 35.0
    r3 = _score(_track(early_turn, v=3.4), "crossing_standon")
    res["N3"] = (r3.verdict == "non_compliant")
    return res

def main():
    gates = {}; detail = {}
    gates["G1"], detail["G1"] = g1()
    gates["G2"], detail["G2"] = g2()
    g3ok, g3d, g3det = g3(); gates["G3"] = g3ok; detail["G3"] = g3d + " :: " + "; ".join(g3det)
    gates["G4"], detail["G4"] = g4()
    gates["G5"], detail["G5"] = g5()
    ctrl = controls()

    gp = sum(1 for v in gates.values() if v); cf = sum(1 for v in ctrl.values() if v)
    verdict = "PASS" if (gp==len(gates) and cf==len(ctrl)) else "FAIL"
    out = {
        "packet":"WP-20260703",
        "title":"Single-target COLREGS encounters + scripted own-ship avoidance",
        "gates":gates, "gates_detail":detail,
        "controls_fired":ctrl,
        "gates_passed":gp,"gates_total":len(gates),
        "controls_fired_n":cf,"controls_total":len(ctrl),
        "verdict":verdict,
    }
    os.makedirs(REPORTS, exist_ok=True)
    json.dump(out, open(os.path.join(REPORTS,"wp_20260703_result.json"),"w"), indent=2)
    for g in sorted(gates): print(f"{'PASS' if gates[g] else 'FAIL'} {g} :: {detail[g]}")
    for c in sorted(ctrl):  print(f"{'FIRED' if ctrl[c] else 'MISS'} {c}")
    print(f"\n{verdict}  {gp}/{len(gates)} gates + {cf}/{len(ctrl)} controls")
    sys.exit(0 if verdict=="PASS" else 1)

if __name__ == "__main__":
    main()
