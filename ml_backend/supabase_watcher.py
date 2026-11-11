"""
supabase_watcher.py — Watches Supabase for stock analysis trigger events.

Runs as a background thread inside the FastAPI server (started via lifespan
in app.py). Can also be run standalone: python supabase_watcher.py

HOW IT WORKS
------------
1. Polls the `ml_triggers` table every POLL_INTERVAL seconds.
2. When a row with status='pending' appears it:
   a. Fetches linked product/store rows from `ml_inventory`.
   b. POSTs them to the local ML API (/recommend or /predict-stock).
   c. Writes results to local CSV/JSON files in OUTPUT_DIR.
   d. Updates the trigger row → status='done' (or 'error').

SUPABASE TABLE SCHEMAS
----------------------

  ml_triggers
  -----------
  id             uuid          PK (gen_random_uuid())
  status         text          'pending' | 'running' | 'done' | 'error'
  trigger_type   text          'recommend' | 'predict-stock'
  filter_store   text          null = all stores
  filter_product text          null = all products
  created_at     timestamptz   default now()
  completed_at   timestamptz
  error_msg      text
  result_file    text          path of the predictions CSV written locally

  ml_inventory
  ------------
  store_id              text
  product_id            text
  product_name          text
  category              text
  stock_qty             float8
  retail_price          float8
  recent_qty            float8
  recent_txns           float8
  recent_avg            float8
  recent_std            float8
  historical_qty        float8
  historical_txns       float8
  historical_avg        float8
  total_sold            float8
  num_sales             float8
  days_since_last_sale  float8
  store_total_txns      float8

QUICK START (standalone)
------------------------
  pip install supabase requests
  python supabase_watcher.py

TRIGGER A RUN (from Supabase dashboard / SQL editor)
-----------------------------------------------------
  insert into ml_triggers (status, trigger_type)
  values ('pending', 'recommend');
"""

import csv
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone

import requests
from supabase import create_client, Client

log = logging.getLogger("watcher")

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
SUPABASE_URL  = os.getenv("SUPABASE_URL", "http://127.0.0.1:54321")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# Use service key so RLS doesn't block status updates; fall back to anon
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
ML_API_URL    = os.getenv("ML_API_URL",   "http://localhost:8001")
OUTPUT_DIR    = os.getenv("OUTPUT_DIR",   "./ml_outputs")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))

TRIGGER_TABLE   = "ml_triggers"
INVENTORY_TABLE = "ml_inventory"

# ---------------------------------------------------------------------------
# Supabase client (lazy-initialised so import doesn't crash if pkg missing)
# ---------------------------------------------------------------------------
_supabase: Client = None

def get_client() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def output_path(trigger_id: str, suffix: str, ext: str = "csv") -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(OUTPUT_DIR, f"{ts}_{trigger_id[:8]}_{suffix}.{ext}")


def mark_trigger(trigger_id: str, status: str, result_file: str = None, error: str = None):
    update = {"status": status, "completed_at": now_iso()}
    if result_file:
        update["result_file"] = result_file
    if error:
        update["error_msg"] = str(error)[:500]
    get_client().table(TRIGGER_TABLE).update(update).eq("id", trigger_id).execute()


def fetch_inventory(filter_store: str, filter_product: str) -> list[dict]:
    query = get_client().table(INVENTORY_TABLE).select("*")
    if filter_store:
        query = query.eq("store_id", filter_store)
    if filter_product:
        query = query.eq("product_id", filter_product)
    return query.execute().data or []


def build_api_payload(rows: list[dict]) -> dict:
    products = []
    for r in rows:
        products.append({
            "store_id":             str(r.get("store_id", "")),
            "product_id":           str(r.get("product_id", "")),
            "product_name":         str(r.get("product_name") or r.get("product_id", "")),
            "category":             str(r.get("category", "unknown")),
            "stock_qty":            float(r.get("stock_qty") or 0),
            "retail_price":         float(r.get("retail_price") or 0),
            "recent_qty":           float(r.get("recent_qty") or 0),
            "recent_txns":          float(r.get("recent_txns") or 0),
            "recent_avg":           float(r.get("recent_avg") or 0),
            "recent_std":           float(r.get("recent_std") or 0),
            "historical_qty":       float(r.get("historical_qty") or 0),
            "historical_txns":      float(r.get("historical_txns") or 0),
            "historical_avg":       float(r.get("historical_avg") or 0),
            "total_sold":           float(r.get("total_sold") or 0),
            "num_sales":            float(r.get("num_sales") or 0),
            "days_since_last_sale": float(r.get("days_since_last_sale") or 0),
            "store_total_txns":     float(r.get("store_total_txns") or 0),
        })
        # Optional fields: passed through only when the Supabase view provides them.
        for key in ("region", "age_days", "stockout_days_30d", "on_order", "lead_time_days",
                    "days_to_next_order", "order_cycle_days", "daily_sales", "daily_stock"):
            if r.get(key) is not None:
                products[-1][key] = r[key]
    return {"products": products}

# ---------------------------------------------------------------------------
# CSV / JSON writers
# ---------------------------------------------------------------------------

