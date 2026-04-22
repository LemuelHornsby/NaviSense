<!-- NaviSense Simulator — GitHub README -->

<div align="center">

<img src="NaviSense_Badge.svg" alt="NaviSense Dev Status" width="860"/>

<br/>
<br/>

# NaviSense Simulator

**Synergized Navigation Autonomy**

A high-fidelity Unity-based marine vessel simulation platform for autonomy research, reinforcement learning, and COLREGS-compliant navigation development.

[![Status](https://img.shields.io/badge/status-active%20development-2ECC71?style=flat-square&logo=unity&logoColor=white)](.)
[![MVP](https://img.shields.io/badge/MVP%20progress-38%25-0DB8CC?style=flat-square)](.)
[![Unity](https://img.shields.io/badge/Unity-2022.3%20LTS-black?style=flat-square&logo=unity)](https://unity.com)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/license-Proprietary-red?style=flat-square)](.)

</div>

---

## What is NaviSense?

NaviSense Simulator is a research-grade digital twin for marine vessels — built for the engineers, scientists, and institutions developing the next generation of autonomous maritime systems.

It bridges Unity's real-time physics engine with Python's AI/ML ecosystem over a live TCP connection, enabling bidirectional control, sensor streaming, and reinforcement learning training loops — all in a physically accurate ocean environment.

**Built for:**
- 🔬 Autonomy researchers needing a realistic sim-to-real testbed
- 🤖 RL engineers building COLREGS-compliant navigation policies
- 🏢 Defense & maritime organizations evaluating autonomous vessel behavior
- 📡 Sensor fusion teams requiring noisy, physics-based GPS, IMU, and camera data

---

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│              Unity Simulation               │
│                                             │
│  ┌──────────────┐   ┌────────────────────┐  │
│  │ Hydrostatics │   │  Wave Physics      │  │
│  │ Controller   │   │  (Crest Ocean)     │  │
│  └──────┬───────┘   └────────┬───────────┘  │
│         │                    │              │
│  ┌──────▼────────────────────▼───────────┐  │
│  │         ActuatorController            │  │
│  │  Propulsion · Rudder · Bow Thruster   │  │
│  └──────────────────┬────────────────────┘  │
│                     │                       │
│  ┌──────────────────▼────────────────────┐  │
│  │         PythonBridgeManager           │  │
│  │    TCP :5005 · JSON · 5Hz streaming   │  │
│  └──────────────────┬────────────────────┘  │
└─────────────────────┼───────────────────────┘
                      │ TCP Bidirectional
┌─────────────────────▼───────────────────────┐
│              Python AI Stack                │
│                                             │
│  ┌────────────┐  ┌───────────┐  ┌────────┐  │
│  │ Gymnasium  │  │ Stable    │  │PyTorch │  │
│  │ Custom Env │  │ Baselines3│  │ Models │  │
│  └────────────┘  └───────────┘  └────────┘  │
└─────────────────────────────────────────────┘
```

**Ownership Model:**
- Python owns: X/Z translation, yaw heading
- Unity owns: heave (Y), roll, pitch — governed by live hydrostatics physics

---

## Features

### ✅ Built & Active

| System | Description |
|--------|-------------|
| **TCP Bridge** | Bidirectional JSON protocol over TCP port 5005; 5Hz sensor stream, camera JPEG frames |
| **Hydrostatics Controller** | Buoyancy, heave spring/damping, pitch/roll restoring moments with multi-strip wave sampling |
| **GPS Sensor Model** | White noise + first-order Gauss-Markov bias (60s τ, 1.5m σ) + Bernoulli dropout |
| **Actuator System** | PropulsionActuator, RudderActuator, BowThrusterActuator with LocalDynamics/ExternalState modes |
| **Wave Physics** | Crest Ocean integration — least-squares slope estimation for pitch/roll excitation |
| **Vessel Configuration** | ScriptableObject-based vessel asset system (366t DolphinExplorer reference vessel) |

### 🔄 In Progress

| System | Status |
|--------|--------|
| **SimulationManager** | Stub — session lifecycle, pause/resume, state machine (MVP priority) |
| **ScenarioManager** | Stub — scenario loading, multi-vessel spawning, COLREGS test cases |
| **BridgeManager** | Stub — unified bridge abstraction over PythonBridgeManager |

### 📋 Planned

| System | Description |
|--------|-------------|
| **RL Training Loop** | Gymnasium environment wrapper, PPO/SAC training pipeline |
| **COLREGS Engine** | Rule-based encounter detection (head-on, crossing, overtaking) |
| **Replay System** | Record/playback scenario runs for evaluation and demonstration |
| **REST API / SDK** | External integration layer for third-party research tools |

---

## Tech Stack

<div align="center">

![Unity](https://img.shields.io/badge/Unity%202022.3-black?style=for-the-badge&logo=unity)
![C#](https://img.shields.io/badge/C%23-239120?style=for-the-badge&logo=csharp&logoColor=white)
![Python](https://img.shields.io/badge/Python%203.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![ROS2](https://img.shields.io/badge/ROS2-22314E?style=for-the-badge&logo=ros&logoColor=white)
![Stable Baselines3](https://img.shields.io/badge/Stable--Baselines3-FF6F00?style=for-the-badge)
![Gymnasium](https://img.shields.io/badge/Gymnasium-0081A5?style=for-the-badge)
![Crest Ocean](https://img.shields.io/badge/Crest%20Ocean-065A82?style=for-the-badge)

</div>

---

## MVP Roadmap

```
◉ M1 — Core Engine Stabilization     [Active]  Weeks 1-3
  ├─ SimulationManager implementation
  ├─ ScenarioManager implementation
  └─ Integration test suite

○ M2 — Python RL Integration         [Planned] Weeks 4-6
  ├─ Gymnasium custom environment
  ├─ PPO baseline training run
  └─ COLREGS encounter detection

○ M3 — Data & Evaluation Pipeline    [Planned] Weeks 7-8
  ├─ Synthetic dataset generation
  ├─ Scenario replay system
  └─ Performance benchmarks

○ M4 — MVP Release & Documentation   [Planned] Weeks 9-10
  ├─ SDK / API documentation
  ├─ Demo scenario package
  └─ Research paper draft
```

**Target MVP:** Q3 2026

---

## Getting Started

> **Prerequisites:** Unity 2022.3 LTS · Python 3.10+ · Crest Ocean System (Asset Store)

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/navisense-simulator.git
cd navisense-simulator

# Install Python dependencies
pip install -r requirements.txt

# Open the Unity project
# File → Open Project → select the project folder
# Load scene: Assets/Scenes/SimulatorBase.unity

# Start the Python bridge
python bridge/main.py
```

> **Note:** Full setup documentation coming in M4. For early access or research collaboration, see contact below.

---

## Use Cases

**Research & Development**
- Train RL agents on physically accurate vessel dynamics without hardware risk
- Generate large-scale synthetic sensor datasets for perception model training
- Benchmark autonomy algorithms against standardized COLREGS scenarios

**Defense & Maritime Industry**
- Evaluate autonomous vessel behavior in controlled simulation before sea trials
- Test sensor fusion pipelines under realistic noise and degradation conditions
- Prototype guidance and control systems prior to hardware integration

---

## Funding & Collaboration

NaviSyn Marine Solutions is actively pursuing **SBIR/STTR funding** through Navy and DoD programs focused on maritime autonomy. We welcome collaboration with:

- University research labs working on maritime autonomy
- Defense contractors building USV/AUV systems
- Maritime simulation companies seeking an AI-ready platform

**Contact:** [navisynmarinesolutions@gmail.com](mailto:navisynmarinesolutions@gmail.com)

---

## About NaviSyn Marine Solutions

> *Synergized Navigation Autonomy*

NaviSyn Marine Solutions is an early-stage deep-tech startup developing simulation infrastructure for the autonomous maritime industry. Our mission is to accelerate the development of safe, intelligent marine vessels through accessible, research-grade simulation tooling.

---

<div align="center">

**© 2026 NaviSyn Marine Solutions · All rights reserved**

*NaviSense Simulator is proprietary software. Contact us for research licensing.*

</div>
