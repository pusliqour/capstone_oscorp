"""Generate the Jiran 1,000-store simulation benchmark (see PROTOCOL.md).

Output (ml_backend/simulation/output/sim1000_v1/):
  series.csv      one row per store-item with its fixed attributes
  stores.csv      one row per store
  sales.npy       units sold per series per day            (n_series, 365) int32
  txns.npy        transactions per series per day          (n_series, 365) int32
  stock.npy       end-of-day stock on hand                 (n_series, 365) int32
  on_order.npy    units ordered but not yet received       (n_series, 365) int32
  demand.npy      true demand incl. lost sales (analysis only, never a model input)
  expected_demand.npy  the true expected units/day used to draw demand (oracle reference only)
  manifest.json   parameters, counts and SHA-256 checksums

Everything is simulated. Nothing here is real retailer data.
"""
import argparse, hashlib, json, time
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 20261111
DAYS = 365
START = pd.Timestamp("2025-01-01")
N_STORES, N_REGIONS, N_PRODUCTS = 1000, 12, 600
CATS = ["bakery", "frozen", "personal_care", "household", "beverages", "snacks", "electronics", "pantry", "dairy", "produce"]
PRICE = dict(bakery=4, frozen=6, personal_care=9, household=8, beverages=3, snacks=3, electronics=60, pantry=5, dairy=4, produce=3)
PACK = dict(bakery=6, frozen=6, personal_care=6, household=6, beverages=12, snacks=12, electronics=1, pantry=12, dairy=6, produce=10)
FOOD = {"bakery", "frozen", "beverages", "snacks", "pantry", "dairy", "produce"}
GIFT = {"snacks", "beverages", "electronics", "household"}
# Mon..Sun shape, scaled per category by a weekend amplitude
WEEK_SHAPE = np.array([-0.4, -0.4, -0.3, -0.2, 0.3, 1.0, 0.7])
UNITS_P = 0.625          # units per order = 1 + NB(n, p): mean 1.6
BULK_P, BULK_RANGE = 0.003, (10, 40)
ORDER_SHAPE = 5.0        # gamma-Poisson day-level over-dispersion
DECLINE_SHARE, LAUNCH_SHARE = 0.10, 0.06


def build_world(rng):
    cat = rng.choice(CATS, N_PRODUCTS)
    products = pd.DataFrame({
        "product_id": [f"SIM-P{i:04d}" for i in range(N_PRODUCTS)], "category": cat,
        "retail_price": np.round([PRICE[c] * rng.lognormal(0, 0.4) for c in cat], 2),
        "pack": [PACK[c] for c in cat],
        "popularity": rng.lognormal(0, 1.2, N_PRODUCTS)})
    stores = pd.DataFrame({
        "store_id": [f"SIM-S{i:04d}" for i in range(N_STORES)],
        "region": rng.integers(0, N_REGIONS, N_STORES),
        "size": rng.lognormal(0, 0.45, N_STORES),
        "review_weekday": rng.integers(0, 7, N_STORES),
        "lead_time": rng.integers(2, 7, N_STORES),
        "safety_days": rng.uniform(3, 7, N_STORES),
        "order_bias": rng.lognormal(0, 0.35, N_STORES),
        "n_items": rng.integers(80, 161, N_STORES)})
    week_amp = {c: rng.uniform(0.15, 0.45) for c in CATS}
    year_amp = {c: rng.uniform(0, 0.25) for c in CATS}
    year_phase = {c: rng.uniform(0, DAYS) for c in CATS}
    t = np.arange(DAYS); dow = np.array([(START + pd.Timedelta(days=int(d))).day_of_week for d in t])
    season = {}
    for c in CATS:
        w = 1 + week_amp[c] * WEEK_SHAPE; w /= w.mean()
        s = w[dow] * (1 + year_amp[c] * np.sin(2 * np.pi * (t - year_phase[c]) / DAYS))
        if c in FOOD: s = s * np.where((t >= 60) & (t < 90), 1.25, 1.0)
        if c in GIFT: s = s * np.where(t >= 328, 1.3, 1.0)
        season[c] = s
    shock = np.zeros((N_REGIONS, DAYS))
    for d in range(1, DAYS): shock[:, d] = 0.9 * shock[:, d - 1] + rng.normal(0, 0.04, N_REGIONS)
    return products, stores, season, np.exp(shock), dow


