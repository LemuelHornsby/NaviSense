"""Adapter that makes the MMG plant look like the StubPlant interface.

python_listener expects any plant to expose:
    plant.state.{x,y,z,yaw_deg,u,v,r,port_rpm,starboard_rpm,rudder_deg,
                 bow_thruster_norm, *_cmd}
    plant.apply_commands(port_rpm_cmd, starboard_rpm_cmd,
                         rudder_cmd_deg, bow_thruster_cmd_norm)
    plant.step(dt)

The MMG plant in ``Maneuvering/maniobrabilidad/mmg`` already exposes this
shape; this adapter just fixes the sys.path and re-exports.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

# Locate Maneuvering/maniobrabilidad next to the NAVISENSE root.
_HERE = Path(__file__).resolve().parent
_MMG_PARENT = _HERE.parent / "Maneuvering" / "maniobrabilidad"
if str(_MMG_PARENT) not in sys.path:
    sys.path.insert(0, str(_MMG_PARENT))

_mmg_module = importlib.import_module("mmg")
MmgPlant = _mmg_module.MmgPlant
load_config = _mmg_module.load_config


def make_mmg_plant(config_path: str = "DOLPHIN.yaml") -> Any:
    """Construct an MmgPlant from a config YAML under the mmg/ package."""
    cfg = load_config(config_path)
    return MmgPlant(cfg)
