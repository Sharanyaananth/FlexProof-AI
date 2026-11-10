from pathlib import Path

import yaml

from baselines.quantile_commitment import calibrate_quantile_commitment

ROOT = Path(__file__).resolve().parents[1]


def _config(name: str = "fp001.yaml") -> dict:
    return yaml.safe_load((ROOT / "configs" / name).read_text(encoding="utf-8"))


def test_commitment_within_request_and_reproducible():
    config = _config()
    first = calibrate_quantile_commitment(config, n_scenarios=200, seed=100_000)
    second = calibrate_quantile_commitment(config, n_scenarios=200, seed=100_000)
    assert 0.0 <= first["accepted_commitment_mw"] <= config["grid_event"]["requested_reduction_mw"]
    assert first["accepted_commitment_mw"] == second["accepted_commitment_mw"]


def test_accepted_commitment_meets_coverage():
    result = calibrate_quantile_commitment(_config(), n_scenarios=200, coverage=0.9)
    assert result["required_successes"] == 180
    assert result["selected_evidence"]["successes"] >= 180
    assert result["recovery_aware"] is False


def test_lower_coverage_never_promises_less():
    config = _config()
    strict = calibrate_quantile_commitment(config, n_scenarios=300, coverage=0.99)
    loose = calibrate_quantile_commitment(config, n_scenarios=300, coverage=0.9)
    assert loose["accepted_commitment_mw"] >= strict["accepted_commitment_mw"]


def test_ignores_recovery_limit():
    normal = calibrate_quantile_commitment(_config(), n_scenarios=300)
    tight = calibrate_quantile_commitment(_config("fp001_recovery_stress_18p0.yaml"), n_scenarios=300)
    assert tight["accepted_commitment_mw"] == normal["accepted_commitment_mw"]