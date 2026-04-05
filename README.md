# 🌊 NaviSense Simulator

> **A Unity-based marine autonomy simulation platform for vessel control, synthetic sensing, and scenario-driven testing.**

---

## ✨ Overview

**NaviSense Simulator** is an evolving marine autonomy platform built around a clear separation of responsibilities: **Python** handles vessel dynamics and autonomy logic, while **Unity** provides the visual environment, scenario tooling, and operator-facing simulation layer. This architecture follows the project guidance that recommends keeping Python as the source of truth for plant dynamics and using Unity as the rendering and scenario frontend.[file:1][file:3]

The project is growing from a research-grade yacht docking prototype into a more reusable simulator platform with modular managers, structured messaging, synthetic sensors, and scenario-ready workflows. The current technical direction is aligned with a product-style architecture that supports repeatability, explainability, and future expansion into replay, benchmarking, and multi-vessel scenarios.[file:1][file:3]

---

## 🧭 Current Development Focus

The current phase has focused on **stabilizing the simulator foundation** before adding more visual or systems complexity. That matches the roadmap guidance, which prioritizes baseline verification, scene cleanup, manager-based architecture, and bridge validation before deeper expansion.[file:1]

### ✅ Progress so far

- Built a working **Unity-to-Python TCP bridge** for simulator communication.[file:1][file:3]
- Verified **newline-delimited JSON** messaging from Unity to Python, which is explicitly recommended as an acceptable and easy-to-debug v1.0 transport choice.[file:3]
- Implemented a **`SensorManager`** to gather and package sensor outputs in Unity before transmission.[file:1]
- Implemented a **`PythonBridgeManager`** to centralize socket ownership, serialization, and message handling responsibilities in Unity.[file:1][file:3]
- Confirmed live sensor packet streaming with a structured schema including `schema`, `runId`, `t`, and nested sensor payloads.[file:3]
- Verified live outputs for:
  - **GPS** world position and speed
  - **IMU** heading, yaw rate, and acceleration
  - **AIS** target list support (currently tested with empty target sets)
- Preserved the intended simulator ownership model: **Unity does not own vessel truth**, and **Python remains the authoritative simulation side**.[file:1][file:3]

---

## 🏗️ Architecture

### Unity frontend

Unity is responsible for:
- 3D visualization
- harbor and marina scene setup
- scenario authoring and organization
- sensor packaging
- bridge communication
- future replay, UI, and debugging overlays

The platform guide recommends organizing Unity around manager objects such as `SimulationManager`, `ScenarioManager`, `TrafficManager`, `SensorManager`, `PythonBridgeManager`, `ReplayManager`, and `UIManager`, all grouped under a clean root hierarchy for maintainability.[file:1]

### Python backend

Python is responsible for:
- vessel dynamics
- controller execution
- autonomy logic
- simulation time advancement
- downstream sensor/state processing

This follows the core architectural recommendation that Python should remain the source of truth for dynamics and autonomy in v1.0, while Unity stays out of hidden plant physics ownership.[file:1][file:3]

---

## 🔌 Communication Flow

The current communication path is simple, transparent, and already working:

1. Unity sensors are sampled.
2. `SensorManager` compiles the outputs into a structured sensor bundle.
3. `PythonBridgeManager` serializes the message as JSON.
4. Unity sends the packet over TCP using newline-delimited JSON.
5. Python receives and prints the packet successfully.

This design fits the project API direction, which treats the bridge as a formal product interface rather than a temporary hack and requires packets to include schema version, run ID, and simulation time.[file:3]

---

## 🧪 Example Packet

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

The received test output confirms that the bridge is already capable of streaming live sensor data from Unity into a Python terminal in a structured and consistent format.[file:3]

---

## 🗺️ Roadmap

### Near term

- Add typed parsing and handling on the Python side.
- Add Unity-side receive handling for state packets.
- Continue reorganizing the scene into manager-owned systems and clean roots.
- Expand from baseline bridge testing into scenario loading and reset workflows.
- Build a first operator UI for vessel state, mission state, and sensor status.

These next steps align with the staged roadmap: stabilize the baseline first, then platform cleanup, then scenario systems, then sensors/UI, and later replay and benchmarking.[file:1]

### Longer term

- ScenarioDefinition and MissionDefinition assets
- multi-vessel support and traffic routes
- replay from saved logs
- evaluation metrics and summaries
- environment presets for calm, windy, and night conditions
- benchmark-ready workflows for NMPC, PPO, and hybrid control comparisons

The product roadmap frames these as core steps toward a simulator that supports research, pilot demonstrations, and eventually broader commercialization workflows.[file:1][file:3]

---

## 🛠️ Tech Stack

| Layer | Technology |
|------|------------|
| Frontend | Unity |
| Water/visual environment | Crest Water 4 URP |
| Backend | Python |
| Messaging | TCP sockets |
| Packet format | JSON |
| Sensors | GPS, IMU, AIS abstractions |
| Controls base | MMG dynamics, NMPC, PPO, hybrid supervision |

These technologies reflect the current stack described in the technical specification and simulator platform guide.[file:1][file:3]

---

## 🎯 Project Goal

The goal is not only to animate a vessel in a scene, but to build a **modular marine autonomy simulator platform** that can support research, testing, replay, scenario design, and future product development. The reference documents explicitly position NaviSense as a Unity-based marine autonomy simulation platform for control development, reinforcement learning validation, scenario evaluation, and commercial pilot demonstrations.[file:3]

---

## 📌 Status Snapshot

> **Current milestone:** Unity is successfully streaming structured sensor packets to Python over TCP, establishing a verified baseline for the simulator bridge.[file:1][file:3]

This is an important foundation for everything that comes next: typed APIs, replay, metrics, scenarios, UI, and more advanced autonomy workflows.[file:1][file:3]
