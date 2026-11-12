"""Live feed + decision engine: watch RAFC-V re-decide the safe promise as data arrives.

    python -m realtime.live                       # one reading every 2 seconds
    python -m realtime.live --delay 0.5 --count 48
"""
from __future__ import annotations

import argparse
import time
from itertools import islice
from pathlib import Path

import yaml

from realtime.decision import LiveDecisionEngine
from realtime.sources import SimulatedSource

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "fp001.yaml")
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between readings")
    parser.add_argument("--count", type=int, default=0, help="number of readings (0 = run until Ctrl+C)")
    parser.add_argument("--interval", type=int, default=15, help="minutes between readings")
    parser.add_argument("--seed", type=int, default=20261014)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.open("r", encoding="utf-8"))
    source = SimulatedSource(config, seed=args.seed, interval_minutes=args.interval)
    engine = LiveDecisionEngine(config)
    stream = source.readings() if args.count <= 0 else islice(source.readings(), args.count)

    print(f"Grid may ask for up to {config['grid_event']['requested_reduction_mw']} MW. "
          "RAFC-V re-decides the safe promise with every reading.\n")
    print(f"{'Time':>5} | {'Battery':>7} | {'Flexible':>8} | {'RAFC-V promise':>14} | {'Proven':>7} | {'Baseline':>8}")
    print("-" * 66)
    previous = None
    try:
        for reading in stream:
            d = engine.decide(reading)
            clock = (9 * 60 + d.minute) % 1440
            change = "" if previous is None or previous == d.rafc_v_promise_mw else \
                (" (up)" if d.rafc_v_promise_mw > previous else " (down)")
            proven = f"{d.rafc_v_proven_reliability:.1%}" if d.rafc_v_proven_reliability is not None else "  n/a"
            print(f"{clock // 60:02d}:{clock % 60:02d} | {d.battery_soc:>6.1%} | {d.flexible_compute_mw:>6.2f}MW | "
                  f"{d.rafc_v_promise_mw:>9.1f} MW{change:<7}| {proven:>7} | {d.baseline_promise_mw:>5.1f} MW", flush=True)
            previous = d.rafc_v_promise_mw
            time.sleep(args.delay)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()