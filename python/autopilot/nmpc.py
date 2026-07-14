"""Nonlinear Model-Predictive Control for the DOLPHIN.

Approach
--------
Direct shooting over a horizon of `horizon_steps` actuator settings.
Every replan period we re-optimise the control sequence
``U = [u_0, u_1, ..., u_{H-1}]``, where each ``u_k = (rpm, rudder_deg)``.

Cost (sum over the horizon):

    J = w_xy * dist_to_goal_at_terminal_step
      + w_heading * heading_error_at_terminal_step
      + w_speed * (u_surge - target_speed)^2 (per step)
      + w_rudder * rudder_deg^2 (per step)
      + w_drudder * (rudder_k - rudder_{k-1})^2 (per step)

Optimisation is plain projected-gradient descent. Slow but dependency-
free (only numpy + the existing MMG plant). Fine for a 50 ms tick at 1
Hz replan over a horizon of 20-40 steps.

If you later want a faster solver, swap the optimiser for CasADi /
ipopt — the cost / dynamics structure stays the same.

Tuning
------
Defaults are set up for the 38 m DOLPHIN. The most-touched gains are
``w_xy`` (how aggressively to chase the goal) and ``w_drudder`` (how
much to penalise rapid rudder changes). Crank ``w_drudder`` up if the
rudder oscillates; crank ``w_xy`` up if you arrive late.
"""

from __future__ import annotations

import copy
import json
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

# Use the validated MMG plant for prediction.
_HERE = Path(__file__).resolve().parent
_MMG_PARENT = _HERE.parent.parent / "Maneuvering" / "maniobrabilidad"
if str(_MMG_PARENT) not in sys.path:
    sys.path.insert(0, str(_MMG_PARENT))
from mmg import MmgPlant, load_config  # noqa: E402

try:
    from python.scenario_controllers import ControllerOutput
except ImportError:
    @dataclass
    class ControllerOutput:        # type: ignore[no-redef]
        port_rpm_cmd: float
        starboard_rpm_cmd: float
        rudder_cmd_deg: float
        bow_thruster_cmd_norm: float
        mode: str


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class NmpcParams:
    horizon_steps: int = 12
    """Prediction horizon in plant steps. With dt_horizon=2.0 s,
    12 = 24 s ahead. Cost scales as O(H^2 * max_iters) for the
    finite-difference gradient, so keep H modest unless you switch the
    optimiser to something analytic."""

    dt_horizon: float = 2.0
    """Plant integration timestep used inside the horizon predictor (s).
    Larger = lookahead farther for the same compute, at the cost of
    discretisation error. 2 s is a reasonable sweet spot for marine
    dynamics with ~ 60 s timescales."""

    replan_period_s: float = 2.0
    """Re-optimise this often. Between replans the previous control sequence
    is replayed, with a one-step shift."""

    # --- Cost weights ---
    # Terminal cost (only at the end of the horizon).
    w_xy_terminal: float = 0.05      # terminal distance^2 to goal
    w_heading_terminal: float = 0.5  # terminal heading error^2
    # Per-step running cost — critical for long-range goals so the
    # gradient pulls every horizon step toward the goal.
    w_xy_running: float = 0.01       # running distance^2 (per step)
    w_heading_align: float = 0.5     # per-step heading-toward-goal alignment
    w_speed: float = 0.05            # per-step speed deviation cost
    w_rudder: float = 0.005          # per-step |rudder|^2 cost
    w_drudder: float = 0.05          # per-step rudder rate-of-change cost
    w_drpm: float = 1e-5             # per-step rpm rate-of-change cost

    # --- Optimisation ---
    max_iters: int = 10
    learning_rate: float = 0.4
    gradient_eps: float = 1e-2

    # --- Action bounds (must match plant saturation) ---
    rudder_max_deg: float = 35.0
    rpm_max: float = 380.0

    # --- References ---
    target_speed_mps: float = 2.5
    """Desired surge speed during transit. The terminal-stop cost reduces it
    automatically near the goal via the speed schedule."""

    stop_radius_m: float = 25.0
    """Inside this radius, the speed reference is scaled toward 0 so the boat
    decelerates into the dock."""


# ---------------------------------------------------------------------------
# Goal definition (loaded from dockgoals.json or set directly)
# ---------------------------------------------------------------------------

@dataclass
class DockGoal:
    id: str
    x: float
    z: float
    capture_radius: float = 12.0
    required_heading_deg: Optional[float] = None
    approach_tolerance_deg: float = 30.0


