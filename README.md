# NaviSense Simulator

NaviSense Simulator is a Unity-based marine autonomy simulation platform for testing vessel dynamics, control logic, synthetic sensors, and harbor scenarios in a reproducible environment.

The project is being built as a layered system:
- **Python** is the source of truth for vessel dynamics and control.
- **Unity** is the visualization, scenario, and operator frontend.
- A **TCP bridge** connects both sides using newline-delimited JSON.
- A **sensor layer** packages GPS, IMU, and AIS outputs into structured messages.

## Project Status

This project is actively under development and has already reached a working baseline for core communication and sensor streaming.

### Completed so far
- Built a Unity-to-Python connection using TCP.
- Verified that Unity can send structured sensor packets to a Python terminal.
- Implemented a `SensorManager` that bundles sensor outputs into a single message.
- Implemented a `PythonBridgeManager` to own connection setup and packet transmission.
- Established a typed message format with a `SensorMessage` wrapper.
- Confirmed live output for:
  - GPS world position and speed
  - IMU heading, yaw rate, and acceleration
  - AIS target list
- Kept the architecture aligned with the simulator roadmap:
  - one source of truth for physics in Python,
  - explicit bridge ownership,
  - modular managers in Unity,
  - structured packets for future replay, UI, and metrics.

## Architecture

### Unity side
Unity handles:
- scene management,
- visual rendering,
- scenario setup,
- operator UI,
- sensor packaging,
- bridge communication.

### Python side
Python handles:
- vessel dynamics,
- control logic,
- autonomy logic,
- simulation truth,
- downstream processing of received sensor data.

### Core managers in Unity
- `SimulationManager`
- `ScenarioManager`
- `TrafficManager`
- `SensorManager`
- `PythonBridgeManager`
- `ReplayManager`
- `UIManager`

## Current Communication Flow

1. Sensors are read in Unity.
2. `SensorManager` compiles them into a structured sensor bundle.
3. `PythonBridgeManager` serializes the bundle as JSON.
4. Unity sends the packet over TCP as newline-delimited JSON.
5. Python receives and prints the packet successfully.

## Example Sensor Packet

```json
{
  "schema": "navisense.sensor.v1",
  "runId": "test-run",
  "t": 0.6851946115493774,
  "sensors": {
    "time": 0.6851946115493774,
    "gps": {
      "worldPosition": {
        "x": -0.174183189868927,
        "y": 0.0,
        "z": 0.09401494264602661
      },
      "speed": 0.04538695886731148
    },
    "imu": {
      "headingDeg": 0.05834144353866577,
      "yawRateDegPerSec": 0.1377786546945572,
      "acceleration": {
        "x": 0.0,
        "y": 0.0,
        "z": 0.0
      }
    },
    "ais": {
      "targets": []
    }
  }
}
```

## What This Project Is Becoming

NaviSense is evolving into a research-grade and demo-ready marine autonomy simulator with:
- synthetic sensors,
- hybrid autonomy support,
- replay and logging,
- scenario-driven experiments,
- future benchmark workflows,
- and an operator-friendly Unity frontend.

## Roadmap

### Next steps
- Add typed parsing on the Python side.
- Add Unity-side receive handling for state packets.
- Introduce replay support from logged runs.
- Expand scenario definitions for docking, avoidance, and traffic.
- Add UI panels for vessel state, mission state, and sensor status.
- Build structured logging for experiments and comparisons.

### Longer-term goals
- Mission definitions and scenario presets.
- Traffic vessel support.
- Sensor realism improvements.
- Benchmark and replay tools.
- Better visualization and environment presets.
- More reusable experiment workflows for research and demos.

## Tech Stack

- **Unity**
- **Python**
- **TCP sockets**
- **JSON messaging**
- **Synthetic sensor models**
- **C# scripts for Unity managers**

## Why This Matters

The goal is not just to make a scene that moves a boat. The goal is to build a simulator platform that can support research, debugging, demos, and future autonomy development in a clean and extensible way.

## Notes

This project follows a layered architecture:
- world and rendering in Unity,
- truth and control in Python,
- structured communication between them,
- and modular managers for scalability.

---

If you want to try the project, the first milestone is already working:
Unity sends live sensor packets to Python over TCP, and Python receives them successfully.
