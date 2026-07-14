"""Trained PPO policy controller for the live bridge.

Loads a Stable-Baselines3 PPO checkpoint produced by train_ppo.py and
acts on real sensor packets coming through python_listener.

Plugs into the listener via ``--controller ppo --policy-file <path>``.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np

_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from python.autopilot.nmpc import DockGoal, load_goals

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


class PpoPolicyController:
    """Wraps a trained SB3 PPO policy. Builds the same observation vector as
    YachtEnv so the policy's input distribution matches what it trained on.
    """

    def __init__(
        self,
        policy_file: str,
        goals_file: str,
        active_goal_id: Optional[str] = None,
        rpm_max: float = 380.0,
        rudder_max_deg: float = 35.0,
    ):
        try:
            from stable_baselines3 import PPO
        except ImportError as e:
            raise ImportError(
                "PpoPolicyController requires stable-baselines3. "
                "Install with: pip install stable-baselines3"
            ) from e

        # Resolve policy path.
        pf = policy_file
        if not Path(pf).is_absolute():
            pf = str(_PROJECT_ROOT / pf)
        print(f"[ppo] loading policy: {pf}")
        self._model = PPO.load(pf, device="cpu")

        # Load goals; pick active.
        gf = goals_file
        if not Path(gf).is_absolute():
            gf = str(_PROJECT_ROOT / gf)
        self._goals: List[DockGoal] = load_goals(gf)
        if not self._goals:
            raise ValueError(f"No goals in {gf}")

        self._active = self._goals[0]
        if active_goal_id is not None:
            for g in self._goals:
                if g.id == active_goal_id:
                    self._active = g
                    break
        print(f"[ppo] active goal: {self._active.id} at ({self._active.x:.1f}, {self._active.z:.1f})")

        self._rpm_max = rpm_max
        self._rudder_max = rudder_max_deg
        self._announced = None

    # ------------------------------------------------------------------
    def step(self, t_sim: float, sensors: Optional[dict]) -> ControllerOutput:
        x, z, heading_deg, surge, yaw_rate_dps = self._read_sensors(sensors)

        obs = self._build_obs(x, z, heading_deg, surge, yaw_rate_dps)
        action, _ = self._model.predict(obs, deterministic=True)

        rpm_cmd = float(np.clip(action[0], -1.0, 1.0)) * self._rpm_max
        if rpm_cmd < 0.0: rpm_cmd = 0.0
        rud_cmd = float(np.clip(action[1], -1.0, 1.0)) * self._rudder_max

        d = math.hypot(x - self._active.x, z - self._active.z)
        if d <= self._active.capture_radius:
            mode = "captured"
        elif d <= 25.0:
            mode = "approach"
        else:
            mode = "transit"

        if mode != self._announced:
            print(f"[ppo] -> {mode} (d={d:.1f}m hdg_err={'?'})")
            self._announced = mode

        return ControllerOutput(
            port_rpm_cmd=rpm_cmd,
            starboard_rpm_cmd=rpm_cmd,
            rudder_cmd_deg=rud_cmd,
            bow_thruster_cmd_norm=0.0,
            mode=mode,
        )

    # ------------------------------------------------------------------
    def _build_obs(self, x: float, z: float, heading_deg: float,
                    surge: float, yaw_rate_dps: float) -> np.ndarray:
        g = self._active
        dx = g.x - x
        dz = g.z - z
        dist = math.hypot(dx, dz) + 1e-6
        bearing = math.atan2(dx, dz)
        head_rad = math.radians(heading_deg)
        if g.required_heading_deg is not None:
            req_diff = _shortest_angle_deg(heading_deg - g.required_heading_deg) / 180.0
        else:
            req_diff = 0.0

        # Mirrors YachtEnv._build_obs exactly.
        return np.array([
            dx / 200.0,
            dz / 200.0,
            math.cos(head_rad),
            math.sin(head_rad),
            math.cos(bearing),
            math.sin(bearing),
            surge / 5.0,
            0.0,                              # v not observed via bridge
            math.radians(yaw_rate_dps) * 5.0,
            0.0,                              # rudder achieved (use 0 — predict only)
            0.5,                              # rpm achieved (mid value)
            min(dist / 200.0, 5.0),
            req_diff,
            0.0,                              # wind (live env may inject; stub for now)
            0.0,                              # current
        ], dtype=np.float32)

    @staticmethod
    def _read_sensors(sensors):
        if not sensors:
            return 0.0, 0.0, 0.0, 0.0, 0.0
        s = sensors.get("sensors") or sensors
        gps = s.get("gps") or {}
        imu = s.get("imu") or {}
        wp = gps.get("worldPosition") or {}
        x = float(wp.get("x") or 0.0)
        z = float(wp.get("z") or 0.0)
        h = float(imu.get("headingDeg") or 0.0)
        u = float(gps.get("speed") or 0.0)
        rdps = float(imu.get("yawRateDegPerSec") or 0.0)
        return x, z, h, u, rdps


def _shortest_angle_deg(deg: float) -> float:
    deg = ((deg + 180.0) % 360.0) - 180.0
    if deg <= -180.0:
        deg += 360.0
    return deg
