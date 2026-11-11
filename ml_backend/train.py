"""
train.py — Jiran ML Training Pipeline (converted from v2222.ipynb)

Run once to train and save models:
    cd ml/
    python train.py

Outputs to saved_models/:
    ensemble.pkl              — RF + GB + XGB VotingClassifier
    scaler.pkl                — StandardScaler fit on training data
    label_encoder.pkl         — LabelEncoder for product categories
    forecasts_aggregated.csv  — Prophet forecast features (one row per store+product)
    feature_cols.json         — Ordered list of feature column names
"""

import argparse
import os
import json
import time
import warnings

import joblib
import numpy as np
import pandas as pd
from prophet import Prophet
from forecasting import daily_series, selected_forecast
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from xgboost import XGBClassifier

from inventory_policy import no_sale_days, policy_metrics, stock_policy_label
from augmentation import PolicyAugmentedClassifier

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# CLI args
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Jiran ML Training Pipeline")
parser.add_argument("--output-dir", default=None, help="Isolated artifact directory")
parser.add_argument("--data-dir",    default=None,  help="Path to data directory")
parser.add_argument("--prophet-top", default=400,   type=int, help="Top N products for Prophet (default 400)")
parser.add_argument("--rf-trees",    default=500,   type=int, help="Random Forest n_estimators (default 500)")
parser.add_argument("--gb-trees",    default=400,   type=int, help="Gradient Boosting n_estimators (default 400)")
parser.add_argument("--xgb-trees",   default=400,   type=int, help="XGBoost n_estimators (default 400)")
args = parser.parse_args()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = args.data_dir if args.data_dir else os.path.join(BASE_DIR, "training", "data")
MODELS_DIR = args.output_dir or os.path.join(BASE_DIR, "saved_models")
os.makedirs(MODELS_DIR, exist_ok=True)

print(f"Data dir  : {DATA_DIR}")
print(f"Models dir: {MODELS_DIR}")
print(f"Prophet top-N  : {args.prophet_top}")
print(f"RF trees       : {args.rf_trees}")
print(f"GB trees       : {args.gb_trees}")
print(f"XGB trees      : {args.xgb_trees}")

# ---------------------------------------------------------------------------
# Step 1 — Load data
# ---------------------------------------------------------------------------
print("Loading data...")
transactions = pd.read_csv(
    os.path.join(DATA_DIR, "transactions.csv"),
    parse_dates=["timestamp"],
)
stock = pd.read_csv(
    os.path.join(DATA_DIR, "stock.csv"),
    parse_dates=["updated_at"],
)
products = pd.read_csv(os.path.join(DATA_DIR, "products.csv"))

print(f"  transactions : {len(transactions):>12,} rows")
print(f"  stock        : {len(stock):>12,} rows")
print(f"  products     : {len(products):>12,} rows")
print(f"  stores       : {transactions['store_id'].nunique()} unique")

# ---------------------------------------------------------------------------
# Step 2 — Model 1: Prophet demand forecasting
# ---------------------------------------------------------------------------

def prepare_prophet_data(txn_df):
    txn_df = txn_df.copy()
    txn_df["date"] = txn_df["timestamp"].dt.date
    daily = (
        txn_df.groupby(["store_id", "product_id", "date"], as_index=False)
        .agg({"quantity": "sum"})
        .rename(columns={"date": "ds", "quantity": "y"})
    )
    daily["ds"] = pd.to_datetime(daily["ds"])
    return daily


