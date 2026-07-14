"""Waypoint follower: LOS guidance + heading PID + speed PID.

Implements the same ``step(t_sim, sensors) -> ControllerOutput`` contract
as the rest of the controllers in ``python/`` so it plugs into
``python_listener.py``'s ``--controller`` flag.

Architecture
------------

::

    sensors (gps + imu)
        |
        v
    LosGuidance --------> desired heading
                                |
                                v
                          headingPid -----> rudder cmd
                                |
                                v
                          speedPid -------> rpm cmd (port + stbd)

Path source
-----------

The path is a JSON file matching the schema written by Unity's
:class:`WaypointPathExporter` (``navisense.path.v1``). Pass the file path
via the ``path_file`` argument to the constructor or
``WaypointFollowerController.from_path_file(...)``.

Schema (relevant fields):

.. code:: json

   {
     "schema": "navisense.path.v1",
     "waypoints": [
       { "x": 0,   "z": 0   },
       { "x": 50,  "z": 100 },
       ...
     ],
     "loop": false
   }
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .los import LosGuidance
from .pid import PID

try:
    # Re-use the ControllerOutput dataclass from scenario_controllers so
    # python_listener can dispatch us identically.
    from python.scenario_controllers import ControllerOutput
except ImportError:
    @dataclass
    class ControllerOutput:        # type: ignore[no-redef]
        port_rpm_cmd: float
        starboard_rpm_cmd: float
        rudder_cmd_deg: float
        bow_thruster_cmd_norm: float
        mode: str


@dataclass
class WaypointFollowerParams:
    target_speed_mps: float = 2.5
    """Cruise speed the speed-PID tracks. Adjust per scenario."""

    rpm_cruise: float = 300.0
    """Feed-forward RPM that, with no PID correction, gives ~ target_speed_mps
    on the DOLPHIN at calm-water cruise."""

    max_rpm: float = 380.0
    """Saturation; matches MMG plant's max."""

    max_rudder_deg: float = 35.0
    """Saturation; matches MMG plant's max."""

    # Heading-PID (rudder).
    heading_kp: float = 1.5
    heading_ki: float = 0.0
    heading_kd: float = 5.0
    heading_rate_limit_deg_per_sec: float = 8.0
    """Limit how fast the rudder command itself can change. Combined with
    plant-side actuator dynamics (~ 4 deg/s), this gives smooth rudder
    motion without saturation chatter."""

    # Speed-PID (rpm). Acts on |u| (surge speed magnitude).
    speed_kp: float = 200.0
    speed_ki: float = 30.0
    speed_kd: float = 0.0
    speed_i_clamp: float = 100.0

    # LOS.
    los_lookahead_m: float = 30.0
    los_accept_radius_m: float = 8.0
    los_loop: bool = False


