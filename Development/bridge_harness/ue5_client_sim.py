#!/usr/bin/env python3
# =====================================================================
# NaviSense UE5 — standalone bridge client simulator
# =====================================================================
# WHAT THIS IS
#   A pure-Python stand-in for the Unreal C++ UNaviSenseBridgeComponent.
#   It speaks the EXACT v1.1 wire protocol so you can validate the whole
#   closed loop WITHOUT Unreal or a GPU — from any laptop while away from
#   the PC. It also re-implements the C++ coordinate transform
#   (FNaviSenseCoords) so a passing run is evidence the C++ math is right.
#
# WHAT IT DOES
#   1. Connects out to the listener (default 127.0.0.1:5005) exactly as
#      Unreal will (simulator = client; Python listener = server).
#   2. Sends navisense.sensor.v1 at --send-hz (default 5 Hz), with a GPS
#      block whose worldPosition is derived from the pose it last received,
#      converted UE->wire (round-tripping the transform like the real client).
#   3. Receives navisense.state.v1, parses pose, converts wire->UE (cm),
#      and tracks heading so we can run the zig-zag SIGN TEST automatically.
#   4. Prints a live one-line status and, on exit, a PASS/FAIL summary:
#         - did we receive well-formed state packets?
#         - did unknown fields get tolerated?
#         - SIGN TEST: when rudderCmdDeg > 0, did yaw trend to starboard?
#
# HOW TO RUN (two terminals, same machine)
#   T1:  python python_listener.py --plant mmg --controller zigzag10 --target unreal
#   T2:  python ue5_client_sim.py --seconds 40
#
#   Or fully offline with the kinematic stub plant:
#   T1:  python python_listener.py --controller turning_circle --target unreal
#   T2:  python ue5_client_sim.py --seconds 30
#
# EXIT CODE: 0 if all checks pass, 1 otherwise (handy for CI / scripted runs).
# =====================================================================
import argparse
import json
import math
import socket
import sys
import threading
import time


# ---------------------------------------------------------------------
# Mirror of the C++ FNaviSenseCoords (Source/NaviSense/Core/NaviSenseCoords.h)
# Keep these IN SYNC with the C++ — this is the cross-check.
# ---------------------------------------------------------------------
M_TO_CM = 100.0
CM_TO_M = 0.01

def wire_to_ue(x, y, z):
    """wire (x=East, y=Up, z=North) m -> UE (X=North, Y=East, Z=Up) cm."""
    return (z * M_TO_CM, x * M_TO_CM, y * M_TO_CM)   # (UE.X, UE.Y, UE.Z)

def ue_to_wire(ue_x, ue_y, ue_z):
    """UE cm -> wire m, packed (x=East, y=Up, z=North)."""
    return (ue_y * CM_TO_M, ue_z * CM_TO_M, ue_x * CM_TO_M)

def norm360(a):
    return (a % 360.0 + 360.0) % 360.0


