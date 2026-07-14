"""3-DOF MMG plant integrator.

Equations of motion (body frame, origin at midship):

    (m + m_x) u_dot - (m + m_y) v r - m*x_G*r^2              =  X
    (m + m_y) v_dot + (m + m_x) u r + m*x_G*r_dot            =  Y
    (I_zz + J_zz) r_dot + m*x_G*(v_dot + u r)                =  N

Matrix form:
    M * [u_dot, v_dot, r_dot]^T = RHS
where
    M = [[m+m_x, 0,         0          ],
         [0,     m+m_y,     m*x_G      ],
         [0,     m*x_G,     I_zz+J_zz  ]]
    RHS_u = X + (m + m_y) v r + m*x_G*r^2
    RHS_v = Y - (m + m_x) u r
    RHS_r = N - m*x_G*u*r

Total forces:
    X = X_H + X_P + X_R + X_BT(=0) + Coriolis already folded into RHS_u
    Y = Y_H + Y_P(=0) + Y_R + Y_BT
    N = N_H + N_P       + N_R + N_BT

World-frame kinematics (yaw=0 faces +Z in the Unity convention):
    x_dot = u * sin(yaw) + v * cos(yaw)
    z_dot = u * cos(yaw) - v * sin(yaw)
    yaw_dot = r

Actuator dynamics (first-order lag + rate limit + saturation) also live
here so the plant presents a single "I am the whole ship" interface to
python_listener. This mirrors the Unity-side ActuatorController; in a
closed-loop run only one of them simulates dynamics at any time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .bow_thruster import BowThrusterForces, compute_bow_thruster_forces
from .config import ShipConfig
from .environment import EnvironmentField
from .hull import HullForces, compute_hull_forces
from .propeller import PropellerForces, compute_propeller_forces
from .rudder import RudderForces, compute_rudder_forces


# ---------------------------------------------------------------------------
# Plant state (what Unity and controllers see)
# ---------------------------------------------------------------------------
@dataclass
class MmgPlantState:
    # World-frame pose (Unity convention: +X=East, +Z=North, +Y=Up, yaw=0 -> +Z)
    x: float = 0.0
    y: float = 0.0            # kept on the water plane; hydrostatics owns Y in Unity
    z: float = 0.0
    yaw_deg: float = 0.0

    # Body-frame velocities
    u: float = 0.0
    v: float = 0.0
    r: float = 0.0

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
class MmgActuatorDynamics:
    """Must mirror the Unity side. Values are sane DOLPHIN defaults."""
    max_rpm: float = 300.0
    max_rpm_rate: float = 120.0
    rpm_tau: float = 1.0

    max_rudder_deg: float = 35.0
    max_rudder_rate: float = 5.0
    rudder_tau: float = 0.1

    max_bow_thruster_rate: float = 1.0
    bow_thruster_tau: float = 0.5


# ---------------------------------------------------------------------------
# Plant
# ---------------------------------------------------------------------------
@dataclass
class MmgPlant:
    config: ShipConfig
    state: MmgPlantState = field(default_factory=MmgPlantState)
    actuator: MmgActuatorDynamics = field(default_factory=MmgActuatorDynamics)
    environment: Optional[EnvironmentField] = None

    # Latest diagnostic breakdown (useful for logging).
    last_hull: Optional[HullForces] = None
    last_prop: Optional[PropellerForces] = None
    last_rudder: Optional[RudderForces] = None
    last_bow_thruster: Optional[BowThrusterForces] = None
    last_wind_force: tuple = (0.0, 0.0, 0.0)   # (X_W, Y_W, N_W)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def apply_commands(
        self,
        port_rpm_cmd: float,
        starboard_rpm_cmd: float,
        rudder_cmd_deg: float,
        bow_thruster_cmd_norm: float,
    ) -> None:
        s = self.state
        a = self.actuator
        s.port_rpm_cmd = _clamp(port_rpm_cmd, -a.max_rpm, a.max_rpm)
        s.starboard_rpm_cmd = _clamp(starboard_rpm_cmd, -a.max_rpm, a.max_rpm)
        s.rudder_cmd_deg = _clamp(rudder_cmd_deg, -a.max_rudder_deg, a.max_rudder_deg)
        s.bow_thruster_cmd_norm = _clamp(bow_thruster_cmd_norm, -1.0, 1.0)

    def step(self, dt: float) -> None:
        """Advance the full plant by dt seconds."""
        if dt <= 0.0:
            return

        # 0) Advance environmental noise (gusts) once per step. The wind
        #    + current direction/speed used inside _derivatives is a
        #    snapshot of this updated state. RK4's four sub-evaluations
        #    all see the same gust value, which is correct: gusts evolve
        #    on a slower timescale than dt.
        if self.environment is not None:
            self.environment.tick(dt)

        # 1) Actuator dynamics (first-order lag + rate limit).
        self._step_actuators(dt)

        # 2) Rigid-body motion via RK4 on body-frame [u, v, r] and
        #    world-frame [x, z, yaw]. We use one RK4 step for dt.
        method = self.config.integrator.method.lower()
        if method == "rk4":
            self._integrate_rk4(dt)
        else:
            self._integrate_euler(dt)

    # ------------------------------------------------------------------
    # Actuator sub-step
    # ------------------------------------------------------------------
    def _step_actuators(self, dt: float) -> None:
        s = self.state
        a = self.actuator

        s.port_rpm = _lag_then_rate(
            s.port_rpm, s.port_rpm_cmd, a.rpm_tau, a.max_rpm_rate, dt,
        )
        s.starboard_rpm = _lag_then_rate(
            s.starboard_rpm, s.starboard_rpm_cmd, a.rpm_tau, a.max_rpm_rate, dt,
        )
        s.rudder_deg = _lag_then_rate(
            s.rudder_deg, s.rudder_cmd_deg, a.rudder_tau, a.max_rudder_rate, dt,
        )
        s.rudder_deg = _clamp(s.rudder_deg, -a.max_rudder_deg, a.max_rudder_deg)
        s.bow_thruster_norm = _lag_then_rate(
            s.bow_thruster_norm,
            s.bow_thruster_cmd_norm,
            a.bow_thruster_tau,
            a.max_bow_thruster_rate,
            dt,
        )

    # ------------------------------------------------------------------
    # Rigid body + kinematic integration
    # ------------------------------------------------------------------
    def _derivatives(
        self, u: float, v: float, r: float, yaw_rad: float,
    ) -> tuple[float, float, float, float, float, float]:
        """Evaluate [u_dot, v_dot, r_dot, x_dot, z_dot, yaw_dot] at the given state."""
        c = self.config
        rho = c.environment.rho_water

        # --- Environment (wind + current). The current shifts the water
        #     frame relative to the world, so the hull / rudder / propeller
        #     experience the relative water velocity (u_r, v_r). Wind adds
        #     a separate aerodynamic force on the superstructure.
        u_r = u
        v_r = v
        wind_X = wind_Y = wind_N = 0.0
        if self.environment is not None:
            u_c, v_c = self.environment.current_velocity_body(yaw_rad)
            u_r = u - u_c
            v_r = v - v_c
            wind_X, wind_Y, wind_N = self.environment.wind_force_body(u, v, yaw_rad)
            self.last_wind_force = (wind_X, wind_Y, wind_N)

        # --- Forces ---
        hull = compute_hull_forces(u_r, v_r, r, c.ship, c.hull, rho)
        prop = compute_propeller_forces(
            u_r, self.state.port_rpm, self.state.starboard_rpm, c.propeller, rho,
        )
        rudder = compute_rudder_forces(
            u_r, v_r, r, math.radians(self.state.rudder_deg),
            prop.port_thrust_N, prop.starboard_thrust_N,
            c.ship, c.propeller, c.rudder, rho,
        )
        bow = compute_bow_thruster_forces(u_r, self.state.bow_thruster_norm, c.bow_thruster)

        self.last_hull = hull
        self.last_prop = prop
        self.last_rudder = rudder
        self.last_bow_thruster = bow

        # --- Right-hand side (forces + Coriolis) ---
        m = c.ship.displacement_mass
        m_x = c.ship.m_x
        m_y = c.ship.m_y
        x_G = c.ship.x_G
        I_zz = c.ship.I_zz
        J_zz = c.ship.J_zz

        X = hull.X_H + prop.X_P + rudder.X_R + wind_X
        Y = hull.Y_H + rudder.Y_R + bow.Y_BT + wind_Y
        N = hull.N_H + prop.N_P + rudder.N_R + bow.N_BT + wind_N

        rhs_u = X + (m + m_y) * v * r + m * x_G * r * r
        rhs_v = Y - (m + m_x) * u * r
        rhs_r = N - m * x_G * u * r

        # --- Solve M * [u_dot, v_dot, r_dot]^T = rhs ---
        # M is block diagonal in surge vs (sway, yaw), so invert 2x2 explicitly.
        u_dot = rhs_u / (m + m_x)

        a11 = m + m_y
        a12 = m * x_G
        a21 = m * x_G
        a22 = I_zz + J_zz
        det = a11 * a22 - a12 * a21
        if abs(det) < 1e-6:
            v_dot = rhs_v / a11
            r_dot = rhs_r / a22
        else:
            v_dot = (a22 * rhs_v - a12 * rhs_r) / det
            r_dot = (-a21 * rhs_v + a11 * rhs_r) / det

        # --- World-frame kinematics (Unity: yaw=0 -> +Z) ---
        sin_y = math.sin(yaw_rad)
        cos_y = math.cos(yaw_rad)
        x_dot = u * sin_y + v * cos_y
        z_dot = u * cos_y - v * sin_y
        yaw_dot = r

        return u_dot, v_dot, r_dot, x_dot, z_dot, yaw_dot

    def _integrate_euler(self, dt: float) -> None:
        s = self.state
        yaw_rad = math.radians(s.yaw_deg)
        u_dot, v_dot, r_dot, x_dot, z_dot, yaw_dot = self._derivatives(
            s.u, s.v, s.r, yaw_rad,
        )
        s.u += u_dot * dt
        s.v += v_dot * dt
        s.r += r_dot * dt
        s.x += x_dot * dt
        s.z += z_dot * dt
        s.yaw_deg = _wrap_deg(s.yaw_deg + math.degrees(yaw_dot) * dt)

    def _integrate_rk4(self, dt: float) -> None:
        s = self.state
        n_sub = max(1, self.config.integrator.max_substeps)
        h = dt / n_sub

        for _ in range(n_sub):
            u0, v0, r0 = s.u, s.v, s.r
            x0, z0 = s.x, s.z
            yaw0 = math.radians(s.yaw_deg)

            # k1
            k1 = self._derivatives(u0, v0, r0, yaw0)

            # k2 at h/2
            u_a = u0 + 0.5 * h * k1[0]
            v_a = v0 + 0.5 * h * k1[1]
            r_a = r0 + 0.5 * h * k1[2]
            yaw_a = yaw0 + 0.5 * h * k1[5]
            k2 = self._derivatives(u_a, v_a, r_a, yaw_a)

            # k3 at h/2
            u_b = u0 + 0.5 * h * k2[0]
            v_b = v0 + 0.5 * h * k2[1]
            r_b = r0 + 0.5 * h * k2[2]
            yaw_b = yaw0 + 0.5 * h * k2[5]
            k3 = self._derivatives(u_b, v_b, r_b, yaw_b)

            # k4 at h
            u_c = u0 + h * k3[0]
            v_c = v0 + h * k3[1]
            r_c = r0 + h * k3[2]
            yaw_c = yaw0 + h * k3[5]
            k4 = self._derivatives(u_c, v_c, r_c, yaw_c)

            # Combine
            s.u = u0 + h * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]) / 6.0
            s.v = v0 + h * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]) / 6.0
            s.r = r0 + h * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2]) / 6.0
            s.x = x0 + h * (k1[3] + 2 * k2[3] + 2 * k3[3] + k4[3]) / 6.0
            s.z = z0 + h * (k1[4] + 2 * k2[4] + 2 * k3[4] + k4[4]) / 6.0

            yaw_new = yaw0 + h * (k1[5] + 2 * k2[5] + 2 * k3[5] + k4[5]) / 6.0
            s.yaw_deg = _wrap_deg(math.degrees(yaw_new))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _lag_then_rate(current: float, target: float, tau: float, max_rate: float, dt: float) -> float:
    if tau <= 1e-6:
        lagged = target
    else:
        alpha = 1.0 - math.exp(-dt / tau)
        lagged = current + (target - current) * alpha
    max_step = max_rate * dt
    delta = max(-max_step, min(max_step, lagged - current))
    return current + delta


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _wrap_deg(deg: float) -> float:
    deg %= 360.0
    if deg < 0.0:
        deg += 360.0
    return deg
