#!/usr/bin/env python3
# =====================================================================
# NaviSense — mock listener for harness SELF-TEST (no MMG deps needed)
# =====================================================================
# This is a tiny stand-in for python_listener.py used ONLY to self-test
# ue5_client_sim.py without the full project Python stack. It binds the
# listener side, accepts the harness, and emits a synthetic
# navisense.state.v1 zig-zag stream where positive rudder command is
# paired with INCREASING heading (the correct starboard convention) plus
# one extra unknown field to exercise forward-compat parsing.
#
# Run:  python mock_listener_selftest.py        (terminal 1)
#       python ue5_client_sim.py --seconds 8    (terminal 2)
# Expect: harness prints ALL CHECKS PASSED (incl. the SIGN TEST).
# =====================================================================
import json, math, socket, time

HOST, PORT, HZ = "127.0.0.1", 5005, 30.0

def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT)); srv.listen(1)
    print(f"[mock] listening on {HOST}:{PORT}")
    conn, addr = srv.accept()
    print(f"[mock] client connected from {addr}")

    dt = 1.0 / HZ
    t = 0.0
    yaw = 0.0
    x = z = 0.0
    nxt = time.perf_counter()
    try:
        while True:
            now = time.perf_counter()
            if now < nxt:
                time.sleep(max(0.0, nxt - now))
            nxt += dt

            # Zig-zag: rudder command sign flips every 3 s; heading follows the
            # CORRECT convention (positive rudder -> heading increases/starboard).
            phase = int(t // 3.0) % 2
            rud_cmd = +15.0 if phase == 0 else -15.0
            yaw_rate = 6.0 if rud_cmd > 0 else -6.0     # deg/s, same sign as rudder
            yaw = (yaw + yaw_rate * dt) % 360.0

            # Advance position a little along heading (metres, Unity frame).
            spd = 2.0
            x += spd * dt * math.sin(math.radians(yaw))   # East
            z += spd * dt * math.cos(math.radians(yaw))   # North

            pkt = {
                "schema": "navisense.state.v1", "runId": "selftest", "t": round(t, 3),
                "x": round(x, 3), "y": 0.0, "z": round(z, 3), "yawDeg": round(yaw, 3),
                "u": spd, "v": 0.0, "r": math.radians(yaw_rate),
                "portRpm": 900.0, "starboardRpm": 900.0,
                "rudderDeg": rud_cmd, "bowThrusterNorm": 0.0,
                "portRpmCmd": 900.0, "starboardRpmCmd": 900.0,
                "rudderCmdDeg": rud_cmd, "bowThrusterCmdNorm": 0.0,
                "mode": "auto",
                "experimentalFutureField": 1,   # unknown-field forward-compat probe
            }
            try:
                conn.sendall((json.dumps(pkt) + "\n").encode("utf-8"))
            except OSError:
                break
            t += dt
    except KeyboardInterrupt:
        pass
    finally:
        conn.close(); srv.close()

if __name__ == "__main__":
    main()
