#!/usr/bin/env python3
# =====================================================================
# NaviSense WP-3 Verify — Bridge robustness (Python half) for 2026-06-14
# =====================================================================
# Run from a terminal (NO Unreal needed):
#
#     python verify_20260614.py            # spawns the listener itself
#     python verify_20260614.py -v         # verbose
#
# What it proves automatically (the Python / transport half of WP-3):
#   P1  Listener accepts a client and streams navisense.state.v1
#   P2  After a HARD client drop, the listener RE-ACCEPTS a new client
#       WITHOUT being relaunched, and resumes streaming
#   P3  A SECOND drop+reconnect also recovers (it's a durable loop, not one-shot)
#   P4  Each reconnect gets a FRESH run (first packet t≈0) — clean per-session state
#
# What still needs Lemuel in PIE (recorded MANUAL_REQUIRED, see PACKET.md):
#   G4  Kill/restart the listener mid-Play => pawn shows STALE + holds, then
#       UE auto-reconnects and the pawn resumes
#   G5  Zero game-thread hitches > 5 ms attributable to Send (Insights trace)
#
# Writes: NaviSense_UE5/Saved/NaviSense_Reports/wp_20260614_result.json
# Exit code 0 if all automated gates pass, 1 otherwise (nightly-friendly).
# =====================================================================

import argparse
import json
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LISTENER = os.path.normpath(os.path.join(HERE, "..", "..", "bridge_harness", "python_listener.py"))
REPORT_DIR = os.path.normpath(os.path.join(
    HERE, "..", "..", "..", "NaviSense_UE5", "Saved", "NaviSense_Reports"))
REPORT_FILE = os.path.join(REPORT_DIR, "wp_20260614_result.json")

VERBOSE = False
def log(m):
    print(f"[WP-3 verify] {m}", flush=True)
def vlog(m):
    if VERBOSE:
        log(m)


def connect_with_retry(host, port, deadline_s):
    """Open a fresh TCP client to the listener, retrying until deadline."""
    end = time.perf_counter() + deadline_s
    last = None
    while time.perf_counter() < end:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5.0)
        try:
            s.connect((host, port))
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            return s
        except OSError as e:
            last = e
            s.close()
            time.sleep(0.1)
    raise TimeoutError(f"could not connect to {host}:{port} within {deadline_s}s ({last})")


def recv_states(sock, n, timeout_s=6.0):
    """Read n newline-delimited navisense.state.v1 packets; return list of dicts."""
    sock.settimeout(timeout_s)
    buf = ""
    out = []
    end = time.perf_counter() + timeout_s
    while len(out) < n and time.perf_counter() < end:
        try:
            data = sock.recv(4096)
        except socket.timeout:
            break
        if not data:
            break
        buf += data.decode("utf-8", errors="replace")
        while "\n" in buf and len(out) < n:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                pkt = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(pkt.get("schema", "")).startswith("navisense.state"):
                out.append(pkt)
    return out


def hard_close(sock):
    """Force an immediate RST so the server sees the drop right away."""
    try:
        import struct
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                        struct.pack("ii", 1, 0))
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass


def stream_ok(states):
    """Schema correct on every packet and time non-decreasing."""
    if not states:
        return False
    if not all(str(p.get("schema", "")).startswith("navisense.state") for p in states):
        return False
    ts = [float(p.get("t", -1)) for p in states]
    return all(b >= a for a, b in zip(ts, ts[1:]))


