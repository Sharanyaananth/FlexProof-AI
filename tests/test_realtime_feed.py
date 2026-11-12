from itertools import islice
from pathlib import Path

import yaml

from realtime.sources import SimulatedSource

CONFIG = yaml.safe_load((Path(__file__).resolve().parents[1] / "configs" / "fp001.yaml").read_text(encoding="utf-8"))


def _take(n: int, seed: int = 1):
    return list(islice(SimulatedSource(CONFIG, seed=seed).readings(), n))


def test_readings_are_reproducible_and_spaced():
    first, second = _take(20), _take(20)
    assert first == second
    assert [r.minute for r in first[:3]] == [0, 5, 10]


def test_readings_stay_within_physical_limits():
    for r in _take(500):
        assert 0.0 <= r.flexible_compute_mw <= CONFIG["facility"]["deferrable_compute_mw"]
        assert CONFIG["battery"]["min_soc"] <= r.battery_soc <= CONFIG["battery"]["max_soc"]
        total = r.critical_load_mw + r.fixed_auxiliary_mw + r.flexible_compute_mw
        assert abs(r.grid_import_mw - total) < 0.01


def test_load_varies_realistically():
    critical = [r.critical_load_mw for r in _take(288)]          # one day at 5-minute steps
    assert max(critical) - min(critical) > 0.3
    assert 11.0 < sum(critical) / len(critical) < 13.0
    


def test_clock_source_reports_the_given_time():
    from datetime import datetime
    from realtime.sources import ClockSource
    fixed = datetime(2026, 11, 13, 14, 30, 0)
    now, reading = ClockSource(CONFIG, seed=1, clock=lambda: fixed).current()
    assert now == fixed
    assert CONFIG["battery"]["min_soc"] <= reading.battery_soc <= CONFIG["battery"]["max_soc"]