"""Wind + current disturbance model for the MMG plant.

Adds two physical effects to the ship dynamics:

  Wind  - aerodynamic drag on the superstructure. Pushes the hull
          horizontally (force) and twists it (moment). Wind speed is
          the **apparent** wind seen by the hull, computed from the
          true wind minus the ship's own velocity. Gusts modulate the
          base wind on a timescale of seconds.

  Current - moves the surrounding water. The hull's hydrodynamic forces
          depend on the **relative water velocity** u_r = u - u_c,
          v_r = v - v_c. We provide that vector to the plant which
          uses it inside compute_hull_forces / compute_rudder_forces.

The model is intentionally a uniform field with optional Gaussian-noise
gusts. For spatial fields (channel currents, wind shadows behind
landmasses) replace `current_at()` / `wind_at()` with a sampler.

Sign / frame conventions
------------------------

Both wind and current vectors are given as **world-frame** velocities
(m/s in the world XZ plane) following the same convention as the rest
of the plant: +X = east, +Z = north. To convert from a meteorological
"direction the wind comes FROM" (e.g. 180 deg = south wind, blowing
toward north) into a world vector pointing in the direction of motion,
use :func:`vector_from_meteo_dir_speed`.

Currents are given as **set** (direction water is moving TOWARDS) and
**drift** (speed). That matches IHO / nav-chart conventions.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Tuple


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def vector_from_meteo_dir_speed(dir_from_deg: float, speed_mps: float) -> Tuple[float, float]:
    """Wind: meteorological 'direction FROM' -> world velocity vector (vx, vz).

    Example: dir_from_deg=180 (south wind) -> wind blows toward north -> (0, +speed).
    """
    # Wind moves opposite to its 'from' direction.
    dir_to_deg = (dir_from_deg + 180.0) % 360.0
    rad = math.radians(dir_to_deg)
    return speed_mps * math.sin(rad), speed_mps * math.cos(rad)


def vector_from_set_drift(set_deg: float, drift_mps: float) -> Tuple[float, float]:
    """Current: set (direction TO) + drift -> world velocity vector (vx, vz).

    Example: set=90 (current sets east) -> (+drift, 0).
    """
    rad = math.radians(set_deg)
    return drift_mps * math.sin(rad), drift_mps * math.cos(rad)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class WindConfig:
    """Uniform wind field with optional gusts."""
    direction_from_deg: float = 0.0   # meteorological "from" direction
    speed_mps: float = 0.0            # base mean wind speed
    gust_amplitude_mps: float = 0.0   # peak gust delta (0 disables gusts)
    gust_period_s: float = 8.0        # rough timescale of gust autocorrelation

    # Aerodynamic coefficients. Defaults are typical for a ~ 38 m motor yacht
    # with moderate superstructure (rho_air * A * Cd ~ 1.5 kg/m).
    rho_air: float = 1.225            # air density, kg/m^3
    frontal_area_m2: float = 80.0     # superstructure projected forward area
    side_area_m2: float = 180.0       # superstructure projected side area
    cd_x: float = 0.7                 # drag coeff for surge (head wind)
    cd_y: float = 0.9                 # drag coeff for sway (beam wind)
    yaw_lever_m: float = 4.0          # arm from CoG to centre of side area


@dataclass
class CurrentConfig:
    """Uniform current field with optional gusts (eddies)."""
    set_deg: float = 0.0              # navigational set (direction TO)
    drift_mps: float = 0.0            # navigational drift (speed)
    gust_amplitude_mps: float = 0.0   # eddy fluctuation
    gust_period_s: float = 12.0


@dataclass
class EnvironmentField:
    """Wraps wind + current and produces forces/moments for the MMG plant.

    Construct once at scenario load; call :meth:`tick` each plant step
    to advance the gust state, then read :attr:`current_velocity_world`
    and :meth:`wind_force` from inside the dynamics.
    """
    wind: WindConfig = field(default_factory=WindConfig)
    current: CurrentConfig = field(default_factory=CurrentConfig)

    # Internal gust state (Ornstein-Uhlenbeck style noise).
    _wind_noise_mps: float = 0.0
    _current_noise_mps: float = 0.0
    _rng: random.Random = field(default_factory=random.Random)

    def tick(self, dt: float) -> None:
        """Advance gust noise. Call once per plant step."""
        # Mean-reverting noise: x' = -x/tau + sigma * white_noise
        if self.wind.gust_amplitude_mps > 0.0 and self.wind.gust_period_s > 0.0:
            tau = self.wind.gust_period_s
            sigma = self.wind.gust_amplitude_mps
            self._wind_noise_mps += (-self._wind_noise_mps * dt / tau +
                                     sigma * math.sqrt(2.0 * dt / tau) *
                                     self._rng.gauss(0.0, 1.0))
        else:
            self._wind_noise_mps = 0.0

        if self.current.gust_amplitude_mps > 0.0 and self.current.gust_period_s > 0.0:
            tau = self.current.gust_period_s
            sigma = self.current.gust_amplitude_mps
            self._current_noise_mps += (-self._current_noise_mps * dt / tau +
                                        sigma * math.sqrt(2.0 * dt / tau) *
                                        self._rng.gauss(0.0, 1.0))
        else:
            self._current_noise_mps = 0.0

    # ------------------------------------------------------------------
    # Current — relative water velocity for the hull
    # ------------------------------------------------------------------
    @property
    def current_velocity_world(self) -> Tuple[float, float]:
        """Current velocity in the world XZ frame, m/s."""
        instantaneous = max(0.0, self.current.drift_mps + self._current_noise_mps)
        return vector_from_set_drift(self.current.set_deg, instantaneous)

    def current_velocity_body(self, yaw_rad: float) -> Tuple[float, float]:
        """Current velocity expressed in the ship's body frame (u, v).

        u = surge component (along bow), v = sway component (toward starboard).
        """
        cx, cz = self.current_velocity_world
        # Body frame: rotate world (cx, cz) by -yaw to align with bow.
        cos_y = math.cos(yaw_rad)
        sin_y = math.sin(yaw_rad)
        u_c = cx * sin_y + cz * cos_y       # surge
        v_c = cx * cos_y - cz * sin_y       # sway
        return u_c, v_c

    # ------------------------------------------------------------------
    # Wind — aerodynamic forces on the superstructure
    # ------------------------------------------------------------------
    def wind_apparent_body(self, u: float, v: float, yaw_rad: float) -> Tuple[float, float, float]:
        """Apparent wind in the body frame, (u_w, v_w, magnitude).

        Apparent wind = true wind - ship velocity, all in world frame,
        then rotated into the body frame.
        """
        # True wind in world frame.
        instant = max(0.0, self.wind.speed_mps + self._wind_noise_mps)
        wx, wz = vector_from_meteo_dir_speed(self.wind.direction_from_deg, instant)

        # Ship velocity in world: rotate body (u, v) by +yaw.
        cos_y = math.cos(yaw_rad)
        sin_y = math.sin(yaw_rad)
        ship_vx = u * sin_y + v * cos_y
        ship_vz = u * cos_y - v * sin_y

        # Apparent wind (relative to ship) in world.
        ax = wx - ship_vx
        az = wz - ship_vz

        # Rotate to body frame.
        u_w = ax * sin_y + az * cos_y
        v_w = ax * cos_y - az * sin_y
        mag = math.hypot(u_w, v_w)
        return u_w, v_w, mag

    def wind_force_body(self, u: float, v: float, yaw_rad: float) -> Tuple[float, float, float]:
        """Aerodynamic force/moment in the body frame, (X_W, Y_W, N_W)."""
        u_w, v_w, mag = self.wind_apparent_body(u, v, yaw_rad)
        if mag < 1e-3:
            return 0.0, 0.0, 0.0

        # Surge drag: -1/2 * rho * A_f * Cd_x * |u_w| * u_w (sign of u_w).
        # This is direction-aware (head wind pushes back, tail wind pushes
        # forward) and quadratic in apparent speed — standard form.
        rho = self.wind.rho_air
        X_W = 0.5 * rho * self.wind.frontal_area_m2 * self.wind.cd_x * abs(u_w) * u_w
        # Sign convention: positive X = forward thrust on hull, so head
        # wind (u_w negative) gives positive force on the wind that pushes
        # the hull backward — actually we want negative force for head wind.
        # Use -X_W: when apparent surge wind is negative (head wind), force
        # on hull is negative (backwards).
        X_W = -X_W

        Y_W = 0.5 * rho * self.wind.side_area_m2 * self.wind.cd_y * abs(v_w) * v_w
        # Same sign convention: beam wind from port (v_w > 0) pushes hull
        # to starboard, but body-frame Y is "starboard-positive" so we flip
        # the sign.
        Y_W = -Y_W

        # Yawing moment from side wind: Y_W acts at yaw_lever (positive
        # = ahead of CoG, which is typical for a top-heavy superstructure).
        N_W = Y_W * self.wind.yaw_lever_m

        return X_W, Y_W, N_W


# ---------------------------------------------------------------------------
# Convenience: build a field from CLI-friendly args
# ---------------------------------------------------------------------------

def make_environment(
    wind_dir_deg: float = 0.0, wind_mps: float = 0.0,
    wind_gust_mps: float = 0.0, wind_gust_period_s: float = 8.0,
    current_set_deg: float = 0.0, current_mps: float = 0.0,
    current_gust_mps: float = 0.0, current_gust_period_s: float = 12.0,
    seed: int | None = None,
) -> EnvironmentField:
    rng = random.Random(seed) if seed is not None else random.Random()
    return EnvironmentField(
        wind=WindConfig(
            direction_from_deg=wind_dir_deg,
            speed_mps=wind_mps,
            gust_amplitude_mps=wind_gust_mps,
            gust_period_s=wind_gust_period_s,
        ),
        current=CurrentConfig(
            set_deg=current_set_deg,
            drift_mps=current_mps,
            gust_amplitude_mps=current_gust_mps,
            gust_period_s=current_gust_period_s,
        ),
        _rng=rng,
    )
