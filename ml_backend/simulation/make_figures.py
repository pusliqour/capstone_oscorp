"""Concern A11: readable figures for the ML evaluation (simulated evidence only).

Horizontal bars, values printed on each bar, 95% store-clustered intervals as whiskers,
one shared axis per chart, colour-blind-safe categorical order, legend always present,
PNG at 2x (300 dpi) plus SVG. Reads results JSON; never re-runs an experiment.

    ../../.venv/bin/python make_figures.py            # -> output/figures/*.png|svg
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent; R = HERE / "output/results"; OUT = HERE / "output/figures"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]           # categorical slots 1-4, fixed order
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams.update({"font.size": 12, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK,
                     "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "font.family": "DejaVu Sans"})
load = lambda f: json.loads((R / f).read_text())


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight"); fig.savefig(OUT / f"{name}.svg", bbox_inches="tight"); plt.close(fig)
    print("wrote", OUT / f"{name}.png")


def style(ax, xlabel):
    ax.set_xlabel(xlabel); ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True)
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)


def grouped_hbar(groups, series_names, values, cis, title, xlabel, name, xmax=1.0, fmt="{:.2f}", note=None):
    """groups x series bars; values[g][s]; cis[g][s] = (lo, hi) or None."""
    n_g, n_s = len(groups), len(series_names); h = 0.8 / n_s
    fig, ax = plt.subplots(figsize=(9, 1.0 + 1.25 * n_g))
    for s in range(n_s):
        y = np.arange(n_g) - 0.4 + h * (s + 0.5)
        v = [values[g][s] for g in range(n_g)]
        ax.barh(y, v, height=h * 0.86, color=SERIES[s], label=series_names[s], edgecolor=SURFACE, linewidth=2)
        for g in range(n_g):
            ci = cis[g][s]
            if ci:
                ax.plot(ci, [y[g]] * 2, color=INK, lw=1.2); ax.plot([ci[0]] * 2, [y[g] - h * .2, y[g] + h * .2], color=INK, lw=1.2)
                ax.plot([ci[1]] * 2, [y[g] - h * .2, y[g] + h * .2], color=INK, lw=1.2)
            right = max(v[g], ci[1] if ci else 0)
            ax.text(right + xmax * 0.01, y[g], fmt.format(v[g]), va="center", fontsize=10.5, color=INK)
    ax.set_yticks(range(n_g)); ax.set_yticklabels(groups); ax.invert_yaxis(); ax.set_xlim(0, xmax)
    style(ax, xlabel); ax.set_title(title, loc="left", fontsize=14, color=INK, pad=12)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0 + 0.35 / n_g), ncol=min(n_s, 2), frameon=False, fontsize=10.5)
    fig.text(0.0, -0.02, note or "Simulated 1,000-store benchmark; test = 200 unseen stores, later dates. Whiskers: 95% store-clustered interval.",
             fontsize=9, color=INK2)
    save(fig, name)


def fig_alerts():
    t = load("alerts_tuned.json"); names = {"shortage_14d": "Stock-out within 14 days", "excess_60d": "Excess over 60 days", "dead_60d": "Dead (no sale) over 60 days"}
    series = ["Rule as shipped", "Rule, thresholds tuned on validation", "ML benchmark as before", "ML benchmark, tuned on validation"]
    vals, cis = [], []
    for k in names:
        r, m = t["rules"][k], t["ml"][k]
        row = [r["default_test"], r["selected_test"], m["default"], m["tuned"]]
        vals.append([x["f1"] for x in row]); cis.append([tuple(x["ci95"]["f1"]) for x in row])
    grouped_hbar(list(names.values()), series, vals, cis, "Alert quality after tuning both sides fairly (F1, higher is better)", "F1 score", "fig_a6_fair_tuning")


def fig_thresholds():
    worlds = [("Main", "alerts_tuned.json")] + [(w, f"seeds/{w}_alerts_tuned_rules.json") for w in ("dev1001", "seed1", "seed2", "seed3", "seed4")]
    for tgt, label, knob in (("dead_60d", "Dead-stock alerts", "Dead after 90 days without a sale → chosen value"),
                             ("excess_60d", "Excess alerts", "Slow cut-off coverage 4 → chosen value")):
        vals, cis, groups = [], [], []
        for w, f in worlds:
            r = load(f)["rules"][tgt]; sel = ", ".join(f"{k}={v:g}" for k, v in r["selected_on_validation"].items())
            groups.append(f"{w}\n({sel})"); vals.append([r["default_test"]["f1"], r["selected_test"]["f1"]])
            cis.append([tuple(r["default_test"]["ci95"]["f1"]), tuple(r["selected_test"]["ci95"]["f1"])])
        grouped_hbar(groups, ["Shipped threshold", "Threshold chosen on validation"], vals, cis,
                     f"{label}: same improvement in every simulated world (test F1)", "F1 score", f"fig_a8_{tgt}_stability", xmax=0.8)


def fig_transfers():
    f = R / "transfers_p1.json"
    if not f.exists():
        print("skip transfers (run evaluate_transfers.py with the P1 arms first)"); return
    t = json.loads(f.read_text()); base = t["arms"]["none"]
    arms = [("improved", "Improved engine (live)"), ("improved+slow2.5", "+ Slow cut-off 2.5"), ("improved+dead30", "+ Dead after 30 days"),
            ("improved+slow2.5+dead30", "+ both")]
    arms = [(k, n) for k, n in arms if k in t["arms"]]
    lost = [100 * (1 - t["arms"][k]["lost_units"] / base["lost_units"]) for k, _ in arms]
    harm = [100 * t["arms"][k]["donor_events_that_caused_a_new_stockout"] for k, _ in arms]
    dead = [100 * (1 - t["arms"][k]["dead_stock_units_end"] / base["dead_stock_units_end"]) for k, _ in arms]
    grouped_hbar([n for _, n in arms], ["Lost sales prevented (%)", "Transfers that caused a stock-out at the giver (%)", "Dead stock cleared (%)"],
                 [[a, b, c] for a, b, c in zip(lost, harm, dead)], [[None] * 3 for _ in arms],
                 "Task P1: transfer replay with the tuned thresholds", "percent", "fig_p1_transfers",
                 xmax=100, fmt="{:.1f}%",
                 note="Simulated paired replay, all 1,000 stores, days 183-364; identical demand in every arm. Main world (dev world 1001 agrees).")


if __name__ == "__main__":
    fig_alerts(); fig_thresholds(); fig_transfers()
