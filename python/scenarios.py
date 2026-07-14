"""Named demo-scenario registry (demo gate D6 -- scenario selection).

WHY THIS EXISTS
    D6 wants a *one-command scenario* -> run CSV + IMO KPIs (evidence pack). The
    pieces already exist (controllers, sea-state field, the WP-20260620 evidence
    pack), but a demo operator had to remember the right combination of
    ``--controller`` / ``--sea-state`` / ``--sea-state-schedule`` / ``--wave-heading-deg``
    flags. This registry names those combinations so a run is a single
    ``--scenario <name>``. The listener resolves the name to flag values; any flag
    the operator passes EXPLICITLY still overrides the scenario (scenario = preset
    defaults, not a lock).

    Pure data + lookups. No wire/DTO change, no recompile. Scenarios reference only
    existing controllers and the existing (fixed or scheduled) sea-state field, so
    every scenario is demo-ready the moment its controller's in-engine gate passes.

CONTRACT
    Each Scenario carries exactly the knobs the listener already understands:
      controller            one of the listener's --controller values
      sea_state             fixed sea state 0..9 (used when sea_state_schedule is None)
      sea_state_schedule    a parse_schedule() string for a RUNTIME-VARYING sea
                            (gate D3); when set it takes precedence over sea_state
      wave_heading_deg      mean swell direction (compass; sets roll-vs-pitch mix)
      wave_seed             replayable wave-field seed
      ais                   scripted AIS traffic preset (python/ais_traffic.py;
                            head_on / crossing / overtaking / harbor_mix) or None.
                            Recorded in the run manifest; the evidence pack reads it
                            to compute CPA/TCPA + COLREGS encounter (gate D4/WP-15).
      description           one-line human summary (shown by `--scenario list`)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Scenario:
    name: str
    controller: str
    description: str
    sea_state: int = 0
    sea_state_schedule: Optional[str] = None
    wave_heading_deg: float = 0.0
    wave_seed: int = 1337
    ais: Optional[str] = None          # scripted AIS traffic preset (D4/WP-15); None = none
    initial_speed_mps: float = 0.0     # running start (m/s); 0 = from rest
    plant: Optional[str] = None        # required plant ("mmg"/"stub"); None = CLI default


# Registry. Keep names short, lower_snake, and stable (they appear in run logs and
# the evidence pack). Add new scenarios as features land.
_SCENARIOS: Dict[str, Scenario] = {
    s.name: s
    for s in [
        # --- IMO maneuvering, calm water (clean KPIs for the evidence pack) ----
        Scenario("imo_turning_circle", "turning_circle",
                 "IMO turning circle in calm water -- clean advance / tactical-diameter KPIs.",
                 sea_state=0),
        Scenario("imo_zigzag10", "zigzag10",
                 "IMO 10/10 zig-zag in calm water -- 1st/2nd overshoot KPIs.",
                 sea_state=0),
        Scenario("imo_zigzag20", "zigzag20",
                 "IMO 20/20 zig-zag in calm water -- larger-amplitude overshoot KPIs.",
                 sea_state=0),
        # --- Seakeeping showcases (fixed rough sea) ---------------------------
        Scenario("rough_turning_circle", "turning_circle",
                 "Turning circle in rough water (SS5, beam swell) -- KPIs unchanged "
                 "(visual proxy), hull heaves/rolls through the turn.",
                 sea_state=5, wave_heading_deg=90.0),
        # --- D3 runtime sea-state SWITCH within one continuous run -------------
        Scenario("building_sea_transit", "demo",
                 "Calm->rough transit: sea builds SS1->SS3->SS5->SS6 over 3 min in "
                 "ONE run (gate D3 runtime switch); beam swell so the hull rolls more "
                 "as it builds.",
                 sea_state_schedule="0:1, 60:3, 120:5, 180:6", wave_heading_deg=90.0),
        Scenario("storm_ride", "demo",
                 "Beam-sea storm build SS3->SS6->SS8 over 90 s (gate D3) -- dramatic "
                 "seakeeping footage for the demo reel.",
                 sea_state_schedule="0:3, 45:6, 90:8", wave_heading_deg=90.0),
        Scenario("easing_sea_zigzag", "zigzag10",
                 "10/10 zig-zag while the sea EASES SS5->SS2->SS0 (gate D3, reverse "
                 "ramp) -- maneuvering KPIs hold as conditions calm.",
                 sea_state_schedule="0:5, 90:2, 150:0", wave_heading_deg=45.0),
        # --- D4 / WP-15: AIS traffic + COLREGS encounters (steady own-ship) ----
        Scenario("head_on_transit", "transit",
                 "Steady transit meeting an inbound vessel head-on -- CPA/TCPA + "
                 "COLREGS Rule 14 (both give way to starboard).",
                 sea_state=2, wave_heading_deg=0.0, ais="head_on"),
        Scenario("crossing_transit", "transit",
                 "Steady transit with a ferry crossing from the starboard bow -- "
                 "COLREGS Rule 15 (own-ship is give-way).",
                 sea_state=2, wave_heading_deg=45.0, ais="crossing"),
        Scenario("overtaking_transit", "transit",
                 "Steady transit overtaking a slow vessel close ahead -- COLREGS "
                 "Rule 13 (own-ship is give-way / must keep clear).",
                 sea_state=2, wave_heading_deg=90.0, ais="overtaking"),
        # --- WP-20260703: single-target COLREGS encounters, SCRIPTED own-ship
        #     avoidance (give-way) or hold (stand-on); compliance scored ----------
        Scenario("colregs_head_on", "avoid_head_on",
                 "COLREGS Rule 14 HEAD-ON: one inbound target fine on the bow; own-ship "
                 "runs a scripted early STARBOARD avoidance; conformance scored.",
                 sea_state=1, wave_heading_deg=0.0, ais="head_on_avoid", plant="mmg"),
        Scenario("colregs_crossing_giveway", "avoid_crossing",
                 "COLREGS Rule 15 CROSSING (target from the STARBOARD bow): own-ship is "
                 "give-way, scripted starboard alteration to pass astern; conformance scored.",
                 sea_state=1, wave_heading_deg=45.0, ais="crossing_avoid", plant="mmg"),
        Scenario("colregs_crossing_standon", "avoid_standon",
                 "COLREGS Rule 17 CROSSING (target from the PORT bow): own-ship is "
                 "stand-on and HOLDS course/speed; conformance scored.",
                 sea_state=1, wave_heading_deg=315.0, ais="crossing_standon",
                 initial_speed_mps=3.4, plant="mmg"),
        Scenario("colregs_overtaking", "avoid_overtaking",
                 "COLREGS Rule 13 OVERTAKING: own-ship overtakes a slow target close "
                 "ahead with a scripted alteration to keep clear; conformance scored.",
                 sea_state=1, wave_heading_deg=90.0, ais="overtaking_avoid", plant="mmg"),
        Scenario("harbor_traffic", "transit",
                 "Port-Hercule approach through mixed AIS traffic (ferry + slow "
                 "vessel + inbound cargo) -- 3 contacts, per-target CPA/TCPA.",
                 sea_state=3, wave_heading_deg=60.0, ais="harbor_mix"),
        Scenario("monaco_capture", "transit",
                 "WP-15B capture: own-ship transits into 3 simultaneous COLREGS "
                 "encounters rendered by the placed Traffic ships (overtaking + "
                 "crossing + head-on; own-ship give-way to all three).",
                 sea_state=2, wave_heading_deg=20.0, ais="monaco_capture"),
    ]
}


def get_scenario(name: str) -> Scenario:
    """Look up a scenario by name. Raises KeyError (with the available names) if
    the name is unknown."""
    key = (name or "").strip()
    if key not in _SCENARIOS:
        raise KeyError(
            f"unknown scenario '{name}'. Available: {', '.join(sorted(_SCENARIOS))}"
        )
    return _SCENARIOS[key]


def list_scenarios() -> List[Scenario]:
    """All scenarios, sorted by name (for `--scenario list`)."""
    return [_SCENARIOS[k] for k in sorted(_SCENARIOS)]


def format_scenarios() -> str:
    """Human-readable table for `--scenario list`."""
    lines = ["Available scenarios (use --scenario <name>):", ""]
    for s in list_scenarios():
        sea = (f"schedule[{s.sea_state_schedule}]" if s.sea_state_schedule
               else f"SS{s.sea_state}")
        ais = f" ais={s.ais}" if s.ais else ""
        lines.append(f"  {s.name:22s} controller={s.controller:14s} {sea}{ais}")
        lines.append(f"  {'':22s} {s.description}")
    return "\n".join(lines)
