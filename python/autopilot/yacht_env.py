"""Gymnasium environment wrapping the offline MMG plant for fast RL training.

Why offline (no Unity in the loop)?
-----------------------------------
RL needs millions of environment steps. Going through the TCP bridge to
Unity at 50 Hz makes that take days. Instead, we step the same validated
MMG plant directly in Python — no rendering, no networking. Once a
policy is trained, the same controller class (PpoPolicyController) plugs
into python_listener and drives the live Unity scene with the deployed
weights.

API conforms to Gymnasium 0.28+:

    env = YachtEnv(goals_file="paths/dockgoals.json")
    obs, info = env.reset()
    action = policy(obs)
    obs, reward, terminated, truncated, info = env.step(action)

Observation
-----------
Continuous Box(15,):
  [0]  rel_x_to_goal / 200            position relative to goal (normalised)
  [1]  rel_z_to_goal / 200
  [2]  cos(heading)                    heading as unit vector
  [3]  sin(heading)
  [4]  cos(heading_to_goal)            bearing-to-goal unit vector
  [5]  sin(heading_to_goal)
  [6]  u / 5                           surge speed (m/s)
  [7]  v / 2                           sway speed
  [8]  r * 5                           yaw rate (rad/s)
  [9]  rudder_deg / 35                 last rudder achieved
  [10] rpm / 380                       last rpm achieved
  [11] dist_to_goal / 200              scalar distance (redundant but useful)
  [12] required_heading_diff / 180     -1..1 if a heading is required, else 0
  [13] wind_x / 10                     environmental wind (world frame, m/s)
  [14] current_z / 1.5                 environmental current

Action
------
Continuous Box(2,) in [-1, 1]:
  [0] rpm normalised: 0 -> 0 rpm, +1 -> rpm_max, -1 -> -rpm_max
  [1] rudder normalised: -1 -> -35 deg, +1 -> +35 deg

Reward (per step)
-----------------
  + 0.5 * (prev_dist - dist) / max_step_progress       progress toward goal
  - 0.0008 * heading_to_goal_error_deg                 alignment penalty
  - 0.0001 * |rudder_deg|                              effort
  - 0.005  * 1[off_world]                              fence penalty
  + 50.0   * 1[captured this step]                     completion bonus
  - 50.0   * 1[collided / off_world hard]              failure penalty
  - 0.001                                              time tax

Termination
-----------
  terminated = capture | collision
  truncated  = step_count >= max_episode_steps | off_world

Curriculum hooks
----------------
The constructor accepts ``curriculum`` (a CurriculumStage) that swaps
parameters per training stage. See CurriculumStage and the four built-in
stages below.
"""

from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
    _HAS_GYM = True
except ImportError:
    _HAS_GYM = False
    # Fallback: stub out enough of the API that the file imports without
    # gymnasium. Training won't work but unit tests / inspection will.
    class gym:
        class Env: pass
    class spaces:
        @staticmethod
        def Box(*a, **kw): return None

# Use the validated MMG plant.
_HERE = Path(__file__).resolve().parent
_MMG_PARENT = _HERE.parent.parent / "Maneuvering" / "maniobrabilidad"
if str(_MMG_PARENT) not in sys.path:
    sys.path.insert(0, str(_MMG_PARENT))
from mmg import MmgPlant, load_config  # noqa: E402

from .nmpc import DockGoal, load_goals


# ---------------------------------------------------------------------------
# Curriculum
# ---------------------------------------------------------------------------

@dataclass
class CurriculumStage:
    """Parameters that vary across the curriculum.

    Fields scale or enable progressively harder conditions:
      * spawn_radius: how far the ship spawns from a randomly-chosen goal.
      * spawn_heading_jitter_deg: random initial heading offset.
      * wind_max_mps: maximum wind speed (sampled uniform 0..max each episode).
      * current_max_mps: maximum current speed.
      * goal_capture_radius_scale: 1.0 = author value; <1 = tighter dock.
      * max_episode_steps: episode length.
      * use_required_heading: include approach-heading constraint in success.
    """
    name: str = "stage1"
    spawn_radius: Tuple[float, float] = (50.0, 100.0)
    spawn_heading_jitter_deg: float = 90.0
    wind_max_mps: float = 0.0
    current_max_mps: float = 0.0
    goal_capture_radius_scale: float = 1.5
    max_episode_steps: int = 500
    use_required_heading: bool = False


# Four built-in stages, easy to extend.
STAGE1_OPEN_WATER = CurriculumStage(
    name="open_water",
    spawn_radius=(40.0, 80.0),
    spawn_heading_jitter_deg=60.0,
    wind_max_mps=0.0,
    current_max_mps=0.0,
    goal_capture_radius_scale=2.0,
    max_episode_steps=600,
    use_required_heading=False,
)

