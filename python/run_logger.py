"""CSV run logger for NaviSense bridge sessions.

For every run driven by ``python_listener.py`` the logger writes a set
of files into a run-specific subdirectory:

* ``sensor.csv``    — one row per ``navisense.sensor.v1`` packet received
                      from Unity, flattened to scalar columns.
* ``state.csv``     — one row per ``navisense.state.v1`` packet emitted
                      back to Unity, i.e. plant state + actuator cmds.
* ``events.csv``    — discrete events: scenario phase changes, helm mode
                      flips, controller-side warnings. Useful for jumping
                      to interesting moments when reviewing a long run.
* ``manifest.json`` — metadata: run id, plant kind, controller kind,
                      start/end wall-clock time, tick rate, plus an
                      ``events`` array mirroring events.csv for tools that
                      prefer JSON.

Additionally the logger appends a one-line summary to
``<log_dir>/runs.csv`` on finalise so all your runs show up in a single
project-level index.

The logger is deliberately tolerant: unknown / missing fields become empty
cells, and new schema fields on either side just appear as new columns at
first sight. This keeps older runs diffable against newer runs without
breaking the CSV reader on the analysis side.

Design notes:
    * Writes are line-buffered so a Ctrl-C leaves readable files.
    * Neither file is append-mode; each run gets a fresh directory
      ``<log_dir>/<run_id>_<YYYYmmdd_HHMMSS>/`` so parallel / re-runs never
      collide.
    * Camera frames are intentionally *not* logged (they're big JPEG blobs).
      Add a separate image-folder sink if you need them.
"""

from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Column order for sensor.csv. Every row has every column; missing fields
# are emitted as empty strings so the CSV loads cleanly in pandas.
SENSOR_COLUMNS: List[str] = [
    "wall_time", "t",
    "gps_x", "gps_y", "gps_z",
    "gps_speed", "gps_latDeg", "gps_lonDeg", "gps_hasFix",
    "imu_headingDeg", "imu_yawRateDegPerSec",
    "imu_acc_x", "imu_acc_y", "imu_acc_z",
    "ais_target_count",
    "t_mono",   # KI-024 canonical: single monotonic run-relative join clock
]

# Column order for state.csv. Matches navisense.state.v1 plus a few derived
# columns useful for quick spreadsheet plotting (speed magnitude, actuator
# error).
STATE_COLUMNS: List[str] = [
    "wall_time", "t", "mode",
    "x", "y", "z", "yawDeg",
    "u", "v", "r",
    "portRpm", "starboardRpm", "rudderDeg", "bowThrusterNorm",
    "portRpmCmd", "starboardRpmCmd", "rudderCmdDeg", "bowThrusterCmdNorm",
    "speed_mag",          # sqrt(u^2 + v^2)
    "rudder_error_deg",   # rudderCmdDeg - rudderDeg
    "rollDeg",            # visual heel: maneuvering + wave-coupled (rev 1.4)
    "pitchDeg",           # visual trim: maneuvering + wave-coupled (rev 1.4)
    "heaveM",             # wave-field vertical bob (rev 1.3)
    "t_mono",             # KI-024 canonical: single monotonic run-relative join clock
]


