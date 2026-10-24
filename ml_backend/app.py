"""
app.py — Jiran ML Prediction API

Start with:
    cd testing_ML/
    uvicorn app:app --reload --port 8001

Requires trained artifacts in saved_models/ (run train.py first).

Endpoints:
    GET  /                  health check
    POST /predict-stock     batch stock status predictions
    POST /recommend         predictions + transfer & restock recommendations
    GET  /feature-importance top features from training

Supabase watcher starts automatically on server startup.
"""

import json
import logging
import os
from collections import defaultdict
from contextlib import asynccontextmanager

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "saved_models")

# ---------------------------------------------------------------------------
# Load artifacts at startup
# ---------------------------------------------------------------------------
def load_artifact(name):
    path = os.path.join(MODELS_DIR, name)
    if not os.path.exists(path):
        raise RuntimeError(
            f"Missing artifact: {path}\n"
            "Run 'python train.py' first to train and save models."
        )
    return joblib.load(path)

def load_json(name):
    path = os.path.join(MODELS_DIR, name)
    if not os.path.exists(path):
        raise RuntimeError(f"Missing artifact: {path}")
    with open(path) as f:
        return json.load(f)

def load_csv(name):
    path = os.path.join(MODELS_DIR, name)
    if not os.path.exists(path):
        raise RuntimeError(f"Missing artifact: {path}")
    return pd.read_csv(path)

AI_AVAILABLE = False
AI_UNAVAILABLE_REASON = "AI artifacts are not validated in this environment."
ensemble = scaler = le_category = None
FEATURE_COLS = []
CATEGORY_CLASSES = []
forecasts_df = pd.DataFrame()
store_stats_df = pd.DataFrame()
product_store_df = pd.DataFrame()
feature_importance = pd.DataFrame()

try:
    ensemble = load_artifact("ensemble.pkl")
    scaler = load_artifact("scaler.pkl")
    le_category = load_artifact("label_encoder.pkl")
    FEATURE_COLS = load_json("feature_cols.json")
    CATEGORY_CLASSES = load_json("category_classes.json")
    forecasts_df = load_csv("forecasts_aggregated.csv").set_index(["store_id", "product_id"])
    store_stats_df = load_csv("store_stats.csv").set_index("store_id")
    product_store_df = load_csv("product_store_ranks.csv").set_index(["store_id", "product_id"])
    feature_importance = load_csv("feature_importance.csv")
    AI_AVAILABLE = True
    AI_UNAVAILABLE_REASON = None
except Exception as exc:
    # The operational API must remain available even when legacy pickles are
    # incompatible. This is an explicit null state, not a fabricated fallback.
    AI_UNAVAILABLE_REASON = f"{type(exc).__name__}: {exc}"
    logging.getLogger("app").warning("AI disabled: %s", AI_UNAVAILABLE_REASON)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Watcher is opt-in during recovery so an unreachable legacy backend cannot
    # block the API or repeatedly transmit stale credentials.
    _watcher_stop = None
    if os.getenv("ENABLE_SUPABASE_WATCHER", "false").lower() == "true":
        try:
            from supabase_watcher import start_watcher_thread
            _watcher_stop = start_watcher_thread()
            logging.getLogger("app").info("Supabase watcher thread started.")
        except Exception as exc:
            logging.getLogger("app").warning("Supabase watcher disabled: %s", exc)
    yield
    # ── Shutdown ─────────────────────────────────────────────────────────────
    if _watcher_stop:
        _watcher_stop.set()


