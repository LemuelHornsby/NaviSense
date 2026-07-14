"""Kinematic 6-DOF attitude proxy — schema v1 rev 1.2 (heel + trim).

WHY THIS EXISTS
    The NaviSense plant is 3-DOF (surge u, sway v, yaw r): the hull slides on a
    flat plane (KI-008). For the demo's visual jump (gate D2, "6-DOF water ride")
    we derive a small, tunable HEEL (roll) and TRIM (pitch) from the vessel's own
    motion at the wire boundary, so the ship visibly leans in turns and noses up
    under acceleration. This is a *visual proxy*, NOT hydrodynamic truth — the
    plant dynamics are unchanged. True 6-DOF + water-surface sampling is F1 part 2.

SIGN CONVENTIONS (wire frame; mirrored in NaviSenseCoords.h on the UE side)
    rollDeg  : + = starboard side DOWN (heel to starboard)
    pitchDeg : + = bow UP (trim by the stern)
    r (yaw rate, rad/s): + = heading increasing CW = turning to STARBOARD

HEEL MODEL (steady-turn, OUTBOARD)
    Displacement ships heel OUTWARD of the turn in a steady turn: the inertial
    reaction acts outward at the CG while the hull side force acts inward at the
    (lower) centre of lateral resistance, and the couple lays the topside outboard.
    A starboard turn (+r) therefore heels the ship to PORT (outboard) => rollDeg<0.
    Magnitude ~ proportional to speed * yaw-rate, clamped.
        roll_deg = clamp(-roll_gain * u * r, +/- roll_clamp)
    To invert the rendered lean (e.g. a cinematic "inboard" look), flip the sign in
    NaviSenseCoords::WireRollToUE — never here and never per-call (invariant #1).

TRIM MODEL (acceleration)
    A coarse squat/trim proxy: bow rises under forward acceleration, drops under
    deceleration.  pitch_deg = clamp(pitch_gain * du_dt, +/- pitch_clamp)

Gains are module-level constants so behaviour is tunable without touching the
listener. Keep this module dependency-free (pure functions) so it can be unit
tested headlessly and imported by the listener with no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass

# --- Tunable gains (visual proxy; not fitted to any towing-tank data) ---------
ROLL_GAIN_DEG_PER_RAD = 9.0     # deg heel per (m/s * rad/s); ~3-6 deg in a hard turn
ROLL_CLAMP_DEG        = 8.0     # never heel past this (keeps the deck out of the sea)
PITCH_GAIN_DEG_PER_MS2 = 0.6    # deg trim per (m/s^2) surge accel
PITCH_CLAMP_DEG        = 3.0


@dataclass(frozen=True)
class Attitude:
    """Visual attitude in degrees (wire sign convention; see module docstring)."""
    roll_deg: float
    pitch_deg: float


def _clamp(x: float, lim: float) -> float:
    return lim if x > lim else (-lim if x < -lim else x)


def attitude_deg(
    u: float,
    v: float,
    r: float,
    du_dt: float = 0.0,
    *,
    roll_gain: float = ROLL_GAIN_DEG_PER_RAD,
    roll_clamp: float = ROLL_CLAMP_DEG,
    pitch_gain: float = PITCH_GAIN_DEG_PER_MS2,
    pitch_clamp: float = PITCH_CLAMP_DEG,
) -> Attitude:
    """Map 3-DOF motion -> (roll_deg, pitch_deg) visual attitude.

    u     surge speed, m/s (forward +)
    v     sway speed, m/s (unused today; reserved for leeway-heel coupling)
    r     yaw rate, rad/s (+ = starboard turn)
    du_dt forward acceleration, m/s^2 (+ = speeding up)
    """
    roll = _clamp(-roll_gain * u * r, roll_clamp)   # outboard steady-turn heel
    pitch = _clamp(pitch_gain * du_dt, pitch_clamp)  # bow-up under acceleration
    return Attitude(roll_deg=roll, pitch_deg=pitch)
