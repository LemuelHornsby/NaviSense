"""MMG rudder module (single rudder, behind the propeller average).

Standard Yasukawa-Yoshimura formulation:

    U_R  = effective rudder inflow from propeller slipstream + freestream
    alpha_R = delta - gamma_R * beta'        (effective angle of attack)
    F_N  = 0.5 * rho * A_R * U_R^2 * f_alpha * sin(alpha_R)

    X_R  = -(1 - t_R) * F_N * sin(delta)
    Y_R  = -(1 + a_H) * F_N * cos(delta)
    N_R  = -(x_R + a_H * x_H) * F_N * cos(delta)

For twin-screw yachts with a single centerline rudder, we feed the average
of port/starboard advance speeds into the slipstream. If you later add twin
rudders, replicate this block per rudder and use per-shaft advance.

The flow-straightening factor gamma_R is a function of sideslip direction;
we use the symmetric form gamma_R_star for |beta'| small, which is the
Yasukawa simplification that works well for ships of this class.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import PropellerConfig, RudderConfig, ShipParticulars


@dataclass
class RudderForces:
    X_R: float
    Y_R: float
    N_R: float
    # Diagnostics
    U_R: float
    alpha_R: float
    F_N: float


# Flow-straightening factor (symmetric, approximate).
_GAMMA_R = 0.5


def compute_rudder_forces(
    u: float,
    v: float,
    r: float,
    delta_rad: float,
    port_thrust_N: float,
    starboard_thrust_N: float,
    ship: ShipParticulars,
    prop: PropellerConfig,
    rud: RudderConfig,
    rho: float,
) -> RudderForces:
    L = ship.L_pp

    # ------------------------------------------------------------------
    # Effective inflow to the rudder, U_R.
    # Composed of:
    #   U_freestream_axial = u * (1 - w_P)  (wake-corrected)
    #   U_slipstream       = additional axial velocity induced by propeller
    # Yasukawa uses:
    #   u_R^2 = eps^2 * (u_advance^2 + kappa * (...)) -- full form -- but for
    # a first-cut twin-screw yacht we use the simplified mean-thrust form:
    #   u_R = eps * sqrt( u_advance^2 + kappa * T_mean/(rho*D^2) )
    # ------------------------------------------------------------------
    u_advance = u * (1.0 - prop.w_P)
    T_mean = 0.5 * (port_thrust_N + starboard_thrust_N)
    axial_sq = (
        rud.eps * rud.eps
        * (
            u_advance * u_advance
            + rud.kappa * abs(T_mean) / max(1e-3, rho * prop.D_p * prop.D_p)
        )
    )
    u_R_axial = math.copysign(math.sqrt(max(0.0, axial_sq)), u_advance + 1e-6)

    # Lateral inflow at the rudder = v + x_R * r  (sideslip at rudder station)
    x_R = rud.x_R_over_L * L
    v_R = v + x_R * r

    # Apply flow-straightening.
    v_R_eff = v_R - _GAMMA_R * v  # pull a fraction of sideslip out
    U_R = math.sqrt(u_R_axial * u_R_axial + v_R_eff * v_R_eff)

    # Angle of attack. delta>0 = rudder to port (trailing edge to port),
    # which commands bow to starboard. atan2(v_R_eff, u_R_axial) is the
    # flow angle at the rudder; effective AOA = delta - flow_angle.
    flow_angle = math.atan2(v_R_eff, u_R_axial) if U_R > 1e-3 else 0.0
    alpha_R = delta_rad - flow_angle

    # Normal force.
    F_N = 0.5 * rho * rud.A_R * U_R * U_R * rud.f_alpha * math.sin(alpha_R)

    # Project onto body frame.
    sin_d = math.sin(delta_rad)
    cos_d = math.cos(delta_rad)
    X_R = -(1.0 - rud.t_R) * F_N * sin_d
    Y_R = -(1.0 + rud.a_H) * F_N * cos_d
    N_R = -(x_R + rud.a_H * rud.x_H_over_L * L) * F_N * cos_d

    return RudderForces(
        X_R=X_R, Y_R=Y_R, N_R=N_R,
        U_R=U_R, alpha_R=alpha_R, F_N=F_N,
    )
