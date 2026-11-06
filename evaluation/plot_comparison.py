"""Draw comparison charts showing where RAFC-V helps versus the other controllers.

Uses the result files already saved in results/summaries, so it runs in seconds:

    python -m evaluation.plot_comparison
    python -m evaluation.plot_comparison --show      # also open the charts in a window

Charts are saved to results/comparison/.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SUMMARIES = ROOT / "results" / "summaries"

LABELS = {
    "fixed_horizon": "Fixed plan",
    "rolling_risk_aware_mpc": "Risk-aware MPC",
    "rolling_rafc_v": "RAFC-V (ours)",
}
COLORS = {
    "fixed_horizon": "#9a9a92",
    "rolling_risk_aware_mpc": "#d8843a",
    "rolling_rafc_v": "#2e8b6e",
}
ORDER = ["fixed_horizon", "rolling_risk_aware_mpc", "rolling_rafc_v"]


def load(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {row["controller"]: row for row in data["results"]}, data["heldout_sample_count"]


def bar_labels(ax, bars, texts):
    for bar, text in zip(bars, texts):
        ax.annotate(text, (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 4), textcoords="offset points", ha="center", fontsize=9)


def chart_normal(ax, rows, n):
    """Normal grid: success rate with 95% confidence intervals."""
    succ = [rows[c]["event_and_recovery_success_probability"] * 100 for c in ORDER]
    ci = [rows[c]["joint_wilson_interval"] for c in ORDER]
    err = [[s - lo * 100 for s, (lo, _) in zip(succ, ci)], [hi * 100 - s for s, (_, hi) in zip(succ, ci)]]
    bars = ax.bar([LABELS[c] for c in ORDER], succ, color=[COLORS[c] for c in ORDER],
                  yerr=err, capsize=4)
    for bar, s in zip(bars, succ):
        ax.text(bar.get_x() + bar.get_width() / 2, s - 1.5, f"{s:.1f}%", ha="center",
                va="top", fontsize=11, color="white", fontweight="bold")
    ax.axhline(95, color="#b03a3a", linestyle="--", linewidth=1, label="95% target")
    ax.set_ylim(80, 102)
    ax.set_ylabel("Event + recovery success (%)")
    ax.set_title(f"1. Normal grid (20 MW ceiling), {n:,} unseen events")
    ax.legend(frameon=False, loc="lower right")


def chart_stress(ax, stress):
    """Tight recovery: success at each lowered grid ceiling."""
    width = 0.26
    names = list(stress)
    for i, c in enumerate(ORDER):
        xs = [k + (i - 1) * width for k in range(len(names))]
        vals = [stress[name][c]["event_and_recovery_success_probability"] * 100 for name in names]
        bars = ax.bar(xs, vals, width, color=COLORS[c], label=LABELS[c])
        bar_labels(ax, bars, [f"{v:.0f}%\n({stress[name][c]['commitment_mw']} MW)"
                              for v, name in zip(vals, names)])
    ax.set_xticks(range(len(names)), names)
    ax.set_ylim(0, 120)
    ax.set_ylabel("Event + recovery success (%)")
    ax.set_title("2. Tight recovery: who keeps their promise?")
    ax.legend(frameon=False, loc="upper left", ncol=3, fontsize=8)


def chart_promise(ax, rows, name):
    """Promised MW vs worst delivered MW: the honest-promise picture."""
    x = range(len(ORDER))
    promised = [rows[c]["commitment_mw"] for c in ORDER]
    delivered = [rows[c]["mean_minimum_delivered_mw"] for c in ORDER]
    b1 = ax.bar([i - 0.2 for i in x], promised, 0.4, color="#c9c9c2", label="Promised to grid")
    b2 = ax.bar([i + 0.2 for i in x], delivered, 0.4, color=[COLORS[c] for c in ORDER],
                label="Actually delivered (worst interval, avg)")
    bar_labels(ax, b1, [f"{v:.2f}" for v in promised])
    bar_labels(ax, b2, [f"{v:.2f}" for v in delivered])
    ax.set_xticks(list(x), [LABELS[c] for c in ORDER])
    ax.set_ylim(0, 6)
    ax.set_ylabel("MW")
    ax.set_title(f"3. Promise vs delivery ({name})")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color="#c9c9c2", label="Promised to grid"),
                       Patch(color="#555", label="Actually delivered (worst interval, avg)")],
              frameon=False, loc="upper left", fontsize=8)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normal", type=Path, default=SUMMARIES / "v2-step0.05-fp001-5000.json")
    parser.add_argument("--stress-18p0", type=Path, default=SUMMARIES / "recovery-stress-18.0MW-1000.json")
    parser.add_argument("--stress-18p2", type=Path, default=SUMMARIES / "recovery-stress-18.2MW-1000.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "comparison")
    parser.add_argument("--show", action="store_true", help="open the charts in a window")
    args = parser.parse_args()

    normal, n_normal = load(args.normal)
    s180, _ = load(args.stress_18p0)
    s182, _ = load(args.stress_18p2)
    stress = {"18.2 MW ceiling": s182, "18.0 MW ceiling": s180}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    charts = [
        ("1_normal_grid.png", lambda ax: chart_normal(ax, normal, n_normal)),
        ("2_tight_recovery.png", lambda ax: chart_stress(ax, stress)),
        ("3_promise_vs_delivery.png", lambda ax: chart_promise(ax, s180, "18.0 MW ceiling")),
    ]
    for filename, draw in charts:
        fig, ax = plt.subplots(figsize=(7.5, 4.6), constrained_layout=True)
        draw(ax)
        ax.grid(axis="y", alpha=0.25)
        fig.savefig(args.output_dir / filename, dpi=180)
        plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(20, 5.6), constrained_layout=True)
    for (_, draw), ax in zip(charts, axes):
        draw(ax)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("FlexProof AI: RAFC-V versus baseline controllers (simulation results)", fontsize=14)
    dashboard = args.output_dir / "dashboard.png"
    fig.savefig(dashboard, dpi=150)
    print(f"Saved charts to {args.output_dir}")
    if args.show:
        plt.show()
    plt.close(fig)


if __name__ == "__main__":
    main()