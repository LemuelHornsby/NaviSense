"""MMG propeller module (twin-screw, independent shafts).

Each shaft contributes an axial thrust, applied at the shaft's lateral
offset y_shaft. For ahead RPM the thrust is ``T = (1 - t_P) * rho * n^2 * D^4 * K_T(J)``
and the resulting body-frame forces are:

    X_P = sum(T_i)                           (both contribute to surge)
    Y_P = 0                                  (shafts are axial)
    N_P = sum(T_i * y_shaft_i)               (differential thrust -> yaw)

For astern operation (negative RPM) we flip the sign of J and use the same
polynomial, which is a reasonable first-cut approximation. In reality K_T
astern is measured separately; TODO: add a second polynomial when/if data
becomes available.

Wake fraction w_P and thrust-deduction t_P are taken as constants; both
vary with loading and could be upgraded later.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import PropellerConfig


@dataclass
class PropellerForces:
    X_P: float
    N_P: float
    # Diagnostics
    port_thrust_N: float
    starboard_thrust_N: float
    port_J: float
    starboard_J: float


def _k_t(J: float, p: PropellerConfig) -> float:
    """Open-water thrust coefficient polynomial."""
    return p.K_T_k0 + p.K_T_k1 * J + p.K_T_k2 * J * J


def _shaft_thrust(rpm: float, u_advance: float, p: PropellerConfig, rho: float) -> tuple[float, float]:
    """Thrust contributed by one shaft.

    Returns (thrust_N, J). Handles zero RPM and astern running.
    """
    n = rpm / 60.0                               # rev/s
    if abs(n) < 1e-4:
        return 0.0, 0.0

    # Advance coefficient; for astern use |n| for J magnitude.
    J = u_advance / (n * p.D_p) if n != 0.0 else 0.0
    # Clamp J into a sane range to protect against divergence when the prop
    # is deeply unloaded (very high u/n).
    J_clamped = max(-1.5, min(1.5, J))

    K_T = _k_t(J_clamped, p)
    # rho * n^2 * D^4 * K_T. Use n*|n| so astern RPM produces astern thrust.
    T = rho * n * abs(n) * (p.D_p ** 4) * K_T
    return T, J


def compute_propeller_forces(
    u: float,
    port_rpm: float,
    starboard_rpm: float,
    prop: PropellerConfig,
    rho: float,
) -> PropellerForces:
    # Effective advance speed into the propeller disc (wake-corrected).
    u_advance = u * (1.0 - prop.w_P)

    T_p, J_p = _shaft_thrust(port_rpm, u_advance, prop, rho)
    T_s, J_s = _shaft_thrust(starboard_rpm, u_advance, prop, rho)

    # Thrust deduction applies to the effective force on the ship.
    T_eff_p = (1.0 - prop.t_P) * T_p
    T_eff_s = (1.0 - prop.t_P) * T_s

    # Port shaft at -y_shaft, starboard at +y_shaft.
    # N = sum(T_i * y_i); port torque is about +z when thrust>0 pushes bow
    # starboard, which happens when starboard shaft is AHEAD and port is ASTERN.
    X_P = T_eff_p + T_eff_s
    N_P = T_eff_s * prop.y_shaft - T_eff_p * prop.y_shaft

    return PropellerForces(
        X_P=X_P,
        N_P=N_P,
        port_thrust_N=T_eff_p,
        starboard_thrust_N=T_eff_s,
        port_J=J_p,
        starboard_J=J_s,
    )
