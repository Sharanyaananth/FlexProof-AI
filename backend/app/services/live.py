"""Live session for the dashboard: a real-time facility source plus the RAFC-V decision engine.

Default mode is real time: every request returns the facility state at the
current clock time and a fresh RAFC-V decision. Mode "demo" fast-forwards one
reading per 15 simulated minutes, for showing a full day quickly.
"""
from __future__ import annotations

from threading import Lock

from realtime.decision import LiveDecisionEngine
from realtime.sources import ClockSource, SimulatedSource
from simulator.engine import load_config

from backend.app.services.simulation import CONFIG_PATH


class LiveSession:
    def __init__(self) -> None:
        self._lock = Lock()
        self._config = load_config(CONFIG_PATH)
        self._engine = LiveDecisionEngine(self._config)
        self.start()

    def start(self, mode: str = "realtime", seed: int | None = None) -> dict:
        if mode not in ("realtime", "demo"):
            raise ValueError("mode must be 'realtime' or 'demo'")
        with self._lock:
            self._mode = mode
            if mode == "realtime":
                self._clock = ClockSource(self._config, seed=seed)
            else:
                self._stream = SimulatedSource(self._config, seed=20261014 if seed is None else seed,
                                               interval_minutes=15).readings()
        return {"status": "started", "mode": mode,
                "requested_mw": self._config["grid_event"]["requested_reduction_mw"]}

    def next(self) -> dict:
        with self._lock:
            if self._mode == "realtime":
                now, reading = self._clock.current()
                time = now.strftime("%H:%M:%S")
            else:
                reading = next(self._stream)
                clock = (9 * 60 + reading.minute) % 1440
                time = f"{clock // 60:02d}:{clock % 60:02d}"
            decision = self._engine.decide(reading)
        return {"time": time, "mode": self._mode,
                "reading": reading.to_dict(), "decision": decision.to_dict()}


live_session = LiveSession()