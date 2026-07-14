#!/usr/bin/env python3
"""camera_sensor -- own-ship camera sensor block (sensor.v1 ``camera``).

Reusable, stdlib-only mirror of the C++ ``USensorBundleComponent::BuildSensorsJson``
camera block (WP-20260701C / WP-14). This is the STILL-FRAME (metadata) camera
sensor: rather than streaming pixels over the socket, the wire carries the camera
*capture metadata* -- pose (world position in the wire frame + heading), field of
view, output resolution, and a deterministic ``frameRef`` naming the still image
the in-engine HighResShot burst (``Phase5_Systems/08_capture_demo_stills.py``,
WP-20260630) writes to the Screenshots dir. A consumer joins the metadata to the
actual PNG on disk by ``frameRef``.

HONESTY (KI-019 / KI-026 family): this is a metadata + on-disk-still sensor, NOT a
real-time in-band video feed. The pose/FOV are exact; the pixels are produced by
the separate (non-real-time) HighResShot capture. Label it "camera capture
metadata + on-disk stills", never "live camera stream".

Convention (identical to the GPS/IMU/AIS blocks + the C++): wire frame
``x=East, y=Up, z=North`` (m); heading compass ``0=N, 90=E`` (own-ship yaw on the
wire). Deterministic -> replays bit-for-bit for a given (pose, frame index).
"""
from __future__ import annotations
from typing import Dict

# Defaults mirror the SBC UPROPERTY defaults (CameraFovDeg / CameraResX/Y) and the
# 08_capture_demo_stills.py RESOLUTION = "3840x2160" (4K). Keep in sync with the
# C++ header; verify_20260701c asserts they match.
DEFAULT_FOV_DEG = 90.0
DEFAULT_RES_X = 3840
DEFAULT_RES_Y = 2160
FRAME_PREFIX = "NaviSense_"          # HighResShot stills are named <prefix><NNNNN>.png


def frame_ref(frame_index: int, prefix: str = FRAME_PREFIX) -> str:
    """Deterministic still-image reference for a capture index (matches the
    HighResShot Screenshots naming <prefix><5-digit index>.png)."""
    return "{}{:05d}.png".format(prefix, int(frame_index))


def camera_record(own_e: float, own_up: float, own_n: float,
                  own_heading_deg: float, frame_index: int,
                  fov_deg: float = DEFAULT_FOV_DEG,
                  res_x: int = DEFAULT_RES_X, res_y: int = DEFAULT_RES_Y,
                  prefix: str = FRAME_PREFIX) -> Dict[str, object]:
    """One ``sensor.v1 camera`` record from own pose + a capture frame index.
    ``own_e/own_up/own_n`` = own-ship world position in the wire frame
    (x=East, y=Up, z=North) metres, matching the C++ Wire.X/Y/Z ordering.

    Keys mirror the C++ BuildSensorsJson camera block exactly (wire-key parity):
    ``fovDeg, resX, resY, headingDeg, frameIndex, frameRef, pose{x,y,z}``.
    ``pose`` is own-ship's world position in the wire frame (m); the still-frame
    camera rides the own-ship chase rig, so its heading == own heading.
    """
    return {
        "fovDeg": float(fov_deg),
        "resX": int(res_x),
        "resY": int(res_y),
        "headingDeg": float(own_heading_deg),
        "frameIndex": int(frame_index),
        "frameRef": frame_ref(frame_index, prefix),
        "pose": {"x": float(own_e), "y": float(own_up), "z": float(own_n)},
    }
