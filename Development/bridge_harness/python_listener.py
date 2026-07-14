# === NaviSense: OFFLINE TEST HARNESS COPY ===
# The CANONICAL run listener is at the workspace root: ../../python_listener.py
# This copy exists only for offline protocol/CI tests (ue5_client_sim.py,
# mock_listener_selftest.py, WP verify scripts). For normal runs use the root one.
#!/usr/bin/env python3
# =====================================================================
# NaviSense — python_listener.py
# =====================================================================
# PURPOSE
#   The Python side of the NaviSense bridge.  Acts as the TCP SERVER
#   (Unreal connects out TO this script).  Runs a ship dynamics plant
#   and a controller, emits navisense.state.v1 at --plant-hz, and
#   receives navisense.sensor.v1 from Unreal.
#
# USAGE (from the Development/bridge_harness/ folder or anywhere with Python 3.9+)
#
#   python python_listener.py                            # MMG plant, zigzag10, default 20 Hz
#   python python_listener.py --controller zigzag10 --target unreal
#   python python_listener.py --controller turning_circle --plant mmg
#   python python_listener.py --controller straight      # steady stream (WP-3 robustness)
#
# CONTROLLERS
#   zigzag10        ±10 deg zig-zag, 3-s half-period (D1 sign test)
#   turning_circle  Full port and stbd turning circles
#   straight        Straight-ahead at design speed (for WP-3 bridge robustness)
#
# PLANTS
#   mmg             Simplified MMG manoeuvring model (DOLPHIN coefficients)
#   kinematic       Dead-reckoning kinematic stub (no forces — position only)
#
# WIRE PROTOCOL
#   Sends  : navisense.state.v1  (newline-delimited JSON)
#   Receives: navisense.sensor.v1 (logged only, not yet used by plant)
#
# ROBUSTNESS (WP-3)
#   The listener re-accepts connections after a client drop (default), so it
#   survives Unreal PIE restarts and the kill/restart reconnect test without
#   needing to be relaunched. Use --once for the old single-client CI behaviour.
#
# EXIT
#   Ctrl-C for clean shutdown.
# =====================================================================

import argparse
import json
import math
import socket
import sys
import threading
import time

# =====================================================================
# -- Coordinate helpers (mirror of FNaviSenseCoords) -------------------
# =====================================================================
M_TO_CM = 100.0

def norm360(a):
    return (a % 360.0 + 360.0) % 360.0

