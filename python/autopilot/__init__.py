"""Autopilot package: building blocks for waypoint-following controllers.

Currently provides:

* :class:`PID` — generic discrete PID with anti-windup + derivative-on-measurement.
* :class:`LosGuidance` — Line-of-sight guidance: turns a path + current pose
  into a desired heading.
* :class:`WaypointFollowerController` — chains LOS + heading-PID + speed-PID
  into the standard ``step(t_sim, sensors)`` controller contract used by
  ``python_listener.py``.

All modules are dependency-free (stdlib only) so they drop into the
existing python listener with no additional installs.
"""

from .pid import PID
from .los import LosGuidance
from .waypoint_follower import WaypointFollowerController
from .nmpc import NmpcController, NmpcParams, DockGoal, load_goals
from .yacht_env import YachtEnv, CurriculumStage, DEFAULT_CURRICULUM
from .ppo_controller import PpoPolicyController

__all__ = [
    "PID",
    "LosGuidance",
    "WaypointFollowerController",
    "NmpcController",
    "NmpcParams",
    "DockGoal",
    "load_goals",
    "YachtEnv",
    "CurriculumStage",
    "DEFAULT_CURRICULUM",
    "PpoPolicyController",
]
