#!/usr/bin/env python3
# =====================================================================
# WP-5 pytest — plant sign convention, controllers, and the v1.1 wire contract.
# Runs against the OFFLINE harness listener (dependency-light). Part of the
# nightly Python suite (Development/automation/nightly_tests.ps1).
#
#   cd Development/bridge_harness && python -m pytest tests -v
# =====================================================================
import importlib.util
import json
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.normpath(os.path.join(HERE, "..", "python_listener.py"))
GOLDEN = os.path.join(HERE, "golden_state_v1.json")

# v1.1 wire contract — must match FNaviSenseState (Source/.../NaviSenseBridgeTypes.h).
CONTRACT_KEYS = {
    "schema", "runId", "t", "x", "y", "z", "yawDeg", "u", "v", "r",
    "portRpm", "starboardRpm", "rudderDeg", "bowThrusterNorm",
    "portRpmCmd", "starboardRpmCmd", "rudderCmdDeg", "bowThrusterCmdNorm", "mode",
}


def _load():
    spec = importlib.util.spec_from_file_location("ns_harness", HARNESS)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


hl = _load()


class _FixedRudder:
    def __init__(self, deg, rpm=900.0):
        self.deg, self.rpm = deg, rpm

    def command(self, dt, state):
        return self.deg, self.rpm


def _integrate(plant, controller, secs, dt=0.05):
    t = 0.0
    for _ in range(int(secs / dt)):
        rud, rpm = controller.command(dt, {"yawDeg": plant.yawDeg, "u": plant.u,
                                           "r": plant.r, "t": t})
        plant.step(dt, rud, rpm)
        t += dt
    return plant


def _signed_yaw(yaw_deg):
    """Map [0,360) heading to a signed change in (-180,180]."""
    return ((yaw_deg + 180.0) % 360.0) - 180.0


# ---- plant dynamics -------------------------------------------------

def test_straight_line_keeps_heading():
    p = _integrate(hl.MMGPlant(), hl.StraightController(), 10.0)
    assert abs(_signed_yaw(p.yawDeg)) < 1.0      # heading within 1 deg of North
    assert p.z > 0.0                              # made way to the North (heading 0 = +z)


def test_positive_rudder_turns_starboard():
    # Corroborates the Python-log half of WP-2 G7: +rudder -> bow to starboard.
    p = _integrate(hl.MMGPlant(), _FixedRudder(+10.0), 8.0)
    assert p.r > 0.0
    assert _signed_yaw(p.yawDeg) > 0.5


def test_negative_rudder_turns_port():
    p = _integrate(hl.MMGPlant(), _FixedRudder(-10.0), 8.0)
    assert p.r < 0.0
    assert _signed_yaw(p.yawDeg) < -0.5


def test_rudder_antisymmetry():
    sp = _signed_yaw(_integrate(hl.MMGPlant(), _FixedRudder(+10.0), 8.0).yawDeg)
    pt = _signed_yaw(_integrate(hl.MMGPlant(), _FixedRudder(-10.0), 8.0).yawDeg)
    assert sp > 0 and pt < 0
    assert abs(sp + pt) < 0.35 * max(abs(sp), abs(pt))   # roughly mirror-image


def test_no_nan_under_zigzag():
    p = _integrate(hl.MMGPlant(), hl.ZigZagController(10.0, 6.0), 30.0)
    for name in ("x", "z", "yawDeg", "u", "v", "r", "rudder_deg"):
        v = getattr(p, name)
        assert v == v and abs(v) < 1e6   # not NaN, bounded


# ---- controllers ----------------------------------------------------

def test_zigzag_flips_sign():
    c = hl.ZigZagController(zig_angle=10.0, half_period_s=6.0)
    first, _ = c.command(0.1, {})
    for _ in range(70):          # advance > one half-period (7 s)
        c.command(0.1, {})
    later, _ = c.command(0.1, {})
    assert first > 0.0 and later < 0.0


def test_straight_controller_zero_rudder():
    rud, rpm = hl.StraightController().command(0.05, {})
    assert rud == 0.0 and rpm > 0.0


def test_turning_circle_holds_one_sign():
    c = hl.TurningCircleController()
    r0, _ = c.command(1.0, {})
    r1, _ = c.command(1.0, {})
    assert r0 == r1 and abs(r0) > 0.0    # constant hard-over within a phase


# ---- wire contract --------------------------------------------------

def test_state_packet_keys_match_contract():
    pkt = hl.build_state_packet(hl.MMGPlant(), "run", 1.0, 5.0, 900.0)
    assert set(pkt.keys()) == CONTRACT_KEYS
    assert pkt["schema"] == "navisense.state.v1"
    assert pkt["mode"] in ("idle", "manual", "auto", "replay")


def test_json_golden_contract():
    """Pin the exact v1.1 packet shape/values for a fixed plant state.
    First run writes the golden; subsequent runs must match it byte-for-value."""
    p = hl.MMGPlant()
    p.x, p.z, p.yawDeg = 10.0, 20.0, 45.0
    p.u, p.v, p.r = 4.0, 0.1, 0.01
    p.rudder_deg, p.rpm = 5.0, 900.0
    pkt = hl.build_state_packet(p, "golden-run", 1.5, 5.0, 900.0)
    if not os.path.exists(GOLDEN):
        with open(GOLDEN, "w") as f:
            json.dump(pkt, f, indent=2, sort_keys=True)
    with open(GOLDEN) as f:
        golden = json.load(f)
    assert pkt == golden, "v1.1 wire contract drifted from golden_state_v1.json"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
