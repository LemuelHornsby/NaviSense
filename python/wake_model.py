#!/usr/bin/env python3
"""NaviSense wake & spray model — the single source of truth for the speed->VFX curve (D5 / WP-16).

The hull is kinematically posed from the MMG plant, so there is no fluid sim to
generate a wake. Instead the wake/spray VFX is *driven* by the own-ship's speed:
a Niagara system reads a 0..1 ``WakeIntensity`` and a 0..1 ``Spray`` user
parameter and scales its bow wave / stern wash / spray bursts accordingly.

This module defines that speed->parameter mapping ONCE, in pure Python, so it can
be (a) unit-tested headless (``verify_20260628.py``) and (b) mirrored verbatim in
C++ (``ANaviSenseShipPawn::GetWakeIntensity01`` / ``GetWakeSpray01``). The verify
parses the C++ defaults and asserts they equal the constants here, so the curve
the demo renders is the curve that is gated.

Grounding (DOLPHIN Explorer Yacht, ~40 m displacement hull):
  * hull speed ~= 1.34*sqrt(LWL_ft) ~= 15 kn -> spray/whitewater bursts begin
    around there (``WAKE_SPRAY_ONSET_MS``);
  * the Master Execution Plan WP-16 acceptance is a "20 kn pass looks right", so
    the wake saturates at ~20 kn design top speed (``WAKE_FULL_SPEED_MS``);
  * below a small dead-band the wake is off (moored / drifting).

Everything is deterministic, stdlib-only, and clamped to [0,1] / sane bounds.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------- constants
# Speeds in m/s.  (1 kn = 0.514444 m/s)
WAKE_MIN_SPEED_MS: float = 0.3      # dead-band: below this the wake is off
WAKE_SPRAY_ONSET_MS: float = 7.7    # ~15 kn ~ hull speed: spray bursts begin
WAKE_FULL_SPEED_MS: float = 10.3    # ~20 kn ~ design top speed: wake saturates

# Visual geometry bounds (the Niagara curve can shape further; these are the
# data-driven anchors the recipe binds to).
RIBBON_WIDTH_MIN_CM: float = 50.0   # stern-wash ribbon width at first motion
RIBBON_WIDTH_FULL_CM: float = 350.0 # ... at full intensity
SPAWN_RATE_FULL: float = 600.0      # wake particles/s at full intensity
SPRAY_RATE_FULL: float = 400.0      # spray particles/s at full spray

KN_TO_MS: float = 0.514444


def kn_to_ms(kn: float) -> float:
    return float(kn) * KN_TO_MS


def _ramp(v: float, lo: float, hi: float) -> float:
    """Clamped linear ramp: 0 at/below lo, 1 at/above hi, linear between."""
    hi = max(hi, lo + 1e-3)
    if v <= lo:
        return 0.0
    if v >= hi:
        return 1.0
    return (v - lo) / (hi - lo)


def intensity01(v_ms: float,
                min_speed: float = WAKE_MIN_SPEED_MS,
                full_speed: float = WAKE_FULL_SPEED_MS) -> float:
    """0..1 overall wake intensity from speed-over-ground (m/s).

    0 below the dead-band, ramps linearly to 1 at the full/design speed, clamped.
    Mirrors ``ANaviSenseShipPawn::GetWakeIntensity01`` exactly.
    """
    if v_ms <= min_speed:
        return 0.0
    return _ramp(v_ms, min_speed, full_speed)


def spray01(v_ms: float,
            onset_speed: float = WAKE_SPRAY_ONSET_MS,
            full_speed: float = WAKE_FULL_SPEED_MS) -> float:
    """0..1 spray/whitewater intensity. 0 below the spray onset (~hull speed),
    ramps to 1 at full speed. Mirrors ``GetWakeSpray01`` exactly."""
    if v_ms <= onset_speed:
        return 0.0
    return _ramp(v_ms, onset_speed, full_speed)


def ribbon_width_cm(v_ms: float) -> float:
    """Stern-wash ribbon width (cm) = lerp(min,full) by wake intensity."""
    return RIBBON_WIDTH_MIN_CM + intensity01(v_ms) * (RIBBON_WIDTH_FULL_CM - RIBBON_WIDTH_MIN_CM)


def spawn_rate(v_ms: float) -> float:
    """Wake particle spawn rate (1/s) scaled by wake intensity."""
    return intensity01(v_ms) * SPAWN_RATE_FULL


def spray_rate(v_ms: float) -> float:
    """Spray particle spawn rate (1/s) scaled by spray intensity."""
    return spray01(v_ms) * SPRAY_RATE_FULL


@dataclass(frozen=True)
class WakeParams:
    speed_ms: float
    intensity01: float
    spray01: float
    ribbon_width_cm: float
    spawn_rate: float
    spray_rate: float

    def to_dict(self) -> dict:
        return {
            "speed_ms": round(self.speed_ms, 4),
            "intensity01": round(self.intensity01, 4),
            "spray01": round(self.spray01, 4),
            "ribbon_width_cm": round(self.ribbon_width_cm, 2),
            "spawn_rate": round(self.spawn_rate, 2),
            "spray_rate": round(self.spray_rate, 2),
        }


def params(v_ms: float) -> WakeParams:
    """All wake VFX parameters for a given speed (the Niagara user-param bundle)."""
    return WakeParams(
        speed_ms=float(v_ms),
        intensity01=intensity01(v_ms),
        spray01=spray01(v_ms),
        ribbon_width_cm=ribbon_width_cm(v_ms),
        spawn_rate=spawn_rate(v_ms),
        spray_rate=spray_rate(v_ms),
    )


def curve_table(max_kn: float = 20.0, step_kn: float = 2.0) -> list:
    """A table of WakeParams across a speed sweep (for the recipe / evidence)."""
    rows = []
    kn = 0.0
    while kn <= max_kn + 1e-9:
        rows.append(params(kn_to_ms(kn)))
        kn += step_kn
    return rows


if __name__ == "__main__":
    print("NaviSense wake model — speed -> VFX parameters")
    print(f"  dead-band {WAKE_MIN_SPEED_MS} m/s · spray onset {WAKE_SPRAY_ONSET_MS} m/s "
          f"(~{WAKE_SPRAY_ONSET_MS/KN_TO_MS:.0f} kn) · full {WAKE_FULL_SPEED_MS} m/s "
          f"(~{WAKE_FULL_SPEED_MS/KN_TO_MS:.0f} kn)")
    print(f"  {'kn':>5} {'m/s':>6} {'intensity':>10} {'spray':>7} {'ribbon_cm':>10} {'spawn/s':>8} {'spray/s':>8}")
    for p in curve_table():
        print(f"  {p.speed_ms/KN_TO_MS:5.1f} {p.speed_ms:6.2f} {p.intensity01:10.3f} "
              f"{p.spray01:7.3f} {p.ribbon_width_cm:10.1f} {p.spawn_rate:8.1f} {p.spray_rate:8.1f}")
