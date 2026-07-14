"""Minimal 3-DOF kinematic yacht stub.

This is NOT an MMG model. It is a deliberately simple placeholder used to
close the Unity <-> Python loop and verify the bridge end to end. The real
plant will replace this module once the bridge is proven.

Coordinate convention (matches BRIDGE_SCHEMA.md):
    +X = East, +Z = North, +Y = Up
    yawDeg = 0 faces +Z (North), +90 faces +X (East)
    Positive rudderDeg causes positive yaw rate (bow swings starboard/east
    when heading North).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class StubPlantParams:
    # First-order surge response: u_dot = (u_target - u) / tau_u
    tau_u_seconds: float = 2.0
    # Map total RPM to steady-state surge speed [m/s per RPM sum].
    # 900 + 900 = 1800 RPM -> ~4.5 m/s. Tune as you like.
    speed_per_total_rpm: float = 4.5 / 1800.0
    # Rudder yaw-rate gain: r_target = gain * rudderDeg * u
    # so the yacht only turns when moving.
    yaw_rate_per_deg_per_speed: float = 0.008
    # First-order yaw-rate response.
    tau_r_seconds: float = 1.0
    # Bow thruster contribution to yaw rate at zero speed [rad/s per unit cmd].
    bow_thruster_yaw_gain: float = 0.15
    # Actuator lag (seconds) from command to actual.
    rudder_tau: float = 0.3
    rpm_tau: float = 0.8
    # Limits.
    max_rudder_deg: float = 35.0
    max_rpm: float = 1800.0


@dataclass
class StubPlantState:
    # Pose (Unity world frame)
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    yaw_deg: float = 0.0

    # Body-frame velocities
    u: float = 0.0  # surge, m/s
    v: float = 0.0  # sway, m/s
    r: float = 0.0  # yaw rate, rad/s

    # Actuator actuals
    port_rpm: float = 0.0
    starboard_rpm: float = 0.0
    rudder_deg: float = 0.0
    bow_thruster_norm: float = 0.0

    # Last commands seen
    port_rpm_cmd: float = 0.0
    starboard_rpm_cmd: float = 0.0
    rudder_cmd_deg: float = 0.0
    bow_thruster_cmd_norm: float = 0.0


@dataclass
class StubPlant:
    params: StubPlantParams = field(default_factory=StubPlantParams)
    state: StubPlantState = field(default_factory=StubPlantState)

    def apply_commands(
        self,
        port_rpm_cmd: float,
        starboard_rpm_cmd: float,
        rudder_cmd_deg: float,
        bow_thruster_cmd_norm: float,
    ) -> None:
        p = self.params
        s = self.state
        s.port_rpm_cmd = _clamp(port_rpm_cmd, -p.max_rpm, p.max_rpm)
        s.starboard_rpm_cmd = _clamp(starboard_rpm_cmd, -p.max_rpm, p.max_rpm)
        s.rudder_cmd_deg = _clamp(rudder_cmd_deg, -p.max_rudder_deg, p.max_rudder_deg)
        s.bow_thruster_cmd_norm = _clamp(bow_thruster_cmd_norm, -1.0, 1.0)

    def step(self, dt: float) -> None:
        """Advance the plant by dt seconds."""
        p = self.params
        s = self.state

        # Actuator first-order lag toward commands.
        s.port_rpm = _first_order(s.port_rpm, s.port_rpm_cmd, p.rpm_tau, dt)
        s.starboard_rpm = _first_order(
            s.starboard_rpm, s.starboard_rpm_cmd, p.rpm_tau, dt
        )
        s.rudder_deg = _first_order(s.rudder_deg, s.rudder_cmd_deg, p.rudder_tau, dt)
        # Bow thruster has no meaningful inertia in this stub.
        s.bow_thruster_norm = s.bow_thruster_cmd_norm

        # Surge response from total RPM.
        total_rpm = s.port_rpm + s.starboard_rpm
        u_target = p.speed_per_total_rpm * total_rpm
        s.u = _first_order(s.u, u_target, p.tau_u_seconds, dt)

        # Yaw rate from rudder (scaled with speed) + bow thruster.
        r_from_rudder = p.yaw_rate_per_deg_per_speed * s.rudder_deg * s.u
        r_from_bt = p.bow_thruster_yaw_gain * s.bow_thruster_norm
        r_target = r_from_rudder + r_from_bt
        s.r = _first_order(s.r, r_target, p.tau_r_seconds, dt)

        # Integrate yaw, then pose in world frame.
        s.yaw_deg = _wrap_deg(s.yaw_deg + math.degrees(s.r) * dt)
        yaw_rad = math.radians(s.yaw_deg)
        # Unity: yaw=0 faces +Z. sin -> +X, cos -> +Z.
        vx = s.u * math.sin(yaw_rad)
        vz = s.u * math.cos(yaw_rad)
        s.x += vx * dt
        s.z += vz * dt
        # y stays on the water plane in this stub.
        s.v = 0.0


def _first_order(current: float, target: float, tau: float, dt: float) -> float:
    if tau <= 1e-6:
        return target
    alpha = 1.0 - math.exp(-dt / tau)
    return current + (target - current) * alpha


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _wrap_deg(deg: float) -> float:
    deg %= 360.0
    if deg < 0.0:
        deg += 360.0
    return deg