def train_prophet_models(daily_data, top_n=100, horizons=None):
    if horizons is None:
        horizons = [7, 14, 30, 60]

    top_products = (
        daily_data.groupby("product_id")["y"].sum().nlargest(top_n).index
    )

    forecasts_list = []
    max_horizon = max(horizons)
    model_count = 0
    start_time = time.time()

    print(f"\nTraining Prophet for top {top_n} products x stores...")

    for idx, product_id in enumerate(top_products):
        product_data = daily_data[daily_data["product_id"] == product_id]
        stores_done = 0

        for store_id in product_data["store_id"].unique():
            sp_data = product_data[product_data["store_id"] == store_id][
                ["ds", "y"]
            ]

            # Zero-fill calendar days through the dataset cutoff, including
            # products whose most recent transaction predates the snapshot.
            series = daily_series(sp_data, daily_data["ds"].max())
            selected = selected_forecast(series, max_horizon)
            values = selected["values"]
            row = {"store_id": store_id, "product_id": product_id,
                   "forecast_method": selected["method"],
                   "validation_mae": selected["validation_mae"]}
            for h in horizons:
                demand = float(values[:h].sum())
                # Empirical validation-error bands, not calibrated confidence intervals.
                error = selected["daily_error"]
                width = (error * h) if error is not None else demand
                row[f"forecast_{h}d"] = round(demand, 1)
                row[f"forecast_{h}d_lower"] = round(max(0, demand-width), 1)
                row[f"forecast_{h}d_upper"] = round(demand+width, 1)
            forecasts_list.append(row)
            model_count += 1
            stores_done += 1

        elapsed = time.time() - start_time
        avg_per_product = elapsed / (idx + 1)
        remaining_min = avg_per_product * (len(top_products) - idx - 1) / 60
        print(
            f"  [{idx+1:3d}/{len(top_products)}] {product_id} "
            f"({stores_done} stores, ~{remaining_min:.0f} min left)"
        )

    forecasts_df = pd.DataFrame(forecasts_list)
    elapsed_total = (time.time() - start_time) / 60
    print(f"\nProphet done — {model_count} models in {elapsed_total:.1f} min")
    print(f"  Forecast records: {len(forecasts_df):,} rows")
    return forecasts_df


print("\n--- Model 1: Prophet ---")
daily_data = prepare_prophet_data(transactions)
print(f"Aggregated to {len(daily_data):,} daily store-product records")

forecasts = train_prophet_models(daily_data, top_n=args.prophet_top)

# Save forecasts (used as features in Model 2 + at inference time)
forecasts_path = os.path.join(MODELS_DIR, "forecasts_aggregated.csv")
forecasts.to_csv(forecasts_path, index=False)
print(f"Saved forecasts -> {forecasts_path}")

# ---------------------------------------------------------------------------
# Step 3 — Feature engineering (mirrors notebook cells 13 exactly)
# ---------------------------------------------------------------------------
print("\n--- Model 2: Feature engineering ---")

# -- Temporal features --
print("  Computing temporal features...")
recent_cutoff = transactions["timestamp"].max() - pd.Timedelta(days=30)
recent_sales = transactions[transactions["timestamp"] >= recent_cutoff]
historical_sales = transactions[transactions["timestamp"] < recent_cutoff]

recent_velocity = (
    recent_sales.groupby(["store_id", "product_id"])
    .agg({"quantity": ["sum", "count", "mean", "std"]})
    .reset_index()
)
recent_velocity.columns = [
    "store_id", "product_id",
    "recent_qty", "recent_txns", "recent_avg", "recent_std",
]

historical_velocity = (
    historical_sales.groupby(["store_id", "product_id"])
    .agg({"quantity": ["sum", "count", "mean"]})
    .reset_index()
)
historical_velocity.columns = [
    "store_id", "product_id",
    "historical_qty", "historical_txns", "historical_avg",
]

last_sale = (
    transactions.groupby(["store_id", "product_id"])["timestamp"]
    .max()
    .reset_index()
)
last_sale["days_since_last_sale"] = (
    transactions["timestamp"].max() - last_sale["timestamp"]
).dt.days

temporal = recent_velocity.merge(
    historical_velocity, on=["store_id", "product_id"], how="outer"
)
temporal = temporal.merge(
    last_sale[["store_id", "product_id", "days_since_last_sale"]],
    on=["store_id", "product_id"],
    how="left",
)
temporal = temporal.fillna(0)

temporal["velocity_trend"] = temporal["recent_avg"] / (temporal["historical_avg"] + 0.1)
temporal["sales_volatility"] = temporal["recent_std"] / (temporal["recent_avg"] + 0.1)
temporal["is_active"] = (temporal["days_since_last_sale"] <= 7).astype(int)
temporal["is_dormant"] = (temporal["days_since_last_sale"] > 90).astype(int)  # aligned with Dead rule threshold

# -- Product features --
print("  Computing product features...")
products["price_tier"] = pd.cut(
    products["retail_price"],
    bins=[-float("inf"), 3, 7, 15, float("inf")],
    labels=[0, 1, 2, 3],
).astype(float)
products["is_perishable"] = products["category"].isin(
    ["produce", "dairy", "meat", "bakery"]
).astype(int)
products["is_budget"] = (products["retail_price"] < 5).astype(int)
products["is_premium"] = (products["retail_price"] > 15).astype(int)

