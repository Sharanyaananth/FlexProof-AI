"""Scenario-filtered commitment baseline (see docs/research_notes.md).

Generates uncertainty scenarios, ranks them by how tight they are, discards the
tightest (1 - coverage) share, and promises the largest commitment that succeeds
in every retained scenario. It checks only event delivery, not post-event
recovery, and reports in-sample coverage rather than a statistical confidence bound.
"""
from __future__ import annotations

from math import ceil, isfinite
from typing import Any

from optimization.commitment import _scenario_passes
from simulator.uncertainty import UncertaintyAssumptions, generate_uncertainty_scenario


def scenario_tightness(config: dict[str, Any], disturbance) -> float:
    """Deliverable reduction (MW) in a scenario. Lower means tighter."""
    facility = config["facility"]
    battery = config["battery"]
    duration_h = float(config["grid_event"]["duration_minutes"]) / 60.0
    flexible = max(0.0, float(facility["deferrable_compute_mw"]) - disturbance.urgent_reclaim_mw)
    soc = float(battery["initial_soc"]) + disturbance.initial_soc_error
    energy = max(0.0, (soc - float(battery["min_soc"])) * float(battery["capacity_mwh"])
                 * float(battery["discharge_efficiency"]))
    discharge = min(float(battery["max_discharge_mw"]) * disturbance.battery_discharge_scale,
                    energy / duration_h)
    return flexible + discharge - disturbance.meter_noise_mw


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
    ranked = sorted(scenarios, key=lambda s: scenario_tightness(config, s), reverse=True)
    retained = ranked[:max(1, int(round(coverage * n_scenarios)))]

    evidence = []
    for candidate in candidates:
        passed = sum(_scenario_passes(config, candidate, s, a, recovery_aware=False,
                                      meter_margin_mw=meter_margin_mw,
                                      observed_noise=observed_noise) for s in retained)
        evidence.append({"commitment_mw": candidate, "successes": passed,
                         "sample_count": len(retained),
                         "estimated_reliability": passed / len(retained),
                         "simultaneous_lower_bound": None})
    accepted = next((row for row in evidence if row["successes"] == len(retained)), None)
    return {"status": "confirmed" if accepted else "unconfirmed",
            "accepted_commitment_mw": accepted["commitment_mw"] if accepted else 0.0,
            "coverage": coverage,
            "calibration_sample_count": n_scenarios,
            "retained_sample_count": len(retained),
            "seed_start": seed,
            "selected_evidence": accepted,
            "candidate_evidence": evidence,
            "method": "discard tightest scenarios; largest commitment feasible in all retained",
            "recovery_aware": False,
            "limitations": ["Coverage is in-sample; no statistical confidence bound is computed.",
                            "Post-event recovery under the grid ceiling is not checked when committing."]}