app = FastAPI(
    title="Jiran ML API",
    description="Stock status prediction using ensemble (RF + GB + XGB) model",
    version="2222",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class ProductInput(BaseModel):
    """
    One product-store record. Fields match what Supabase can provide.
    All sales aggregations can be computed via a Supabase RPC function.
    """
    store_id:    str
    product_id:  str
    product_name: Optional[str] = ""
    category:    str

    # From stock table
    stock_qty:   float

    # From products table
    retail_price:    float

    # Aggregated from transactions (last 30 days)
    recent_qty:   float = 0.0
    recent_txns:  float = 0.0
    recent_avg:   float = 0.0
    recent_std:   float = 0.0

    # Aggregated from transactions (older than 30 days)
    historical_qty:   float = 0.0
    historical_txns:  float = 0.0
    historical_avg:   float = 0.0

    # All-time totals
    total_sold: float = 0.0
    num_sales:  float = 0.0

    # Days since last transaction
    days_since_last_sale: float = 0.0

    # Total transactions for this store (used to size the store)
    store_total_txns: float = Field(
        0.0,
        description="Total transactions in this store. Leave 0 to use training-time value.",
    )


class PredictRequest(BaseModel):
    products: List[ProductInput]


# ---------------------------------------------------------------------------
# Dataflow JSON schema — matches structured_inventory_from_supabase.json
# ---------------------------------------------------------------------------

class InventoryRecord(BaseModel):
    """Flat record produced by the dataflow ETL (export_structured_inventory_from_supabase.py)."""
    store_id:             str
    product_id:           str
    category:             str
    stock_qty:            float
    retail_price:         float
    recent_qty:           float = 0.0
    recent_txns:          float = 0.0
    days_since_last_sale: Optional[float] = 0.0
    product_name:         Optional[str]   = ""


def _inventory_to_product_input(r: InventoryRecord) -> ProductInput:
    """Map a dataflow InventoryRecord → ProductInput for the ML pipeline."""
    return ProductInput(
        store_id=r.store_id,
        product_id=r.product_id,
        product_name=r.product_name or "",
        category=r.category,
        stock_qty=r.stock_qty,
        retail_price=r.retail_price,
        recent_qty=r.recent_qty,
        recent_txns=r.recent_txns,
        days_since_last_sale=r.days_since_last_sale or 0.0,
    )


class InventoryRequest(BaseModel):
    inventory: List[InventoryRecord]


class ProductPrediction(BaseModel):
    store_id:    str
    product_id:  str
    product_name: str
    prediction:  str      # Low | Optimum | Excess | Slow | Dead
    confidence:  float    # max class probability
    probabilities: dict   # all 5 class probabilities


class PredictResponse(BaseModel):
    count:   int
    results: List[ProductPrediction]


class TransferRecommendation(BaseModel):
    from_store:        str
    to_store:          str
    product_id:        str
    product_name:      str
    transfer_qty:      int
    from_label:        str    # label of sending store
    to_label:          str    # label of receiving store
    from_stock_before: float
    from_stock_after:  float
    to_stock_before:   float
    to_stock_after:    float
    from_coverage_after: float   # coverage_30d of sender after transfer
    to_coverage_after:   float   # coverage_30d of receiver after transfer
    demand_30d:        float     # estimated 30-day demand (used for coverage calc)
    transfer_type:     str       # "macro" (>50% of need) or "micro" (partial)
    transfer_mode:     str       # "single" = 1 donor covers all | "combined" = multiple donors
    group_id:          str       # links transfers serving the same receiver


class RestockRecommendation(BaseModel):
    store_id:      str
    product_id:    str
    product_name:  str
    restock_qty:   int
    current_stock: float
    target_stock:  float
    demand_30d:    float
    reason:        str


class RecommendSummary(BaseModel):
    total_products:   int
    total_stores:     int
    label_counts:     Dict[str, int]
    transfer_count:   int
    restock_count:    int
    products_needing_action: int
    total_units_to_transfer: int
    total_units_to_restock:  int


class RecommendResponse(BaseModel):
    predictions: List[ProductPrediction]
    transfers:   List[TransferRecommendation]
    restocks:    List[RestockRecommendation]
    summary:     RecommendSummary


# ---------------------------------------------------------------------------
# Recommendation constants
# ---------------------------------------------------------------------------

# After a transfer, target coverage for the receiving store
OPTIMUM_TARGET_COVERAGE = 1.5   # 1.5x 30-day demand = healthy optimum

# Minimum coverage a sending store must retain after donating stock
OPTIMUM_MIN_COVERAGE_AFTER = 0.9  # keep at least ~27 days of demand

# Labels that can donate stock
DONOR_LABELS   = {"Excess", "Slow", "Dead"}

# Labels that need to receive stock
RECEIVE_LABELS = {"Low"}


# ---------------------------------------------------------------------------
# Feature engineering helpers (must mirror train.py exactly)
# ---------------------------------------------------------------------------

def encode_category(category: str) -> float:
    """Encode a category using the fitted LabelEncoder. Unknown → -1."""
    cat = str(category).lower().strip() if category else "unknown"
    if cat in CATEGORY_CLASSES:
        return float(le_category.transform([cat])[0])
    return -1.0


def get_forecast_features(store_id: str, product_id: str) -> dict:
    """
    Look up Prophet forecast features from saved forecasts.
    Returns zeros if this store-product pair wasn't in the top-100 trained set.
    """
    key = (store_id, product_id)
    if key in forecasts_df.index:
        row = forecasts_df.loc[key]
        return {
            "forecast_7d":  float(row.get("forecast_7d",  0)),
            "forecast_14d": float(row.get("forecast_14d", 0)),
            "forecast_30d": float(row.get("forecast_30d", 0)),
            "forecast_60d": float(row.get("forecast_60d", 0)),
            "forecast_acceleration":    float(row.get("forecast_acceleration",    1.0)),
            "forecast_confidence_30d":  float(row.get("forecast_confidence_30d",  0.0)),
            "is_trending_up":   int(row.get("is_trending_up",   0)),
            "is_trending_down": int(row.get("is_trending_down", 0)),
            "is_stable":        int(row.get("is_stable",        1)),
        }
    # Fallback: estimate forecast from recent sales velocity
    return {
        "forecast_7d":  0.0,
        "forecast_14d": 0.0,
        "forecast_30d": 0.0,
        "forecast_60d": 0.0,
        "forecast_acceleration":   1.0,
        "forecast_confidence_30d": 0.0,
        "is_trending_up":   0,
        "is_trending_down": 0,
        "is_stable":        1,
    }


def get_store_features(store_id: str, store_total_txns_input: float) -> dict:
    """
    Look up store size from training data, or use caller-provided total if given.
    """
    if store_id in store_stats_df.index:
        row = store_stats_df.loc[store_id]
        return {
            "store_total_txns":   float(row["store_total_txns"]),
            "store_size_encoded": float(row["store_size_encoded"]),
        }
    # Derive from caller-provided total
    total = store_total_txns_input
    if total <= 200_000:
        size_enc = 0.0
    elif total <= 350_000:
        size_enc = 1.0
    else:
        size_enc = 2.0
    return {"store_total_txns": total, "store_size_encoded": size_enc}


def get_product_store_features(store_id: str, product_id: str, total_sold: float, num_sales: float) -> dict:
    """
    Look up product-store rank from training data.
    Falls back to rank 999 (not top-10 or top-50) for unseen pairs.
    """
    key = (store_id, product_id)
    if key in product_store_df.index:
        row = product_store_df.loc[key]
        return {
            "sales_rank_in_store": float(row["sales_rank_in_store"]),
            "is_top_10_in_store":  int(row["is_top_10_in_store"]),
            "is_top_50_in_store":  int(row["is_top_50_in_store"]),
            "total_sold":          float(row["total_sold"]),
            "num_sales":           float(row["num_sales"]),
        }
    return {
        "sales_rank_in_store": 999.0,
        "is_top_10_in_store":  0,
        "is_top_50_in_store":  0,
        "total_sold":          total_sold,
        "num_sales":           num_sales,
    }


def build_feature_row(p: ProductInput) -> dict:
    """Convert a ProductInput into the 41-feature vector used during training."""

    # -- Derived product features --
    retail   = p.retail_price
    category = str(p.category).lower().strip()

    if retail <= 3:
        price_tier = 0.0
    elif retail <= 7:
        price_tier = 1.0
    elif retail <= 15:
        price_tier = 2.0
    else:
        price_tier = 3.0

    is_perishable = int(category in {"produce", "dairy", "meat", "bakery"})
    is_budget     = int(retail < 5)
    is_premium    = int(retail > 15)

    # -- Temporal derived features --
    velocity_trend   = p.recent_avg / (p.historical_avg + 0.1)
    sales_volatility = p.recent_std  / (p.recent_avg   + 0.1)
    is_active  = int(p.days_since_last_sale <= 7)
    is_dormant = int(p.days_since_last_sale > 90)  # aligned with Dead rule threshold

    # -- Stock value --
    stock_value = p.stock_qty * retail

    # -- Interaction --
    price_velocity_interaction = retail * velocity_trend

    # -- Explicit boundary features (computed after forecast lookup below) --
    # coverage_30d_feat and days_since_over_90 are added after fc is known

    # -- Forecast features (from saved Prophet outputs) --
    fc = get_forecast_features(p.store_id, p.product_id)

    # -- Explicit boundary features (mirrors label-rule metrics exactly) --
    forecast_30d = fc.get("forecast_30d", 0)
    forecast_7d  = fc.get("forecast_7d",  0)
    # If no Prophet forecast, fall back to recent_qty as 30d demand proxy
    demand_30d_est = forecast_30d if forecast_30d > 0 else max(p.recent_qty, 1.0)
    demand_7d_est  = forecast_7d  if forecast_7d  > 0 else max(p.recent_qty / 4.0, 1.0)

    coverage_30d_feat      = p.stock_qty / (demand_30d_est + 1)
    days_of_stock_30d_feat = p.stock_qty / (demand_30d_est / 30 + 0.1)
    stockout_risk_7d       = int(p.stock_qty < demand_7d_est)
    days_since_over_90     = int(p.days_since_last_sale > 90)

    # -- Store features --
    sf = get_store_features(p.store_id, p.store_total_txns)

    # -- Product-store features --
    ps = get_product_store_features(p.store_id, p.product_id, p.total_sold, p.num_sales)

    row = {
        # Stock
        "stock_qty":   p.stock_qty,
        "stock_value": stock_value,
        # Forecast
        **fc,
        # Temporal
        "days_since_last_sale": p.days_since_last_sale,
        "velocity_trend":       velocity_trend,
        "sales_volatility":     sales_volatility,
        "is_active":            is_active,
        "is_dormant":           is_dormant,
        "recent_qty":           p.recent_qty,
        "recent_txns":          p.recent_txns,
        "recent_avg":           p.recent_avg,
        "recent_std":           p.recent_std,
        "historical_qty":       p.historical_qty,
        "historical_txns":      p.historical_txns,
        "historical_avg":       p.historical_avg,
        # Product
        "price_tier":        price_tier,
        "is_perishable":     is_perishable,
        "is_budget":         is_budget,
        "is_premium":        is_premium,
        "category_encoded":  encode_category(p.category),
        "retail_price":      retail,
        # Store
        **sf,
        # Product-store
        **ps,
        # Interaction
        "price_velocity_interaction": price_velocity_interaction,
        # Explicit boundary features
        "coverage_30d_feat":      coverage_30d_feat,
        "days_since_over_90":     days_since_over_90,
        "days_of_stock_30d_feat": days_of_stock_30d_feat,
        "stockout_risk_7d":       stockout_risk_7d,
    }
    return row


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def health():
    return {
        "status": "ok",
        "ai_available": AI_AVAILABLE,
        "ai_status": "ready" if AI_AVAILABLE else "null",
        "ai_unavailable_reason": None if AI_AVAILABLE else AI_UNAVAILABLE_REASON,
        "model": "Jiran ML v2222 (RF + GB + XGB ensemble)" if AI_AVAILABLE else None,
        "features": len(FEATURE_COLS),
        "labels": ["Dead", "Excess", "Low", "Optimum", "Slow"] if AI_AVAILABLE else [],
    }


@app.post("/predict-stock", response_model=PredictResponse)
def predict_stock(req: PredictRequest):
    if not AI_AVAILABLE:
        raise HTTPException(status_code=503, detail="AI pipeline is intentionally null until artifacts and data are validated.")
    if not req.products:
        raise HTTPException(status_code=422, detail="products list is empty")
    try:
        results = _run_predictions(req.products)
        return PredictResponse(count=len(results), results=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _run_predictions(products: List[ProductInput]):
    """Shared prediction logic used by both /predict-stock and /recommend."""
    rows = [build_feature_row(p) for p in products]
    X = pd.DataFrame(rows, columns=FEATURE_COLS).fillna(0)
    X_scaled = scaler.transform(X)
    preds = ensemble.predict(X_scaled)
    proba = ensemble.predict_proba(X_scaled)
    class_labels = ensemble.classes_

    results = []
    for i, p in enumerate(products):
        prob_dict = {
            label: round(float(proba[i][j]), 4)
            for j, label in enumerate(class_labels)
        }
        results.append(ProductPrediction(
            store_id=p.store_id,
            product_id=p.product_id,
            product_name=p.product_name or "",
            prediction=str(preds[i]),
            confidence=round(float(proba[i].max()), 4),
            probabilities=prob_dict,
        ))
    return results


def _demand_30d(p: ProductInput) -> float:
    """
    Best estimate of 30-day demand for a product-store pair.
    Uses Prophet forecast if available, falls back to recent_qty (actual sales).
    """
    fc = get_forecast_features(p.store_id, p.product_id)
    if fc["forecast_30d"] > 0:
        return fc["forecast_30d"]
    # Fallback: use last 30 days of actual sales
    return max(p.recent_qty, 1.0)


def _calc_available(donor: dict) -> float:
    """How many units a donor store can safely give without falling below health threshold."""
    if donor["label"] == "Dead" or donor["demand_30d"] <= 0:
        return donor["sim_stock"]
    elif donor["label"] == "Excess":
        return max(0.0, donor["sim_stock"] - OPTIMUM_MIN_COVERAGE_AFTER * donor["demand_30d"])
    else:  # Slow
        return max(0.0, donor["sim_stock"] - OPTIMUM_TARGET_COVERAGE * donor["demand_30d"])


def _make_transfer(donor: dict, recv: dict, qty: int,
                   mode: str, group_id: str, product_id: str) -> TransferRecommendation:
    """Build a TransferRecommendation and update simulated stock in-place."""
    from_after = donor["sim_stock"] - qty
    to_after   = recv["sim_stock"]  + qty
    from_cov   = round(from_after / (donor["demand_30d"] + 0.1), 2)
    to_cov     = round(to_after   / (recv["demand_30d"]  + 0.1), 2)
    ttype      = "macro" if qty >= recv["needed"] * 0.5 else "micro"

    t = TransferRecommendation(
        from_store=donor["store_id"],
        to_store=recv["store_id"],
        product_id=product_id,
        product_name=recv["product_name"],
        transfer_qty=qty,
        from_label=donor["label"],
        to_label=recv["label"],
        from_stock_before=round(donor["sim_stock"], 1),
        from_stock_after=round(from_after, 1),
        to_stock_before=round(recv["sim_stock"], 1),
        to_stock_after=round(to_after, 1),
        from_coverage_after=from_cov,
        to_coverage_after=to_cov,
        demand_30d=round(recv["demand_30d"], 1),
        transfer_type=ttype,
        transfer_mode=mode,
        group_id=group_id,
    )

    # Update simulation state
    donor["sim_stock"] -= qty
    donor["available"] -= qty
    recv["sim_stock"]  += qty

    return t


def _compute_recommendations(
    products: List[ProductInput],
    predictions: List[ProductPrediction],
):
    """
    Core recommendation engine.

    Decision logic per receiver store:

      1. SINGLE-STORE CHECK
         Can any one donor fully cover the receiver's need on its own?
         If yes → use the best single donor (prefer Excess > Dead > Slow,
         then most available within tier). Clean, minimal logistics.

      2. COMBINED-STORE FALLBACK
         No single donor can cover the full need → draw from multiple donors
         in order of availability (largest surplus first) until the need is met.
         All transfers in this group share a group_id so the caller can display
         them as one coordinated action.

      3. RESTOCK
         If even all donors combined can't fill the gap → issue a restock
         recommendation for the remaining shortfall.
    """

    pred_lookup = {(r.store_id, r.product_id): r for r in predictions}

    by_product: dict = defaultdict(list)
    for p in products:
        by_product[p.product_id].append(p)

    transfers: List[TransferRecommendation] = []
    restocks:  List[RestockRecommendation]  = []
    group_counter = [0]

    def next_group(product_id, to_store):
        group_counter[0] += 1
        return f"{product_id}→{to_store}#{group_counter[0]}"

    # Donor tier priority: Excess first (most obligated to give), then Dead, then Slow
    DONOR_TIER = {"Excess": 0, "Dead": 1, "Slow": 2}

    for product_id, prod_list in by_product.items():

        stores = []
        for p in prod_list:
            key  = (p.store_id, p.product_id)
            pred = pred_lookup[key]
            d30  = _demand_30d(p)
            stores.append({
                "store_id":    p.store_id,
                "product_id":  product_id,
                "product_name": p.product_name or "",
                "stock_qty":   p.stock_qty,
                "demand_30d":  d30,
                "label":       pred.prediction,
                "p":           p,
                "sim_stock":   p.stock_qty,
                "available":   0.0,
            })

        donors    = [s for s in stores if s["label"] in DONOR_LABELS]
        receivers = [s for s in stores if s["label"] in RECEIVE_LABELS]

        if not receivers:
            continue

        # Calculate how much each receiver needs
        for r in receivers:
            r["target_stock"] = OPTIMUM_TARGET_COVERAGE * r["demand_30d"]
            r["needed"]       = max(0.0, r["target_stock"] - r["sim_stock"])

        # Calculate available from each donor (recalculated fresh per receiver
        # to reflect prior simulation state correctly)
        for d in donors:
            d["available"] = _calc_available(d)

        # Sort receivers: most urgent first (lowest current coverage)
        receivers.sort(key=lambda x: x["sim_stock"] / (x["demand_30d"] + 0.1))

        for recv in receivers:
            needed = recv["needed"]
            if needed <= 0:
                continue

            # Refresh available for all donors (sim_stock may have changed)
            for d in donors:
                d["available"] = _calc_available(d)

            # Sort donors: tier first (Excess→Dead→Slow), then most available
            donors.sort(key=lambda x: (DONOR_TIER.get(x["label"], 9), -x["available"]))

            # ── Decision: can a single donor cover the full need? ──────────
            single_donor = next(
                (d for d in donors if d["available"] >= needed), None
            )

            if single_donor:
                # SINGLE-STORE transfer
                qty = max(1, round(needed))
                gid = next_group(product_id, recv["store_id"])
                transfers.append(
                    _make_transfer(single_donor, recv, qty, "single", gid, product_id)
                )
                recv["sim_stock"] += qty   # already updated inside _make_transfer
                continue

            # ── Fallback: COMBINED transfer from multiple donors ──────────
            gid          = next_group(product_id, recv["store_id"])
            still_needed = needed

            for donor in donors:
                if still_needed <= 0:
                    break
                if donor["available"] <= 0:
                    continue

                qty = max(1, round(min(still_needed, donor["available"])))
                transfers.append(
                    _make_transfer(donor, recv, qty, "combined", gid, product_id)
                )
                still_needed -= qty

            # Anything still unmet → restock
            if still_needed > 1:
                restocks.append(RestockRecommendation(
                    store_id=recv["store_id"],
                    product_id=product_id,
                    product_name=recv["product_name"],
                    restock_qty=round(still_needed),
                    current_stock=round(recv["p"].stock_qty, 1),
                    target_stock=round(recv["target_stock"], 1),
                    demand_30d=round(recv["demand_30d"], 1),
                    reason=(
                        "No donor stores available — order from supplier"
                        if not donors
                        else "Donor network insufficient — partial restock needed"
                    ),
                ))

    return transfers, restocks


@app.post("/recommend", response_model=RecommendResponse)
def recommend(req: PredictRequest):
    """
    Full recommendation pass:
    1. Runs ML predictions on all products.
    2. Computes transfer recommendations (multi-store, macro + micro).
    3. Computes restock recommendations for any remaining shortfalls.
    """
    if not AI_AVAILABLE:
        raise HTTPException(status_code=503, detail="AI pipeline is intentionally null until artifacts and data are validated.")
    if not req.products:
        raise HTTPException(status_code=422, detail="products list is empty")

    try:
        predictions = _run_predictions(req.products)
        transfers, restocks = _compute_recommendations(req.products, predictions)

        # Summary
        label_counts: Dict[str, int] = defaultdict(int)
        for r in predictions:
            label_counts[r.prediction] += 1

        products_needing_action = len({
            (r.store_id, r.product_id)
            for r in predictions
            if r.prediction in DONOR_LABELS | RECEIVE_LABELS
        })

        summary = RecommendSummary(
            total_products=len(set(p.product_id for p in req.products)),
            total_stores=len(set(p.store_id for p in req.products)),
            label_counts=dict(label_counts),
            transfer_count=len(transfers),
            restock_count=len(restocks),
            products_needing_action=products_needing_action,
            total_units_to_transfer=sum(t.transfer_qty for t in transfers),
            total_units_to_restock=sum(r.restock_qty for r in restocks),
        )

        return RecommendResponse(
            predictions=predictions,
            transfers=transfers,
            restocks=restocks,
            summary=summary,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/feature-importance")
def get_feature_importance(top_n: int = 20):
    if not AI_AVAILABLE:
        raise HTTPException(status_code=503, detail="AI pipeline is intentionally null until artifacts and data are validated.")
    rows = feature_importance.head(top_n).to_dict(orient="records")
    return {"top_n": top_n, "features": rows}
