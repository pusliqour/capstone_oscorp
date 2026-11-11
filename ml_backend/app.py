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
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict

import time
from stock_planning import stock_planning_matrix

from inventory_policy import (days_until_next_delivery, donor_reserve, in_stock_rate, policy_metrics,
                              receiver_target_stock, stock_policy_label_v2)

# Saved forecasts older than this are not used; the live 30-day rate from the
# request replaces them until the model is retrained ("unfrozen" forecasts).
FORECAST_MAX_AGE_DAYS = float(os.getenv("JIRAN_FORECAST_MAX_AGE_DAYS", "7"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.getenv("JIRAN_MODELS_DIR", os.path.join(BASE_DIR, "saved_models"))

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

@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    # Non-finite input values cannot themselves be serialized as JSON.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()
    ]})


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class ProductInput(BaseModel):
    model_config = {"allow_inf_nan": False}

    """
    One product-store record. Fields match what Supabase can provide.
    All sales aggregations can be computed via a Supabase RPC function.
    """
    store_id:    str
    product_id:  str
    product_name: Optional[str] = ""
    category:    str

    # From stock table
    stock_qty:   float = Field(..., ge=0, le=1e12)
    # From products table
    retail_price:    float = Field(..., ge=0, le=1e12)
    # Aggregated from transactions (last 30 days)
    recent_qty:   float = Field(0.0, ge=0, le=1e12)
    recent_txns:  float = Field(0.0, ge=0, le=1e12)
    recent_avg:   float = Field(0.0, ge=0, le=1e12)
    recent_std:   float = Field(0.0, ge=0, le=1e12)

    # Aggregated from transactions (older than 30 days)
    historical_qty:   float = Field(0.0, ge=0, le=1e12)
    historical_txns:  float = Field(0.0, ge=0, le=1e12)
    historical_avg:   float = Field(0.0, ge=0, le=1e12)

    # All-time totals
    total_sold: float = Field(0.0, ge=0, le=1e12)
    num_sales:  float = Field(0.0, ge=0, le=1e12)

    # Days since last transaction
    days_since_last_sale: float = Field(0.0, ge=0, le=1e12)

    # --- Optional inputs (12 Nov 2026). Leave them out and behaviour is unchanged. ---
    region: Optional[str] = Field(None, description="Neighbourhood/region. Transfers stay within one region.")
    age_days: Optional[float] = Field(None, ge=0, le=1e6, description="Days since this product was first stocked in this store. Under 28 = 'New'.")
    stockout_days_30d: Optional[float] = Field(None, ge=0, le=30, description="Days in the last 30 with zero stock (lost-sales correction).")
    on_order: Optional[float] = Field(None, ge=0, le=1e12, description="Units ordered from the supplier but not yet received.")
    lead_time_days: Optional[float] = Field(None, ge=0, le=365, description="Supplier delivery time in days.")
    days_to_next_order: Optional[float] = Field(None, ge=0, le=365, description="Days until this store next places a supplier order (default 7).")
    daily_sales: Optional[List[float]] = Field(None, max_length=730, description="Daily units sold, oldest first, ending today. Enables a fresh forecast.")
    daily_stock: Optional[List[float]] = Field(None, max_length=730, description="End-of-day stock aligned with daily_sales; marks stock-out days.")

    # Total transactions for this store (used to size the store)
    store_total_txns: float = Field(
        0.0, ge=0, le=1e12,
        description="Total transactions in this store. Leave 0 to use training-time value.",
    )


class PredictRequest(BaseModel):
    products: List[ProductInput] = Field(..., min_length=1, max_length=5000)

    @model_validator(mode="after")
    def unique_pairs(self):
        keys = [(p.store_id, p.product_id) for p in self.products]
        if len(keys) != len(set(keys)):
            raise ValueError("Each store/product pair must appear once per batch")
        return self


# ---------------------------------------------------------------------------
# Dataflow JSON schema — matches structured_inventory_from_supabase.json
# ---------------------------------------------------------------------------

