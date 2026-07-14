"""MMG bow thruster module.

Simple linear model:

    F_BT = rated_thrust * norm_cmd * effectiveness(u)

    Y_BT = +F_BT                              (positive command -> bow to starboard)
    N_BT = +F_BT * x_BT                       (lever arm about CG)

Effectiveness drops linearly with forward speed, reaching zero at
``effective_above_u``. This captures the well-known "bow thrusters become
useless at speed" behavior. Literature shows a more complex curve with a
slight reverse effect at high speed; we ignore that here.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import BowThrusterConfig


@dataclass
class BowThrusterForces:
    Y_BT: float
    N_BT: float
    effectiveness: float


def compute_bow_thruster_forces(
    u: float,
    bow_thruster_norm: float,
    bt: BowThrusterConfig,
) -> BowThrusterForces:
    # Saturate the command.
    cmd = max(-1.0, min(1.0, bow_thruster_norm))

    # Effectiveness: 1.0 at rest, 0.0 at effective_above_u and above.
    u_abs = abs(u)
    if bt.effective_above_u <= 0.0:
        eta = 1.0
    else:
        eta = max(0.0, 1.0 - u_abs / bt.effective_above_u)

    F = bt.rated_thrust_N * cmd * eta

    return BowThrusterForces(
        Y_BT=F,
        N_BT=F * bt.x_BT,
        effectiveness=eta,
    )
