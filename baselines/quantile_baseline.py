"""Scenario-filtered baseline controller for the PoC (see docs/research_notes.md)."""
from baselines.deterministic_mpc import solve_deterministic_dispatch
from baselines.quantile_commitment import calibrate_quantile_commitment


def run_quantile_baseline(config: dict, *, calibration_scenarios: int = 1000,
                          calibration_seed: int = 100_000, commitment_step_mw: float = 0.1,
                          coverage: float = 0.90) -> dict:
    calibration = calibrate_quantile_commitment(config, n_scenarios=calibration_scenarios,
        seed=calibration_seed, step_mw=commitment_step_mw, coverage=coverage)
    accepted = calibration["accepted_commitment_mw"]
    result = solve_deterministic_dispatch(config, accepted_commitment_mw=accepted)
    result["controller"] = "quantile_baseline"
    result["controller_version"] = "quantile-baseline-0.1.0"
    selected = calibration["selected_evidence"]
    result["reliability"] = {"status": calibration["status"],
        "estimate": selected["estimated_reliability"] if selected else None,
        "confidence_lower_bound": None,
        "confidence_level": None,
        "sample_count": calibration["calibration_sample_count"],
        "evidence_split": "calibration (worst 10% of scenarios ignored)",
        "target": coverage}
    result["commitment_calibration"] = calibration
    result["commitment_basis"] = "scenario-filtered commitment; no statistical bound; no recovery check"
    return result