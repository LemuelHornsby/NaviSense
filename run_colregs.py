#!/usr/bin/env python3
"""run_colregs -- ONE terminal command per COLREGS scenario (WP-20260709C).

The scenario is chosen in code, the target ship defaults to marine_rescue_boat,
and the run verifies itself when it ends. You never touch the editor scripts
for a normal run -- just make sure (one-time) the pawn's TrafficActors[0] is
the marine_rescue_boat (see Documents/NaviSense_COLREGS_Encounter_Recipe.md).

Usage (from the workspace root -- pick ONE scenario flag):
  python run_colregs.py --head-on               # Rule 14
  python run_colregs.py --crossing-giveway      # Rule 15
  python run_colregs.py --crossing-standon      # Rule 17
  python run_colregs.py --overtaking            # Rule 13

Then press PLAY in the already-open editor. Stop PIE when the encounter is
done -- the listener exits (--once) and the run is AUTO-VERIFIED
(python/verify_colregs.py: health + verdict + identity, per-scenario result
file). Options:
  --ship LABEL     swap the target ship for this run (--target-name passthrough)
  --no-verify      skip the auto-verification
  --selftest       no Unreal: drive the run with the bundled headless client
  --dry-run        print the listener command and exit (CI / sanity)
  --list           list the scenario flags and exit
"""
from __future__ import annotations
import argparse, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "python"
LISTENER = os.path.join(ROOT, "python_listener.py")
CLIENT = os.path.join(ROOT, "Development", "bridge_harness", "ue5_client_sim.py")
VERIFY = os.path.join(ROOT, "python", "verify_colregs.py")

FLAGS = {  # CLI flag dest -> scenario
    "head_on": "colregs_head_on",
    "crossing_giveway": "colregs_crossing_giveway",
    "crossing_standon": "colregs_crossing_standon",
    "overtaking": "colregs_overtaking",
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog="Pick exactly one scenario flag.")
    for dest in FLAGS:
        ap.add_argument("--" + dest.replace("_", "-"), dest=dest,
                        action="store_true", help=FLAGS[dest])
    ap.add_argument("--ship", default=None, metavar="LABEL",
                    help="swap the target ship for this run "
                         "(default: the preset's marine_rescue_boat)")
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--selftest", action="store_true",
                    help="headless: drive the run with the bundled client (no Unreal)")
    ap.add_argument("--seconds", type=float, default=25.0,
                    help="--selftest run length (default 25)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5005,
                    help="wire port; MUST match the UE pawn (NaviSenseBridgeComponent.Port = 5005). "
                         "KI-039: the old default 5502 left the bridge RECONNECTING forever on live runs.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)

    if args.list:
        for dest, sc in FLAGS.items():
            print(f"  --{dest.replace('_', '-'):<20} -> {sc}")
        return 0

    chosen = [dest for dest in FLAGS if getattr(args, dest)]
    if len(chosen) != 1:
        ap.error(f"pick exactly ONE scenario flag (got {len(chosen)}): "
                 + " ".join("--" + d.replace("_", "-") for d in FLAGS))
    scenario = FLAGS[chosen[0]]

    # Selftest runs are isolated in git-ignored logs/_selftest (23-Jun rule: a
    # rehearsal never shadows a real run) and accelerated 25x like run_demo;
    # real PIE runs stay real-time in logs/.
    log_dir = os.path.join(ROOT, "logs", "_selftest") if args.selftest \
        else os.path.join(ROOT, "logs")
    cmd = [PY, "-u", LISTENER, "--target", "unreal", "--scenario", scenario,
           "--host", args.host, "--port", str(args.port), "--once", "-v",
           "--log-dir", log_dir]
    if args.selftest:
        cmd += ["--time-scale", "25", "--run-id", f"colregs-{scenario}-selftest"]
    if args.ship:
        cmd += ["--target-name", args.ship]
    printable = " ".join(cmd[2:])
    if args.dry_run:
        print("[run_colregs] DRY RUN -- would launch:\n  python " + printable)
        return 0

    print("=" * 64)
    print(f"[run_colregs] scenario : {scenario}")
    print(f"[run_colregs] target   : {args.ship or 'marine_rescue_boat (default)'}")
    print(f"[run_colregs] listener : python {printable}")
    if not args.selftest:
        print("[run_colregs] >>> press PLAY in the editor; stop PIE to end the run")
    print("=" * 64)

    import glob as _glob
    pre_dirs = set(_glob.glob(os.path.join(log_dir, "*_*")))
    client = None
    try:
        if args.selftest:
            listener = subprocess.Popen(cmd, cwd=ROOT)
            time.sleep(2.5)                      # let it bind
            if listener.poll() is not None:
                print("[run_colregs] listener exited early -- see output above")
                return 1
            client = subprocess.Popen(
                [PY, "-u", CLIENT, "--host", args.host, "--port", str(args.port),
                 "--seconds", f"{args.seconds:g}"], cwd=ROOT,
                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            rc = listener.wait()
        else:
            rc = subprocess.call(cmd, cwd=ROOT)   # foreground, streams -v output
    except KeyboardInterrupt:
        print("\n[run_colregs] interrupted -- verifying whatever completed...")
        rc = 0
    finally:
        if client is not None and client.poll() is None:
            client.terminate()

    if args.no_verify:
        print(f"[run_colregs] listener rc={rc}; verification skipped (--no-verify)")
        return 0 if rc == 0 else 1

    print(f"[run_colregs] run ended (rc={rc}) -- verifying...")
    new_dirs = sorted(set(_glob.glob(os.path.join(log_dir, "*_*"))) - pre_dirs,
                      key=os.path.getmtime)
    if new_dirs:
        vcmd = [PY, VERIFY, "--run-dir", new_dirs[-1]]     # verify THIS run
    else:
        vcmd = [PY, VERIFY, "--latest", "--scenario", scenario]
    v = subprocess.call(vcmd, cwd=ROOT)
    if v == 0:
        print(f"[run_colregs] {scenario}: VERIFIED (see "
              f"Saved/NaviSense_Reports/{scenario}_result.json; "
              f"all four: python python/verify_colregs.py --matrix)")
    else:
        print(f"[run_colregs] {scenario}: verification FAILED -- see gates above")
    return v


if __name__ == "__main__":
    sys.exit(main())