class InventoryRecord(BaseModel):
    """Flat record produced by the dataflow ETL (export_structured_inventory_from_supabase.py)."""
    store_id:             str
    product_id:           str
    category:             str
    stock_qty:            float = Field(..., ge=0, le=1e12)
    retail_price:         float = Field(..., ge=0, le=1e12)
    recent_qty:           float = Field(0.0, ge=0, le=1e12)
    recent_txns:          float = Field(0.0, ge=0, le=1e12)
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
    confidence:  float    # ensemble support for the policy decision
    probabilities: dict   # all 5 class probabilities
    decision_source: str = "stock_policy"
    model_prediction: str
    demand_30d: float = 0.0
    demand_source: str = "observed_recent_sales"
    stock_plan: dict = Field(default_factory=dict)


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
# Recommendation constants live in transfer_policy.py (shared with the simulation)
# ---------------------------------------------------------------------------
from transfer_policy import DONOR_LABELS, RECEIVE_LABELS, plan_transfers  # noqa: E402


# ---------------------------------------------------------------------------
# Feature engineering helpers (must mirror train.py exactly)
# ---------------------------------------------------------------------------

def encode_category(category: str) -> float:
    """Encode a category using the fitted LabelEncoder. Unknown → -1."""
    cat = str(category).lower().strip() if category else "unknown"
    if cat in CATEGORY_CLASSES:
        return float(le_category.transform([cat])[0])
    return -1.0


def _forecast_age_days(row) -> float:
    stamp = row.get("generated_at") if hasattr(row, "get") else None
    if isinstance(stamp, str) and stamp:
        return (pd.Timestamp.now(tz="UTC") - pd.Timestamp(stamp)).total_seconds() / 86400
    path = os.path.join(MODELS_DIR, "forecasts_aggregated.csv")
    return (time.time() - os.path.getmtime(path)) / 86400 if os.path.exists(path) else float("inf")


def _rate_features(daily_rate: float, method: str, seven_day_rate: float | None = None) -> dict:
    r7 = daily_rate if seven_day_rate is None else seven_day_rate
    return {
        "forecast_method": method,
        "forecast_7d": 7 * r7, "forecast_14d": 14 * daily_rate,
        "forecast_30d": 30 * daily_rate, "forecast_60d": 60 * daily_rate,
        "forecast_acceleration": r7 / (daily_rate + 0.1),
        "forecast_confidence_30d": 0.0, "is_trending_up": 0, "is_trending_down": 0, "is_stable": 1,
    }


def live_daily_rate(p: "ProductInput") -> float:
    """Recent units/day from the request, counting only days the item was in stock."""
    if p.daily_sales:
        sales = np.asarray(p.daily_sales[-28:], dtype=float)
        if p.daily_stock and len(p.daily_stock) == len(p.daily_sales):
            stock = np.asarray(p.daily_stock[-28:], dtype=float)
            return in_stock_rate(sales.sum(), len(sales), float((stock <= 0).sum()))
        return float(sales.mean())
    return in_stock_rate(p.recent_qty, 30, p.stockout_days_30d or 0.0)