class WaypointFollowerController:
    """Top-level autopilot controller wiring LOS + heading-PID + speed-PID."""

    def __init__(
        self,
        waypoints: List[Tuple[float, float]],
        params: Optional[WaypointFollowerParams] = None,
    ):
        if not waypoints or len(waypoints) < 2:
            raise ValueError("WaypointFollowerController needs at least 2 waypoints.")

        self.waypoints = waypoints
        self.params = params or WaypointFollowerParams()

        self._los = LosGuidance(
            lookahead_meters=self.params.los_lookahead_m,
            accept_radius_meters=self.params.los_accept_radius_m,
            loop=self.params.los_loop,
        )

        self._heading_pid = PID(
            kp=self.params.heading_kp,
            ki=self.params.heading_ki,
            kd=self.params.heading_kd,
            output_min=-self.params.max_rudder_deg,
            output_max=+self.params.max_rudder_deg,
            rate_limit=self.params.heading_rate_limit_deg_per_sec,
        )

        self._speed_pid = PID(
            kp=self.params.speed_kp,
            ki=self.params.speed_ki,
            kd=self.params.speed_kd,
            i_clamp=self.params.speed_i_clamp,
            output_min=-self.params.max_rpm,
            output_max=+self.params.max_rpm,
        )

        self._last_t: Optional[float] = None
        self._announced_phase: Optional[str] = None

    # ------------------------------------------------------------------
    @classmethod
    def from_path_file(
        cls,
        path_file: str,
        params: Optional[WaypointFollowerParams] = None,
    ) -> "WaypointFollowerController":
        """Load a navisense.path.v1 JSON file and build a follower from it."""
        with open(path_file, "r") as f:
            data = json.load(f)
        if data.get("schema") != "navisense.path.v1":
            print(f"[autopilot] WARNING: '{path_file}' schema "
                  f"{data.get('schema')!r} not navisense.path.v1; trying anyway.")
        wps_in = data.get("waypoints", [])
        wps = [(float(w["x"]), float(w["z"])) for w in wps_in]
        if not params:
            params = WaypointFollowerParams()
        params.los_loop = bool(data.get("loop", params.los_loop))
        return cls(wps, params)

    # ------------------------------------------------------------------
    def step(self, t_sim: float, sensors: Optional[dict]) -> ControllerOutput:
        """Compute one control cycle.

        Reads ownship XZ, heading, and surge speed from the sensor packet:

        * ``sensors.gps.worldPosition.{x,z}`` for position.
        * ``sensors.imu.headingDeg`` for heading.
        * ``sensors.gps.speed`` for surge magnitude.

        Falls back to zeros if any field is missing.
        """
        # dt
        if self._last_t is None:
            dt = 0.02
        else:
            dt = max(1e-3, t_sim - self._last_t)
        self._last_t = t_sim

        # Read sensors.
        ox, oz, heading_deg, surge = self._read_sensors(sensors)

        # Guidance: desired heading (deg).
        desired_heading_deg = self._los.desired_heading_deg((ox, oz), self.waypoints)

        # Heading error (signed, -180..+180).
        heading_err = _shortest_angle_deg(desired_heading_deg - heading_deg)
        # Heading PID acts on the error: setpoint=0, measurement = -err
        # so a positive error commands positive rudder.
        rudder_cmd = self._heading_pid.step(setpoint=0.0, measurement=-heading_err, dt=dt)

        # Speed PID: target the cruise speed.
        rpm_correction = self._speed_pid.step(
            setpoint=self.params.target_speed_mps,
            measurement=surge,
            dt=dt,
        )
        rpm_cmd = self.params.rpm_cruise + rpm_correction
        rpm_cmd = max(-self.params.max_rpm, min(self.params.max_rpm, rpm_cmd))

        # Phase tracking for the run logger.
        phase = self._classify_phase(ox, oz)
        if phase != self._announced_phase:
            print(f"[autopilot] -> {phase} (heading_err={heading_err:+.1f} xte={self._los.cross_track_error_meters((ox, oz), self.waypoints):+.1f})")
            self._announced_phase = phase

        return ControllerOutput(
            port_rpm_cmd=rpm_cmd,
            starboard_rpm_cmd=rpm_cmd,
            rudder_cmd_deg=rudder_cmd,
            bow_thruster_cmd_norm=0.0,
            mode=phase,
        )

    # ------------------------------------------------------------------
    def _classify_phase(self, ox: float, oz: float) -> str:
        # Simple classifier for the run logger's mode_change event:
        # 'approach' until we capture the first leg; otherwise 'follow';
        # 'arrived' when we exhaust legs.
        leg = self._los._leg_idx
        if leg == 0:
            return "approach"
        if not self.params.los_loop and leg >= len(self.waypoints) - 1:
            return "arrived"
        return "follow"

    @staticmethod
    def _read_sensors(sensors: Optional[dict]) -> Tuple[float, float, float, float]:
        """Returns (x, z, heading_deg, surge_speed_mps)."""
        if not sensors:
            return 0.0, 0.0, 0.0, 0.0
        s = sensors.get("sensors") or sensors
        gps = s.get("gps") or {}
        imu = s.get("imu") or {}
        wp = gps.get("worldPosition") or {}
        x = _f(wp.get("x"), 0.0)
        z = _f(wp.get("z"), 0.0)
        speed = _f(gps.get("speed"), 0.0)
        heading = _f(imu.get("headingDeg"), 0.0)
        return x, z, heading, abs(speed)


def _f(v, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _shortest_angle_deg(deg: float) -> float:
    """Wrap to (-180, +180]."""
    deg = ((deg + 180.0) % 360.0) - 180.0
    if deg <= -180.0:
        deg += 360.0
    return deg