def main():
    global VERBOSE
    ap = argparse.ArgumentParser(description="WP-3 bridge robustness verify (Python half)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5071, help="dedicated test port (not 5005)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    VERBOSE = args.verbose

    if not os.path.isfile(LISTENER):
        log(f"ERROR: listener not found at {LISTENER}")
        sys.exit(2)

    results = {}
    passed = 0
    total = 0

    log(f"Spawning listener: {LISTENER}  (port {args.port}, straight controller)")
    proc = subprocess.Popen(
        [sys.executable, LISTENER, "--controller", "straight", "--hz", "20",
         "--port", str(args.port), "--run-id", "wp3-verify"],
        stdout=(None if VERBOSE else subprocess.DEVNULL),
        stderr=(None if VERBOSE else subprocess.DEVNULL),
    )

    try:
        # ---- P1: initial connect + stream ------------------------------------
        total += 1
        s1 = connect_with_retry(args.host, args.port, deadline_s=8.0)
        st1 = recv_states(s1, 5)
        p1 = stream_ok(st1) and len(st1) >= 5
        results["P1_initial_stream"] = {
            "pass": p1,
            "detail": f"received {len(st1)} state.v1 packets on first connect"
        }
        passed += p1
        log(("PASS" if p1 else "FAIL") + f" P1 initial_stream: {len(st1)} packets")

        # ---- P2: reconnect after a hard drop (no relaunch) -------------------
        total += 1
        hard_close(s1)
        vlog("dropped first client; reconnecting...")
        time.sleep(0.4)
        s2 = connect_with_retry(args.host, args.port, deadline_s=8.0)
        st2 = recv_states(s2, 5)
        p2 = stream_ok(st2) and len(st2) >= 5
        results["P2_reaccept_after_drop"] = {
            "pass": p2,
            "detail": f"listener re-accepted and streamed {len(st2)} packets after a hard drop"
        }
        passed += p2
        log(("PASS" if p2 else "FAIL") + f" P2 reaccept_after_drop: {len(st2)} packets")

        # ---- P4: fresh run per connection (first packet t≈0) -----------------
        total += 1
        first_t = float(st2[0].get("t", 9.9)) if st2 else 9.9
        p4 = first_t < 0.5
        results["P4_fresh_run_per_connection"] = {
            "pass": p4,
            "detail": f"first packet t after reconnect = {first_t:.3f}s (expected < 0.5)"
        }
        passed += p4
        log(("PASS" if p4 else "FAIL") + f" P4 fresh_run_per_connection: first t={first_t:.3f}s")

        # ---- P3: a SECOND drop+reconnect also recovers -----------------------
        total += 1
        hard_close(s2)
        vlog("dropped second client; reconnecting again...")
        time.sleep(0.4)
        s3 = connect_with_retry(args.host, args.port, deadline_s=8.0)
        st3 = recv_states(s3, 5)
        p3 = stream_ok(st3) and len(st3) >= 5
        results["P3_second_reconnect"] = {
            "pass": p3,
            "detail": f"second reconnect streamed {len(st3)} packets (durable accept loop)"
        }
        passed += p3
        log(("PASS" if p3 else "FAIL") + f" P3 second_reconnect: {len(st3)} packets")
        hard_close(s3)

    except Exception as e:
        results["exception"] = {"pass": False, "detail": repr(e)}
        log(f"ERROR during verify: {e!r}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    # ---- manual UE-side gates (recorded, not auto-checkable here) ------------
    results["G4_ue_reconnect_and_hold"] = {
        "pass": "MANUAL_REQUIRED",
        "detail": ("In PIE: kill the listener -> within ~1 s the pawn shows STALE and "
                   "holds; restart the listener -> UE auto-reconnects and the pawn resumes.")
    }
    results["G5_no_send_hitch"] = {
        "pass": "MANUAL_REQUIRED",
        "detail": ("Insights (-trace=cpu): no game-thread hitch > 5 ms in "
                   "NaviSenseBridge_PumpTx / NaviSenseBridge_QueueSensorPacket.")
    }

    os.makedirs(REPORT_DIR, exist_ok=True)
    report = {
        "packet": "WP-3",
        "date": "2026-06-14",
        "theme": "Bridge robustness (F3)",
        "gates_passed": passed,
        "gates_total": total,
        "gates_manual": 2,
        "auto_result": "PASS" if passed == total else "PARTIAL",
        "checks": results,
        "note": ("P1–P4 verify the Python/transport half automatically. G4–G5 are "
                 "UE-side and require Lemuel in PIE (reconnect/hold + Insights hitch "
                 "trace). WP-3 closes when P1–P4 PASS and Lemuel confirms G4–G5."),
    }
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)

    log("=" * 60)
    log(f"WP-3 Python-half verify: {passed}/{total} automated gates PASS")
    log(f"Report: {REPORT_FILE}")
    log("G4–G5 remain MANUAL in PIE — see PACKET.md.")
    log("=" * 60)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
