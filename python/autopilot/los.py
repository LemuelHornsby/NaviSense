"""Line-of-sight (LOS) guidance for path following.

Given the current ownship XZ position and a polyline path, LOS produces
a desired heading that aims the ship at a "look-ahead point" on the path
some distance ahead. This naturally suppresses cross-track error: when
off-track, the look-ahead point is offset back onto the path, so the
heading command pulls the ship back to the line.

Reference: Fossen, *Handbook of Marine Craft Hydrodynamics and Motion
Control*, Sec. 12.3 (Lookahead-based steering).

The path is a list of (x, z) world points in Unity's coordinate frame.
We don't depend on Unity here — the autopilot is pure Python.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class LosGuidance:
    lookahead_meters: float = 30.0
    """Look-ahead distance along the path. Larger = smoother but lazier
    convergence, smaller = aggressive snap-to-line behaviour. Rule of
    thumb: 1.5-3x ship length."""

    accept_radius_meters: float = 8.0
    """When the ship is within this distance of the *current* leg's end
    point, advance to the next leg. Should be larger than typical
    cross-track error so we don't skip ahead too aggressively."""

    loop: bool = False
    """If True, treat the path as closed (last point connects to first)."""

    # Internal: index of the leg we're currently following (waypoints[idx] -> idx+1).
    _leg_idx: int = 0

    # ------------------------------------------------------------------
    def reset(self) -> None:
        self._leg_idx = 0

    def desired_heading_deg(
        self, ownship_xz: Tuple[float, float], waypoints: List[Tuple[float, float]],
    ) -> float:
        """Compute desired heading (deg, 0..360, north = 0, +x = east)
        based on current pose and path. Advances the leg index when the
        ship reaches the leg endpoint within the accept radius.
        """
        if len(waypoints) < 2:
            return 0.0

        # Advance leg if close to current leg endpoint.
        end_idx = self._leg_idx + 1
        if end_idx >= len(waypoints):
            if self.loop:
                end_idx = 0
                self._leg_idx = len(waypoints) - 1
            else:
                # Past the last leg: aim for the last waypoint.
                end_idx = len(waypoints) - 1
                self._leg_idx = end_idx - 1

        end_xz = waypoints[end_idx]
        dx = end_xz[0] - ownship_xz[0]
        dz = end_xz[1] - ownship_xz[1]
        if dx * dx + dz * dz < self.accept_radius_meters ** 2:
            # Captured this end point — move to the next leg.
            self._leg_idx = end_idx
            if not self.loop and self._leg_idx >= len(waypoints) - 1:
                # No more legs — return current heading along last leg.
                a = waypoints[self._leg_idx - 1]
                b = waypoints[self._leg_idx]
                return _heading_deg(b[0] - a[0], b[1] - a[1])

        a_xz = waypoints[self._leg_idx]
        b_xz = waypoints[(self._leg_idx + 1) % len(waypoints)] if self.loop \
               else waypoints[min(self._leg_idx + 1, len(waypoints) - 1)]

        # Closest point on the leg to the ownship.
        leg = (b_xz[0] - a_xz[0], b_xz[1] - a_xz[1])
        leg_len_sq = leg[0] ** 2 + leg[1] ** 2
        if leg_len_sq < 1e-6:
            return _heading_deg(b_xz[0] - ownship_xz[0], b_xz[1] - ownship_xz[1])

        rel = (ownship_xz[0] - a_xz[0], ownship_xz[1] - a_xz[1])
        s = (rel[0] * leg[0] + rel[1] * leg[1]) / leg_len_sq    # 0..1 along leg
        s = max(0.0, min(1.0, s))
        closest = (a_xz[0] + leg[0] * s, a_xz[1] + leg[1] * s)

        # Look-ahead point: project lookahead_meters further along the leg
        # from the closest point. If we'd run past the leg end, clamp at
        # the leg end (LOS won't peek into the next leg here — that's a
        # variant if you want it).
        leg_len = math.sqrt(leg_len_sq)
        s_la = s + (self.lookahead_meters / leg_len)
        s_la = max(0.0, min(1.0, s_la))
        la_point = (a_xz[0] + leg[0] * s_la, a_xz[1] + leg[1] * s_la)

        return _heading_deg(la_point[0] - ownship_xz[0], la_point[1] - ownship_xz[1])

    def cross_track_error_meters(
        self, ownship_xz: Tuple[float, float], waypoints: List[Tuple[float, float]],
    ) -> float:
        """Signed perpendicular distance from the ship to the active leg.
        Positive = ownship is to STARBOARD of the leg; negative = port.
        """
        if len(waypoints) < 2 or self._leg_idx >= len(waypoints) - 1 and not self.loop:
            return 0.0
        a = waypoints[self._leg_idx]
        b = waypoints[(self._leg_idx + 1) % len(waypoints)] if self.loop \
            else waypoints[min(self._leg_idx + 1, len(waypoints) - 1)]
        leg = (b[0] - a[0], b[1] - a[1])
        leg_len_sq = leg[0] ** 2 + leg[1] ** 2
        if leg_len_sq < 1e-6:
            return 0.0
        rel = (ownship_xz[0] - a[0], ownship_xz[1] - a[1])
        # 2D cross product gives signed perpendicular distance scaled by leg length.
        cross = leg[0] * rel[1] - leg[1] * rel[0]
        return cross / math.sqrt(leg_len_sq)


def _heading_deg(dx: float, dz: float) -> float:
    """Heading in deg, 0 = +Z (north), 90 = +X (east), 0..360.

    Matches the Unity convention used elsewhere in the simulator.
    """
    h = math.degrees(math.atan2(dx, dz))
    return h % 360.0