def build_series(rng, products, stores):
    p = np.sqrt(products.popularity.to_numpy()); p /= p.sum()
    rows = []
    for s in stores.itertuples():
        items = rng.choice(N_PRODUCTS, s.n_items, replace=False, p=p)
        for i in items: rows.append((s.Index, i))
    sr = pd.DataFrame(rows, columns=["store_idx", "product_idx"])
    n = len(sr)
    life = rng.random(n)
    sr["decline_day"] = np.where(life < DECLINE_SHARE, rng.integers(120, 331, n), -1)
    sr["launch_day"] = np.where(life > 1 - LAUNCH_SHARE, rng.integers(60, 251, n), 0)
    sr["affinity"] = rng.lognormal(0, 0.5, n)
    sr["trend_per_year"] = rng.normal(0, 0.35, n)
    sr["item_order_bias"] = rng.lognormal(0, 0.3, n)
    return sr


def demand_rate(rng, sr, products, stores, season, shock):
    """Expected units/day for each series and day (float64, chunk-sized)."""
    pr = products.iloc[sr.product_idx.to_numpy()]; st = stores.iloc[sr.store_idx.to_numpy()]
    base = 0.6 * pr.popularity.to_numpy() * st["size"].to_numpy() * sr.affinity.to_numpy()
    t = np.arange(DAYS)
    lam = base[:, None] * np.stack([season[c] for c in pr.category]) * shock[st.region.to_numpy()]
    lam *= np.exp(sr.trend_per_year.to_numpy()[:, None] * (t / DAYS - 0.5))
    n = len(sr)
    promo = np.ones((n, DAYS))
    for i, k in enumerate(rng.poisson(3, n)):
        for start in rng.integers(0, DAYS - 7, k): promo[i, start:start + 7] *= rng.uniform(1.4, 2.5)
    lam *= promo
    dec = sr.decline_day.to_numpy()[:, None]
    lam *= np.where((dec >= 0) & (t >= dec), np.maximum(0.03, np.exp(-(t - dec) / 15.0)), 1.0)
    lam *= np.where(t >= sr.launch_day.to_numpy()[:, None], 1.0, 0.0)
    return lam


def draw_demand(rng, lam):
    orders = rng.poisson(rng.gamma(ORDER_SHAPE, lam / 1.6 / ORDER_SHAPE))
    extra = np.where(orders > 0, rng.negative_binomial(np.maximum(orders, 1), UNITS_P), 0)
    bulk = rng.binomial(orders, BULK_P) * rng.integers(*BULK_RANGE, size=orders.shape)
    return orders, orders + extra + bulk


