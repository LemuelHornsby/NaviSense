"""Print a tabular summary of recent NaviSense bridge runs.

Reads ``<log_dir>/runs.csv`` (the project-level index appended by
:class:`python.run_logger.RunLogger.finalise`) and prints the most
recent N rows in a terminal-friendly table. No external dependencies.

Usage from the NAVISENSE root:
    python python/list_runs.py
    python python/list_runs.py --log-dir logs --tail 20
    python python/list_runs.py --controller turning_circle
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import List


def _read_index(log_dir: str) -> List[dict]:
    path = os.path.join(log_dir, "runs.csv")
    if not os.path.exists(path):
        print(f"[list_runs] no index found at {path}", file=sys.stderr)
        print("[list_runs] (logs are only created when you launch with --log-dir)", file=sys.stderr)
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _print_table(rows: List[dict]) -> None:
    if not rows:
        print("(no runs)")
        return

    cols = [
        ("started_local", "started"),
        ("duration_s", "dur (s)"),
        ("run_id", "run id"),
        ("plant", "plant"),
        ("controller", "controller"),
        ("state_rows", "ticks"),
        ("modes", "phases"),
        ("run_dir", "dir"),
    ]
    widths = {key: len(label) for key, label in cols}
    for r in rows:
        for key, _ in cols:
            v = str(r.get(key, ""))
            if len(v) > widths[key]:
                widths[key] = min(len(v), 60)

    sep = "  "

    def line(items):
        return sep.join(items)

    print(line(label.ljust(widths[key]) for key, label in cols))
    print(line("-" * widths[key] for key, _ in cols))
    for r in rows:
        print(line(
            (str(r.get(key, ""))[:widths[key]]).ljust(widths[key]) for key, _ in cols
        ))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log-dir", default="logs", help="Root log folder (default: logs)")
    p.add_argument("--tail", type=int, default=10, help="Show the last N runs (default: 10)")
    p.add_argument("--controller", default=None, help="Filter to a single controller kind (e.g. turning_circle).")
    p.add_argument("--plant", default=None, help="Filter by plant kind (mmg, stub).")
    args = p.parse_args()

    rows = _read_index(args.log_dir)
    if args.controller:
        rows = [r for r in rows if r.get("controller") == args.controller]
    if args.plant:
        rows = [r for r in rows if r.get("plant") == args.plant]

    rows = rows[-args.tail:] if args.tail > 0 else rows
    _print_table(rows)


if __name__ == "__main__":
    main()
