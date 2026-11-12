"""Live decision engine: turns each telemetry reading into a fresh, safe promise.

For every reading, the facility's current state (battery charge, available
flexible compute, critical load) is written into the scenario and RAFC-V
recalculates the largest promise it can prove at the reliability target,
including safe recovery. The scenario-filtered baseline is computed alongside
for comparison.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass

from baselines.quantile_commitment import calibrate_quantile_commitment
from optimization.commitment import calibrate_commitment
from realtime.sources import TelemetryReading


@dataclass(frozen=True)
class LiveDecision:
    minute: int
    battery_soc: float
    flexible_compute_mw: float
    grid_import_mw: float
    rafc_v_promise_mw: float
    rafc_v_proven_reliability: float | None
    baseline_promise_mw: float
    requested_mw: float

    def to_dict(self) -> dict:
        return asdict(self)


class LiveDecisionEngine:
    def __init__(self, config: dict, *, calibration_scenarios: int = 1000,
                 calibration_seed: int = 100_000, step_mw: float = 0.1):
        self.base_config = config
        self.n = calibration_scenarios
        self.seed = calibration_seed
        self.step = step_mw

    def current_config(self, reading: TelemetryReading) -> dict:
        """Scenario reflecting the facility as it is right now."""
        config = copy.deepcopy(self.base_config)
        battery = config["battery"]
        battery["initial_soc"] = min(float(battery["max_soc"]),
                                     max(float(battery["min_soc"]), reading.battery_soc))
        config["facility"]["deferrable_compute_mw"] = max(0.0, reading.flexible_compute_mw)
        return config

    def decide(self, reading: TelemetryReading) -> LiveDecision:
        config = self.current_config(reading)
        common = dict(n_scenarios=self.n, seed=self.seed, step_mw=self.step,
                      meter_margin_mw=0.0, observed_noise=True)
        rafc = calibrate_commitment(config, recovery_aware=True, **common)
        baseline = calibrate_quantile_commitment(config, **common)
        evidence = rafc["selected_evidence"]
        return LiveDecision(
            minute=reading.minute,
            battery_soc=reading.battery_soc,
            flexible_compute_mw=reading.flexible_compute_mw,
            grid_import_mw=reading.grid_import_mw,
            rafc_v_promise_mw=round(float(rafc["accepted_commitment_mw"]), 2),
            rafc_v_proven_reliability=(round(evidence["simultaneous_lower_bound"], 4)
                                       if evidence else None),
            baseline_promise_mw=round(float(baseline["accepted_commitment_mw"]), 2),
            requested_mw=float(config["grid_event"]["requested_reduction_mw"]),
        )