def get_forecast_features(p: "ProductInput") -> dict:
    """Forecast features for one store-product, never older than FORECAST_MAX_AGE_DAYS.

    1. daily_sales in the request -> fresh forecast now (weekly-naive vs 28-day
       mean, chosen on the last 28 days; stock-out days excluded from the mean).
    2. saved training forecast, if it is recent enough.
    3. otherwise the live 30-day in-stock rate from the request.
    """
    if p.daily_sales and len(p.daily_sales) >= 56:
        from forecasting import selected_forecast, uncensor  # imports Prophet; only load when needed
        values = np.asarray(p.daily_sales, dtype=float)
        if p.daily_stock and len(p.daily_stock) == len(p.daily_sales):
            values = uncensor(values, p.daily_stock)  # stock-out days: hidden demand -> in-stock mean
        sales = pd.Series(values, index=pd.date_range(end=pd.Timestamp.today().normalize(), periods=len(values)))
        fc = selected_forecast(sales, 60, methods=("weekly_naive", "recent_mean"))
        v = fc["values"]
        feats = _rate_features(v[:30].mean(), f"live_{fc['method']}", v[:7].mean())
        feats.update({"forecast_7d": float(v[:7].sum()), "forecast_14d": float(v[:14].sum()),
                      "forecast_30d": float(v[:30].sum()), "forecast_60d": float(v.sum())})
        return feats
    key = (p.store_id, p.product_id)
    if key in forecasts_df.index:
        row = forecasts_df.loc[key]
        if _forecast_age_days(row) <= FORECAST_MAX_AGE_DAYS:
            return {
                "forecast_method": str(row.get("forecast_method", "prophet")),
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
    return _rate_features(live_daily_rate(p), "observed_recent_sales")


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
    fc = get_forecast_features(p)

    # -- Explicit boundary features (mirrors label-rule metrics exactly) --
    forecast_30d = fc.get("forecast_30d", 0)
    forecast_7d  = fc.get("forecast_7d",  0)
    metrics = policy_metrics(
        stock_qty=p.stock_qty,
        forecast_30d=forecast_30d,
        forecast_7d=forecast_7d,
        recent_qty=p.recent_qty,
    )
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
        "coverage_30d_feat":      metrics["coverage_30d_feat"],
        "days_since_over_90":     days_since_over_90,
        "days_of_stock_30d_feat": metrics["days_of_stock_30d_feat"],
        "stockout_risk_7d":       metrics["stockout_risk_7d"],
        # Inputs for stock_policy_label_v2 only (not model features)
        "age_days":           p.age_days,
        "lead_time_days":     p.lead_time_days,
        "days_to_next_order": p.days_to_next_order,
        "on_order":           p.on_order or 0.0,
        "daily_rate":         fc.get("forecast_30d", 0) / 30 if fc.get("forecast_30d", 0) > 0 else live_daily_rate(p),
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
        "model": "Jiran ML v2222 (stock policy + RF + GB + XGB ensemble)" if AI_AVAILABLE else None,
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
    proba = ensemble.predict_proba(X_scaled)
    class_labels = ensemble.classes_

    results = []
    for i, p in enumerate(products):
        raw_probabilities = {
            str(label): float(proba[i][j])
            for j, label in enumerate(class_labels)
        }
        model_label = max(
            raw_probabilities, key=lambda label: raw_probabilities[label]
        )
        policy_label = stock_policy_label_v2(rows[i])
        prob_dict = {
            label: round(value, 4) for label, value in raw_probabilities.items()
        }
        results.append(ProductPrediction(
            store_id=p.store_id,
            product_id=p.product_id,
            product_name=p.product_name or "",
            prediction=policy_label,
            confidence=round(float(raw_probabilities.get(policy_label, 0.0)), 4),
            probabilities=prob_dict,
            model_prediction=model_label,
            demand_30d=float(rows[i]["forecast_30d"] if rows[i]["forecast_30d"] > 0 else max(p.recent_qty, 0.0)),
            demand_source=str(rows[i].get("forecast_method", "observed_recent_sales")),
            stock_plan=stock_planning_matrix(rows[i], p.stock_qty, age_days=p.age_days,
                lead_time_days=p.lead_time_days,
                review_days=p.days_to_next_order if p.days_to_next_order is not None else 7,
                on_order=p.on_order or 0, policy_label=policy_label),
        ))
    return results


def _demand_30d(p: ProductInput) -> float:
    """
    Best estimate of 30-day demand for a product-store pair.
    Uses Prophet forecast if available, falls back to recent_qty (actual sales).
    """
    fc = get_forecast_features(p)
    if fc["forecast_30d"] > 0:
        return fc["forecast_30d"]
    # Fallback: use last 30 days of actual sales
    return max(p.recent_qty, 1.0)


def _compute_recommendations(
    products: List[ProductInput],
    predictions: List[ProductPrediction],
):
    """Build transfer and restock recommendations (logic in transfer_policy.plan_transfers)."""
    pred_lookup = {(r.store_id, r.product_id): r for r in predictions}
    records = []
    for p in products:
        pred = pred_lookup[(p.store_id, p.product_id)]
        rec = {
            "store_id": p.store_id, "product_id": p.product_id, "product_name": p.product_name or "",
            "stock_qty": p.stock_qty, "demand_30d": pred.demand_30d if pred.demand_30d > 0 else _demand_30d(p),
            "label": pred.prediction, "group": p.region or None,
        }
        if p.lead_time_days is not None:  # delivery timing known: size transfers by it
            rate = rec["demand_30d"] / 30
            if pred.prediction == "Low":
                wait = days_until_next_delivery(p.lead_time_days, 7.0 if p.days_to_next_order is None else p.days_to_next_order)
                rec["target_stock"] = receiver_target_stock(rate, wait, p.on_order or 0.0)
            else:
                rec["keep_stock"] = donor_reserve(rate, p.lead_time_days)
        records.append(rec)
    transfers, restocks = plan_transfers(records)
    return ([TransferRecommendation(**t) for t in transfers],
            [RestockRecommendation(**r) for r in restocks])


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
