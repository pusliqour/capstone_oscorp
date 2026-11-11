"""Concerns A6 and A8: fair tuning of the benchmark ML model and of the rule thresholds.

A6 ("the baseline lost because the ML model was untuned / unfair comparison"):
    the benchmark HistGradientBoosting model gets a small hyperparameter grid,
    chosen on the VALIDATION snapshot (non-test stores, day 216) by PR-AUC.
A8 ("thresholds are not justified, maybe tuned on test"):
    the hand-set rule thresholds (SAFETY_DAYS, Dead/Slow coverage cut-offs,
    days-without-sale for Dead) are swept on the same validation snapshot.
    The selected value and the shipped default are both reported on the test set.

Nothing is selected on test. Same splits, features and targets as evaluate_alerts.py.
Writes a NEW file (default output/results/alerts_tuned.json); alerts.json is untouched.
"""
import argparse, itertools, json, time
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, f1_score

from evaluate_alerts import (FEATURES, HERE, TARGETS, TEST_T, TRAIN_T, VAL_T, best_threshold, metrics, rule_labels,
                             rule_v2_labels, snapshot)
from inventory_policy import SAFETY_DAYS

DEFAULT_HGB = dict(learning_rate=0.05, max_leaf_nodes=31, l2_regularization=0.0, min_samples_leaf=20)
HGB_GRID = [dict(learning_rate=lr, max_leaf_nodes=nl, l2_regularization=l2, min_samples_leaf=ms)
            for lr, nl, l2, ms in itertools.product((0.05, 0.1), (15, 31, 63), (0.0, 1.0), (20, 100))]
RULE_DEFAULT = dict(safety_days=SAFETY_DAYS, dead_cov=8.0, slow_cov=4.0, dead_days=90.0)
SAFETY_GRID = (0.0, 1.0, 2.0, 3.0, 5.0, 7.0)
DEAD_COV_GRID = (4.0, 6.0, 8.0, 10.0)
SLOW_COV_GRID = (2.5, 3.0, 4.0, 5.0)
DEAD_DAYS_GRID = (30.0, 45.0, 60.0, 90.0)