def simulate_inventory(rng, sr, products, stores, lam, demand, orders):
    n = len(sr); st = stores.iloc[sr.store_idx.to_numpy()]
    pack = products.pack.to_numpy()[sr.product_idx.to_numpy()]
    lead = st.lead_time.to_numpy(); review = st.review_weekday.to_numpy()
    cover = 7 + lead + st.safety_days.to_numpy()
    bias = st.order_bias.to_numpy() * sr.item_order_bias.to_numpy()
    launch = sr.launch_day.to_numpy()
    sales = np.zeros((n, DAYS), np.int32); stock = np.zeros((n, DAYS), np.int32)
    on_order_rec = np.zeros((n, DAYS), np.int32)
    arrivals = np.zeros((n, DAYS + 12), np.int64)
    # Planned rate for the first order: true mean of the first 28 selling days (a store's launch plan).
    expected = np.array([l[l > 0][:28].mean() if (l > 0).any() else 0.0 for l in lam])
    csum = np.zeros((n, DAYS + 1), np.int64)
    level = np.ceil(bias * expected * cover / pack) * pack * (launch == 0)
    on_hand = level.astype(np.int64); on_order = np.zeros(n, np.int64)
    for d in range(DAYS):
        on_hand += arrivals[:, d]; on_order -= arrivals[:, d]
        sold = np.minimum(demand[:, d], on_hand); sold[d < launch] = 0
        on_hand -= sold; sales[:, d] = sold; stock[:, d] = on_hand; csum[:, d + 1] = csum[:, d] + sold
        due = (review == (START + pd.Timedelta(days=d)).day_of_week) & (d >= launch)
        if due.any():
            lo = np.maximum(launch, d - 27); hist = d - lo + 1
            trailing = (csum[np.arange(n), d + 1] - csum[np.arange(n), lo]) / np.maximum(hist, 1)
            est = np.where(hist >= 7, trailing, expected)  # new items: planned expectation
            target = bias * est * cover
            pos = on_hand + on_order
            q = np.where(due & (pos < target), np.ceil((target - pos) / pack) * pack, 0).astype(np.int64)
            arrive = d + lead + rng.integers(0, 2, n)
            idx = np.nonzero(q)[0]
            arrivals[idx, arrive[idx]] += q[idx]; on_order += q
        on_order_rec[:, d] = on_order
    lost = demand - sales
    txns = np.where(demand > 0, np.rint(orders * np.divide(sales, demand, out=np.zeros(sales.shape), where=demand > 0)), 0).astype(np.int32)
    return sales, txns, stock, on_order_rec, lost


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "output/sim1000_v1")
    ap.add_argument("--stores", type=int, default=N_STORES)
    ap.add_argument("--seed", type=int, default=SEED, help="Repeat-seed runs; the main benchmark uses the default")
    args = ap.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    t0 = time.time(); rng = np.random.default_rng(args.seed)
    products, stores, season, shock, _ = build_world(rng)
    stores = stores.iloc[:args.stores]
    sr = build_series(rng, products, stores)
    out = {k: [] for k in ("sales", "txns", "stock", "on_order", "demand", "expected_demand")}; lost_total = 0
    for lo in range(0, len(stores), 50):
        part = sr[(sr.store_idx >= lo) & (sr.store_idx < lo + 50)]
        lam = demand_rate(rng, part, products, stores, season, shock)
        orders, demand = draw_demand(rng, lam)
        sales, txns, stock, on_order, lost = simulate_inventory(rng, part, products, stores, lam, demand, orders)
        for k, v in (("sales", sales), ("txns", txns), ("stock", stock), ("on_order", on_order), ("demand", demand.astype(np.int32)), ("expected_demand", lam.astype(np.float32))):
            out[k].append(v)
        lost_total += int(lost.sum()); print(f"stores {lo}-{lo + 49} done, {time.time() - t0:.0f}s", flush=True)
    sums = {}
    for k, parts in out.items():
        arr = np.concatenate(parts); np.save(args.out / f"{k}.npy", arr)
        sums[k] = hashlib.sha256(arr.tobytes()).hexdigest()
    series = sr.assign(store_id=stores.store_id.to_numpy()[sr.store_idx], product_id=products.product_id.to_numpy()[sr.product_idx],
                       category=products.category.to_numpy()[sr.product_idx], retail_price=products.retail_price.to_numpy()[sr.product_idx],
                       pack=products.pack.to_numpy()[sr.product_idx], region=stores.region.to_numpy()[sr.store_idx])
    series.to_csv(args.out / "series.csv", index_label="series_id"); stores.to_csv(args.out / "stores.csv", index=False)
    sales = np.concatenate(out["sales"]); demand = np.concatenate(out["demand"])
    manifest = {"data_origin": "simulated", "generator": "ml_backend/simulation/generate.py", "seed": args.seed,
                "protocol": "ml_backend/simulation/PROTOCOL.md", "start": str(START.date()), "days": DAYS,
                "stores": len(stores), "series": len(sr), "products": N_PRODUCTS, "regions": N_REGIONS,
                "units_sold": int(sales.sum()), "true_demand_units": int(demand.sum()), "lost_sales_units": lost_total,
                "zero_sales_day_share": float((sales == 0).mean()),
                "parameters": {"units_per_order_p": UNITS_P, "bulk_p": BULK_P, "order_shape": ORDER_SHAPE,
                               "decline_share": DECLINE_SHARE, "launch_share": LAUNCH_SHARE, "price": PRICE, "pack": PACK},
                "sha256": sums, "runtime_s": round(time.time() - t0, 1)}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps({k: v for k, v in manifest.items() if k not in ("sha256", "parameters")}, indent=2))


if __name__ == "__main__":
    main()
