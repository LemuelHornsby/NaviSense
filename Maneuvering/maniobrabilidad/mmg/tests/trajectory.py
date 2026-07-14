"""Shared trajectory log used by all MMG scenarios."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class TrajectoryLog:
    t: List[float] = field(default_factory=list)
    x: List[float] = field(default_factory=list)
    z: List[float] = field(default_factory=list)
    yaw_deg: List[float] = field(default_factory=list)
    u: List[float] = field(default_factory=list)
    v: List[float] = field(default_factory=list)
    r: List[float] = field(default_factory=list)
    rudder_deg: List[float] = field(default_factory=list)
    port_rpm: List[float] = field(default_factory=list)
    starboard_rpm: List[float] = field(default_factory=list)
    bow_thruster_norm: List[float] = field(default_factory=list)

    def record(self, t: float, state) -> None:
        self.t.append(t)
        self.x.append(state.x)
        self.z.append(state.z)
        self.yaw_deg.append(state.yaw_deg)
        self.u.append(state.u)
        self.v.append(state.v)
        self.r.append(state.r)
        self.rudder_deg.append(state.rudder_deg)
        self.port_rpm.append(state.port_rpm)
        self.starboard_rpm.append(state.starboard_rpm)
        self.bow_thruster_norm.append(state.bow_thruster_norm)

    def to_csv(self, path: str) -> None:
        import csv
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "t", "x", "z", "yaw_deg", "u", "v", "r",
                "rudder_deg", "port_rpm", "starboard_rpm", "bow_thruster_norm",
            ])
            for i in range(len(self.t)):
                w.writerow([
                    self.t[i], self.x[i], self.z[i], self.yaw_deg[i],
                    self.u[i], self.v[i], self.r[i],
                    self.rudder_deg[i], self.port_rpm[i],
                    self.starboard_rpm[i], self.bow_thruster_norm[i],
                ])