@dataclass
class RunLogger:
    """Writes sensor + state CSVs for a single bridge session.

    Usage:
        logger = RunLogger.create("logs", run_id="demo", plant="mmg", controller="gamepad")
        ...
        logger.record_sensor(sensor_dict)
        logger.record_state(state_dict)
        ...
        logger.finalise()

    All file handles are owned by the logger and closed on ``finalise()``.
    If the logger is created with ``run_dir=None`` (i.e. disabled) every
    method becomes a no-op so the listener can call it unconditionally.
    """

    run_dir: Optional[str]
    run_id: str
    plant_kind: str
    controller_kind: str
    tick_hz: float
    sea_state: int = 0
    wave_heading_deg: float = 0.0
    wave_seed: int = 1337
    sea_state_schedule: Optional[str] = None   # runtime sea-state schedule (D3); None = fixed
    scenario: Optional[str] = None             # named scenario (D6); None = ad-hoc run
    ais_preset: Optional[str] = None           # scripted AIS traffic preset (D4/WP-15); None = none
    ais_target_name: Optional[str] = None      # --target-name ship swap (WP-20260709B); None = preset default

    # Set post-create by ``create``.
    _sensor_file: Any = field(default=None, init=False, repr=False)
    _state_file: Any = field(default=None, init=False, repr=False)
    _events_file: Any = field(default=None, init=False, repr=False)
    _sensor_writer: Any = field(default=None, init=False, repr=False)
    _state_writer: Any = field(default=None, init=False, repr=False)
    _events_writer: Any = field(default=None, init=False, repr=False)
    _sensor_rows: int = field(default=0, init=False, repr=False)
    _state_rows: int = field(default=0, init=False, repr=False)
    # WP-20260708C: sampled raw sensor.v1 JSONL sink (rich-block evidence).
    _sensor_raw_file: Any = field(default=None, init=False, repr=False)
    _sensor_raw_lines: int = field(default=0, init=False, repr=False)
    _events: List[Dict[str, Any]] = field(default_factory=list, init=False, repr=False)
    _last_mode: Optional[str] = field(default=None, init=False, repr=False)
    _log_root: Optional[str] = field(default=None, init=False, repr=False)
    _started_at: float = field(default_factory=time.time, init=False, repr=False)
    # KI-024: ONE monotonic clock for BOTH logs. time.monotonic() never steps
    # backwards (NTP-safe) and is process-wide, so sensor (RX) and state (TX)
    # rows stamped from it share one timeline regardless of PIE FPS / clock skew.
    _mono_start: float = field(default_factory=time.monotonic, init=False, repr=False)

    # ----------------------------------------------------------------- ctor
    @staticmethod
    def create(
        log_dir: Optional[str],
        run_id: str,
        plant_kind: str,
        controller_kind: str,
        tick_hz: float,
        sea_state: int = 0,
        wave_heading_deg: float = 0.0,
        wave_seed: int = 1337,
        sea_state_schedule: Optional[str] = None,
        scenario: Optional[str] = None,
        ais_preset: Optional[str] = None,
        ais_target_name: Optional[str] = None,
    ) -> "RunLogger":
        """Create the run directory and CSV headers. If ``log_dir`` is None
        or empty, returns a disabled logger that no-ops on every call."""
        if not log_dir:
            return RunLogger(
                run_dir=None,
                run_id=run_id,
                plant_kind=plant_kind,
                controller_kind=controller_kind,
                tick_hz=tick_hz,
                sea_state=sea_state,
                wave_heading_deg=wave_heading_deg,
                wave_seed=wave_seed,
                sea_state_schedule=sea_state_schedule,
                scenario=scenario,
                ais_preset=ais_preset,
                ais_target_name=ais_target_name,
            )

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        run_dir = os.path.join(log_dir, f"{run_id}_{timestamp}")
        os.makedirs(run_dir, exist_ok=True)

        logger = RunLogger(
            run_dir=run_dir,
            run_id=run_id,
            plant_kind=plant_kind,
            controller_kind=controller_kind,
            tick_hz=tick_hz,
            sea_state=sea_state,
            wave_heading_deg=wave_heading_deg,
            wave_seed=wave_seed,
            sea_state_schedule=sea_state_schedule,
            scenario=scenario,
            ais_preset=ais_preset,
            ais_target_name=ais_target_name,
        )

        # open CSVs line-buffered so Ctrl-C leaves readable files
        logger._sensor_file = open(os.path.join(run_dir, "sensor.csv"), "w", newline="", buffering=1)
        logger._state_file = open(os.path.join(run_dir, "state.csv"), "w", newline="", buffering=1)
        logger._events_file = open(os.path.join(run_dir, "events.csv"), "w", newline="", buffering=1)
        logger._sensor_writer = csv.writer(logger._sensor_file)
        logger._state_writer = csv.writer(logger._state_file)
        logger._events_writer = csv.writer(logger._events_file)
        logger._sensor_writer.writerow(SENSOR_COLUMNS)
        logger._state_writer.writerow(STATE_COLUMNS)
        logger._events_writer.writerow(["wall_time", "t", "name", "details", "t_mono"])
        # WP-20260708C: raw sensor.v1 JSONL sink. The flat sensor.csv drops the
        # rich blocks (ais.targets[], radar.contacts[], camera{}), which made the
        # in-engine sensor gates (G_AIS_SENSOR_UE / G_RADAR_UE / G_CAMERA_UE)
        # console eye-checks with NO on-disk evidence. This sink persists a
        # sampled raw copy so python/verify_sensor_suite.py can gate them
        # objectively after the run. Best-effort: failure to open can never
        # break the run.
        try:
            logger._sensor_raw_file = open(
                os.path.join(run_dir, "sensor_raw.jsonl"), "w", buffering=1)
        except Exception as e:  # pragma: no cover - defensive
            print(f"[run_logger] sensor_raw.jsonl disabled: {e}")
            logger._sensor_raw_file = None
        logger._log_root = log_dir

        # Mark the start as the first event so reviewers can see params at
        # the top of events.csv without opening the manifest.
        logger.record_event(
            t_sim=0.0,
            name="run_started",
            details=(
                f"plant={plant_kind} controller={controller_kind} "
                f"hz={tick_hz:g} seaState=SS{sea_state} runId={run_id}"
                + (f" schedule=[{sea_state_schedule}]" if sea_state_schedule else "")
                + (f" scenario={scenario}" if scenario else "")
            ),
        )

        # Write a preliminary manifest so you can see params even if the
        # process is killed before finalise.
        logger._write_manifest(final=False)

        print(f"[run_logger] writing to {run_dir}")
        return logger

    # ------------------------------------------------------------ record()
    def _t_mono(self) -> str:
        """Run-relative seconds from a single monotonic clock (KI-024).

        Stamped on every sensor (RX) and state (TX) row so both logs share
        ONE timeline. This is the canonical join key; ``t`` stays the raw
        per-side clock (sensor t = UE engine, state t = Python plant) and
        ``wall_time`` stays the absolute epoch.
        """
        return f"{time.monotonic() - self._mono_start:.6f}"

    def record_sensor(self, msg: Optional[Dict[str, Any]]) -> None:
        if self._sensor_writer is None or msg is None:
            return
        sensors = msg.get("sensors") or {}
        gps = sensors.get("gps") or {}
        imu = sensors.get("imu") or {}
        ais = sensors.get("ais") or {}
        gps_pos = gps.get("worldPosition") or {}
        acc = imu.get("acceleration") or {}
        targets = ais.get("targets") or []

        row = [
            f"{time.time():.6f}",
            _fmt(msg.get("t")),
            _fmt(gps_pos.get("x")), _fmt(gps_pos.get("y")), _fmt(gps_pos.get("z")),
            _fmt(gps.get("speed")), _fmt(gps.get("latDeg")), _fmt(gps.get("lonDeg")),
            _fmt_bool(gps.get("hasFix")),
            _fmt(imu.get("headingDeg")), _fmt(imu.get("yawRateDegPerSec")),
            _fmt(acc.get("x")), _fmt(acc.get("y")), _fmt(acc.get("z")),
            len(targets),
            self._t_mono(),
        ]
        self._sensor_writer.writerow(row)
        self._sensor_rows += 1

        # WP-20260708C: sampled raw persistence. Every packet for the first
        # 300 rows (startup detail), then 1-in-10 (~6 Hz at 60 fps -> a few MB
        # per 10-min run). Envelope keeps the wire packet byte-intact under
        # "msg" and adds the two run clocks. Defensive: raw-sink errors are
        # swallowed so logging can never take down the bridge loop.
        if self._sensor_raw_file is not None and (
                self._sensor_rows <= 300 or self._sensor_rows % 10 == 0):
            try:
                self._sensor_raw_file.write(json.dumps({
                    "wall_time": round(time.time(), 6),
                    "t_mono": float(self._t_mono()),
                    "msg": msg,
                }, separators=(",", ":")) + "\n")
                self._sensor_raw_lines += 1
            except Exception:  # pragma: no cover - defensive
                pass

    def record_state(self, pkt: Dict[str, Any]) -> None:
        if self._state_writer is None or pkt is None:
            return
        u = pkt.get("u") or 0.0
        v = pkt.get("v") or 0.0
        speed_mag = (u * u + v * v) ** 0.5
        rud_err = (pkt.get("rudderCmdDeg") or 0.0) - (pkt.get("rudderDeg") or 0.0)

        row = [
            f"{time.time():.6f}",
            _fmt(pkt.get("t")), pkt.get("mode", ""),
            _fmt(pkt.get("x")), _fmt(pkt.get("y")), _fmt(pkt.get("z")), _fmt(pkt.get("yawDeg")),
            _fmt(pkt.get("u")), _fmt(pkt.get("v")), _fmt(pkt.get("r")),
            _fmt(pkt.get("portRpm")), _fmt(pkt.get("starboardRpm")),
            _fmt(pkt.get("rudderDeg")), _fmt(pkt.get("bowThrusterNorm")),
            _fmt(pkt.get("portRpmCmd")), _fmt(pkt.get("starboardRpmCmd")),
            _fmt(pkt.get("rudderCmdDeg")), _fmt(pkt.get("bowThrusterCmdNorm")),
            f"{speed_mag:.6f}", f"{rud_err:.6f}",
            _fmt(pkt.get("rollDeg")), _fmt(pkt.get("pitchDeg")), _fmt(pkt.get("heaveM")),
            self._t_mono(),
        ]
        self._state_writer.writerow(row)
        self._state_rows += 1

        # Auto-detect mode transitions from the state stream. This catches
        # IMO scenario phase changes ("approach" -> "turning_circle" ->
        # "coast" -> "idle") and helm mode flips without the listener
        # having to call record_event() explicitly.
        mode = pkt.get("mode")
        if mode and mode != self._last_mode:
            t = pkt.get("t")
            self.record_event(
                t_sim=float(t) if t is not None else 0.0,
                name="mode_change",
                details=f"{self._last_mode or '<init>'} -> {mode}",
            )
            self._last_mode = mode

    # ----------------------------------------------------------- events
    def record_event(self, t_sim: float, name: str, details: str = "") -> None:
        """Append a discrete event to events.csv and the manifest list."""
        if self.run_dir is None:
            return
        wall = time.time()
        if self._events_writer is not None:
            self._events_writer.writerow([f"{wall:.6f}", f"{t_sim:.6f}", name, details, self._t_mono()])
        self._events.append({
            "wallTime": wall,
            "t": t_sim,
            "name": name,
            "details": details,
        })

    # --------------------------------------------------------- lifecycle
    def finalise(self) -> None:
        """Flush and close files, write final manifest, and append a row
        to the project-level <log_dir>/runs.csv index."""
        if self.run_dir is None:
            return
        # One last event so the duration is visible in events.csv too.
        self.record_event(
            t_sim=0.0,
            name="run_ended",
            details=f"sensorRows={self._sensor_rows} stateRows={self._state_rows}",
        )
        try:
            if self._sensor_file is not None:
                self._sensor_file.flush()
                self._sensor_file.close()
            if self._state_file is not None:
                self._state_file.flush()
                self._state_file.close()
            if self._events_file is not None:
                self._events_file.flush()
                self._events_file.close()
            if self._sensor_raw_file is not None:
                self._sensor_raw_file.flush()
                self._sensor_raw_file.close()
        except Exception as e:
            print(f"[run_logger] close error: {e}")
        self._write_manifest(final=True)
        self._append_project_index()
        print(
            f"[run_logger] closed. sensor rows={self._sensor_rows}, "
            f"state rows={self._state_rows}, events={len(self._events)}"
        )

    # --------------------------------------------------------- internals
    def _write_manifest(self, final: bool) -> None:
        if self.run_dir is None:
            return
        manifest = {
            "runId": self.run_id,
            "plantKind": self.plant_kind,
            "controllerKind": self.controller_kind,
            "tickHz": self.tick_hz,
            "seaState": self.sea_state,
            "waveHeadingDeg": self.wave_heading_deg,
            "waveSeed": self.wave_seed,
            "startedAtEpoch": self._started_at,
            "startedAtLocal": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._started_at)),
            "final": final,
            "sensorRows": self._sensor_rows,
            "sensorRawLines": self._sensor_raw_lines,
            "stateRows": self._state_rows,
            "eventCount": len(self._events),
            "events": self._events,
            "timeBase": {
                "joinKey": "t_mono",
                "source": "time.monotonic() run-relative (seconds from run start)",
                "note": ("KI-024: sensor t=UE engine clock, state t=Python plant "
                         "clock (they diverge under high PIE FPS); t_mono is the "
                         "single canonical clock on BOTH logs -- fuse on t_mono."),
            },
        }
        if self.sea_state_schedule:
            manifest["seaStateSchedule"] = self.sea_state_schedule
        if self.scenario:
            manifest["scenario"] = self.scenario
        if self.ais_preset:
            manifest["ais"] = self.ais_preset
        if self.ais_target_name:
            manifest["aisTargetName"] = self.ais_target_name
        if final:
            manifest["endedAtEpoch"] = time.time()
            manifest["durationSeconds"] = manifest["endedAtEpoch"] - self._started_at
        path = os.path.join(self.run_dir, "manifest.json")
        with open(path, "w") as f:
            json.dump(manifest, f, indent=2)

    def _append_project_index(self) -> None:
        """Append one summary row to ``<log_root>/runs.csv``. Creates the
        file with a header on first write."""
        if not self._log_root or self.run_dir is None:
            return
        index_path = os.path.join(self._log_root, "runs.csv")
        ended = time.time()
        duration = ended - self._started_at

        # Pull a few interesting bits from the events list for the summary
        # column. For an IMO scenario this gives "approach -> turning_circle
        # -> coast -> idle" so you can scan runs.csv at a glance.
        modes: List[str] = []
        for ev in self._events:
            if ev.get("name") == "mode_change":
                d = ev.get("details", "")
                # details look like "<prev> -> <next>"; pick the next.
                arrow = d.find("-> ")
                if arrow >= 0:
                    modes.append(d[arrow + 3:].strip())
        modes_str = " > ".join(modes) if modes else ""

        # Relative path is friendlier than absolute for portability.
        try:
            run_dir_rel = os.path.relpath(self.run_dir, self._log_root)
        except ValueError:
            run_dir_rel = self.run_dir

        is_new = not os.path.exists(index_path)
        try:
            with open(index_path, "a", newline="", buffering=1) as f:
                w = csv.writer(f)
                if is_new:
                    w.writerow([
                        "started_local", "duration_s", "run_id",
                        "plant", "controller", "tick_hz",
                        "sensor_rows", "state_rows", "event_count",
                        "modes", "run_dir", "sea_state",
                    ])
                w.writerow([
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._started_at)),
                    f"{duration:.1f}",
                    self.run_id,
                    self.plant_kind,
                    self.controller_kind,
                    f"{self.tick_hz:g}",
                    self._sensor_rows,
                    self._state_rows,
                    len(self._events),
                    modes_str,
                    run_dir_rel,
                    f"SS{self.sea_state}",
                ])
        except OSError as e:
            print(f"[run_logger] couldn't append to runs.csv: {e}")


# ------------------------------------------------------------ helpers

def _fmt(v: Any) -> str:
    """Format a scalar for the CSV. None -> ''. Floats fixed width."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int,)):
        return str(v)
    if isinstance(v, float):
        return f"{v:.6f}"
    return str(v)


def _fmt_bool(v: Any) -> str:
    if v is None:
        return ""
    return "1" if v else "0"
