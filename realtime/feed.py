"""Run the live telemetry feed in the terminal.

    python -m realtime.feed                 # one reading every 2 seconds
    python -m realtime.feed --delay 0.5 --count 24
"""
from __future__ import annotations

import argparse
import time
from itertools import islice
from pathlib import Path

import yaml

from realtime.sources import SimulatedSource

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "fp001.yaml")
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between readings")
    parser.add_argument("--count", type=int, default=0, help="number of readings (0 = run until Ctrl+C)")
    parser.add_argument("--seed", type=int, default=20261014)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.open("r", encoding="utf-8"))
    source = SimulatedSource(config, seed=args.seed)
    stream = source.readings() if args.count <= 0 else islice(source.readings(), args.count)

    print(f"{'Minute':>6} | {'Critical':>8} | {'Fixed':>6} | {'Flexible':>8} | {'Battery':>7} | {'Grid import':>11}")
    print("-" * 64)
    try:
        for r in stream:
            print(f"{r.minute:>6} | {r.critical_load_mw:>6.2f}MW | {r.fixed_auxiliary_mw:>4.1f}MW | "
                  f"{r.flexible_compute_mw:>6.2f}MW | {r.battery_soc:>6.1%} | {r.grid_import_mw:>9.2f}MW", flush=True)
            time.sleep(args.delay)
    except KeyboardInterrupt:
        print("\nFeed stopped.")


if __name__ == "__main__":
    main()