# -- Store features --
print("  Computing store features...")
store_stats = (
    transactions.groupby("store_id")
    .agg({"transaction_id": "nunique"})
    .reset_index()
)
store_stats.columns = ["store_id", "store_total_txns"]
store_stats["store_size_encoded"] = pd.cut(
    store_stats["store_total_txns"],
    bins=[-float("inf"), 200_000, 350_000, float("inf")],
    labels=[0, 1, 2],
).astype(float)

# -- Product-store interaction features --
print("  Computing product-store features...")
product_store = (
    transactions.groupby(["store_id", "product_id"])
    .agg({"quantity": ["sum", "count"]})
    .reset_index()
)
product_store.columns = ["store_id", "product_id", "total_sold", "num_sales"]
product_store["sales_rank_in_store"] = product_store.groupby("store_id")[
    "total_sold"
].rank(ascending=False, method="dense")
product_store["is_top_10_in_store"] = (
    product_store["sales_rank_in_store"] <= 10
).astype(int)
product_store["is_top_50_in_store"] = (
    product_store["sales_rank_in_store"] <= 50
).astype(int)

# -- Forecast-derived features --
print("  Computing forecast features...")
forecasts["forecast_acceleration"] = (forecasts["forecast_7d"] / 7) / (
    forecasts["forecast_30d"] / 30 + 0.1
)
forecasts["forecast_confidence_30d"] = (
    forecasts["forecast_30d_upper"] - forecasts["forecast_30d_lower"]
) / (forecasts["forecast_30d"] + 0.1)
forecasts["is_trending_up"] = (forecasts["forecast_acceleration"] > 1.1).astype(int)
forecasts["is_trending_down"] = (forecasts["forecast_acceleration"] < 0.9).astype(int)
forecasts["is_stable"] = (
    (forecasts["forecast_acceleration"] >= 0.9)
    & (forecasts["forecast_acceleration"] <= 1.1)
).astype(int)

# -- Merge everything onto stock --
print("  Merging feature sets...")
sf = stock.copy()
sf = sf.merge(forecasts, on=["store_id", "product_id"], how="left")
sf = sf.merge(
    products[
        [
            "product_id", "category", "retail_price",
            "price_tier", "is_perishable", "is_budget", "is_premium",
        ]
    ],
    on="product_id",
    how="left",
)
sf = sf.merge(temporal, on=["store_id", "product_id"], how="left")
sf = sf.merge(store_stats, on="store_id", how="left")
sf = sf.merge(product_store, on=["store_id", "product_id"], how="left")
# Never-sold stock rows: censor recency at the observed history length instead
# of letting fillna(0) claim they sold today.
history_days = (transactions["timestamp"].max() - transactions["timestamp"].min()).days
never_sold = sf["days_since_last_sale"].isna()
sf.loc[never_sold, "days_since_last_sale"] = no_sale_days(history_days)
sf["is_active"] = (sf["days_since_last_sale"] <= 7).astype(int)
sf["is_dormant"] = (sf["days_since_last_sale"] > 90).astype(int)
print(f"  Never-sold stock rows: {int(never_sold.sum())} (recency set to {history_days} days)")
sf = sf.fillna(0)

# -- Derived features (used for both labeling and training) --
# The shared helper is also used by app.py, including its fallback from a
# missing Prophet forecast to recent observed demand.
policy_features = sf.apply(
    lambda row: pd.Series(
        policy_metrics(
            stock_qty=row["stock_qty"],
            forecast_30d=row["forecast_30d"],
            forecast_7d=row["forecast_7d"],
            recent_qty=row["recent_qty"],
        )
    ),
    axis=1,
)
sf["coverage_30d"] = policy_features["coverage_30d_feat"]
sf["days_of_stock_30d"] = policy_features["days_of_stock_30d_feat"]
sf["stockout_risk_7d"] = policy_features["stockout_risk_7d"].astype(int)

# -- Explicit boundary features (exact metrics used in label rules → makes thresholds learnable) --
sf["coverage_30d_feat"]      = sf["coverage_30d"]          # same as above, named for clarity
sf["days_of_stock_30d_feat"] = sf["days_of_stock_30d"]     # same as above, named for clarity
sf["days_since_over_90"]     = (sf["days_since_last_sale"] > 90).astype(int)

