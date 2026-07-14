"""MMG test scenarios: IMO turning circle, zig-zag, and free-running control.

Each module exposes:
    run_offline(plant, ...) -> TrajectoryLog
        Runs the scenario purely in Python, returning a trajectory log.

    run_live(host, port, ...) (where applicable)
        Connects as a controller client to python_listener.py and drives the
        Unity yacht in real time.
"""