# =====================================================================
# -- MMG-lite plant ----------------------------------------------------
# =====================================================================
# Simplified 3-DOF MMG model (surge, sway, yaw) with DOLPHIN coefficients.
# Not validated against CFD — used for visual plausibility and sign correctness.
# The execution plan marks visual seakeeping as "honest approximation, flagged
# as such in docs" (§7, Risk R8).
#
# Reference non-dimensional coefficients are from standard MMG literature
# scaled to DOLPHIN LOA=40 m, displacement=~800 t.
# =====================================================================
class MMGPlant:
    def __init__(self):
        # ---- vessel geometry / mass ---
        self.L   = 40.0      # m  LOA
        self.B   = 7.5       # m  beam
        self.d   = 2.5       # m  draft
        self.m   = 800e3     # kg displacement mass
        self.Izz = self.m * (self.L ** 2) * 0.025   # yaw moment of inertia (approx)

        # Added mass (non-dim, scaled)
        self.mx  = 0.05 * self.m    # surge
        self.my  = 0.30 * self.m    # sway
        self.Jzz = 0.025 * self.Izz

        # Hull derivatives (linear + key nonlinear)
        self.Yv   = -0.31 * self.m
        self.Yr   = -0.001 * self.m * self.L
        self.Nv   = -0.14 * self.m * self.L
        self.Nr   = -0.065 * self.m * self.L ** 2
        self.Xu_u = -0.0055 * self.m           # surge drag coefficient (~speed^2)

        # Propeller (twin-screw simplified as single centre)
        self.Dp   = 1.8       # m  propeller diameter
        self.wp   = 0.30      # wake fraction
        self.tp   = 0.20      # thrust deduction
        self.etaR = 1.01      # relative rotative efficiency
        self.Kt0  = 0.43      # thrust coefficient at J=0 (bollard pull)
        self.Kq0  = 0.053

        # Rudder
        self.Ar   = 2.0       # m²  rudder area
        self.fAlpha = 2.74    # rudder lift slope (low AR fin)
        self.xR   = -0.5 * self.L    # rudder x position from midship (negative = aft)
        self.epsilon = 0.9    # wake at rudder vs propeller
        self.kappa  = 0.55    # rudder inflow factor

        # Design speed
        self.U_design = 4.12  # m/s (~8 kn)

        # State  [x_m (East), z_m (North), yaw_deg (CW from N), u, v, r]
        self.x     = 0.0
        self.z     = 0.0
        self.yawDeg = 0.0
        self.u     = self.U_design
        self.v     = 0.0
        self.r     = 0.0   # rad/s

        # Actuator state
        self.rudder_deg  = 0.0    # actual (rate-limited)
        self.rpm         = 900.0  # actual (rate-limited), both shafts same

    def _rho(self):
        return 1025.0  # salt water kg/m³

    def _thrust(self, rpm, u):
        """Single-prop thrust (N) from rpm and advance speed u (m/s)."""
        n   = abs(rpm) / 60.0        # rev/s
        Vp  = u * (1 - self.wp)
        J   = (Vp / (n * self.Dp)) if n > 0.1 else 0.0
        J   = max(0.0, min(J, 0.9))
        Kt  = self.Kt0 * (1.0 - 1.3 * J)   # linear approximation
        Kt  = max(0.0, Kt)
        T   = self.rho * n ** 2 * self.Dp ** 4 * Kt
        return math.copysign(T, rpm)

    @property
    def rho(self):
        return 1025.0

    def _rudder_forces(self, u, v, r, rudder_rad, rpm):
        """Rudder normal force and resulting X/Y/N contributions."""
        n   = abs(rpm) / 60.0
        Vp  = u * (1 - self.wp)
        J   = (Vp / (n * self.Dp)) if n > 0.1 else 0.0
        J   = max(0.0, min(J, 0.9))
        Kt  = max(0.0, self.Kt0 * (1.0 - 1.3 * J))
        # Effective inflow velocity at rudder
        uR  = self.epsilon * Vp + self.kappa * math.sqrt(
              abs(8.0 * Kt * n**2 * self.Dp**2 / math.pi) + Vp**2) if n > 0.1 else Vp
        vR  = v + self.xR * r   # sway at rudder
        aR  = math.atan2(-vR, uR) - rudder_rad  # attack angle
        FN  = 0.5 * self.rho * self.Ar * uR**2 * self.fAlpha * math.sin(aR)
        Xr  = -FN * math.sin(rudder_rad)
        Yr  =  FN * math.cos(rudder_rad)
        Nr  =  self.xR * Yr
        return Xr, Yr, Nr

    def step(self, dt, rudder_cmd_deg, rpm_cmd):
        """Integrate one time step."""
        # Rate-limit actuators
        rud_rate = 8.0   # deg/s
        rpm_rate = 300.0 # rpm/s
        dr = rudder_cmd_deg - self.rudder_deg
        self.rudder_deg += math.copysign(min(abs(dr), rud_rate * dt), dr)
        self.rudder_deg  = max(-35.0, min(35.0, self.rudder_deg))

        dn = rpm_cmd - self.rpm
        self.rpm += math.copysign(min(abs(dn), rpm_rate * dt), dn)
        self.rpm  = max(-1800.0, min(1800.0, self.rpm))

        rudder_rad = math.radians(self.rudder_deg)
        T = self._thrust(self.rpm, self.u)

        # Forces in body frame
        Xu  = self.Xu_u * self.u * abs(self.u)
        X   = (1 - self.tp) * T + Xu
        Y   = self.Yv * self.v + self.Yr * self.r
        N   = self.Nv * self.v + self.Nr * self.r
        Xr, Yr, Nr = self._rudder_forces(self.u, self.v, self.r, rudder_rad, self.rpm)
        X  += Xr
        Y  += Yr
        N  += Nr

        # EOM
        Mx = self.m + self.mx
        My = self.m + self.my
        Mn = self.Izz + self.Jzz

        u_dot = (X + self.m * self.v * self.r) / Mx
        v_dot = (Y - self.m * self.u * self.r) / My
        r_dot = N / Mn

        self.u += u_dot * dt
        self.v += v_dot * dt
        self.r += r_dot * dt

        # Cap surge to reasonable range
        self.u = max(-2.0, min(12.0, self.u))

        # Kinematic integration in world frame (Unity: x=East, z=North, yaw CW from N)
        psi = math.radians(self.yawDeg)
        x_dot =  self.u * math.sin(psi) + self.v * math.cos(psi)
        z_dot =  self.u * math.cos(psi) - self.v * math.sin(psi)
        psi_dot = self.r

        self.x      += x_dot * dt
        self.z      += z_dot * dt
        self.yawDeg  = norm360(self.yawDeg + math.degrees(psi_dot) * dt)


