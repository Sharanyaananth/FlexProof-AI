"""Draw comparison charts for RAFC-V, the scenario-filtered baseline and the other controllers.

Run from the project folder with the venv active, after running the closed-loop comparisons:

    python -m evaluation.plot_comparison
    python -m evaluation.plot_comparison --show      # also open the charts in a window

By default it reads:
    results/baseline-normal/closed_loop_comparison.json   (normal 20 MW ceiling)
    results/baseline-stress/closed_loop_comparison.json   (tight 18 MW ceiling)

Charts are saved to results/comparison/.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]

LABELS = {
    "fixed_horizon": "Fixed plan",
    "rolling_risk_aware_mpc": "Risk-aware MPC",
    "rolling_quantile_baseline": "Baseline",
    "rolling_rafc_v": "RAFC-V (ours)",
}
COLORS = {
    "fixed_horizon": "#9a9a92",
    "rolling_risk_aware_mpc": "#d8843a",
    "rolling_quantile_baseline": "#5b7fbf",
    "rolling_rafc_v": "#2e8b6e",
}
ORDER = list(LABELS)


def load(path: Path) -> tuple[dict[str, dict], int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = {row["controller"]: row for row in data["results"]}
    return rows, data["heldout_sample_count"]


def present(rows: dict) -> list[str]:
    return [c for c in ORDER if c in rows]


def bar_labels(ax, bars, texts, inside: bool = False):
    for bar, text in zip(bars, texts):
        if inside and bar.get_height() > 10:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() - 3, text,
                    ha="center", va="top", fontsize=9, color="white", fontweight="bold")
        else:
            ax.annotate(text, (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        xytext=(0, 4), textcoords="offset points", ha="center", fontsize=9)


def chart_success(ax, rows, n, title):
    names = present(rows)
    succ = [rows[c]["event_and_recovery_success_probability"] * 100 for c in names]
    bars = ax.bar([LABELS[c] for c in names], succ, color=[COLORS[c] for c in names])
    bar_labels(ax, bars, [f"{s:.0f}%\n({rows[c]['commitment_mw']:.1f} MW)" for s, c in zip(succ, names)],
               inside=True)
    ax.axhline(95, color="#b03a3a", linestyle="--", linewidth=1, label="95% target")
    ax.set_ylim(0, 110)
    ax.set_ylabel("Event + recovery success (%)")
    ax.set_title(f"{title}, {n:,} unseen events")
    ax.legend(frameon=False, loc="upper left")
    ax.tick_params(axis="x", labelsize=9)


def chart_promise(ax, rows, title):
    names = present(rows)
    x = range(len(names))
    promised = [rows[c]["commitment_mw"] for c in names]
    delivered = [rows[c]["mean_minimum_delivered_mw"] for c in names]
    b1 = ax.bar([i - 0.2 for i in x], promised, 0.4, color="#c9c9c2")
    b2 = ax.bar([i + 0.2 for i in x], delivered, 0.4, color=[COLORS[c] for c in names])
    bar_labels(ax, b1, [f"{v:.2f}" for v in promised])
    bar_labels(ax, b2, [f"{v:.2f}" for v in delivered])
    ax.set_xticks(list(x), [LABELS[c] for c in names], fontsize=9)
    ax.set_ylim(0, 6.5)
    ax.set_ylabel("MW")
    ax.set_title(title)
    ax.legend(handles=[Patch(color="#c9c9c2", label="Promised to grid"),
                       Patch(color="#555", label="Delivered (worst interval, avg)")],
              frameon=False, loc="upper left", fontsize=8)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--normal", type=Path,
                        default=ROOT / "results" / "baseline-normal" / "closed_loop_comparison.json")
    parser.add_argument("--stress", type=Path,
                        default=ROOT / "results" / "baseline-stress" / "closed_loop_comparison.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "comparison")
    parser.add_argument("--show", action="store_true", help="open the charts in a window")
    args = parser.parse_args()

    for path in (args.normal, args.stress):
        if not path.exists():
            raise SystemExit(f"Missing results file: {path}\nRun the closed-loop comparison first.")
    normal, n_normal = load(args.normal)
    stress, n_stress = load(args.stress)

    charts = [
        ("1_normal_grid.png", lambda ax: chart_success(ax, normal, n_normal, "1. Normal grid (20 MW ceiling)")),
        ("2_tight_recovery.png", lambda ax: chart_success(ax, stress, n_stress, "2. Tight recovery (18 MW ceiling)")),
        ("3_promise_vs_delivery.png", lambda ax: chart_promise(ax, stress, "3. Promise vs delivery (tight recovery)")),
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, draw in charts:
        fig, ax = plt.subplots(figsize=(8, 4.8), constrained_layout=True)
        draw(ax)
        ax.grid(axis="y", alpha=0.25)
        fig.savefig(args.output_dir / filename, dpi=180)
        plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(21, 5.8), constrained_layout=True)
    for (_, draw), ax in zip(charts, axes):
        draw(ax)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("FlexProof AI: RAFC-V versus baseline and other controllers (simulation results)", fontsize=14)
    fig.savefig(args.output_dir / "dashboard.png", dpi=150)
    print(f"Saved charts to {args.output_dir}")
    if args.show:
        plt.show()
    plt.close(fig)


if __name__ == "__main__":
    main()