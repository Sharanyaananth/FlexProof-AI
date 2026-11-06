"""Live, step-by-step demo of how RAFC-V decides its promise and keeps it.

Run from the project folder with the venv active:

    python -m evaluation.live_demo                      # tight-recovery case (best demo)
    python -m evaluation.live_demo --config configs/fp001.yaml   # normal 20 MW case
    python -m evaluation.live_demo --seed 400022 --no-pause      # another surprise, no Enter prompts

Act 1: both controllers search for the largest MW they can safely promise.
Act 2: one random "bad day" is generated, and both controllers run it live,
       re-planning every 5 minutes, while a chart draws in real time.
Act 3: RecoveryGuard checks the after-event recovery.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import matplotlib.pyplot as plt
import yaml

from optimization.commitment import calibrate_commitment
from optimization.dispatch import solve_rolling_event_dispatch
from optimization.recovery import plan_recovery
from simulator.uncertainty import UncertaintyAssumptions, generate_uncertainty_scenario
from statistics import NormalDist

ROOT = Path(__file__).resolve().parents[1]
MPC, RAFC = "Risk-aware MPC", "RAFC-V (ours)"
COLORS = {MPC: "#d8843a", RAFC: "#2e8b6e"}


def say(text: str = "", delay: float = 0.0) -> None:
    print(text, flush=True)
    if delay:
        time.sleep(delay)


def pause(enabled: bool, message: str = "Press Enter to continue...") -> None:
    if enabled:
        input(f"\n  >> {message}")
    say()


def banner(title: str) -> None:
    say("\n" + "=" * 72)
    say(f"  {title}")
    say("=" * 72)


def act1_promise_search(config: dict, n: int, speed: float) -> dict[str, float]:
    banner("ACT 1: How much can we safely promise the grid?")
    req = config["grid_event"]["requested_reduction_mw"]
    target = config["grid_event"]["target_complete_event_success_probability"]
    ceiling = config["recovery"]["grid_import_ceiling_mw"]
    say(f"  The grid asks for {req} MW less, for {config['grid_event']['duration_minutes']} minutes.")
    say(f"  After the event, total grid import must stay under {ceiling} MW during recovery.")
    say(f"  Each candidate promise is tested against {n:,} simulated futures.")
    say(f"  A promise is accepted only if we can PROVE >= {target:.0%} success (Wilson lower bound).\n", 0.5)

    common = dict(n_scenarios=n, seed=100_000, step_mw=0.1, meter_margin_mw=0.0, observed_noise=True)
    mpc = calibrate_commitment(config, recovery_aware=False, **common)
    rafc = calibrate_commitment(config, recovery_aware=True, **common)

    say(f"  {'Promise':>8} | {'MPC: checks the event only':^28} | {'RAFC-V: event + recovery':^28}")
    say(f"  {'':>8} | {'success   proof    verdict':^28} | {'success   proof    verdict':^28}")
    say("  " + "-" * 70)
    done = {MPC: False, RAFC: False}
    for m_row, r_row in zip(mpc["candidate_evidence"], rafc["candidate_evidence"]):
        cells = []
        for name, row in ((MPC, m_row), (RAFC, r_row)):
            ok = row["simultaneous_lower_bound"] >= target
            if done[name]:
                verdict = ""
            elif ok:
                verdict = "<< CHOSEN"
                done[name] = True
            else:
                verdict = "reject"
            cells.append(f"{row['estimated_reliability']:6.1%}   {row['simultaneous_lower_bound']:6.1%}   {verdict:<9}")
        say(f"  {m_row['commitment_mw']:>6.1f}MW | {cells[0]:<28} | {cells[1]:<28}", speed)
        if all(done.values()):
            break

    promises = {MPC: float(mpc["accepted_commitment_mw"]), RAFC: float(rafc["accepted_commitment_mw"])}
    say(f"\n  MPC promises    {promises[MPC]:.1f} MW  (it ignored recovery)")
    say(f"  RAFC-V promises {promises[RAFC]:.1f} MW  (it checked recovery before promising)")
    return promises


def act2_live_event(config: dict, promises: dict[str, float], seed: int, speed: float, show_plot: bool):
    banner("ACT 2: A real 'bad day' - both controllers run it live")
    a = UncertaintyAssumptions()
    d = generate_uncertainty_scenario(seed, a)
    say(f"  Random scenario #{seed} (neither controller has seen it before):")
    say(f"    - battery starts {d.initial_soc_error*100:+.2f}% off its expected charge")
    say(f"    - critical AI load drifts by {d.critical_power_delta_mw:+.3f} MW")
    say(f"    - urgent jobs reclaim flexible compute: {'YES, ' + str(d.urgent_reclaim_mw) + ' MW' if d.urgent_reclaim else 'no'}")
    say(f"    - battery derated: {'YES, ' + format(1 - d.battery_discharge_scale, '.0%') if d.battery_derated else 'no'}")
    say(f"    - meter error: {d.meter_noise_mw:+.3f} MW", 0.5)

    steps = config["grid_event"]["duration_minutes"] // config["grid_event"]["interval_minutes"]
    observed = {
        "available_flexible_compute_mw": max(0.0, config["facility"]["deferrable_compute_mw"] - d.urgent_reclaim_mw),
        "battery_discharge_scale": d.battery_discharge_scale,
        "critical_power_delta_mw": d.critical_power_delta_mw,
        "meter_noise_mw": d.meter_noise_mw,
    }
    obs = [dict(observed) for _ in range(steps)]
    obs[0]["initial_soc_error"] = d.initial_soc_error
    margin = NormalDist().inv_cdf(0.99) * a.meter_noise_std_mw

    say("\n  Solving: each controller re-optimizes every 5 minutes (Pyomo + HiGHS)...")
    runs = {}
    for name, mw in promises.items():
        started = time.perf_counter()
        runs[name] = solve_rolling_event_dispatch(config, mw, observations=obs, delivery_margin_mw=margin,
                                                  forecast="persistence", soft_margin=True)
        tel = runs[name]["telemetry"]
        say(f"    {name}: {tel.get('optimizer_calls', 0)} optimizations in {time.perf_counter()-started:.2f}s")

    fig = axes = None
    if show_plot:
        plt.ion()
        fig, axes = plt.subplots(1, 2, figsize=(13, 5))
        fig.suptitle(f"Live event, scenario #{seed}", fontsize=13)

    say(f"\n  {'Minute':>7} | {'MPC  promise ' + format(promises[MPC], '.1f') + ' MW':^24} | {'RAFC-V  promise ' + format(promises[RAFC], '.1f') + ' MW':^24}")
    say(f"  {'':>7} | {'paused  battery  result':^24} | {'paused  battery  result':^24}")
    say("  " + "-" * 62)
    rows = {n: runs[n]["telemetry"]["event_time_series"] for n in runs}
    history = {n: {"t": [], "mw": [], "soc": []} for n in runs}
    for k in range(steps):
        cells = []
        for name in (MPC, RAFC):
            if k >= len(rows[name]):
                cells.append(f"{'(stopped)':^24}")
                continue
            r = rows[name][k]
            ok = r["success"]
            res = f"{r['delivered_reduction_mw']:.2f} {'OK' if ok else 'MISS'}"
            cells.append(f"{r['flexible_compute_curtailment_mw']:5.2f}   {max(0.0, r['battery_discharge_mw']):5.2f}   {res:<9}")
            h = history[name]
            h["t"].append(r["end_minute"]); h["mw"].append(r["delivered_reduction_mw"]); h["soc"].append(r["battery_soc_end"] * 100)
        say(f"  {rows[RAFC][k]['end_minute'] if k < len(rows[RAFC]) else (k+1)*5:>5}min | {cells[0]} | {cells[1]}")
        if show_plot:
            draw(axes, history, promises, config, steps)
            plt.pause(max(0.05, speed))
        else:
            time.sleep(speed)

    say()
    for name in (MPC, RAFC):
        miss = sum(not r["success"] for r in rows[name])
        verdict = "KEPT its promise in every interval" if miss == 0 else f"MISSED its promise in {miss} of {steps} intervals"
        say(f"  {name}: {verdict}")
    return runs, fig


def draw(axes, history, promises, config, steps):
    ax1, ax2 = axes
    ax1.clear(); ax2.clear()
    end = config["grid_event"]["duration_minutes"]
    for name, h in history.items():
        ax1.step(h["t"], h["mw"], where="pre", color=COLORS[name], linewidth=2.5, label=f"{name} delivered")
        ax1.axhline(promises[name], color=COLORS[name], linestyle="--", linewidth=1, label=f"{name} promise {promises[name]:.1f} MW")
        ax2.plot(h["t"], h["soc"], color=COLORS[name], linewidth=2.5, marker="o", markersize=3, label=name)
    ax1.set(xlim=(0, end), ylim=(0, 6), xlabel="Minute of event", ylabel="Power cut delivered (MW)",
            title="Did we deliver what we promised?")
    ax1.legend(fontsize=8, loc="lower left"); ax1.grid(alpha=0.25)
    ax2.axhline(config["battery"]["min_soc"] * 100, color="#b03a3a", linestyle="--", linewidth=1, label="Protected reserve")
    ax2.set(xlim=(0, end), ylim=(15, 40), xlabel="Minute of event", ylabel="Battery charge (%)",
            title="Battery state of charge")
    ax2.legend(fontsize=8, loc="upper right"); ax2.grid(alpha=0.25)


def act3_recovery(config: dict, runs: dict) -> None:
    banner("ACT 3: RecoveryGuard - can we recover without breaking the grid limit?")
    ceiling = config["recovery"]["grid_import_ceiling_mw"]
    for name, run in runs.items():
        tel = run["telemetry"]
        rec = plan_recovery(config, backlog_mwh=float(tel["final_workload_backlog_mwh"]),
                            current_soc=float(tel["final_battery_soc"]))
        rt = rec.get("telemetry", {})
        if rec["status"] == "completed":
            say(f"  {name}: catch up {tel['final_workload_backlog_mwh']:.2f} MWh of paused work, recharge from "
                f"{tel['final_battery_soc']:.1%} -> peak grid import {rt.get('max_grid_import_mw', 0):.2f} MW "
                f"(limit {ceiling} MW) -> OK")
        else:
            say(f"  {name}: recovery NOT possible -> {rec.get('infeasibility_reason')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "fp001_recovery_stress_18p0.yaml")
    parser.add_argument("--seed", type=int, default=400037, help="which random 'bad day' to run")
    parser.add_argument("--scenarios", type=int, default=1000, help="calibration futures per candidate")
    parser.add_argument("--speed", type=float, default=0.6, help="seconds between printed steps")
    parser.add_argument("--no-pause", action="store_true", help="do not wait for Enter between acts")
    parser.add_argument("--no-plot", action="store_true", help="text only, no live chart")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.open("r", encoding="utf-8"))
    interactive = not args.no_pause

    say(f"\nFlexProof AI live demo  |  scenario {config['scenario_id']}")
    promises = act1_promise_search(config, args.scenarios, args.speed / 2)
    pause(interactive)
    runs, fig = act2_live_event(config, promises, args.seed, args.speed, not args.no_plot)
    pause(interactive)
    act3_recovery(config, runs)
    if promises[RAFC] < promises[MPC]:
        say("\n  Takeaway: RAFC-V promises less, but it is a promise it can keep.\n")
    else:
        say("\n  Takeaway: recovery was not the bottleneck here, so both made the same promise.")
        say("  Run the default tight-recovery config to see where RAFC-V differs.\n")
    if fig is not None:
        out = ROOT / "results" / "comparison" / f"live_event_{args.seed}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=150)
        say(f"  Chart saved to {out}")
        plt.ioff()
        plt.show()


if __name__ == "__main__":
    main()