# -- Stock value (clean, not a label-leaking feature) --
sf["stock_value"] = sf["stock_qty"] * sf["retail_price"]

# -- Price-velocity interaction --
sf["price_velocity_interaction"] = sf["retail_price"] * sf["velocity_trend"]

# -- Category encoding --
le_category = LabelEncoder()
sf["category_encoded"] = le_category.fit_transform(sf["category"].fillna("unknown"))

# ---------------------------------------------------------------------------
# Step 4 — Smart labeling (mirrors notebook exactly)
# ---------------------------------------------------------------------------
print("  Assigning labels...")
sf["label"] = sf.apply(stock_policy_label, axis=1)

print("\n  Label distribution:")
for label, count in sf["label"].value_counts().items():
    pct = count / len(sf) * 100
    print(f"    {label:8s}: {count:5d} ({pct:5.1f}%)")

# ---------------------------------------------------------------------------
# Step 5 — Train ensemble (41 features for policy imitation)
# ---------------------------------------------------------------------------
FEATURE_COLS = [
    # Stock
    "stock_qty", "stock_value",
    # Forecast
    "forecast_7d", "forecast_14d", "forecast_30d", "forecast_60d",
    "forecast_acceleration", "forecast_confidence_30d",
    "is_trending_up", "is_trending_down", "is_stable",
    # Temporal
    "days_since_last_sale", "velocity_trend", "sales_volatility",
    "is_active", "is_dormant",
    "recent_qty", "recent_txns", "recent_avg", "recent_std",
    "historical_qty", "historical_txns", "historical_avg",
    # Product
    "price_tier", "is_perishable",
    "is_budget", "is_premium", "category_encoded",
    "retail_price",
    # Store
    "store_size_encoded", "store_total_txns",
    # Product-store
    "sales_rank_in_store", "is_top_10_in_store", "is_top_50_in_store",
    "total_sold", "num_sales",
    # Interaction
    "price_velocity_interaction",
    # Explicit boundary features (exact metrics used in label rules)
    "coverage_30d_feat", "days_since_over_90",
    "days_of_stock_30d_feat", "stockout_risk_7d",
]

print(f"\n--- Model 2: Ensemble training on {len(FEATURE_COLS)} features (policy-generated labels) ---")

from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.utils.class_weight import compute_sample_weight

X = sf[FEATURE_COLS].fillna(0)
y = sf["label"]

groups = sf["product_id"]
train_idx, test_idx = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42).split(X, y, groups))
X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
if set(y_train) != set(y):
    raise ValueError("Product holdout leaves a class absent from training; collect more independent data.")

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled  = scaler.transform(X_test)
X_all_scaled   = scaler.transform(X)

print(f"  Building Random Forest ({args.rf_trees} trees)...")
rf = RandomForestClassifier(
    n_estimators=args.rf_trees, max_depth=6, class_weight="balanced",
    min_samples_leaf=5, max_features="sqrt",
    random_state=42, n_jobs=-1,
)

print(f"  Building Gradient Boosting ({args.gb_trees} trees)...")
gb = GradientBoostingClassifier(
    n_estimators=args.gb_trees, learning_rate=0.05, max_depth=2,
    subsample=0.8, min_samples_leaf=3,
    random_state=42,
)

print(f"  Building XGBoost ({args.xgb_trees} trees)...")
xgb = XGBClassifier(
    n_estimators=args.xgb_trees, max_depth=3, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8, min_child_weight=5, reg_lambda=5,
    random_state=42, n_jobs=-1, eval_metric="mlogloss",
)

ensemble = VotingClassifier(
    estimators=[("rf", rf), ("gb", gb), ("xgb", xgb)],
    voting="soft",
    n_jobs=-1,
)

# Validation uses only the training partition. Products never cross folds.
print("\n  Running product-grouped validation on training partition...")
cv = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=42)
t0 = time.time()
validation = cross_validate(
    PolicyAugmentedClassifier(clone(ensemble)),
    X_train, y_train, groups=groups.iloc[train_idx], cv=cv,
    scoring={"macro_f1": "f1_macro", "accuracy": "accuracy"},
    return_train_score=True, return_estimator=True, return_indices=True,
    error_score="raise", n_jobs=1,
)
cv_scores = validation["test_accuracy"]
print("  Validation macro F1:", validation["test_macro_f1"].tolist())

