"""Demo open-loop controller for bridge smoke testing.

Sends constant throttle and a sinusoidal rudder for N seconds, then stops.
Replace with your NMPC / PPO / hybrid controller once the loop is proven.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class DemoControllerParams:
    # Commanded RPM (applied to both shafts).
    cruise_rpm: float = 900.0
    # Rudder amplitude and period.
    rudder_amplitude_deg: float = 10.0
    rudder_period_seconds: float = 12.0
    # How long to run before commanding idle.
    duration_seconds: float = 30.0
    # Bow thruster: unused in the demo.
    bow_thruster_norm: float = 0.0


@dataclass
class ControllerOutput:
    port_rpm_cmd: float
    starboard_rpm_cmd: float
    rudder_cmd_deg: float
    bow_thruster_cmd_norm: float
    mode: str


class DemoController:
    def __init__(self, params: DemoControllerParams | None = None) -> None:
        self.params = params or DemoControllerParams()

    def step(self, t_sim: float, sensors: dict | None = None) -> ControllerOutput:
        p = self.params
        if t_sim >= p.duration_seconds:
            return ControllerOutput(0.0, 0.0, 0.0, 0.0, "idle")

        omega = 2.0 * math.pi / p.rudder_period_seconds
        rudder = p.rudder_amplitude_deg * math.sin(omega * t_sim)

        return ControllerOutput(
            port_rpm_cmd=p.cruise_rpm,
            starboard_rpm_cmd=p.cruise_rpm,
            rudder_cmd_deg=rudder,
            bow_thruster_cmd_norm=p.bow_thruster_norm,
            mode="auto",
        )
