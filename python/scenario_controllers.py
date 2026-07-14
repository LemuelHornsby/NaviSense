"""IMO scenario controllers for the NaviSense bridge.

These controllers drive the MMG plant through standard IMO maneuvering
tests while the bridge streams state to Unity for visualization. They
implement the same ``step(t_sim, sensors) -> ControllerOutput`` contract
as :class:`python.demo_controller.DemoController`, so they drop straight
into :mod:`python_listener` via the ``--controller`` flag.

Controllers:
    TurningCircleController  --controller turning_circle
    ZigzagController         --controller zigzag10   (also zigzag20)

All three use an "approach" phase to bring the ship to steady speed
before the maneuver begins, so Unity sees the same lead-in the offline
tests use.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ControllerOutput:
    port_rpm_cmd: float
    starboard_rpm_cmd: float
    rudder_cmd_deg: float
    bow_thruster_cmd_norm: float
    mode: str


# ---------------------------------------------------------------------------
# Turning circle
# ---------------------------------------------------------------------------
@dataclass
class TurningCircleParams:
    approach_rpm: float = 300.0
    approach_seconds: float = 60.0
    rudder_deg: float = 35.0
    side: str = "stbd"                     # "stbd" or "port"
    turn_seconds: float = 400.0            # total time holding rudder
    # After turn_seconds, rudder zeros and RPM is kept so Unity keeps rendering.
    hold_after_seconds: float = 60.0


class TurningCircleController:
    """Drives an IMO turning-circle test: approach -> hard rudder -> coast."""

    def __init__(self, params: Optional[TurningCircleParams] = None) -> None:
        self.params = params or TurningCircleParams()
        self._sign = +1.0 if self.params.side == "stbd" else -1.0
        self._announced_phase = None

    def step(self, t_sim: float, sensors: dict | None = None) -> ControllerOutput:
        p = self.params

        if t_sim < p.approach_seconds:
            return self._phase("approach", p.approach_rpm, p.approach_rpm, 0.0, 0.0)

        t_after = t_sim - p.approach_seconds
        if t_after < p.turn_seconds:
            return self._phase(
                "turning_circle",
                p.approach_rpm, p.approach_rpm,
                self._sign * p.rudder_deg,
                0.0,
            )

        if t_after < p.turn_seconds + p.hold_after_seconds:
            return self._phase("coast", p.approach_rpm, p.approach_rpm, 0.0, 0.0)

        return self._phase("idle", 0.0, 0.0, 0.0, 0.0)

    def _phase(self, mode: str, pr: float, sr: float, rud: float, bt: float) -> ControllerOutput:
        if mode != self._announced_phase:
            print(f"[scenario] turning-circle -> {mode}")
            self._announced_phase = mode
        return ControllerOutput(pr, sr, rud, bt, mode)


# ---------------------------------------------------------------------------
# Zig-zag
# ---------------------------------------------------------------------------
@dataclass
class ZigzagParams:
    approach_rpm: float = 300.0
    approach_seconds: float = 60.0
    angle_deg: float = 10.0                 # 10 for 10/10, 20 for 20/20
    max_seconds: float = 600.0              # maneuver duration cap
    n_reversals: int = 4
    # After the maneuver ends, rudder zeros. RPM kept so Unity can keep panning.
    hold_after_seconds: float = 60.0


class ZigzagController:
    """Drives an IMO zig-zag test (10/10 or 20/20) over the live bridge.

    The controller uses the vessel's own heading (read from the sensor
    packet, field ``yawDeg``) to detect trigger crossings, exactly as the
    offline test does.
    """

    def __init__(self, params: Optional[ZigzagParams] = None) -> None:
        self.params = params or ZigzagParams()
        self._announced_phase = None

        # Maneuver state, populated when we leave the approach phase.
        self._in_maneuver = False
        self._yaw0: Optional[float] = None
        self._last_yaw: Optional[float] = None
        self._unwrapped_yaw: float = 0.0
        self._rudder_sign: float = +1.0
        self._reversals_done: int = 0
        self._maneuver_done: bool = False
        self._maneuver_start_t: Optional[float] = None

    def step(self, t_sim: float, sensors: dict | None = None) -> ControllerOutput:
        p = self.params

        # ----- approach -----
        if t_sim < p.approach_seconds:
            return self._phase("approach", p.approach_rpm, p.approach_rpm, 0.0, 0.0)

        # ----- maneuver enter -----
        if not self._in_maneuver and not self._maneuver_done:
            yaw_now = self._yaw_from(sensors)
            if yaw_now is None:
                # Haven't seen a packet yet; hold steady.
                return self._phase("approach", p.approach_rpm, p.approach_rpm, 0.0, 0.0)
            self._yaw0 = yaw_now
            self._last_yaw = yaw_now
            self._unwrapped_yaw = yaw_now
            self._rudder_sign = +1.0
            self._reversals_done = 0
            self._maneuver_start_t = t_sim
            self._in_maneuver = True

        # ----- after maneuver -----
        if self._maneuver_done:
            t_after = t_sim - (self._maneuver_start_t or t_sim)
            if t_after < p.max_seconds + p.hold_after_seconds:
                return self._phase("coast", p.approach_rpm, p.approach_rpm, 0.0, 0.0)
            return self._phase("idle", 0.0, 0.0, 0.0, 0.0)

        # ----- maneuver run -----
        yaw_now = self._yaw_from(sensors)
        if yaw_now is not None:
            # Unwrap step-to-step.
            delta = yaw_now - (self._last_yaw if self._last_yaw is not None else yaw_now)
            if delta > 180.0:
                delta -= 360.0
            elif delta < -180.0:
                delta += 360.0
            self._unwrapped_yaw += delta
            self._last_yaw = yaw_now

            dh = self._unwrapped_yaw - (self._yaw0 or 0.0)
            crossed = (self._rudder_sign > 0 and dh >= p.angle_deg) or (
                self._rudder_sign < 0 and dh <= -p.angle_deg
            )
            if crossed:
                self._reversals_done += 1
                self._rudder_sign *= -1.0
                print(
                    f"[scenario] zigzag reversal #{self._reversals_done}: "
                    f"dh={dh:+.2f}, rudder->{self._rudder_sign * p.angle_deg:+.1f} deg"
                )

        # Timeout or reversal count exit.
        t_in = t_sim - (self._maneuver_start_t or t_sim)
        if self._reversals_done >= p.n_reversals + 1 or t_in >= p.max_seconds:
            self._maneuver_done = True
            return self._phase("coast", p.approach_rpm, p.approach_rpm, 0.0, 0.0)

        return self._phase(
            f"zigzag_{int(p.angle_deg)}",
            p.approach_rpm,
            p.approach_rpm,
            self._rudder_sign * p.angle_deg,
            0.0,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _yaw_from(sensors: dict | None) -> Optional[float]:
        """Extract heading from an incoming Unity sensor packet.

        Tolerates both the nested ``navisense.sensor.v1`` layout
        (``sensors.imu.headingDeg``) and flat testing payloads that put
        ``yawDeg`` or ``headingDeg`` at the top level.
        """
        if not sensors:
            return None
        # Nested Unity packet: sensors.sensors.imu.headingDeg
        s = sensors.get("sensors")
        if isinstance(s, dict):
            imu = s.get("imu")
            if isinstance(imu, dict) and "headingDeg" in imu:
                try:
                    return float(imu["headingDeg"])
                except (TypeError, ValueError):
                    pass
        # Flat fallbacks.
        for key in ("yawDeg", "headingDeg"):
            y = sensors.get(key)
            if y is not None:
                try:
                    return float(y)
                except (TypeError, ValueError):
                    pass
        return None

    def _phase(self, mode: str, pr: float, sr: float, rud: float, bt: float) -> ControllerOutput:
        if mode != self._announced_phase:
            print(f"[scenario] zigzag -> {mode}")
            self._announced_phase = mode
        return ControllerOutput(pr, sr, rud, bt, mode)


# ---------------------------------------------------------------------------
# Steady transit (own-ship for AIS / COLREGS encounter scenarios)
# ---------------------------------------------------------------------------
@dataclass
class TransitParams:
    cruise_rpm: float = 300.0      # steady service-speed RPM (matches scenario lead-in)
    rudder_deg: float = 0.0        # straight ahead -> a clean steady course for COLREGS


class TransitController:
    """Drive the ship straight ahead at a steady cruise RPM (zero rudder).

    This is the own-ship for the AIS / COLREGS encounter scenarios (WP-15): a
    steady course is what makes a head-on / crossing / overtaking geometry a
    textbook encounter for CPA/TCPA + rule classification, unlike the IMO
    maneuvering controllers which turn the ship. Same ``step`` contract as the
    others; mode is always ``transit``.
    """

    def __init__(self, params: Optional["TransitParams"] = None) -> None:
        self.params = params or TransitParams()
        self._announced = False

    def step(self, t_sim: float, sensors: dict | None = None) -> ControllerOutput:
        if not self._announced:
            print("[scenario] transit -> steady course")
            self._announced = True
        p = self.params
        return ControllerOutput(p.cruise_rpm, p.cruise_rpm, p.rudder_deg, 0.0, "transit")


# ---------------------------------------------------------------------------
# COLREGS scripted avoidance (WP-20260703)
# ---------------------------------------------------------------------------
@dataclass
class ColregsAvoidParams:
    """Scripted own-ship avoidance for ONE COLREGS encounter, executed as a
    closed-loop heading hold (the controller is fed the plant's authoritative yaw,
    invariant #5). The maneuver is fully scripted/deterministic: hold the base
    course, then for a GIVE-WAY encounter (head_on / crossing_giveway / overtaking)
    turn a BOUNDED amount to STARBOARD at ``alter_start_s`` (Rules 8/14/15/16 --
    ample time, made in good time, to starboard, safe distance), hold the new
    course through CPA, then resume the base course. The STAND-ON encounter
    (crossing_standon, Rule 17) holds the base course/speed throughout -- no
    alteration. colregs_score then MEASURES conformance; these defaults are tuned so
    a give-way run scores COMPLIANT (realistic ~35 deg alteration, miss >= 200 m)
    and the stand-on hold scores COMPLIANT.
    """
    encounter: str = "head_on"        # head_on | crossing_giveway | overtaking | crossing_standon
    cruise_rpm: float = 300.0
    alter_start_s: float = 20.0       # begin the alteration well before CPA (Rule 8a "ample time")
    alter_deg: float = 35.0           # +ve = STARBOARD heading change from the base course
    alter_end_s: float = 220.0        # resume the base course after this (hold the new course through CPA)
    ramp_s: float = 40.0              # ramp the heading setpoint over this long (gentle, no rudder saturation)
    kp: float = 1.5                   # heading-hold P gain (deg rudder per deg error)
    kd: float = 10.0                  # heading-hold D gain (deg rudder per deg/s yaw rate) -- damps overshoot
    max_rudder_deg: float = 20.0      # rudder clamp


def _wrap180(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


class ColregsAvoidController:
    """Own-ship for a single COLREGS encounter: a scripted, deterministic starboard
    alteration (give-way) or a course/speed hold (stand-on), executed as a bounded
    heading hold on the plant's authoritative yaw. Same ``step`` contract as the
    other scenario controllers.
    """

    _GIVE_WAY = {"head_on", "crossing_giveway", "overtaking"}

    def __init__(self, params=None) -> None:
        self.params = params or ColregsAvoidParams()
        self._base_heading = None
        self._last_yaw = None
        self._last_t = None
        self._announced = False

    def _target_heading(self, t_sim: float) -> float:
        """Ramped starboard setpoint: hold base, ramp to base+alter over ramp_s,
        hold the new course through CPA, then ramp back to base. Ramping keeps the
        heading error small so the turn is gentle and never saturates the rudder."""
        p = self.params
        base = self._base_heading or 0.0
        if p.encounter == "crossing_standon":
            return base                                   # Rule 17: hold course
        r = max(p.ramp_s, 1e-3)
        if t_sim < p.alter_start_s:
            return base
        if t_sim < p.alter_start_s + r:                   # ramp OUT to the avoidance course
            return base + p.alter_deg * (t_sim - p.alter_start_s) / r
        if t_sim < p.alter_end_s:                         # hold the new course through CPA
            return base + p.alter_deg
        if t_sim < p.alter_end_s + r:                     # ramp BACK to the base course
            return base + p.alter_deg * (1.0 - (t_sim - p.alter_end_s) / r)
        return base

    def step(self, t_sim: float, sensors: dict | None = None) -> ControllerOutput:
        p = self.params
        yaw = float(sensors.get("yawDeg", 0.0)) if sensors else 0.0
        if self._base_heading is None:
            self._base_heading = yaw                       # capture the initial course once
        if not self._announced:
            print(f"[scenario] colregs_avoid -> {p.encounter} (base heading {self._base_heading:.1f} deg)")
            self._announced = True

        # Estimate yaw rate internally (deg/s) for the damping term.
        if self._last_yaw is None or self._last_t is None or t_sim <= self._last_t:
            rate = 0.0
        else:
            rate = _wrap180(yaw - self._last_yaw) / max(t_sim - self._last_t, 1e-3)
        self._last_yaw, self._last_t = yaw, t_sim

        tgt = self._target_heading(t_sim)
        err = _wrap180(tgt - yaw)                           # +err => need to turn starboard
        rudder = p.kp * err - p.kd * rate                   # PD heading hold (damped)
        rudder = max(-p.max_rudder_deg, min(p.max_rudder_deg, rudder))

        if p.encounter == "crossing_standon":
            mode = "standon_hold"
        elif t_sim < p.alter_start_s:
            mode = "approach"
        elif t_sim < p.alter_end_s:
            mode = "avoid_starboard"
        else:
            mode = "resume"
        return ControllerOutput(p.cruise_rpm, p.cruise_rpm, rudder, 0.0, mode)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def make_scenario_controller(kind: str):
    """Map a ``--controller`` name to a concrete scenario controller."""
    k = kind.lower()
    if k in ("turning_circle", "turn", "turning"):
        return TurningCircleController()
    if k in ("zigzag10", "zigzag", "zz10"):
        return ZigzagController(ZigzagParams(angle_deg=10.0))
    if k in ("zigzag20", "zz20"):
        return ZigzagController(ZigzagParams(angle_deg=20.0))
    if k in ("transit", "straight", "steady"):
        return TransitController()
    if k in ("avoid_head_on", "colregs_head_on"):
        return ColregsAvoidController(ColregsAvoidParams(encounter="head_on", alter_start_s=20.0, alter_deg=55.0, ramp_s=20.0, alter_end_s=130.0))  # 14 Jul v3: turn t=24 s (~380 m, near the Rule-8 floor), snappier 20 s ramp, target 3 kn
    if k in ("avoid_crossing", "avoid_crossing_giveway", "colregs_crossing_giveway"):
        return ColregsAvoidController(ColregsAvoidParams(encounter="crossing_giveway", alter_start_s=18.0, alter_deg=45.0, alter_end_s=130.0))  # 14 Jul: matched to the closer 720 m staging
    if k in ("avoid_standon", "avoid_crossing_standon", "colregs_crossing_standon"):
        return ColregsAvoidController(ColregsAvoidParams(encounter="crossing_standon"))
    if k in ("avoid_overtaking", "colregs_overtaking"):
        return ColregsAvoidController(ColregsAvoidParams(encounter="overtaking", alter_start_s=25.0, alter_deg=45.0, alter_end_s=170.0))
    raise ValueError(f"Unknown scenario controller: {kind!r}")