# --- Final fit on full training set with balanced sample weights ---
print("\n  Fitting final model on train split (balanced sample weights)...")
t1 = time.time()
augmented_model = PolicyAugmentedClassifier(ensemble).fit(X_train, y_train)
ensemble = augmented_model.model_
scaler = augmented_model.scaler_
X_train_scaled = scaler.transform(X_train)
X_test_scaled = scaler.transform(X_test)
fit_elapsed = (time.time() - t1) / 60

y_pred   = ensemble.predict(X_test_scaled)
accuracy = accuracy_score(y_test, y_pred)
total_elapsed = (time.time() - t0) / 60

print(f"\n  Hold-out accuracy : {accuracy:.2%}")
print(f"  CV accuracy       : {cv_scores.mean():.2%} ± {cv_scores.std():.2%}")
print(f"  Total time        : {total_elapsed:.1f} min")
print(f"\n{classification_report(y_test, y_pred)}")

# This measures agreement with rule-generated labels, not business ground truth.
labels = sorted(y.unique())

# Permutation importance on each grouped validation fold (held-out rows only).
# Impurity importance from one tree model is biased toward continuous,
# correlated features, so it is no longer the reported ranking.
from sklearn.inspection import permutation_importance
print("\n  Permutation importance on grouped validation folds...")
perm = []
for est, val_idx in zip(validation["estimator"], validation["indices"]["test"]):
    r = permutation_importance(est, X_train.iloc[val_idx], y_train.iloc[val_idx],
                               scoring="f1_macro", n_repeats=10, random_state=42, n_jobs=1)
    perm.append(r.importances_mean)
perm = np.mean(perm, axis=0)

# Repeated product-grouped CV over all rows gives a less fragile estimate than
# one 35-row holdout that has already been inspected.
def grouped_oof(columns, seeds=(0, 1, 2, 3, 4)):
    scores, pooled_true, pooled_pred = [], [], []
    for seed in seeds:
        folds = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=seed)
        pred = pd.Series(index=y.index, dtype=object)
        for tr, te in folds.split(X, y, groups):
            m = PolicyAugmentedClassifier(clone(ensemble_template), columns=columns).fit(X.iloc[tr], y.iloc[tr])
            pred.iloc[te] = m.predict(X.iloc[te])
        scores.append(f1_score(y, pred, average="macro", labels=labels, zero_division=0))
        pooled_true.append(y.to_numpy()); pooled_pred.append(pred.to_numpy())
    t, p = np.concatenate(pooled_true), np.concatenate(pooled_pred)
    rng = np.random.default_rng(42); n = len(y)
    boot = [f1_score(t[i], p[i], average="macro", labels=labels, zero_division=0)
            for i in (rng.integers(0, len(t), len(t)) for _ in range(1000))]
    return {"per_repeat_macro_f1": scores, "mean": float(np.mean(scores)),
            "ci95": [float(np.quantile(boot, .025)), float(np.quantile(boot, .975))],
            "confusion_matrix": confusion_matrix(t, p, labels=labels).tolist(),
            "classification_report": classification_report(t, p, labels=labels, output_dict=True, zero_division=0)}

ensemble_template = VotingClassifier(estimators=[("rf", rf), ("gb", gb), ("xgb", xgb)], voting="soft", n_jobs=-1)
# Target-leakage check: the label is a fixed function of these inputs.
RULE_INPUTS = ["coverage_30d_feat", "days_of_stock_30d_feat", "stockout_risk_7d", "days_since_over_90", "is_dormant"]
print("  Repeated grouped CV (5x3), all features...")
repeated_full = grouped_oof(None)
print("  Repeated grouped CV (5x3), without the rule's own inputs...")
repeated_ablation = grouped_oof([c for c in FEATURE_COLS if c not in RULE_INPUTS])
print("   full:", round(repeated_full["mean"], 3), repeated_full["ci95"],
      " no-rule-inputs:", round(repeated_ablation["mean"], 3), repeated_ablation["ci95"])