class KinematicPlant:
    """Dead-reckoning stub — no forces, just integrate heading from rudder."""
    def __init__(self):
        self.x = self.z = 0.0
        self.yawDeg = 0.0
        self.u = 4.12   # fixed design speed
        self.v = 0.0
        self.r = 0.0
        self.rudder_deg = 0.0
        self.rpm = 900.0

    def step(self, dt, rudder_cmd_deg, rpm_cmd):
        self.rudder_deg = max(-35.0, min(35.0, rudder_cmd_deg))
        self.rpm = rpm_cmd
        # Simple: yaw rate proportional to rudder
        self.r = math.radians(self.rudder_deg * 1.2)   # ~1.2 deg/s per deg rudder
        psi = math.radians(self.yawDeg)
        self.x      += (self.u * math.sin(psi)) * dt
        self.z      += (self.u * math.cos(psi)) * dt
        self.yawDeg  = norm360(self.yawDeg + math.degrees(self.r) * dt)


# =====================================================================
# -- Controllers -------------------------------------------------------
# =====================================================================
class ZigZagController:
    """±zig_angle deg zig-zag; flips rudder every half_period_s seconds."""
    def __init__(self, zig_angle=10.0, half_period_s=6.0, rpm=900.0):
        self.zig   = zig_angle
        self.half  = half_period_s
        self.rpm   = rpm
        self._t    = 0.0

    def command(self, dt, state):
        self._t += dt
        phase = int(self._t // self.half) % 2
        rudder = +self.zig if phase == 0 else -self.zig
        return rudder, self.rpm


class TurningCircleController:
    """Full 360° turn to port then starboard."""
    def __init__(self, rudder_angle=35.0, rpm=900.0, turns=2):
        self.rud  = rudder_angle
        self.rpm  = rpm
        self.turns = turns
        self._t   = 0.0
        self._turn = 0

    def command(self, dt, state):
        self._t += dt
        # Switch direction every 120 s (enough for one full turn at 8 kn)
        idx = int(self._t // 120.0) % 2
        rudder = +self.rud if idx == 0 else -self.rud
        return rudder, self.rpm


class StraightController:
    def __init__(self, rpm=900.0):
        self.rpm = rpm
    def command(self, dt, state):
        return 0.0, self.rpm


# =====================================================================
# -- Server / main loop -----------------------------------------------
# =====================================================================
def build_state_packet(plant, run_id, t, rud_cmd, rpm_cmd):
    return {
        "schema": "navisense.state.v1",
        "runId":  run_id,
        "t":      round(t, 3),
        "x":      round(plant.x, 4),
        "y":      0.0,
        "z":      round(plant.z, 4),
        "yawDeg": round(plant.yawDeg, 4),
        "u":      round(plant.u, 4),
        "v":      round(plant.v, 4),
        "r":      round(plant.r, 6),
        "portRpm":         round(plant.rpm, 1),
        "starboardRpm":    round(plant.rpm, 1),
        "rudderDeg":       round(plant.rudder_deg, 3),
        "bowThrusterNorm": 0.0,
        "portRpmCmd":         round(rpm_cmd, 1),
        "starboardRpmCmd":    round(rpm_cmd, 1),
        "rudderCmdDeg":       round(rud_cmd, 3),
        "bowThrusterCmdNorm": 0.0,
        "mode": "auto",
    }


def rx_thread_fn(conn, stop_evt, verbose):
    """Background thread: receive sensor packets from Unreal (log only for now)."""
    buf = ""
    while not stop_evt.is_set():
        try:
            data = conn.recv(4096)
            if not data:
                break
            buf += data.decode("utf-8", errors="replace")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if line and verbose:
                    try:
                        pkt = json.loads(line)
                        t = pkt.get("t", "?")
                        schema = pkt.get("schema", "?")
                        print(f"  [rx] {schema} t={t}")
                    except json.JSONDecodeError:
                        pass
        except OSError:
            break


def serve_connection(conn, addr, plant, controller, plant_hz, run_id, verbose, timeout_s=None):
    """Stream state.v1 to one connected client until it disconnects, the timeout
    is hit, or Ctrl-C. Returns one of: 'client_disconnect', 'timeout'.
    WP-3: a client drop is a NORMAL, recoverable event — we return so the caller
    can go back to accept() and wait for Unreal to reconnect."""
    dt = 1.0 / plant_hz
    t  = 0.0

    print(f"[listener] Unreal connected from {addr}")
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    stop_evt = threading.Event()
    rx = threading.Thread(target=rx_thread_fn, args=(conn, stop_evt, verbose), daemon=True)
    rx.start()

    reason = "client_disconnect"
    nxt = time.perf_counter()
    try:
        while True:
            now = time.perf_counter()
            if now < nxt:
                time.sleep(max(0.0, nxt - now))
            nxt += dt

            # Step plant and controller.
            # Pass a minimal state dict for controllers that need it.
            state = {"yawDeg": plant.yawDeg, "u": plant.u, "r": plant.r, "t": t}
            rud_cmd, rpm_cmd = controller.command(dt, state)
            plant.step(dt, rud_cmd, rpm_cmd)

            pkt = build_state_packet(plant, run_id, t, rud_cmd, rpm_cmd)
            line = json.dumps(pkt) + "\n"
            try:
                conn.sendall(line.encode("utf-8"))
            except OSError as e:
                print(f"\n[listener] Send error: {e} — Unreal disconnected.")
                reason = "client_disconnect"
                break

            if verbose:
                print(f"\r[tx] t={t:7.2f}s  yaw={plant.yawDeg:6.1f}deg  u={plant.u:4.2f}m/s  rud={plant.rudder_deg:+5.1f}deg  r={math.degrees(plant.r):+5.2f}deg/s  ", end="", flush=True)

            t += dt

            if timeout_s and t >= timeout_s:
                print(f"\n[listener] Timeout {timeout_s}s reached, shutting down cleanly.")
                reason = "timeout"
                break
    finally:
        stop_evt.set()
        try:
            conn.close()
        except OSError:
            pass
    return reason


def run_server(host, port, plant_factory, controller_factory, plant_hz, run_id,
               verbose, timeout_s=None, reaccept=True):
    """Bind once, then (re)accept clients. Each new client gets a FRESH plant +
    controller so every PIE session / reconnect starts from a clean run state.
    With reaccept=True (default) the listener survives Unreal restarts and the
    WP-3 kill/restart test without needing to be relaunched."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(1)
    srv.settimeout(1.0)   # short timeout so Ctrl-C is responsive between clients

    print(f"[listener] Waiting for Unreal to connect on {host}:{port} ...")
    print(f"[listener] Press Ctrl-C to stop. Re-accept={'on' if reaccept else 'off'}")

    sessions = 0
    try:
        while True:
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue   # no client yet; loop so Ctrl-C stays responsive
            except OSError:
                break

            sessions += 1
            plant = plant_factory()
            controller = controller_factory()
            print(f"[listener] Session #{sessions}  Plant: {plant.__class__.__name__}  "
                  f"Controller: {controller.__class__.__name__}  {plant_hz} Hz")

            reason = serve_connection(conn, addr, plant, controller, plant_hz,
                                      run_id, verbose, timeout_s)

            if reason == "timeout" or not reaccept:
                break
            print("[listener] Client gone - waiting for Unreal to reconnect "
                  "(Ctrl-C to stop)...")
    except KeyboardInterrupt:
        print("\n[listener] Interrupted by user.")
    finally:
        srv.close()
        print("[listener] Closed.")


def main():
    p = argparse.ArgumentParser(description="NaviSense bridge Python listener")
    p.add_argument("--host",       default="127.0.0.1")
    p.add_argument("--port",       type=int, default=5005)
    p.add_argument("--plant",      default="mmg",       choices=["mmg", "kinematic"])
    p.add_argument("--controller", default="zigzag10",  choices=["zigzag10", "turning_circle", "straight"])
    p.add_argument("--hz",         type=float, default=20.0, dest="plant_hz",
                   help="State packet rate (Hz)")
    p.add_argument("--run-id",     default="run-001")
    p.add_argument("--timeout",    type=float, default=None,
                   help="Stop after this many sim-seconds (for scripted CI runs)")
    p.add_argument("--target",     default="unreal",    choices=["unreal"],
                   help="(Future: select sim target; currently only 'unreal' supported)")
    p.add_argument("--once",       action="store_true",
                   help="Exit after the first client disconnects (old CI behaviour). "
                        "Default is to re-accept so the listener survives UE restarts.")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    # Factories: a FRESH plant + controller is built for every accepted client
    # so each reconnect / PIE session starts from a clean, repeatable run state.
    def plant_factory():
        return MMGPlant() if args.plant == "mmg" else KinematicPlant()

    def controller_factory():
        if args.controller == "zigzag10":
            return ZigZagController(zig_angle=10.0, half_period_s=6.0)
        elif args.controller == "turning_circle":
            return TurningCircleController()
        return StraightController()

    run_server(args.host, args.port, plant_factory, controller_factory, args.plant_hz,
               args.run_id, args.verbose, args.timeout, reaccept=not args.once)


if __name__ == "__main__":
    main()
