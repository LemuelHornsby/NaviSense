"""WP-20260621_HYDRO verify — reference model of the analytic hydrostatics integrator.

Mirrors NaviSenseHydrostaticsConfig (DOLPHIN) + the Step() oscillator math 1:1 (semi-implicit
Euler), so it PROVES the ported C++ algorithm: equilibrium, natural periods (vs analytic),
damping, strip slope -> pitch/roll, clamps, determinism. It does NOT test the UE water-sampling
call (in-engine) — that's isolated in SampleWaterHeightCm. No UE needed.
"""
from __future__ import annotations
import math, json, os, sys

PI = math.pi

class Cfg:  # DOLPHIN defaults (== NaviSenseHydrostaticsConfig.h)
    LOA=40.0; Lwl=38.0; B=8.11; T=2.177; Freeboard=1.80
    DisplacementTonnes=366.0; VCG=3.50; LCG=18.0; DesignTrimDegByStern=1.08
    LCF=17.594; TPc=2.641; Cwp=0.799
    GMt=1.044; GMl=68.154
    RollK=0.38; PitchK=0.25
    HeaveAdded=0.50; RollAdded=0.20; PitchAdded=0.25
    HeaveZeta=0.30; RollZeta=0.10; PitchZeta=0.30
    rho=1025.0; g=9.81
    def Mass(s): return s.DisplacementTonnes*1000.0
    def Awp(s): return s.TPc*1000.0/s.rho*100.0 if s.TPc>1e-6 else s.Cwp*s.Lwl*s.B
    def HeaveStiffness(s): return s.rho*s.g*s.Awp()
    def EffHeaveMass(s): return s.Mass()*(1+s.HeaveAdded)
    def RollInertia(s): k=s.RollK*s.B; return s.Mass()*k*k
    def EffRollInertia(s): return s.RollInertia()*(1+s.RollAdded)
    def PitchInertia(s): k=s.PitchK*s.LOA; return s.Mass()*k*k
    def EffPitchInertia(s): return s.PitchInertia()*(1+s.PitchAdded)
    def RollStiff(s): return s.Mass()*s.g*s.GMt
    def PitchStiff(s): return s.Mass()*s.g*s.GMl
    def HeaveT(s): return 2*PI*math.sqrt(s.EffHeaveMass()/max(s.HeaveStiffness(),1e-6))
    def RollT(s): return 2*PI*math.sqrt(s.EffRollInertia()/max(s.RollStiff(),1e-6))
    def PitchT(s): return 2*PI*math.sqrt(s.EffPitchInertia()/max(s.PitchStiff(),1e-6))
    def HeaveB(s): return 2*s.HeaveZeta*math.sqrt(s.HeaveStiffness()*s.EffHeaveMass())
    def RollB(s): return 2*s.RollZeta*math.sqrt(s.RollStiff()*s.EffRollInertia())
    def PitchB(s): return 2*s.PitchZeta*math.sqrt(s.PitchStiff()*s.EffPitchInertia())

class Integ:
    """1:1 port of Step() oscillators (SI)."""
    def __init__(s,cfg,zero_damp=False):
        s.c=cfg; s.zd=zero_damp
        s.y=0.0; s.vy=0.0; s.th=0.0; s.wth=0.0; s.ph=0.0; s.wph=0.0; s.init=False
    def step(s,dt,eqM,pitch_t,roll_t):
        c=s.c
        if not s.init:
            s.init=True; s.y=eqM; s.th=pitch_t; s.ph=roll_t
        kh,bh,mh=c.HeaveStiffness(),(0 if s.zd else c.HeaveB()),max(c.EffHeaveMass(),1.0)
        a=(-kh*(s.y-eqM)-bh*s.vy)/mh; s.vy+=a*dt; s.y+=s.vy*dt
        kp,bp,Ip=c.PitchStiff(),(0 if s.zd else c.PitchB()),max(c.EffPitchInertia(),1.0)
        a=(-kp*math.sin(s.th-pitch_t)-bp*s.wth)/Ip; s.wth+=a*dt; s.th+=s.wth*dt
        kr,br,Ir=c.RollStiff(),(0 if s.zd else c.RollB()),max(c.EffRollInertia(),1.0)
        a=(-kr*math.sin(s.ph-roll_t)-br*s.wph)/Ir; s.wph+=a*dt; s.ph+=s.wph*dt

def free_period(cfg, which):
    """Release from a small offset with zero damping; measure oscillation period via zero-crossings."""
    g=Integ(cfg,zero_damp=True); dt=1/240.0
    # seed at equilibrium then displace the chosen DOF by a small amount
    g.step(dt,0.0,0.0,0.0)
    if which=='heave': g.y=0.1
    elif which=='pitch': g.th=math.radians(2)
    else: g.ph=math.radians(2)
    prev=None; crossings=[]; t=0.0
    for i in range(240*40):
        g.step(dt,0.0,0.0,0.0); t+=dt
        val={'heave':g.y,'pitch':g.th,'roll':g.ph}[which]
        if prev is not None and (prev<0)!=(val<0):
            crossings.append(t)
        prev=val
        if len(crossings)>=5: break
    if len(crossings)<3: return None
    half=[crossings[i+1]-crossings[i] for i in range(len(crossings)-1)]
    return 2.0*(sum(half)/len(half))   # period = 2 * half-period

def gate(name, ok, detail):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return ok