STAGE2_LIGHT_DISTURB = CurriculumStage(
    name="light_disturbance",
    spawn_radius=(60.0, 120.0),
    spawn_heading_jitter_deg=120.0,
    wind_max_mps=3.0,
    current_max_mps=0.3,
    goal_capture_radius_scale=1.5,
    max_episode_steps=800,
    use_required_heading=False,
)

STAGE3_TIGHT_APPROACH = CurriculumStage(
    name="tight_approach",
    spawn_radius=(80.0, 150.0),
    spawn_heading_jitter_deg=180.0,
    wind_max_mps=5.0,
    current_max_mps=0.5,
    goal_capture_radius_scale=1.0,
    max_episode_steps=1000,
    use_required_heading=True,
)

STAGE4_FULL_CONDITIONS = CurriculumStage(
    name="full_conditions",
    spawn_radius=(100.0, 200.0),
    spawn_heading_jitter_deg=180.0,
    wind_max_mps=8.0,
    current_max_mps=1.0,
    goal_capture_radius_scale=1.0,
    max_episode_steps=1200,
    use_required_heading=True,
)

DEFAULT_CURRICULUM: List[CurriculumStage] = [
    STAGE1_OPEN_WATER, STAGE2_LIGHT_DISTURB, STAGE3_TIGHT_APPROACH, STAGE4_FULL_CONDITIONS,
]


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

