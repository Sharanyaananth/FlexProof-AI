"""Scenario-filtered commitment baseline (see docs/research_notes.md).

Generates uncertainty scenarios and promises the largest commitment that succeeds
in at least `coverage` (default 90%) of them, i.e. the worst 10% of scenarios are
ignored. It checks only event delivery, not post-event recovery, and reports
in-sample coverage rather than a statistical confidence bound.
"""
from __future__ import annotations

from math import ceil, isfinite
from typing import Any

from optimization.commitment import _scenario_passes
from simulator.uncertainty import UncertaintyAssumptions, generate_uncertainty_scenario


def calibrate_quantile_commitment(config: dict[str, Any], *, n_scenarios: int = 1000,
                                  seed: int = 100_000, step_mw: float = 0.1,
                                  coverage: float = 0.90,
                                  assumptions: UncertaintyAssumptions | None = None,
                                  meter_margin_mw: float | None = None,
                                  observed_noise: bool = False) -> dict:
    if n_scenarios <= 0:
        raise ValueError("n_scenarios must be positive")
    if not 0 < coverage <= 1:
        raise ValueError("coverage must be in (0, 1]")
    if not isfinite(step_mw) or step_mw <= 0:
        raise ValueError("step_mw must be finite and positive")
    a = assumptions or UncertaintyAssumptions()
    requested = float(config["grid_event"]["requested_reduction_mw"])
    candidates = [max(0.0, requested - i * step_mw) for i in range(ceil(requested / step_mw) + 1)]
    scenarios = [generate_uncertainty_scenario(seed + i, a) for i in range(n_scenarios)]
    required = ceil(coverage * n_scenarios - 1e-9)

    evidence = []
    for candidate in candidates:
        passed = sum(_scenario_passes(config, candidate, s, a, recovery_aware=False,
                                      meter_margin_mw=meter_margin_mw,
                                      observed_noise=observed_noise) for s in scenarios)
        evidence.append({"commitment_mw": candidate, "successes": passed,
                         "sample_count": n_scenarios,
                         "estimated_reliability": passed / n_scenarios,
                         "simultaneous_lower_bound": None})
    accepted = next((row for row in evidence if row["successes"] >= required), None)
    return {"status": "confirmed" if accepted else "unconfirmed",
            "accepted_commitment_mw": accepted["commitment_mw"] if accepted else 0.0,
            "coverage": coverage,
            "calibration_sample_count": n_scenarios,
            "required_successes": required,
            "seed_start": seed,
            "selected_evidence": accepted,
            "candidate_evidence": evidence,
            "method": "largest commitment that succeeds in at least the coverage share of scenarios",
            "recovery_aware": False,
            "limitations": ["Coverage is in-sample; no statistical confidence bound is computed.",
                            "Post-event recovery under the grid ceiling is not checked when committing."]}