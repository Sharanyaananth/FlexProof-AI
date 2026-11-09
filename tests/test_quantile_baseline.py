from pathlib import Path

import yaml

from baselines.quantile_commitment import calibrate_quantile_commitment, scenario_tightness
from simulator.uncertainty import generate_uncertainty_scenario

ROOT = Path(__file__).resolve().parents[1]


def _config(name: str = "fp001.yaml") -> dict:
    return yaml.safe_load((ROOT / "configs" / name).read_text(encoding="utf-8"))


def test_commitment_within_request_and_reproducible():
    config = _config()
    first = calibrate_quantile_commitment(config, n_scenarios=200, seed=100_000)
    second = calibrate_quantile_commitment(config, n_scenarios=200, seed=100_000)
    assert 0.0 <= first["accepted_commitment_mw"] <= config["grid_event"]["requested_reduction_mw"]
    assert first["accepted_commitment_mw"] == second["accepted_commitment_mw"]


def test_retains_requested_coverage():
    result = calibrate_quantile_commitment(_config(), n_scenarios=200, coverage=0.9)
    assert result["retained_sample_count"] == 180
    assert result["recovery_aware"] is False


def test_lower_coverage_never_promises_less():
    config = _config()
    strict = calibrate_quantile_commitment(config, n_scenarios=300, coverage=1.0)
    loose = calibrate_quantile_commitment(config, n_scenarios=300, coverage=0.9)
    assert loose["accepted_commitment_mw"] >= strict["accepted_commitment_mw"]


def test_urgent_reclaim_scenarios_rank_as_tighter():
    config = _config()
    tight = [s for s in (generate_uncertainty_scenario(400_000 + i) for i in range(200)) if s.urgent_reclaim]
    loose = [s for s in (generate_uncertainty_scenario(400_000 + i) for i in range(200))
             if not s.urgent_reclaim and not s.battery_derated]
    assert tight and loose
    assert max(scenario_tightness(config, s) for s in tight) < min(scenario_tightness(config, s) for s in loose)