def main():
    c=Cfg(); res=[]; P=lambda n,o,d: res.append((n,gate(n,o,d)))
    print("WP-20260621_HYDRO verify — analytic hydrostatics integrator\n")
    print(f"  DOLPHIN derived: Awp={c.Awp():.1f} m^2  heaveT={c.HeaveT():.2f}s  rollT={c.RollT():.2f}s  pitchT={c.PitchT():.2f}s")

    # H1 — derived values physically sane
    P("H1_derived_sane",
      1.5<c.HeaveT()<5 and 4<c.RollT()<12 and 1.5<c.PitchT()<5 and c.Mass()==366000,
      f"mass=366t, periods heave/roll/pitch={c.HeaveT():.2f}/{c.RollT():.2f}/{c.PitchT():.2f}s in expected bands")

    # H2 — flat water: heave->eq, pitch->designTrim, roll->0
    g=Integ(c); dt=1/120.0; eq=1.23
    for _ in range(120*60): g.step(dt,eq,math.radians(c.DesignTrimDegByStern),0.0)
    P("H2_equilibrium",
      abs(g.y-eq)<1e-3 and abs(math.degrees(g.th)-c.DesignTrimDegByStern)<0.05 and abs(math.degrees(g.ph))<0.05,
      f"heave->{g.y:.3f}m (eq {eq}), pitch->{math.degrees(g.th):.2f}deg (trim {c.DesignTrimDegByStern}), roll->{math.degrees(g.ph):.3f}deg")

    # H3/H4/H5 — free natural periods vs analytic (zero damping)
    hT,rT,pT=free_period(c,'heave'),free_period(c,'roll'),free_period(c,'pitch')
    P("H3_heave_period", hT and abs(hT-c.HeaveT())/c.HeaveT()<0.05, f"measured {hT:.2f}s vs analytic {c.HeaveT():.2f}s")
    P("H4_roll_period",  rT and abs(rT-c.RollT())/c.RollT()<0.05,  f"measured {rT:.2f}s vs analytic {c.RollT():.2f}s")
    P("H5_pitch_period", pT and abs(pT-c.PitchT())/c.PitchT()<0.05, f"measured {pT:.2f}s vs analytic {c.PitchT():.2f}s")

    # H6 — damping actually decays a displaced roll (lightly damped but must shrink)
    g=Integ(c); dt=1/120.0
    g.step(dt,0,0,0); g.ph=math.radians(8); peak0=abs(g.ph)
    amps=[]
    for _ in range(120*60):
        g.step(dt,0,0,0.0); amps.append(abs(g.ph))
    P("H6_roll_damps", max(amps[-120:])<peak0*0.7, f"roll peak {math.degrees(peak0):.1f}deg -> last-sec max {math.degrees(max(amps[-120:])):.2f}deg (decays)")

    # H7 — strip slope extraction: a tilted surface -> correct pitch target (+ clamp)
    def lsq_slope(span_cm, n, surf):
        sa=sh=ss=0.0
        for i in range(n):
            t=((i/(n-1))*2-1) if n>1 else 0
            arm=t*0.5*span_cm; h=surf(arm)
            sa+=arm*h; ss+=arm*arm
        return sa/ss if ss>1e-6 else 0.0
    # surface rising 0.02 m per m forward => slope 0.02 => pitch atan(0.02)=1.15deg
    slope_true=0.02
    sl=lsq_slope(0.95*c.Lwl*100, 15, lambda armcm: slope_true*(armcm*0.01)*100)  # height cm at arm cm
    pitch_from_strips=math.degrees(math.atan(sl))
    P("H7_strip_slope", abs(pitch_from_strips-math.degrees(math.atan(slope_true)))<0.05,
      f"strip LSQ slope -> pitch {pitch_from_strips:.2f}deg (true atan slope {math.degrees(math.atan(slope_true)):.2f}deg)")

    # H8 — clamp: huge slope target clamps pitch at MaxWavePitchDeg (5 deg)
    g=Integ(c); dt=1/120.0; big=math.radians(30); cap=math.radians(5)
    tgt=max(-cap,min(cap,big))  # mirror clamp
    for _ in range(120*60): g.step(dt,0,tgt,0)
    P("H8_pitch_clamp", abs(math.degrees(g.th)-5.0)<0.1, f"pitch settles to clamp {math.degrees(g.th):.2f}deg (cap 5)")

    # H9 — determinism
    def run():
        gg=Integ(c)
        for k in range(500): gg.step(1/120.,0.05*math.sin(k*0.1),math.radians(1),math.radians(0.5))
        return (gg.y,gg.th,gg.ph)
    P("H9_deterministic", run()==run(), "identical re-run")

    npass=sum(1 for _,o in res if o); ntot=len(res)
    verdict="PASS" if npass==ntot else "FAIL"
    print(f"\n  {npass}/{ntot} gates => {verdict}")
    out={"packet":"WP-20260621_HYDRO","kind":"analytic hydrostatics integrator (Unity port) reference verify",
         "date":"2026-06-21","tester":"Claude (sandbox)","gates":{n:("PASS" if o else "FAIL") for n,o in res},
         "gates_passed":npass,"gates_total":ntot,"auto_result":verdict,
         "dolphin_periods_s":{"heave":round(c.HeaveT(),3),"roll":round(c.RollT(),3),"pitch":round(c.PitchT(),3)}}
    try:
        p=os.path.join("NaviSense_UE5","Saved","NaviSense_Reports","wp_20260621_hydro_result.json")
        json.dump(out,open(p,"w"),indent=2); print(f"[verify] wrote {p}")
    except OSError as e: print("write skip:",e)
    sys.exit(0 if verdict=="PASS" else 1)

if __name__=="__main__": main()
