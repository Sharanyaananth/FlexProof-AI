"""Telemetry sources for the live feed.

Every source produces the same TelemetryReading, so the rest of the pipeline
(decision engine, dashboard) does not care where the data comes from.

- ClockSource: a reading for the current real time, on demand (used by the dashboard).
- SimulatedSource: a fast-forward stream of readings, e.g. one per 15 minutes (demos, tests).
- A real-data source (a replay of a public power dataset or a site's meters) can be
  added later by producing the same TelemetryReading.

Both simulated sources use the same facility model: inference load follows a
daily usage pattern plus noise; flexible compute occasionally drops when urgent
jobs take capacity back; the battery follows a daily cycle (drawn down at busy
times, recharged at quiet times).
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass
from datetime import datetime
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


class FacilityModel:
    """Synthetic facility state at a given time of day."""

    def __init__(self, config: dict, rng: random.Random):
        self.facility = config["facility"]
        self.battery = config["battery"]
        self.rng = rng

    def reading(self, *, hour: float, minute: int, source: str) -> TelemetryReading:
        crit_nominal = float(self.facility["critical_inference_mw"])
        fixed = float(self.facility["fixed_auxiliary_mw"])
        flex_nominal = float(self.facility["deferrable_compute_mw"])
        daily = 0.04 * math.sin(2 * math.pi * (hour - 9) / 24)        # busier in the day
        critical = crit_nominal * (1 + daily) + self.rng.gauss(0, 0.08)
        flexible = flex_nominal + self.rng.gauss(0, 0.05)
        if self.rng.random() < 0.05:                                   # urgent jobs reclaim capacity
            flexible -= 0.4
        flexible = max(0.0, min(flex_nominal, flexible))
        cycle = -0.10 * math.sin(2 * math.pi * (hour - 9) / 12)         # about +/-10 points twice a day
        soc = min(float(self.battery["max_soc"]),
                  max(float(self.battery["min_soc"]),
                      float(self.battery["initial_soc"]) + cycle + self.rng.gauss(0, 0.003)))
        return TelemetryReading(
            minute=minute,
            critical_load_mw=round(critical, 3),
            fixed_auxiliary_mw=round(fixed, 3),
            flexible_compute_mw=round(flexible, 3),
            battery_soc=round(soc, 4),
            grid_import_mw=round(critical + fixed + flexible, 3),
            source=source,
        )


class SimulatedSource:
    """Fast-forward stream: one reading per `interval_minutes` of simulated time."""

    def __init__(self, config: dict, *, seed: int = 20261014, interval_minutes: int = 5,
                 start_minute_of_day: int = 9 * 60):
        if interval_minutes <= 0:
            raise ValueError("interval_minutes must be positive")
        self.model = FacilityModel(config, random.Random(seed))
        self.interval = interval_minutes
        self.start = start_minute_of_day

    def readings(self) -> Iterator[TelemetryReading]:
        minute = 0
        while True:
            hour = ((self.start + minute) % 1440) / 60.0
            yield self.model.reading(hour=hour, minute=minute, source="simulated")
            minute += self.interval


class ClockSource:
    """Real-time source: each call returns the facility state at the current clock time."""

    def __init__(self, config: dict, *, seed: int | None = None, clock=datetime.now):
        self.model = FacilityModel(config, random.Random(seed))
        self.clock = clock
        self.started = clock()

    def current(self) -> tuple[datetime, TelemetryReading]:
        now = self.clock()
        hour = now.hour + now.minute / 60 + now.second / 3600
        minute = int((now - self.started).total_seconds() // 60)
        return now, self.model.reading(hour=hour, minute=minute, source="simulated (real-time clock)")