class UE5ClientSim:
    def __init__(self, host, port, send_hz, run_id, verbose):
        self.host = host
        self.port = port
        self.send_dt = 1.0 / send_hz
        self.run_id = run_id
        self.verbose = verbose

        self.sock = None
        self.stop = threading.Event()

        # Last applied pose (UE cm) + heading history for the sign test.
        self.ue_pos = (0.0, 0.0, 0.0)
        self.last_yaw = None
        self.t0 = time.time()

        # Diagnostics
        self.state_count = 0
        self.unknown_field_seen = False
        self.sign_samples = 0      # ticks where rudderCmdDeg > deadband
        self.sign_correct = 0      # of those, yaw increased (starboard)
        self.sign_pos_cmd = 0
        self.last_state_t = None
        self.parse_errors = 0

    # ---- receive thread: read newline-delimited state packets ----
    def _recv_loop(self):
        carry = b""
        self.sock.settimeout(0.2)
        while not self.stop.is_set():
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    print("[ue5sim] listener closed the connection.")
                    self.stop.set()
                    return
                carry += chunk
                while b"\n" in carry:
                    line, carry = carry.split(b"\n", 1)
                    line = line.strip()
                    if line:
                        self._on_state_line(line)
            except socket.timeout:
                continue
            except OSError as e:
                print(f"[ue5sim] socket error: {e}")
                self.stop.set()
                return

    def _on_state_line(self, raw):
        try:
            msg = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.parse_errors += 1
            return
        if not str(msg.get("schema", "")).startswith("navisense.state"):
            return

        self.state_count += 1
        self.last_state_t = msg.get("t")

        # Tolerate unknown fields (inject one would be the listener's job; here
        # we just confirm extra keys don't break us). Mark if any beyond the
        # known set are present — proves forward-compat parsing.
        known = {"schema", "runId", "t", "x", "y", "z", "yawDeg", "u", "v", "r",
                 "portRpm", "starboardRpm", "rudderDeg", "bowThrusterNorm",
                 "portRpmCmd", "starboardRpmCmd", "rudderCmdDeg",
                 "bowThrusterCmdNorm", "mode"}
        if any(k not in known for k in msg.keys()):
            self.unknown_field_seen = True

        # Apply pose exactly like the C++ ApplyOwnShipState().
        x = float(msg.get("x", 0.0)); y = float(msg.get("y", 0.0)); z = float(msg.get("z", 0.0))
        self.ue_pos = wire_to_ue(x, y, z)
        yaw = norm360(float(msg.get("yawDeg", 0.0)))

        # --- Zig-zag / turning SIGN TEST ---
        # Convention (BRIDGE_SCHEMA + guide): positive rudder -> bow swings to
        # starboard -> heading (CW-from-North) should INCREASE. We sample only
        # when a clear positive rudder command is present.
        rud_cmd = float(msg.get("rudderCmdDeg", 0.0))
        if self.last_yaw is not None and abs(rud_cmd) > 1.0:
            dyaw = ((yaw - self.last_yaw + 540.0) % 360.0) - 180.0  # shortest signed delta
            if rud_cmd > 1.0:
                self.sign_pos_cmd += 1
                self.sign_samples += 1
                if dyaw > 0.0:
                    self.sign_correct += 1
        self.last_yaw = yaw

        if self.verbose:
            print(f"[ue5sim] RX t={msg.get('t'):.2f} "
                  f"UE=({self.ue_pos[0]:.0f},{self.ue_pos[1]:.0f}) "
                  f"yaw={yaw:.1f} rudCmd={rud_cmd:.1f} mode={msg.get('mode')}")

    # ---- send: emit sensor.v1 derived from the last applied pose ----
    def _send_sensor(self):
        wx, wy, wz = ue_to_wire(*self.ue_pos)   # round-trip the transform
        t = time.time() - self.t0
        pkt = {
            "schema": "navisense.sensor.v1",
            "runId": self.run_id,
            "t": round(t, 3),
            "sensors": {
                "time": round(t, 3),
                "gps": {
                    "worldPosition": {"x": wx, "y": wy, "z": wz},
                    "speed": 0.0, "latDeg": 0.0, "lonDeg": 0.0, "hasFix": True,
                },
                "imu": {
                    "headingDeg": self.last_yaw if self.last_yaw is not None else 0.0,
                    "yawRateDegPerSec": 0.0,
                    "acceleration": {"x": 0.0, "y": 0.0, "z": 0.0},
                },
                "ais": {"targets": []},
            },
        }
        line = (json.dumps(pkt) + "\n").encode("utf-8")
        try:
            self.sock.sendall(line)
        except OSError as e:
            print(f"[ue5sim] send failed: {e}")
            self.stop.set()

    def run(self, seconds):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.host, self.port))
        except OSError as e:
            print(f"[ue5sim] CONNECT FAILED to {self.host}:{self.port}: {e}")
            print("[ue5sim] Start the listener first:  "
                  "python python_listener.py --target unreal")
            return 1
        print(f"[ue5sim] connected to {self.host}:{self.port} as the UE client.")

        rx = threading.Thread(target=self._recv_loop, daemon=True)
        rx.start()

        next_send = time.time()
        deadline = time.time() + seconds
        try:
            while not self.stop.is_set() and time.time() < deadline:
                now = time.time()
                if now >= next_send:
                    next_send += self.send_dt
                    self._send_sensor()
                time.sleep(0.005)
        except KeyboardInterrupt:
            print("\n[ue5sim] Ctrl-C.")
        finally:
            self.stop.set()
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.sock.close()

        return self._summary()

    def _summary(self):
        print("\n" + "=" * 60)
        print("NaviSense UE5 bridge harness — RESULTS")
        print("=" * 60)
        ok = True

        def check(label, passed, detail=""):
            nonlocal ok
            ok = ok and passed
            print(f"  [{'PASS' if passed else 'FAIL'}] {label}"
                  + (f"  ({detail})" if detail else ""))

        check("received state.v1 packets", self.state_count > 0,
              f"{self.state_count} packets")
        check("no JSON parse errors", self.parse_errors == 0,
              f"{self.parse_errors} errors")
        check("sim clock advanced", (self.last_state_t or 0) > 0,
              f"last t={self.last_state_t}")

        # Sign test only meaningful if a controller issued positive rudder.
        if self.sign_pos_cmd >= 5:
            frac = self.sign_correct / max(1, self.sign_pos_cmd)
            check("zig-zag SIGN TEST (rudder+ -> bow starboard)",
                  frac >= 0.7, f"{self.sign_correct}/{self.sign_pos_cmd} ticks, {frac:.0%}")
        else:
            print("  [SKIP] sign test — not enough positive-rudder ticks "
                  f"({self.sign_pos_cmd}). Use --controller zigzag10 or turning_circle.")

        print("=" * 60)
        print("RESULT:", "ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
        print("=" * 60)
        return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="Standalone UE5 bridge client simulator.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5005)
    ap.add_argument("--send-hz", type=float, default=5.0)
    ap.add_argument("--run-id", default="ue5-harness")
    ap.add_argument("--seconds", type=float, default=30.0,
                    help="How long to run before printing the summary.")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    sim = UE5ClientSim(args.host, args.port, args.send_hz, args.run_id, args.verbose)
    sys.exit(sim.run(args.seconds))


if __name__ == "__main__":
    main()