class YachtEnv(gym.Env if _HAS_GYM else object):
    """Gymnasium env: steer the DOLPHIN to a randomly-chosen dock goal."""

    metadata = {"render_modes": []}

    OBS_DIM = 15
    ACT_DIM = 2

    def __init__(
        self,
        goals: Optional[List[DockGoal]] = None,
        goals_file: Optional[str] = None,
        plant_config_yaml: str = "DOLPHIN.yaml",
        curriculum: Optional[CurriculumStage] = None,
        dt: float = 0.5,
        rpm_max: float = 380.0,
        rudder_max_deg: float = 35.0,
        seed: Optional[int] = None,
    ):
        super().__init__()
        if not _HAS_GYM:
            print("[yacht_env] WARNING: gymnasium not installed; install with "
                  "`pip install gymnasium` for training.")

        if goals is None and goals_file is not None:
            goals = load_goals(goals_file)
        if not goals:
            # Synthetic single-goal fallback so the env can run without Unity.
            goals = [DockGoal(id="synthetic", x=0.0, z=120.0,
                              capture_radius=12.0, required_heading_deg=None)]
        self._goals = goals

        self._plant_yaml = plant_config_yaml
        self._plant = MmgPlant(load_config(plant_config_yaml))
        self._curriculum = curriculum or STAGE1_OPEN_WATER
        self._dt = dt
        self._rpm_max = rpm_max
        self._rudder_max = rudder_max_deg

        self._rng = random.Random(seed) if seed is not None else random.Random()
        self._np_rng = np.random.default_rng(seed)

        if _HAS_GYM:
            self.action_space = spaces.Box(
                low=np.array([-1.0, -1.0], dtype=np.float32),
                high=np.array([1.0, 1.0], dtype=np.float32),
                dtype=np.float32,
            )
            self.observation_space = spaces.Box(
                low=-5.0, high=5.0,
                shape=(self.OBS_DIM,), dtype=np.float32,
            )

        self._steps = 0
        self._prev_dist = 0.0
        self._active: Optional[DockGoal] = None
        self._wind_x = 0.0
        self._wind_z = 0.0
        self._current_x = 0.0
        self._current_z = 0.0

    # ------------------------------------------------------------------
    def set_curriculum_stage(self, stage: CurriculumStage) -> None:
        self._curriculum = stage

    # ------------------------------------------------------------------
    def reset(self, *, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None):
        if seed is not None:
            self._rng = random.Random(seed)
            self._np_rng = np.random.default_rng(seed)
        self._steps = 0

        # Pick a random goal.
        self._active = self._rng.choice(self._goals)

        # Spawn at a random radius/bearing from the goal.
        c = self._curriculum
        r = self._rng.uniform(*c.spawn_radius)
        bearing = self._rng.uniform(0.0, 2.0 * math.pi)
        spawn_x = self._active.x + r * math.cos(bearing)
        spawn_z = self._active.z + r * math.sin(bearing)

        # Heading: face roughly toward the goal with a jitter.
        face = math.degrees(math.atan2(self._active.x - spawn_x,
                                        self._active.z - spawn_z))
        jitter = self._rng.uniform(-c.spawn_heading_jitter_deg, c.spawn_heading_jitter_deg)
        spawn_heading = (face + jitter) % 360.0

        # Reset plant.
        self._plant = MmgPlant(load_config(self._plant_yaml))
        self._plant.state.x = spawn_x
        self._plant.state.z = spawn_z
        self._plant.state.yaw_deg = spawn_heading
        self._plant.state.u = self._rng.uniform(0.0, 1.5)
        self._plant.state.v = 0.0
        self._plant.state.r = 0.0
        self._plant.state.port_rpm = 200.0
        self._plant.state.starboard_rpm = 200.0
        self._plant.state.rudder_deg = 0.0

        # Sample wind / current for this episode.
        self._wind_x = self._rng.uniform(-1.0, 1.0) * c.wind_max_mps
        self._wind_z = self._rng.uniform(-1.0, 1.0) * c.wind_max_mps
        self._current_x = self._rng.uniform(-1.0, 1.0) * c.current_max_mps
        self._current_z = self._rng.uniform(-1.0, 1.0) * c.current_max_mps

        self._prev_dist = math.hypot(spawn_x - self._active.x, spawn_z - self._active.z)

        return self._build_obs(), {}

    def step(self, action: np.ndarray):
        if self._active is None:
            self.reset()

        # Map normalised action to plant commands.
        rpm_cmd = float(np.clip(action[0], -1.0, 1.0)) * self._rpm_max
        rud_cmd = float(np.clip(action[1], -1.0, 1.0)) * self._rudder_max
        # Clamp negative RPM to zero so we don't reward reversing for free.
        if rpm_cmd < 0.0: rpm_cmd = 0.0

        self._plant.apply_commands(rpm_cmd, rpm_cmd, rud_cmd, 0.0)
        self._plant.step(self._dt)

        # Apply environmental drift simply: shift world position by the
        # current vector. (The plant doesn't have wind/current built in
        # to keep the env fast — the EnvironmentField add-on is used in
        # the live bridge; for training we approximate.)
        self._plant.state.x += self._current_x * self._dt
        self._plant.state.z += self._current_z * self._dt

        self._steps += 1

        s = self._plant.state
        c = self._curriculum
        eff_radius = self._active.capture_radius * c.goal_capture_radius_scale

        dx = s.x - self._active.x
        dz = s.z - self._active.z
        dist = math.hypot(dx, dz)

        # Reward.
        progress = (self._prev_dist - dist) / max(0.5, c.spawn_radius[1])
        bearing_to_goal = math.degrees(math.atan2(self._active.x - s.x,
                                                   self._active.z - s.z))
        heading_err = abs(_shortest_angle_deg(s.yaw_deg - bearing_to_goal))
        reward = (
            0.5 * progress
            - 0.0008 * heading_err
            - 0.0001 * abs(s.rudder_deg)
            - 0.001
        )

        # Off-world fence (1500 m beyond the spawn radius).
        off_world = abs(s.x) > 2000.0 or abs(s.z) > 2000.0

        # Capture.
        captured = dist <= eff_radius
        if captured and c.use_required_heading and self._active.required_heading_deg is not None:
            ah = abs(_shortest_angle_deg(s.yaw_deg - self._active.required_heading_deg))
            if ah > self._active.approach_tolerance_deg:
                captured = False

        terminated = bool(captured)
        truncated = bool(self._steps >= c.max_episode_steps or off_world)

        if captured:
            reward += 50.0
        if off_world:
            reward -= 50.0

        self._prev_dist = dist

        info = {
            "captured": captured,
            "off_world": off_world,
            "dist_m": dist,
            "heading_err_deg": heading_err,
            "goal_id": self._active.id,
            "stage": c.name,
        }

        return self._build_obs(), float(reward), terminated, truncated, info

    # ------------------------------------------------------------------
    def _build_obs(self) -> np.ndarray:
        s = self._plant.state
        g = self._active
        if g is None:
            return np.zeros(self.OBS_DIM, dtype=np.float32)

        dx = g.x - s.x
        dz = g.z - s.z
        dist = math.hypot(dx, dz) + 1e-6
        bearing = math.atan2(dx, dz)             # rad, world frame, north=0
        head_rad = math.radians(s.yaw_deg)

        if g.required_heading_deg is not None and self._curriculum.use_required_heading:
            req_diff = _shortest_angle_deg(s.yaw_deg - g.required_heading_deg) / 180.0
        else:
            req_diff = 0.0

        return np.array([
            dx / 200.0,
            dz / 200.0,
            math.cos(head_rad),
            math.sin(head_rad),
            math.cos(bearing),
            math.sin(bearing),
            s.u / 5.0,
            s.v / 2.0,
            s.r * 5.0,
            s.rudder_deg / self._rudder_max,
            s.port_rpm / self._rpm_max,
            min(dist / 200.0, 5.0),
            req_diff,
            self._wind_x / 10.0,
            self._current_z / 1.5,
        ], dtype=np.float32)


def _shortest_angle_deg(deg: float) -> float:
    deg = ((deg + 180.0) % 360.0) - 180.0
    if deg <= -180.0:
        deg += 360.0
    return deg
