"""Cold-start check (post-protocol addition 5b). Everything is simulated.

Products launched mid-year (6% of store-items, launch days 60-250). Weekly snapshots
while each is under 28 days old: what would the current rule call it, what happened
next, and how wrong is its 30-day demand estimate? Compared with the same products
once they have 28-41 days of history. Rule-based only, so all 1,000 stores are used.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
from evaluate_alerts import rule_labels, window  # noqa: E402

data = HERE / "output/sim1000_v1"
series = pd.read_csv(data / "series.csv"); stores = pd.read_csv(data / "stores.csv")
D = {k: np.load(data / f"{k}.npy") for k in ("sales", "stock", "on_order", "txns")}
D["cs"] = np.pad(np.cumsum(D["sales"], 1, dtype=np.int64), ((0, 0), (1, 0))); D["ctx"] = np.pad(np.cumsum(D["txns"], 1, dtype=np.int64), ((0, 0), (1, 0)))
demand = np.load(data / "demand.npy", mmap_mode="r")
launch = series.launch_day.to_numpy(); launched = np.flatnonzero(launch > 0)
rows = []
for T in range(63, 300, 7):
    # Same features the current rule uses, for every series; keep products 1-41 days old.
    S = D["sales"]; f_all = pd.DataFrame({"series_id": series.series_id, "T": T, "age": T - launch})
    f_all["stock_qty"] = D["stock"][:, T]; f_all["sales_28"] = window(D["cs"], T, 28)
    f_all["recent_qty"] = window(D["cs"], T, 30); rtx = window(D["ctx"], T, 30)
    hq = D["cs"][:, T + 1] - f_all.recent_qty; htx = D["ctx"][:, T + 1] - rtx
    f_all["velocity_trend"] = (f_all.recent_qty / np.maximum(rtx, 1)) / (hq / np.maximum(htx, 1) + 0.1)
    f_all["mean_28"] = f_all.sales_28 / 28
    f_all["forecast_30d"] = f_all.mean_28 * 30; f_all["forecast_7d"] = f_all.mean_28 * 7
    f_all["forecast_acceleration"] = (f_all.forecast_7d / 7) / (f_all.forecast_30d / 30 + 0.1)
    sold = S[:, :T + 1] > 0; last = np.where(sold.any(1), T - np.argmax(sold[:, ::-1], 1), -1)
    f_all["days_since_last_sale"] = np.where(last >= 0, T - last, np.maximum(T - launch, 0))
    fut60 = S[:, T + 1:T + 61].sum(1)
    f_all["shortage_14d"] = (D["stock"][:, T + 1:T + 15] == 0).any(1).astype(int)
    f_all["excess_60d"] = (f_all.stock_qty > fut60).astype(int); f_all["dead_60d"] = ((f_all.stock_qty > 0) & (fut60 == 0)).astype(int)
    f_all["true_demand_30d"] = np.asarray(demand[:, T + 1:T + 31]).sum(1)
    keep = (launch > 0) & (f_all.age >= 1) & (f_all.age <= 41)
    rows.append(f_all[keep])
f = pd.concat(rows, ignore_index=True)
_, lab = rule_labels(f); f["label"] = lab.to_numpy()
f["bucket"] = pd.cut(f.age, [0, 7, 14, 21, 28, 41], right=False, labels=["1-6", "7-13", "14-20", "21-27", "28-41"])
out = {"data_origin": "simulated", "note": "simulated launches start with no stock until the first supplier order arrives, so days 1-6 are dominated by that", "launched_series": int(len(launched)), "rows": int(len(f)), "by_age": {}}
for b, g in f.groupby("bucket", observed=True):
    ratio = (g.forecast_30d / g.true_demand_30d.clip(lower=1))
    low = g.label == "Low"
    out["by_age"][str(b)] = {"rows": int(len(g)), "labels": g.label.value_counts(normalize=True).round(4).to_dict(),
                             "median_estimate_to_true_demand": float(ratio.median()),
                             "share_estimate_under_half_true": float((ratio < 0.5).mean()),
                             "low_precision": float(g.shortage_14d[low].mean()) if low.any() else None,
                             "dead_or_slow_label_share": float(g.label.isin(["Dead", "Slow"]).mean()),
                             "dead_or_slow_label_precision": float(g.dead_60d[g.label.isin(["Dead", "Slow"])].mean()) if g.label.isin(["Dead", "Slow"]).any() else None,
                             "shortage_rate": float(g.shortage_14d.mean()), "dead_rate": float(g.dead_60d.mean())}
(HERE / "output/results/cold_start.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
