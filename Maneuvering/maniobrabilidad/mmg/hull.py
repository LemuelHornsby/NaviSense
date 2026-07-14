"""MMG hull force module.

Yasukawa-Yoshimura 2015 non-dimensional polynomial in (v', r') with a
simple quadratic-in-u resistance term. All hull forces are decomposed into:

    X_H(u,v,r) = -R_0(u) + (rho/2)*L*d*U^2 * f_surge(v',r')
    Y_H(u,v,r) =            (rho/2)*L*d*U^2 * f_sway (v',r')
    N_H(u,v,r) =            (rho/2)*L^2*d*U^2 * f_yaw  (v',r')

Sign convention (Fossen / Yasukawa):
    u>0 forward, v>0 to starboard, r>0 bow to starboard.

Notes on the quadratic-cross terms: we follow Yoshimura 2009 where only
|v'| and |r'| enter, to keep the model smooth through origin.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import HullCoefficients, ShipParticulars


@dataclass
class HullForces:
    X_H: float
    Y_H: float
    N_H: float


def compute_hull_forces(
    u: float,
    v: float,
    r: float,
    ship: ShipParticulars,
    hull: HullCoefficients,
    rho: float,
) -> HullForces:
    """Evaluate hull forces at the given body-frame velocity state.

    Args:
        u: surge speed [m/s], positive forward
        v: sway speed [m/s], positive to starboard
        r: yaw rate [rad/s], positive bow-to-starboard
        ship: principal particulars
        hull: non-dimensional derivatives
        rho: water density [kg/m^3]
    """
    L = ship.L_pp
    d = ship.d

    # Resultant speed and non-dimensional velocities.
    U = math.sqrt(u * u + v * v)
    if U < 1e-3:
        # No forward motion -> hull lift terms collapse; keep only resistance.
        return HullForces(X_H=0.0, Y_H=0.0, N_H=0.0)

    v_dash = v / U
    r_dash = r * L / U

    # ------------------------------------------------------------------
    # Surge (dimensionless)
    #   X'_H = -R_0' + X_vr * v' * r' + X_vv * v'^2 + X_rr * r'^2
    # We collapse Kijima's X_vr and X_vv into approximations to keep the
    # YAML compact. Override via future YAML keys as needed.
    # ------------------------------------------------------------------
    R_0 = hull.R_0_dash
    X_vr_dash = 1.11 * ship.C_b * ship.B / L - 0.07       # empirical approx
    X_vv_dash = 0.4  * ship.C_b * ship.B / L - 0.064      # empirical approx
    X_rr_dash = -0.08                                     # empirical approx

    X_dash = (
        -R_0
        + X_vr_dash * v_dash * r_dash
        + X_vv_dash * v_dash * v_dash
        + X_rr_dash * r_dash * r_dash
    )

    # ------------------------------------------------------------------
    # Sway
    # ------------------------------------------------------------------
    Y_dash = (
        hull.Y_v * v_dash
        + hull.Y_r * r_dash
        + hull.Y_vvv * v_dash * v_dash * v_dash
        + hull.Y_vvr * v_dash * v_dash * r_dash
        + hull.Y_vrr * v_dash * r_dash * r_dash
        + hull.Y_rrr * r_dash * r_dash * r_dash
    )

    # ------------------------------------------------------------------
    # Yaw
    # ------------------------------------------------------------------
    N_dash = (
        hull.N_v * v_dash
        + hull.N_r * r_dash
        + hull.N_vvv * v_dash * v_dash * v_dash
        + hull.N_vvr * v_dash * v_dash * r_dash
        + hull.N_vrr * v_dash * r_dash * r_dash
        + hull.N_rrr * r_dash * r_dash * r_dash
    )

    # Redimensionalize.
    q = 0.5 * rho * L * d * U * U
    X_H = q * X_dash
    Y_H = q * Y_dash
    N_H = q * L * N_dash  # N normalization carries an extra L

    return HullForces(X_H=X_H, Y_H=Y_H, N_H=N_H)