def rule_vec(f, safety_days, dead_cov, slow_cov, dead_days, v2=True):
    """Vectorised stock_policy_label (+ v2 Low test) with the thresholds as parameters.
    At the shipped defaults it must equal rule_labels / rule_v2_labels exactly (checked in main)."""
    rate30 = f.rate_instock * 30 if v2 else f.forecast_30d
    rate7 = f.rate_instock * 7 if v2 else f.forecast_7d
    d30 = np.where(rate30 > 0, rate30, np.maximum(f.recent_qty, 1.0))
    d7 = np.where(rate7 > 0, rate7, np.maximum(f.recent_qty / 4.0, 1.0))
    cov = f.stock_qty / (d30 + 1); days = f.stock_qty / (d30 / 30 + 0.1)
    acc = (rate7 / 7) / (rate30 / 30 + 0.1); vel = f.velocity_trend; since = f.days_since_last_sale
    dead = (cov > dead_cov) | (days > 180) | (since > dead_days) | ((cov > 0.75 * dead_cov) & (vel < 0.2))
    slow = ~dead & ((cov > slow_cov) | (days > 120) | ((cov > 0.75 * slow_cov) & (vel < 0.5)))
    low_v1 = (cov < 0.6) | (days < 14) | ((cov < 0.8) & (acc > 1.2)) | (f.stock_qty < d7)
    exc = (cov > 2.0) & (cov <= slow_cov) & (vel > 0.5)
    if v2:
        low = (f.rate_instock > 0) & ((f.stock_qty + f.on_order) / f.rate_instock.clip(lower=1e-9) < f.days_until_delivery + safety_days)
    else:
        low = low_v1
    lab = np.select([dead, slow, low, exc], ["Dead", "Slow", "Low", "Excess"], "Optimum")
    lab = pd.Series(lab, index=f.index)
    return {"shortage_14d": (lab == "Low").astype(int), "dead_60d": (lab == "Dead").astype(int),
            "excess_60d": lab.isin(["Dead", "Slow", "Excess"]).astype(int)}, lab


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data", type=Path, default=HERE / "output/sim1000_v1")
    ap.add_argument("--out", type=Path, default=HERE / "output/results/alerts_tuned.json")
    ap.add_argument("--quick", action="store_true", help="smaller HGB grid (smoke test)")
    ap.add_argument("--rules-only", action="store_true", help="skip the ML grid (threshold stability across worlds)")
    a = ap.parse_args(); a.out.parent.mkdir(parents=True, exist_ok=True); t0 = time.time()
    series = pd.read_csv(a.data / "series.csv"); stores = pd.read_csv(a.data / "stores.csv")
    D = {k: np.load(a.data / f"{k}.npy") for k in ("sales", "stock", "on_order", "txns")}
    D["cs"] = np.pad(np.cumsum(D["sales"], 1, dtype=np.int64), ((0, 0), (1, 0))); D["ctx"] = np.pad(np.cumsum(D["txns"], 1, dtype=np.int64), ((0, 0), (1, 0)))
    test_stores = set(stores.store_id.sample(200, random_state=7))  # identical to evaluate_alerts.py

    def frames(days, held_out):
        f = pd.concat([snapshot(T, D, series, stores) for T in days], ignore_index=True)
        return f[f.store_id.isin(test_stores) == held_out].reset_index(drop=True)
    tr, va, te = frames(TRAIN_T, False), frames(VAL_T, False), frames(TEST_T, True)
    assert not set(va.store_id) & set(te.store_id)
    print("rows", len(tr), len(va), len(te), flush=True)

    # Fidelity check: the vectorised rule equals the shipped rule at default thresholds.
    _, lab1 = rule_labels(te); _, lab2 = rule_v2_labels(te)
    _, v1 = rule_vec(te, v2=False, **RULE_DEFAULT); _, v2 = rule_vec(te, v2=True, **RULE_DEFAULT)
    fidelity = {"v1_agreement": float((lab1 == v1).mean()), "v2_agreement": float((lab2 == v2).mean())}
    print("fidelity", fidelity, flush=True)
    assert fidelity["v1_agreement"] > 0.999 and fidelity["v2_agreement"] > 0.999, fidelity

    res = {"data_origin": "simulated", "concerns": ["A6", "A8"], "selection": "validation snapshot day 216, non-test stores",
           "rows": {"train": len(tr), "validation": len(va), "test": len(te)}, "rule_fidelity": fidelity, "rules": {}, "ml": {}}

    # ---- A8: rule threshold sensitivity (select on validation F1, report test) ----
    def rule_eval(params, target, frame):
        flags, _ = rule_vec(frame, v2=True, **params)
        return flags[target]
    sweeps = {"shortage_14d": [("safety_days", SAFETY_GRID)],
              "excess_60d": [("slow_cov", SLOW_COV_GRID)],
              "dead_60d": [("dead_cov", DEAD_COV_GRID), ("dead_days", DEAD_DAYS_GRID)]}
    for t, knobs in sweeps.items():
        names = [k for k, _ in knobs]; grid = list(itertools.product(*[g for _, g in knobs]))
        rows = []
        for vals in grid:
            p = dict(RULE_DEFAULT, **dict(zip(names, vals)))
            rows.append({**dict(zip(names, vals)), "val_f1": float(f1_score(va[t], rule_eval(p, t, va), zero_division=0)),
                         "test_f1": float(f1_score(te[t], rule_eval(p, t, te), zero_division=0))})
        best = max(rows, key=lambda r: r["val_f1"])
        p_best = dict(RULE_DEFAULT, **{k: best[k] for k in names})
        res["rules"][t] = {"knobs": names, "default": {k: RULE_DEFAULT[k] for k in names},
                           "selected_on_validation": {k: best[k] for k in names},
                           "default_test": metrics(te[t], rule_eval(RULE_DEFAULT, t, te), None, te.store_id),
                           "selected_test": metrics(te[t], rule_eval(p_best, t, te), None, te.store_id),
                           "grid": rows}
        print("rule", t, "default", {k: RULE_DEFAULT[k] for k in names}, "->", {k: best[k] for k in names},
              "test F1", round(res["rules"][t]["default_test"]["f1"], 3), "->", round(res["rules"][t]["selected_test"]["f1"], 3), flush=True)

    # ---- A6: benchmark ML tuning (select on validation PR-AUC, report test) ----
    grid = HGB_GRID[:4] if a.quick else HGB_GRID
    for t in ([] if a.rules_only else TARGETS):
        rows, models = [], {}
        for i, hp in enumerate([DEFAULT_HGB] + grid):
            m = HistGradientBoostingClassifier(max_iter=500, early_stopping=True, validation_fraction=0.1, random_state=0, **hp).fit(tr[FEATURES], tr[t])
            pv = m.predict_proba(va[FEATURES])[:, 1]
            rows.append({**hp, "is_default": i == 0, "val_pr_auc": float(average_precision_score(va[t], pv)), "iterations": int(m.n_iter_)})
            models[i] = (m, pv)
        best_i = max(range(len(rows)), key=lambda i: rows[i]["val_pr_auc"])
        out = {}
        for name, i in (("default", 0), ("tuned", best_i)):
            m, pv = models[i]; thr = best_threshold(va[t], pv); pt = m.predict_proba(te[FEATURES])[:, 1]
            out[name] = metrics(te[t], (pt >= thr).astype(int), pt, te.store_id, prob=pt) | {"params": {k: rows[i][k] for k in DEFAULT_HGB}, "threshold_prob": thr}
            out[name].pop("reliability", None)
        res["ml"][t] = out | {"grid": rows}
        print("ml", t, "default F1", round(out["default"]["f1"], 3), "tuned F1", round(out["tuned"]["f1"], 3), out["tuned"]["params"], flush=True)
    res["runtime_s"] = round(time.time() - t0, 1)
    a.out.write_text(json.dumps(res, indent=1, default=float)); print("runtime", res["runtime_s"])


if __name__ == "__main__":
    main()