def write_predictions_csv(path: str, predictions: list[dict]):
    if not predictions:
        return
    fields = ["store_id", "product_id", "product_name", "prediction", "confidence",
              "prob_dead", "prob_excess", "prob_low", "prob_optimum", "prob_slow"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for p in predictions:
            probs = p.get("probabilities", {})
            w.writerow({
                "store_id":     p.get("store_id"),
                "product_id":   p.get("product_id"),
                "product_name": p.get("product_name"),
                "prediction":   p.get("prediction"),
                "confidence":   round(p.get("confidence", 0), 4),
                "prob_dead":    round(probs.get("Dead", 0), 4),
                "prob_excess":  round(probs.get("Excess", 0), 4),
                "prob_low":     round(probs.get("Low", 0), 4),
                "prob_optimum": round(probs.get("Optimum", 0), 4),
                "prob_slow":    round(probs.get("Slow", 0), 4),
            })
    log.info("  → predictions: %s", path)


def write_transfers_csv(path: str, transfers: list[dict]):
    if not transfers:
        return
    fields = [
        "group_id", "product_id", "from_store", "to_store",
        "transfer_qty", "transfer_mode", "transfer_type",
        "from_label", "to_label",
        "from_stock_before", "from_stock_after", "from_coverage_after",
        "to_stock_before",   "to_stock_after",   "to_coverage_after",
        "demand_30d",
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for t in transfers:
            w.writerow(t)
    log.info("  → transfers:   %s", path)


def write_restocks_csv(path: str, restocks: list[dict]):
    if not restocks:
        return
    fields = ["store_id", "product_id", "restock_qty", "current_stock",
              "target_stock", "demand_30d", "reason"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in restocks:
            w.writerow(r)
    log.info("  → restocks:    %s", path)


def write_summary_json(path: str, summary: dict):
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)
    log.info("  → summary:     %s", path)

# ---------------------------------------------------------------------------
# Core: process one trigger row
# ---------------------------------------------------------------------------

def process_trigger(trigger: dict):
    tid          = trigger["id"]
    ttype        = trigger.get("trigger_type") or "recommend"
    filter_store = trigger.get("filter_store") or ""
    filter_prod  = trigger.get("filter_product") or ""

    endpoint = f"{ML_API_URL}/{'predict-stock' if ttype == 'predict-stock' else 'recommend'}"
    log.info("[%s] trigger %s  type=%s  store=%s  product=%s",
             now_iso(), tid[:8], ttype, filter_store or "ALL", filter_prod or "ALL")

    # Claim the row immediately so other watcher instances skip it
    claimed = get_client().table(TRIGGER_TABLE).update({
        "status": "running", "completed_at": None, "error_msg": None,
    }).eq("id", tid).eq("status", "pending").execute().data
    if not claimed:
        return

    try:
        rows = fetch_inventory(filter_store, filter_prod)
        if not rows:
            raise ValueError(
                f"No inventory rows for store={filter_store!r} product={filter_prod!r}"
            )
        log.info("  Fetched %d rows → %s", len(rows), endpoint)

        resp = requests.post(endpoint, json=build_api_payload(rows), timeout=60)
        resp.raise_for_status()
        result = resp.json()

        ensure_output_dir()
        pred_path  = output_path(tid, "predictions")
        trans_path = output_path(tid, "transfers")
        rest_path  = output_path(tid, "restocks")
        summ_path  = output_path(tid, "summary", ext="json")

        predictions = result.get("predictions") or result.get("results") or []
        transfers   = result.get("transfers", [])
        restocks    = result.get("restocks", [])
        summary     = result.get("summary", {})

        write_predictions_csv(pred_path, predictions)
        write_transfers_csv(trans_path, transfers)
        write_restocks_csv(rest_path, restocks)
        write_summary_json(summ_path, summary)

        from publish_results import publish_results
        publish_results(get_client(), result, include_transfers=(ttype != "predict-stock"))
        mark_trigger(tid, "done", result_file=pred_path)
        log.info("  Done — %d predictions, %d transfers, %d restocks",
                 len(predictions), len(transfers), len(restocks))

    except Exception as e:
        log.error("  ERROR on trigger %s: %s", tid[:8], e)
        mark_trigger(tid, "error", error=str(e))

# ---------------------------------------------------------------------------
# Poll loop
# ---------------------------------------------------------------------------

def poll(stop_event: threading.Event = None):
    log.info("Supabase watcher started  |  url=%s  interval=%ds  out=%s",
             SUPABASE_URL, POLL_INTERVAL, OUTPUT_DIR)
    while True:
        if stop_event and stop_event.is_set():
            log.info("Watcher stopping.")
            break
        try:
            pending = (
                get_client()
                .table(TRIGGER_TABLE)
                .select("*")
                .eq("status", "pending")
                .order("created_at")
                .limit(10)
                .execute()
                .data or []
            )
            if pending:
                log.info("Found %d pending trigger(s)", len(pending))
                for trigger in pending:
                    process_trigger(trigger)
        except Exception as e:
            log.error("Poll error: %s", e)
        time.sleep(POLL_INTERVAL)


def start_watcher_thread() -> threading.Event:
    """
    Start the watcher in a daemon thread.
    Returns a stop_event — call stop_event.set() to shut it down gracefully.
    """
    stop_event = threading.Event()
    t = threading.Thread(target=poll, args=(stop_event,), daemon=True, name="supabase-watcher")
    t.start()
    return stop_event


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    poll()
