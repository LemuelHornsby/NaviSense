#!/usr/bin/env python3
# =====================================================================
# verify_canonical_reaccept.py - WP-10 re-accept check for the CANONICAL listener
# =====================================================================
# KI-017: the canonical run listener at the WORKSPACE ROOT
#   "<workspace>/python_listener.py"
# used to do a SINGLE socket.accept() then exit when the client dropped, so a
# UE PIE stop/restart ENDED the listener instead of it re-accepting. WP-10 ports
# the WP-3 re-accept loop into it. This verify proves, headless, that:
#   R1 initial stream      - first client gets >=5 navisense.state.v1 packets
#   R2 reaccept after drop  - after a HARD drop, a new client connects + streams
#   R3 fresh run            - the reconnect's first packet has t < 0.5 s (new run)
#   R4 second reconnect     - a 2nd hard drop + reconnect also streams (loop, not one-shot)
#   R5 --once exits          - with --once, the process exits after the first drop
#
# Dependency-light path (--plant stub --controller demo --no-log) so it runs
# anywhere the python/ package imports. Targets the CANONICAL listener via the
# corrected workspace-root path (the old verify_root_reaccept.py resolved three
# levels up to the BACKUP root - see KI-017).
#
# Run from anywhere:
#     python verify_canonical_reaccept.py
#     python verify_canonical_reaccept.py --port 5079 -v
#
# Writes: NaviSense_UE5/Saved/NaviSense_Reports/wp_20260619_canonical_reaccept_result.json
# Exit 0 if all checks pass, 1 otherwise.
# =====================================================================
import argparse, json, os, socket, struct, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
# WP_20260619 -> work_packets -> Development -> <workspace root> (the CANONICAL root)
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
LISTENER = os.path.join(ROOT, "python_listener.py")
REPORT_DIR = os.path.join(ROOT, "NaviSense_UE5", "Saved", "NaviSense_Reports")
REPORT_FILE = os.path.join(REPORT_DIR, "wp_20260619_canonical_reaccept_result.json")


def spawn(port, once=False, verbose=False):
    env = dict(os.environ)
    env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [sys.executable, LISTENER, "--plant", "stub", "--controller", "demo",
           "--no-log", "--hz", "20", "--port", str(port), "--run-id", "reaccept-verify"]
    if once:
        cmd.append("--once")
    return subprocess.Popen(
        cmd, env=env, cwd=ROOT,
        stdout=(None if verbose else subprocess.DEVNULL),
        stderr=(None if verbose else subprocess.DEVNULL))


def connect(port, deadline=8.0):
    end = time.perf_counter() + deadline
    last = None
    while time.perf_counter() < end:
        s = socket.socket(); s.settimeout(5.0)
        try:
            s.connect(("127.0.0.1", port)); return s
        except OSError as e:
            last = e; s.close(); time.sleep(0.1)
    raise TimeoutError(f"could not connect to 127.0.0.1:{port} ({last})")


def read_states(s, n, to=6.0):
    s.settimeout(to); buf = ""; out = []; end = time.perf_counter() + to
    while len(out) < n and time.perf_counter() < end:
        try:
            d = s.recv(4096)
        except socket.timeout:
            break
        if not d:
            break
        buf += d.decode("utf-8", "replace")
        while "\n" in buf and len(out) < n:
            ln, buf = buf.split("\n", 1); ln = ln.strip()
            if not ln:
                continue
            try:
                p = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if str(p.get("schema", "")).startswith("navisense.state"):
                out.append(p)
    return out


def hard_close(s):
    # SO_LINGER 0 => send a RST on close, mimicking a hard UE/PIE kill.
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    except OSError:
        pass
    s.close()


def main():
    ap = argparse.ArgumentParser(description="WP-10 re-accept check for the CANONICAL listener")
    ap.add_argument("--port", type=int, default=5079)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(LISTENER):
        print(f"[verify] ERROR: canonical listener not found at {LISTENER}"); sys.exit(2)

    results, passed, total = {}, 0, 0

    def check(name, ok, detail):
        nonlocal passed, total
        total += 1; passed += bool(ok)
        results[name] = {"pass": bool(ok), "detail": detail}
        print(("PASS" if ok else "FAIL"), name, "-", detail)

    # ---- R1-R4: re-accept ON (default) -------------------------------------
    proc = spawn(args.port, once=False, verbose=args.verbose)
    try:
        try:
            s1 = connect(args.port); a = read_states(s1, 5)
            ok = len(a) >= 5 and all(str(p["schema"]).startswith("navisense.state") for p in a)
            check("R1_initial_stream", ok, f"{len(a)} state.v1 on first connect")
        except Exception as e:
            check("R1_initial_stream", False, f"exception: {e!r}")

        try:
            hard_close(s1); time.sleep(0.6)
            s2 = connect(args.port); b = read_states(s2, 5)
            check("R2_reaccept_after_drop", len(b) >= 5, f"{len(b)} packets after hard drop")
        except Exception as e:
            b = []
            check("R2_reaccept_after_drop", False, f"exception: {e!r}")

        first_t = float(b[0].get("t", 9.9)) if b else 9.9
        check("R3_fresh_run", first_t < 0.5, f"first t after reconnect = {first_t:.3f}s")

        try:
            if b:
                hard_close(s2); time.sleep(0.6)
            s3 = connect(args.port); c = read_states(s3, 5)
            check("R4_second_reconnect", len(c) >= 5, f"{len(c)} packets on 2nd reconnect")
            hard_close(s3)
        except Exception as e:
            check("R4_second_reconnect", False, f"exception: {e!r}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    # ---- R5: --once exits after the first client -----------------------------
    proc1 = spawn(args.port, once=True, verbose=args.verbose)
    try:
        try:
            s = connect(args.port); a = read_states(s, 5)
            got_first = len(a) >= 5
            hard_close(s)
            # Give the one-shot listener a moment to exit after the drop.
            exited = False
            for _ in range(30):
                if proc1.poll() is not None:
                    exited = True; break
                time.sleep(0.1)
            check("R5_once_exits_after_drop", got_first and exited,
                  f"first stream={got_first}, process_exited={exited}")
        except Exception as e:
            check("R5_once_exits_after_drop", False, f"exception: {e!r}")
    finally:
        if proc1.poll() is None:
            proc1.terminate()
            try:
                proc1.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc1.kill()

    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(REPORT_FILE, "w") as f:
        json.dump({"target": "canonical workspace-root python_listener.py",
                   "ki": "KI-017", "packet": "WP-10 (2026-06-19)",
                   "gates_passed": passed, "gates_total": total,
                   "auto_result": "PASS" if passed == total else "PARTIAL",
                   "checks": results}, f, indent=2)
    print(f"{passed}/{total} PASS -> {REPORT_FILE}")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
