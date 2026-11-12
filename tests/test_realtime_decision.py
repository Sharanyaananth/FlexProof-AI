from dataclasses import replace
from itertools import islice
from pathlib import Path

import yaml

from realtime.decision import LiveDecisionEngine
from realtime.sources import SimulatedSource

CONFIG = yaml.safe_load((Path(__file__).resolve().parents[1] / "configs" / "fp001.yaml").read_text(encoding="utf-8"))
ENGINE = LiveDecisionEngine(CONFIG, calibration_scenarios=300)


def _reading(**changes):
    first = next(SimulatedSource(CONFIG, seed=1).readings())
    return replace(first, **changes)


def test_promise_never_exceeds_request():
    decision = ENGINE.decide(_reading())
    assert 0.0 <= decision.rafc_v_promise_mw <= CONFIG["grid_event"]["requested_reduction_mw"]


def test_lower_battery_never_raises_the_promise():
    high = ENGINE.decide(_reading(battery_soc=0.40))
    low = ENGINE.decide(_reading(battery_soc=0.26))
    assert low.rafc_v_promise_mw <= high.rafc_v_promise_mw


def test_baseline_promises_at_least_as_much_as_rafc_v():
    for soc in (0.26, 0.32, 0.40):
        d = ENGINE.decide(_reading(battery_soc=soc))
        assert d.baseline_promise_mw >= d.rafc_v_promise_mw


def test_decisions_change_over_a_day():
    readings = islice(SimulatedSource(CONFIG, seed=3, interval_minutes=60).readings(), 12)
    promises = {ENGINE.decide(r).rafc_v_promise_mw for r in readings}
    assert len(promises) > 1