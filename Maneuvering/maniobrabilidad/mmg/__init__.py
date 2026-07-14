"""MMG 3-DOF maneuvering plant for the NaviSense Simulator.

Public surface:
    from mmg import MmgPlant, load_config

    plant = MmgPlant(load_config("DOLPHIN.yaml"))
    plant.apply_commands(port_rpm_cmd=180, starboard_rpm_cmd=180,
                         rudder_cmd_deg=0.0, bow_thruster_cmd_norm=0.0)
    plant.step(dt=0.02)
    print(plant.state.x, plant.state.yaw_deg)
"""

from .config import ShipConfig, load_config
from .plant import MmgPlant, MmgPlantState

__all__ = ["ShipConfig", "load_config", "MmgPlant", "MmgPlantState"]
