"""Telemetry sources for the live feed.

Every source yields the same TelemetryReading, so the rest of the pipeline
(decision engine, dashboard) does not care where the data comes from.

- SimulatedSource: realistic synthetic AI datacentre readings (available now).
- A real-data source (e.g. a replay of a public power dataset or a site's meters)
  can be added later by implementing the same `readings()` method.
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass
from typing import Iterator, Protocol


@dataclass(frozen=True)
class TelemetryReading:
    minute: int                    # minutes since the feed started
    critical_load_mw: float        # AI inference and other load that cannot be paused
    fixed_auxiliary_mw: float      # cooling, lighting and other fixed facility load
    flexible_compute_mw: float     # compute that can be paused (training, batch jobs)
    battery_soc: float             # battery state of charge, 0 to 1
    grid_import_mw: float          # total power drawn from the grid
    source: str                    # where the reading came from

    def to_dict(self) -> dict:
        return asdict(self)


class TelemetrySource(Protocol):
    def readings(self) -> Iterator[TelemetryReading]: ...


class SimulatedSource:
    """Synthetic readings around the FP-001 facility, with daily and random variation.

    Inference load follows a daily usage pattern plus noise; flexible compute
    occasionally drops when urgent jobs take capacity back.
    """

    def __init__(self, config: dict, *, seed: int = 20261014, interval_minutes: int = 5,
                 start_minute_of_day: int = 9 * 60):
        if interval_minutes <= 0:
            raise ValueError("interval_minutes must be positive")
        self.facility = config["facility"]
        self.battery = config["battery"]
        self.interval = interval_minutes
        self.start = start_minute_of_day
        self.rng = random.Random(seed)

    def readings(self) -> Iterator[TelemetryReading]:
        minute = 0
        soc = float(self.battery["initial_soc"])
        crit_nominal = float(self.facility["critical_inference_mw"])
        fixed = float(self.facility["fixed_auxiliary_mw"])
        flex_nominal = float(self.facility["deferrable_compute_mw"])
        while True:
            hour = ((self.start + minute) % 1440) / 60.0
            daily = 0.04 * math.sin(2 * math.pi * (hour - 9) / 24)   # busier in the day
            critical = crit_nominal * (1 + daily) + self.rng.gauss(0, 0.08)
            flexible = flex_nominal + self.rng.gauss(0, 0.05)
            if self.rng.random() < 0.05:                              # urgent jobs reclaim capacity
                flexible -= 0.4
            flexible = max(0.0, min(flex_nominal, flexible))
            soc = min(float(self.battery["max_soc"]),
                      max(float(self.battery["min_soc"]), soc + self.rng.gauss(0, 0.001)))
            yield TelemetryReading(
                minute=minute,
                critical_load_mw=round(critical, 3),
                fixed_auxiliary_mw=round(fixed, 3),
                flexible_compute_mw=round(flexible, 3),
                battery_soc=round(soc, 4),
                grid_import_mw=round(critical + fixed + flexible, 3),
                source="simulated",
            )
            minute += self.interval