"""Stock-alert evaluation on the 1,000-store simulation (PROTOCOL.md, "Alerts").

Targets are future outcomes; features use only data up to the snapshot day.
Methods: Jiran's current rule, a one-feature days-of-cover threshold, and
HistGradientBoosting. Test = 200 held-out stores at later snapshot days.
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, f1_score, precision_score, recall_score, roc_auc_score

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from inventory_policy import MIN_HISTORY_DAYS, SAFETY_DAYS, no_sale_days, policy_metrics, stock_policy_label  # noqa: E402

TRAIN_T = list(range(90, 203, 14)); VAL_T = [216]; TEST_T = [276, 290, 304]
TARGETS = ("shortage_14d", "excess_60d", "dead_60d")
ORDERING = {"on_order", "cover_days_with_orders", "lead_time", "days_to_next_review"}
START_DOW = pd.Timestamp("2025-01-01").day_of_week
FEATURES = ["stock_qty", "on_order", "sales_7", "sales_14", "sales_28", "sales_56", "sales_90", "txns_28", "txns_90",
            "mean_28", "std_28", "zero_share_28", "days_since_last_sale", "age_days", "stockout_days_28", "trend_28_vs_prior",
            "cover_days", "cover_days_with_orders", "retail_price", "category_code", "pack", "store_sales_per_item_28",
            "lead_time", "days_to_next_review"]


def window(cs, T, w):
    return cs[:, T + 1] - cs[:, max(T + 1 - w, 0)]


def snapshot(T, D, series, stores, new_only=False):
    S, ST, OO, TX, cs, ctx = D["sales"], D["stock"], D["on_order"], D["txns"], D["cs"], D["ctx"]
    launch = series.launch_day.to_numpy()
    keep = (launch <= T - 28) & (ST[:, T - 27:T + 1].max(1) > 0)
    if new_only:  # products on sale here for fewer than 28 days (cold start)
        keep = (launch > T - MIN_HISTORY_DAYS) & (launch < T) & (ST[:, T - 27:T + 1].max(1) > 0)
    f = pd.DataFrame({"series_id": series.series_id, "store_id": series.store_id, "T": T})
    f["stock_qty"] = ST[:, T]; f["on_order"] = OO[:, T]
    for w in (7, 14, 28, 56, 90): f[f"sales_{w}"] = window(cs, T, w)
    f["txns_28"] = window(ctx, T, 28); f["txns_90"] = window(ctx, T, 90)
    last28 = S[:, T - 27:T + 1]
    f["mean_28"] = last28.mean(1); f["std_28"] = last28.std(1); f["zero_share_28"] = (last28 == 0).mean(1)
    sold = S[:, :T + 1] > 0
    last = np.where(sold.any(1), T - np.argmax(sold[:, ::-1], 1), -1)
    f["days_since_last_sale"] = np.where(last >= 0, T - last, [no_sale_days(T - l) for l in launch])
    f["age_days"] = T - launch
    f["stockout_days_28"] = (ST[:, T - 27:T + 1] == 0).sum(1)
    f["trend_28_vs_prior"] = (f.sales_28 + 1) / (f.sales_56 - f.sales_28 + 1)
    f["cover_days"] = f.stock_qty / (f.mean_28 + 0.1)
    f["cover_days_with_orders"] = (f.stock_qty + f.on_order) / (f.mean_28 + 0.1)
    f["retail_price"] = series.retail_price; f["category_code"] = series.category.astype("category").cat.codes; f["pack"] = series.pack
    st = stores.set_index("store_id").loc[series.store_id]
    f["store_sales_per_item_28"] = f.groupby("store_id").sales_28.transform("mean")
    f["lead_time"] = st.lead_time.to_numpy()
    f["days_to_next_review"] = (st.review_weekday.to_numpy() - (START_DOW + T) % 7) % 7
    # Jiran rule inputs, computed the way the app does (30-day recent window; forecast = 28-day mean)
    f["recent_qty"] = window(cs, T, 30); recent_txns = window(ctx, T, 30)
    hist_qty = cs[:, T + 1] - f.recent_qty; hist_txns = ctx[:, T + 1] - recent_txns
    f["velocity_trend"] = (f.recent_qty / np.maximum(recent_txns, 1)) / (hist_qty / np.maximum(hist_txns, 1) + 0.1)
    f["forecast_30d"] = f.mean_28 * 30; f["forecast_7d"] = f.mean_28 * 7
    f["forecast_acceleration"] = (f.forecast_7d / 7) / (f.forecast_30d / 30 + 0.1)
    # Improved rule inputs (post-protocol addition 5): in-stock rate and next-delivery timing
    f["rate_instock"] = f.sales_28 / np.maximum(28 - f.stockout_days_28, 7)
    f["days_until_delivery"] = np.where(f.days_to_next_review == 0, 7, f.days_to_next_review) + f.lead_time + 0.5
    # Future outcomes (labels)
    fut60 = S[:, T + 1:T + 61].sum(1)
    f["shortage_14d"] = (ST[:, T + 1:T + 15] == 0).any(1).astype(int)
    f["excess_60d"] = (f.stock_qty > fut60).astype(int)
    f["dead_60d"] = ((f.stock_qty > 0) & (fut60 == 0)).astype(int)
    return f[keep].reset_index(drop=True)


def rule_labels(f):
    out = []
    for r in f[["stock_qty", "forecast_30d", "forecast_7d", "recent_qty", "velocity_trend", "forecast_acceleration", "days_since_last_sale"]].itertuples(index=False):
        row = r._asdict(); row.update(policy_metrics(stock_qty=row["stock_qty"], forecast_30d=row["forecast_30d"], forecast_7d=row["forecast_7d"], recent_qty=row["recent_qty"]))
        out.append(stock_policy_label(row))
    lab = pd.Series(out, index=f.index)
    return {"shortage_14d": (lab == "Low").astype(int), "dead_60d": (lab == "Dead").astype(int),
            "excess_60d": lab.isin(["Dead", "Slow", "Excess"]).astype(int)}, lab


def rule_v2_labels(f):
    """Improved rule: same Dead/Slow/Excess thresholds on the in-stock rate; Low = stock plus
    open orders will not last until the next supplier delivery + SAFETY_DAYS."""
    g = f.copy(); g["forecast_30d"] = g.rate_instock * 30; g["forecast_7d"] = g.rate_instock * 7
    g["forecast_acceleration"] = (g.forecast_7d / 7) / (g.forecast_30d / 30 + 0.1)
    _, lab = rule_labels(g)
    low = (g.rate_instock > 0) & ((g.stock_qty + g.on_order) / g.rate_instock.clip(lower=1e-9) < g.days_until_delivery + SAFETY_DAYS)
    lab = pd.Series(np.where(lab.isin(["Dead", "Slow"]), lab, np.where(low, "Low", np.where(lab == "Excess", "Excess", "Optimum"))), index=f.index)
    return {"shortage_14d": (lab == "Low").astype(int), "dead_60d": (lab == "Dead").astype(int),
            "excess_60d": lab.isin(["Dead", "Slow", "Excess"]).astype(int)}, lab


def best_threshold(y, score):
    qs = np.unique(np.quantile(score, np.linspace(0.01, 0.99, 197)))
    f1s = [f1_score(y, score >= q, zero_division=0) for q in qs]
    return float(qs[int(np.argmax(f1s))])


def cluster_ci(y, pred, stores, n=1000, seed=0):
    df = pd.DataFrame({"s": stores, "tp": (y == 1) & (pred == 1), "fp": (y == 0) & (pred == 1), "fn": (y == 1) & (pred == 0)}).groupby("s").sum()
    rng = np.random.default_rng(seed); vals = df.to_numpy(float); out = {"precision": [], "recall": [], "f1": []}
    for _ in range(n):
        tp, fp, fn = vals[rng.integers(0, len(vals), len(vals))].sum(0)
        p = tp / (tp + fp) if tp + fp else 0; r = tp / (tp + fn) if tp + fn else 0
        out["precision"].append(p); out["recall"].append(r); out["f1"].append(2 * p * r / (p + r) if p + r else 0)
    return {k: [float(np.quantile(v, .025)), float(np.quantile(v, .975))] for k, v in out.items()}


def metrics(y, pred, score, stores, prob=None):
    m = {"precision": precision_score(y, pred, zero_division=0), "recall": recall_score(y, pred, zero_division=0),
         "f1": f1_score(y, pred, zero_division=0), "alerts": int(pred.sum()), "ci95": cluster_ci(y.to_numpy(), np.asarray(pred), stores.to_numpy())}
    if score is not None:
        m["pr_auc"] = average_precision_score(y, score)
        m["roc_auc"] = roc_auc_score(y, score)
    if prob is not None:
        m["brier"] = brier_score_loss(y, prob)
        bins = np.minimum((prob * 10).astype(int), 9)
        m["reliability"] = [{"bin": b / 10, "n": int((bins == b).sum()), "mean_pred": float(prob[bins == b].mean()), "observed": float(y[bins == b].mean())}
                            for b in range(10) if (bins == b).any()]
    return {k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in m.items()}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data", type=Path, default=HERE / "output/sim1000_v1")
    ap.add_argument("--out", type=Path, default=HERE / "output/results/alerts.json")
    ap.add_argument("--exclude-ordering", action="store_true",
                    help="Exploratory (not pre-registered): drop open orders, lead time and review timing from ML features")
    a = ap.parse_args()
    feats = [c for c in FEATURES if not (a.exclude_ordering and c in ORDERING)]; a.out.parent.mkdir(parents=True, exist_ok=True); t0 = time.time()
    series = pd.read_csv(a.data / "series.csv"); stores = pd.read_csv(a.data / "stores.csv")
    D = {k: np.load(a.data / f"{k}.npy") for k in ("sales", "stock", "on_order", "txns")}
    D["cs"] = np.pad(np.cumsum(D["sales"], 1, dtype=np.int64), ((0, 0), (1, 0))); D["ctx"] = np.pad(np.cumsum(D["txns"], 1, dtype=np.int64), ((0, 0), (1, 0)))
    test_stores = set(stores.store_id.sample(200, random_state=7))
    def frames(days, held_out):
        f = pd.concat([snapshot(T, D, series, stores) for T in days], ignore_index=True)
        return f[f.store_id.isin(test_stores) == held_out].reset_index(drop=True)
    tr, va, te = frames(TRAIN_T, False), frames(VAL_T, False), frames(TEST_T, True)
    assert not set(tr.store_id) & set(te.store_id) and not set(va.store_id) & set(te.store_id)
    print("rows train/val/test", len(tr), len(va), len(te), f"{time.time() - t0:.0f}s", flush=True)
    rule_te, rule_lab_te = rule_labels(te)
    rule2_te, rule2_lab_te = rule_v2_labels(te)
    # Cold start: how the current rule labels products that are under 28 days old, and what happened next.
    nw = pd.concat([snapshot(T, D, series, stores, new_only=True) for T in TEST_T], ignore_index=True)
    nw = nw[nw.store_id.isin(test_stores)].reset_index(drop=True)
    nw_rule, nw_lab = rule_labels(nw)
    cold = {"rows": len(nw), "current_rule_labels": nw_lab.value_counts().to_dict(),
            "outcome_rates": {t: float(nw[t].mean()) for t in TARGETS},
            "current_rule_precision": {t: float(nw[t][nw_rule[t] == 1].mean()) if nw_rule[t].sum() else None for t in TARGETS},
            "labelled_dead_but_sold_within_60d": float(1 - nw.dead_60d[nw_lab == "Dead"].mean()) if (nw_lab == "Dead").any() else None}
    res = {"data_origin": "simulated", "protocol": "PROTOCOL.md", "rows": {"train": len(tr), "validation": len(va), "test": len(te)},
           "snapshots": {"train": TRAIN_T, "validation": VAL_T, "test": TEST_T}, "test_stores": len(test_stores),
           "features": feats, "exploratory": bool(a.exclude_ordering), "rule_label_counts_test": rule_lab_te.value_counts().to_dict(),
           "rule_v2_label_counts_test": rule2_lab_te.value_counts().to_dict(), "cold_start_test": cold, "targets": {}}
    for t in TARGETS:
        y_te = te[t]; r = {"prevalence": {"train": float(tr[t].mean()), "validation": float(va[t].mean()), "test": float(y_te.mean())}}
        r["jiran_rule"] = metrics(y_te, rule_te[t], None, te.store_id)
        r["jiran_rule_v2"] = metrics(y_te, rule2_te[t], None, te.store_id)
        sign = -1 if t == "shortage_14d" else 1  # low cover -> shortage; high cover -> excess / dead
        thr = best_threshold(va[t], sign * va.cover_days)
        r["cover_threshold"] = metrics(y_te, (sign * te.cover_days >= thr).astype(int), sign * te.cover_days, te.store_id)
        r["cover_threshold"]["threshold_days"] = float(sign * thr)
        model = HistGradientBoostingClassifier(learning_rate=0.05, max_iter=300, max_leaf_nodes=31, early_stopping=True,
                                               validation_fraction=0.1, random_state=0).fit(tr[feats], tr[t])
        thr_m = best_threshold(va[t], model.predict_proba(va[feats])[:, 1])
        p_te = model.predict_proba(te[feats])[:, 1]
        r["ml_hgb"] = metrics(y_te, (p_te >= thr_m).astype(int), p_te, te.store_id, prob=p_te)
        r["ml_hgb"].update({"threshold_prob": thr_m, "iterations": int(model.n_iter_)})
        res["targets"][t] = r
        print(t, {k: round(v, 3) for k, v in r["prevalence"].items()},
              {m: {k: round(r[m][k], 3) for k in ("precision", "recall", "f1", "pr_auc") if k in r[m]} for m in ("jiran_rule", "jiran_rule_v2", "cover_threshold", "ml_hgb")}, flush=True)
    res["runtime_s"] = round(time.time() - t0, 1)
    a.out.write_text(json.dumps(res, indent=1, default=float)); print("runtime", res["runtime_s"])


if __name__ == "__main__":
    main()