def load_goals(goals_file: str) -> List[DockGoal]:
    """Read a navisense.dockgoals.v1 file written by Unity's DockGoalsExporter."""
    with open(goals_file, "r") as f:
        data = json.load(f)
    if data.get("schema") != "navisense.dockgoals.v1":
        print(f"[nmpc] WARNING: '{goals_file}' is not navisense.dockgoals.v1; trying anyway.")
    out: List[DockGoal] = []
    for g in data.get("goals", []):
        rh = g.get("requiredApproachHeadingDeg", -1.0)
        out.append(DockGoal(
            id=g.get("id", "?"),
            x=float(g["x"]),
            z=float(g["z"]),
            capture_radius=float(g.get("captureRadius", 12.0)),
            required_heading_deg=(float(rh) if rh is not None and rh >= 0.0 else None),
            approach_tolerance_deg=float(g.get("approachToleranceDeg", 30.0)),
        ))
    return out


# ---------------------------------------------------------------------------
# NMPC controller
# ---------------------------------------------------------------------------

class NmpcController:
    """NMPC dock-goal tracker matching the listener's ``step(t, sensors)`` API."""

    def __init__(
        self,
        goals: List[DockGoal],
        plant_config_yaml: str = "DOLPHIN.yaml",
        params: Optional[NmpcParams] = None,
        active_goal_id: Optional[str] = None,
    ):
        if not goals:
            raise ValueError("NmpcController needs at least one DockGoal")
        self._goals = goals
        self._params = params or NmpcParams()
        self._predictor = MmgPlant(load_config(plant_config_yaml))

        # Pick first goal by default; can be changed with set_goal().
        self._active = goals[0]
        if active_goal_id is not None:
            for g in goals:
                if g.id == active_goal_id:
                    self._active = g
                    break

        # Warm-start control sequence.
        H = self._params.horizon_steps
        self._U = np.zeros((H, 2), dtype=np.float64)   # [rpm, rudder]
        self._U[:, 0] = self._params.target_speed_mps * 100.0   # rough seed

        self._t_last_replan: Optional[float] = None
        self._step_in_plan: int = 0

    # ------------------------------------------------------------------
    def set_active_goal(self, goal_id: str) -> bool:
        for g in self._goals:
            if g.id == goal_id:
                self._active = g
                return True
        return False

    def step(self, t_sim: float, sensors: Optional[dict]) -> ControllerOutput:
        # Read measured state.
        x, z, heading_deg, u, v, r = self._read_sensors(sensors)

        # Replan?
        if (self._t_last_replan is None
                or t_sim - self._t_last_replan >= self._params.replan_period_s):
            self._optimise(x, z, heading_deg, u, v, r)
            self._t_last_replan = t_sim
            self._step_in_plan = 0
        else:
            # Advance through the plan; clamp at the last step.
            self._step_in_plan = min(self._step_in_plan + 1,
                                      self._params.horizon_steps - 1)

        rpm, rudder = self._U[self._step_in_plan]

        # Determine the active scenario phase for the run logger.
        d = math.hypot(x - self._active.x, z - self._active.z)
        if d <= self._active.capture_radius:
            mode = "captured"
        elif d <= self._params.stop_radius_m:
            mode = "approach"
        else:
            mode = "transit"

        return ControllerOutput(
            port_rpm_cmd=float(rpm),
            starboard_rpm_cmd=float(rpm),
            rudder_cmd_deg=float(rudder),
            bow_thruster_cmd_norm=0.0,
            mode=mode,
        )

    # ==================================================================
    # Optimisation
    # ==================================================================
    def _optimise(self, x: float, z: float, heading_deg: float, u: float, v: float, r: float) -> None:
        H = self._params.horizon_steps
        p = self._params

        # Warm-start: shift the previous plan by one step (the action we
        # just executed) and append a copy of the last action.
        U = np.empty_like(self._U)
        U[:-1] = self._U[1:]
        U[-1] = self._U[-1]

        # Project current state into the predictor.
        self._predictor.state.x = x
        self._predictor.state.z = z
        self._predictor.state.yaw_deg = heading_deg
        self._predictor.state.u = u
        self._predictor.state.v = v
        self._predictor.state.r = r
        # Initial actuator state = first commanded action (saturated).
        self._predictor.state.port_rpm = U[0, 0]
        self._predictor.state.starboard_rpm = U[0, 0]
        self._predictor.state.rudder_deg = U[0, 1]

        # Snapshot for finite-difference rollouts.
        snap = copy.deepcopy(self._predictor.state)

        # Projected gradient descent.
        for it in range(p.max_iters):
            J0 = self._rollout_cost(U, snap)
            grad = np.zeros_like(U)
            for k in range(H):
                for j in range(2):
                    eps = p.gradient_eps * (p.rpm_max if j == 0 else p.rudder_max_deg)
                    Uplus = U.copy(); Uplus[k, j] += eps
                    Jp = self._rollout_cost(Uplus, snap)
                    grad[k, j] = (Jp - J0) / eps

            # Step. Normalise the gradient by its max magnitude so the step
            # size is well-conditioned regardless of cost units.
            gmax = max(1e-9, float(np.max(np.abs(grad))))
            step = grad / gmax
            U_new = U - p.learning_rate * step * np.array([p.rpm_max, p.rudder_max_deg])
            self._project(U_new)
            U = U_new

        self._U = U

    def _rollout_cost(self, U: np.ndarray, snap) -> float:
        """Roll out the predictor with control sequence U and return total cost."""
        p = self._params

        # Reset the predictor state from the snapshot.
        self._predictor.state.x = snap.x
        self._predictor.state.z = snap.z
        self._predictor.state.yaw_deg = snap.yaw_deg
        self._predictor.state.u = snap.u
        self._predictor.state.v = snap.v
        self._predictor.state.r = snap.r
        self._predictor.state.port_rpm = snap.port_rpm
        self._predictor.state.starboard_rpm = snap.starboard_rpm
        self._predictor.state.rudder_deg = snap.rudder_deg

        H = self._params.horizon_steps
        dt = p.dt_horizon
        prev_rpm = snap.port_rpm
        prev_rudder = snap.rudder_deg

        cost = 0.0
        for k in range(H):
            rpm_cmd = float(np.clip(U[k, 0], 0.0, p.rpm_max))
            rud_cmd = float(np.clip(U[k, 1], -p.rudder_max_deg, p.rudder_max_deg))
            self._predictor.apply_commands(rpm_cmd, rpm_cmd, rud_cmd, 0.0)
            self._predictor.step(dt)

            s = self._predictor.state
            # Running goal-distance cost — critical for long-range goals.
            dx = s.x - self._active.x
            dz = s.z - self._active.z
            cost += p.w_xy_running * (dx * dx + dz * dz)

            # Heading-toward-goal alignment (squared error vs bearing-to-goal).
            bearing_to_goal = math.degrees(math.atan2(self._active.x - s.x,
                                                      self._active.z - s.z))
            heading_err = _shortest_angle_deg(s.yaw_deg - bearing_to_goal)
            cost += p.w_heading_align * (heading_err ** 2)

            # Per-step costs.
            v_ref = self._speed_ref(s.x, s.z)
            cost += p.w_speed * (s.u - v_ref) ** 2
            cost += p.w_rudder * (s.rudder_deg ** 2)
            cost += p.w_drudder * ((s.rudder_deg - prev_rudder) ** 2)
            cost += p.w_drpm * ((s.port_rpm - prev_rpm) ** 2)
            prev_rpm = s.port_rpm
            prev_rudder = s.rudder_deg

        # Terminal costs.
        s = self._predictor.state
        dx = s.x - self._active.x
        dz = s.z - self._active.z
        cost += p.w_xy_terminal * (dx * dx + dz * dz)
        if self._active.required_heading_deg is not None:
            err = _shortest_angle_deg(s.yaw_deg - self._active.required_heading_deg)
            cost += p.w_heading_terminal * (err ** 2)

        return cost

    def _speed_ref(self, x: float, z: float) -> float:
        d = math.hypot(x - self._active.x, z - self._active.z)
        if d >= self._params.stop_radius_m:
            return self._params.target_speed_mps
        # Linear deceleration from target -> 0 across the stop radius.
        frac = max(0.0, d / self._params.stop_radius_m)
        return self._params.target_speed_mps * frac

    def _project(self, U: np.ndarray) -> None:
        """In-place box-projection onto the action bounds."""
        np.clip(U[:, 0], 0.0, self._params.rpm_max, out=U[:, 0])
        np.clip(U[:, 1], -self._params.rudder_max_deg, self._params.rudder_max_deg, out=U[:, 1])

    # ==================================================================
    # Helpers
    # ==================================================================
    @staticmethod
    def _read_sensors(sensors: Optional[dict]) -> Tuple[float, float, float, float, float, float]:
        """Returns (x, z, heading_deg, u, v, r). u,v,r are zero if unobservable."""
        if not sensors:
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        s = sensors.get("sensors") or sensors
        gps = s.get("gps") or {}
        imu = s.get("imu") or {}
        wp = gps.get("worldPosition") or {}
        x = _f(wp.get("x"), 0.0)
        z = _f(wp.get("z"), 0.0)
        heading = _f(imu.get("headingDeg"), 0.0)
        # Surge is approximated from gps speed (sign info lost — assume forward).
        u = _f(gps.get("speed"), 0.0)
        # We don't have v / r in the standard sensor packet; predictor uses
        # what it has as the IC, and rolls forward with its own dynamics.
        v = 0.0
        r = math.radians(_f(imu.get("yawRateDegPerSec"), 0.0))
        return x, z, heading, u, v, r


def _f(v, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _shortest_angle_deg(deg: float) -> float:
    deg = ((deg + 180.0) % 360.0) - 180.0
    if deg <= -180.0:
        deg += 360.0
    return deg
