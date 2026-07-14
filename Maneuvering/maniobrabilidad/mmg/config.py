"""Strongly-typed, loadable ship configuration for the MMG plant.

The YAML on disk is the single source of truth for coefficients. This module
turns it into a frozen dataclass graph so that (a) typos fail at load time,
(b) coefficients are immutable once the plant starts (stops foot-guns in
long runs), and (c) IDE autocomplete works.

Design rule: the loader never does physics. Kijima estimation helpers are
exposed separately so they can be re-run whenever principal particulars
change.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------
def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "PyYAML is required. Install with: pip install pyyaml"
        ) from exc
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not parse to a mapping.")
    return data


# ---------------------------------------------------------------------------
# Sub-configs
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ShipParticulars:
    name: str
    L_pp: float
    B: float
    d: float
    displacement_mass: float
    C_b: float
    x_G: float
    k_zz_over_L: float
    m_x_over_m: float
    m_y_over_m: float
    J_zz_over_Izz: float

    @property
    def I_zz(self) -> float:
        k_zz = self.k_zz_over_L * self.L_pp
        return self.displacement_mass * k_zz * k_zz

    @property
    def m_x(self) -> float:
        return self.m_x_over_m * self.displacement_mass

    @property
    def m_y(self) -> float:
        return self.m_y_over_m * self.displacement_mass

    @property
    def J_zz(self) -> float:
        return self.J_zz_over_Izz * self.I_zz


@dataclass(frozen=True)
class HullCoefficients:
    Y_v: float
    Y_r: float
    N_v: float
    N_r: float
    Y_vvv: float
    Y_vvr: float
    Y_vrr: float
    Y_rrr: float
    N_vvv: float
    N_vvr: float
    N_vrr: float
    N_rrr: float
    R_0_dash: float


@dataclass(frozen=True)
class PropellerConfig:
    D_p: float
    P_over_D: float
    K_T_k0: float
    K_T_k1: float
    K_T_k2: float
    w_P: float
    t_P: float
    y_shaft: float


@dataclass(frozen=True)
class RudderConfig:
    A_R: float
    h_R: float
    lambda_R: float
    f_alpha: float
    t_R: float
    a_H: float
    x_R_over_L: float
    x_H_over_L: float
    eps: float
    kappa: float


@dataclass(frozen=True)
class BowThrusterConfig:
    rated_thrust_N: float
    x_BT: float
    effective_above_u: float


@dataclass(frozen=True)
class EnvironmentConfig:
    rho_water: float = 1025.0


@dataclass(frozen=True)
class IntegratorConfig:
    method: str = "rk4"
    max_substeps: int = 4


@dataclass(frozen=True)
class ShipConfig:
    ship: ShipParticulars
    hull: HullCoefficients
    propeller: PropellerConfig
    rudder: RudderConfig
    bow_thruster: BowThrusterConfig
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    integrator: IntegratorConfig = field(default_factory=IntegratorConfig)


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------
def load_config(path: str | Path) -> ShipConfig:
    """Parse a DOLPHIN.yaml-style file into a ShipConfig."""
    p = Path(path)
    if not p.is_absolute() and not p.exists():
        # Fall back to this file's directory (so ``load_config("DOLPHIN.yaml")``
        # works regardless of the caller's cwd).
        p = Path(__file__).parent / p
    raw = _load_yaml(p)

    return ShipConfig(
        ship=ShipParticulars(**raw["ship"]),
        hull=HullCoefficients(**raw["hull"]),
        propeller=PropellerConfig(**raw["propeller"]),
        rudder=RudderConfig(**raw["rudder"]),
        bow_thruster=BowThrusterConfig(**raw["bow_thruster"]),
        environment=EnvironmentConfig(**raw.get("environment", {})),
        integrator=IntegratorConfig(**raw.get("integrator", {})),
    )


# ---------------------------------------------------------------------------
# Kijima regression helpers (optional)
# ---------------------------------------------------------------------------
def recompute_kijima(ship: ShipParticulars) -> Dict[str, float]:
    """Re-estimate linear hull derivatives from principal particulars.

    Returns a dict of ``{"Y_v": ..., "Y_r": ..., "N_v": ..., "N_r": ...}``
    which you can splice into the YAML by hand.

    Formulas from Kijima et al. (1990) / Yoshimura (2009). Non-dimensional.
    """
    L = ship.L_pp
    B = ship.B
    d = ship.d
    C_b = ship.C_b
    k = 2.0 * d / L

    Y_v = -(math.pi * k / 2.0 + 1.4 * C_b * B / L)
    Y_r = ship.m_x_over_m * (ship.displacement_mass / (0.5 * 1025.0 * L * L * d)) \
          + 1.5 * C_b * B / L - math.pi * k / 4.0
    N_v = -k
    N_r = -(0.54 * k - k * k + 0.675 * C_b * B / L - 0.1) / 4.0
    return {"Y_v": Y_v, "Y_r": Y_r, "N_v": N_v, "N_r": N_r}