baseline = DummyClassifier(strategy="most_frequent").fit(X_train, y_train)
metrics = {
    "training_only_synthetic_rows": augmented_model.synthetic_rows_,
    "augmentation": "fold-local stock/demand/recency policy simulations; not independent evidence",
    "evaluation_status": "development re-evaluation; historical holdout has already been inspected",
    "target": "policy-generated stock labels; not independently annotated outcomes",
    "split": "product-group holdout; grouped CV on training partition only",
    "seed": 42, "train_rows": len(train_idx), "test_rows": len(test_idx),
    "train_products": sorted(groups.iloc[train_idx].unique().tolist()),
    "test_products": sorted(groups.iloc[test_idx].unique().tolist()),
    "macro_f1": f1_score(y_test, y_pred, average="macro", labels=labels, zero_division=0),
    "weighted_f1": f1_score(y_test, y_pred, average="weighted", zero_division=0),
    "train_macro_f1": f1_score(y_train, ensemble.predict(X_train_scaled), average="macro", labels=labels, zero_division=0),
    "baseline_macro_f1": f1_score(y_test, baseline.predict(X_test), average="macro", labels=labels, zero_division=0),
    "validation_macro_f1": validation["test_macro_f1"].tolist(),
    "validation_train_macro_f1": validation["train_macro_f1"].tolist(),
    "labels": labels, "confusion_matrix": confusion_matrix(y_test, y_pred, labels=labels).tolist(),
    "classification_report": classification_report(y_test, y_pred, labels=labels, output_dict=True, zero_division=0),
    "repeated_grouped_cv_5x3": repeated_full,
    "leakage_ablation_without_rule_inputs": {"removed": RULE_INPUTS, **repeated_ablation},
    "never_sold_rows": int(never_sold.sum()),
    "limitations": ["Only three stores", "One stock snapshot", "Forecast accuracy needs temporal backtesting", "Rule agreement is not business effectiveness"],
}
with open(os.path.join(MODELS_DIR, "evaluation.json"), "w") as f:
    json.dump(metrics, f, indent=2)
sf.to_csv(os.path.join(MODELS_DIR, "training_features.csv"), index=False)

# Reported ranking: mean drop in held-out macro F1 when a feature is shuffled.
# RF impurity importance is kept as a second column for comparison only.
rf_model = ensemble.named_estimators_["rf"]
feature_importance = (
    pd.DataFrame({"feature": FEATURE_COLS, "importance": perm,
                  "method": "permutation_f1_drop_grouped_cv",
                  "rf_impurity_importance": rf_model.feature_importances_})
    .sort_values("importance", ascending=False)
)
print("Top 10 features:")
for _, row in feature_importance.head(10).iterrows():
    print(f"  {row['feature']:30s}: {row['importance']:.4f}")

# ---------------------------------------------------------------------------
# Step 6 — Save all artifacts
# ---------------------------------------------------------------------------
print("\n--- Saving models ---")

joblib.dump(ensemble, os.path.join(MODELS_DIR, "ensemble.pkl"))
print("  Saved: ensemble.pkl")

joblib.dump(scaler, os.path.join(MODELS_DIR, "scaler.pkl"))
print("  Saved: scaler.pkl")

joblib.dump(le_category, os.path.join(MODELS_DIR, "label_encoder.pkl"))
print("  Saved: label_encoder.pkl")

# Save updated forecasts with derived forecast features
# When these forecasts were made; the API stops trusting them after FORECAST_MAX_AGE_DAYS.
forecasts["generated_at"] = pd.Timestamp.now(tz="UTC").isoformat()
forecasts.to_csv(os.path.join(MODELS_DIR, "forecasts_aggregated.csv"), index=False)
print("  Saved: forecasts_aggregated.csv (with acceleration + trend flags)")

# Save feature column order — required for inference to match training order
with open(os.path.join(MODELS_DIR, "feature_cols.json"), "w") as f:
    json.dump(FEATURE_COLS, f, indent=2)
print("  Saved: feature_cols.json")

# Save category classes so inference can handle unseen categories
with open(os.path.join(MODELS_DIR, "category_classes.json"), "w") as f:
    json.dump(list(le_category.classes_), f, indent=2)
print("  Saved: category_classes.json")

# Save store stats (used to compute store_size_encoded at inference)
store_stats.to_csv(os.path.join(MODELS_DIR, "store_stats.csv"), index=False)
print("  Saved: store_stats.csv")

# Save product-store ranks (used for sales_rank_in_store at inference)
product_store.to_csv(os.path.join(MODELS_DIR, "product_store_ranks.csv"), index=False)
print("  Saved: product_store_ranks.csv")

feature_importance.to_csv(
    os.path.join(MODELS_DIR, "feature_importance.csv"), index=False
)
print("  Saved: feature_importance.csv")

print("\nTraining complete.")
print(f"All artifacts in: {MODELS_DIR}")
