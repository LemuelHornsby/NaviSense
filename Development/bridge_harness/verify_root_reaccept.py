#!/usr/bin/env python3
# =====================================================================
# verify_root_reaccept.py — WP-3 robustness check for the CANONICAL listener
# =====================================================================
# Confirms the *real run* listener at the workspace root
# (NAVISENSE/python_listener.py) survives client drops: it re-accepts a new
# connection after a hard drop and starts a fresh run each time. Uses the
# dependency-light default path (--plant stub --controller demo --no-log) so it
# runs anywhere the python/ package imports.
#
# Run from anywhere:
#     python verify_root_reaccept.py            # auto-locates the root listener
#     python verify_root_reaccept.py --port 5074 -v
#
# Writes: NaviSense_UE5/Saved/NaviSense_Reports/root_listener_reaccept_result.json
# Exit 0 if all checks pass, 1 otherwise.
# =====================================================================
import argparse, json, os, socket, struct, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
# bridge_harness -> Development -> "NaviSense Simulator with Unreal Engine" -> NAVISENSE
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
LISTENER = os.path.join(ROOT, "python_listener.py")
REPORT_DIR = os.path.normpath(os.path.join(
    HERE, "..", "..", "NaviSense_UE5", "Saved", "NaviSense_Reports"))
REPORT_FILE = os.path.join(REPORT_DIR, "root_listener_reaccept_result.json")


def connect(port, deadline=8.0):
    end = time.perf_counter() + deadline
    while time.perf_counter() < end:
        s = socket.socket(); s.settimeout(5.0)
        try:
            s.connect(("127.0.0.1", port)); return s
        except OSError:
            s.close(); time.sleep(0.1)
    raise TimeoutError(f"could not connect to 127.0.0.1:{port}")


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
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    except OSError:
        pass
    s.close()


def main():
    ap = argparse.ArgumentParser(description="WP-3 re-accept check for the canonical root listener")
    ap.add_argument("--port", type=int, default=5074)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(LISTENER):
        print(f"[verify] ERROR: root listener not found at {LISTENER}"); sys.exit(2)

    env = dict(os.environ)
    env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        [sys.executable, LISTENER, "--plant", "stub", "--controller", "demo",
         "--no-log", "--hz", "20", "--port", str(args.port), "--run-id", "reaccept-verify"],
        env=env, cwd=ROOT,
        stdout=(None if args.verbose else subprocess.DEVNULL),
        stderr=(None if args.verbose else subprocess.DEVNULL))

    results, passed, total = {}, 0, 0
    try:
        total += 1
        s1 = connect(args.port); a = read_states(s1, 5)
        ok = len(a) >= 5 and all(str(p["schema"]).startswith("navisense.state") for p in a)
        results["R1_initial_stream"] = {"pass": ok, "detail": f"{len(a)} state.v1 on first connect"}
        passed += ok; print(("PASS" if ok else "FAIL"), "R1_initial_stream")

        total += 1
        hard_close(s1); time.sleep(0.5)
        s2 = connect(args.port); b = read_states(s2, 5)
        ok = len(b) >= 5
        results["R2_reaccept_after_drop"] = {"pass": ok, "detail": f"{len(b)} packets after hard drop"}
        passed += ok; print(("PASS" if ok else "FAIL"), "R2_reaccept_after_drop")

        total += 1
        first_t = float(b[0].get("t", 9.9)) if b else 9.9
        ok = first_t < 0.5
        results["R3_fresh_run"] = {"pass": ok, "detail": f"first t after reconnect = {first_t:.3f}s"}
        passed += ok; print(("PASS" if ok else "FAIL"), "R3_fresh_run")

        total += 1
        hard_close(s2); time.sleep(0.5)
        s3 = connect(args.port); c = read_states(s3, 5)
        ok = len(c) >= 5
        results["R4_second_reconnect"] = {"pass": ok, "detail": f"{len(c)} packets on 2nd reconnect"}
        passed += ok; print(("PASS" if ok else "FAIL"), "R4_second_reconnect")
        hard_close(s3)
    except Exception as e:
        results["exception"] = {"pass": False, "detail": repr(e)}
        print("ERROR:", repr(e))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(REPORT_FILE, "w") as f:
        json.dump({"target": "canonical root python_listener.py", "date": "2026-06-14",
                   "gates_passed": passed, "gates_total": total,
                   "auto_result": "PASS" if passed == total else "PARTIAL",
                   "checks": results}, f, indent=2)
    print(f"{passed}/{total} PASS -> {REPORT_FILE}")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
