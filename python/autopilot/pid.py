"""Discrete PID controller with practical guards.

Features
--------
* Anti-windup: integral term is clamped at ``i_clamp``.
* Derivative on measurement (not error) to avoid setpoint-step kicks.
* Saturation: ``output_min`` and ``output_max`` clip the result.
* Optional output rate limit (deg/s on a rudder, rpm/s on a shaft).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PID:
    kp: float = 1.0
    ki: float = 0.0
    kd: float = 0.0
    i_clamp: float = 1e6
    output_min: float = -1e6
    output_max: float = +1e6
    rate_limit: float = 1e6   # max change per second of the output

    _integral: float = 0.0
    _last_meas: float = 0.0
    _have_meas: bool = False
    _last_output: float = 0.0

    def reset(self) -> None:
        self._integral = 0.0
        self._have_meas = False
        self._last_output = 0.0

    def step(self, setpoint: float, measurement: float, dt: float) -> float:
        if dt <= 0.0:
            return self._last_output

        error = setpoint - measurement

        # Integral with clamp.
        self._integral += error * dt
        if self._integral > self.i_clamp:  self._integral = self.i_clamp
        if self._integral < -self.i_clamp: self._integral = -self.i_clamp

        # Derivative on measurement.
        if not self._have_meas:
            d_meas = 0.0
            self._have_meas = True
        else:
            d_meas = (measurement - self._last_meas) / dt
        self._last_meas = measurement

        out = self.kp * error + self.ki * self._integral - self.kd * d_meas

        # Rate limit.
        max_step = self.rate_limit * dt
        delta = out - self._last_output
        if delta > max_step:  out = self._last_output + max_step
        if delta < -max_step: out = self._last_output - max_step

        # Saturation.
        if out > self.output_max: out = self.output_max
        if out < self.output_min: out = self.output_min

        self._last_output = out
        return out
