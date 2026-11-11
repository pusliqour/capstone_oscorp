"""Lost-sales (censoring) check on the 1,000-store simulation. Post-protocol addition 4.

Same 3,000 held-out series and test origins (day 304, 334) as evaluate_forecasts.py.
Each method is run twice: on recorded sales as they are, and with stock-out days
corrected by forecasting.uncensor (needs daily stock, which Jiran must then record).
Scored against recorded future sales AND against true future customer demand
(demand.npy, known only in a simulation). Everything is simulated.
"""
import argparse, json, logging, os, sys, time
from multiprocessing import Pool
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from evaluate_forecasts import ORIGINS, START, H  # noqa: E402

DATA = None


def run_one(job):
    for n in ("cmdstanpy", "prophet"): logging.getLogger(n).setLevel(logging.ERROR)
    from forecasting import forecast_daily, selected_forecast, uncensor
    sid, launch, hist, stock, origin, fut_sales, fut_demand = job
    idx = pd.date_range(START + pd.Timedelta(days=int(launch)), periods=len(hist))
    raw = pd.Series(hist.astype(float), index=idx); fixed = pd.Series(uncensor(hist, stock), index=idx)
    out = {"series_id": sid, "origin": origin, "sales": fut_sales.tolist(), "demand": fut_demand.tolist(),
           "stockout_days_28": int((stock[-28:] <= 0).sum())}
    for tag, s in (("raw", raw), ("fixed", fixed)):
        out[f"selected_{tag}"] = selected_forecast(s, H)["values"].tolist()
        out[f"recent_mean_{tag}"] = forecast_daily(s, H, "recent_mean").tolist()
    return out


def score(folds, key, target):
    a = np.array([f[target] for f in folds], float); p = np.array([f[key] for f in folds], float)
    ta, tp = a.sum(1), p.sum(1)
    return {"series": len(folds), "wape_total": float(np.abs(ta - tp).sum() / ta.sum()), "bias": float((tp.sum() - ta.sum()) / ta.sum()),
            "wape_daily": float(np.abs(a - p).sum() / a.sum())}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data", type=Path, default=HERE / "output/sim1000_v1")
    ap.add_argument("--out", type=Path, default=HERE / "output/results/lost_sales.json"); ap.add_argument("--n", type=int, default=3000)
    a = ap.parse_args(); t0 = time.time()
    series = pd.read_csv(a.data / "series.csv"); load = lambda k: np.load(a.data / f"{k}.npy", mmap_mode="r")
    sales, stock, demand = load("sales"), load("stock"), load("demand")
    test_stores = set(pd.read_csv(a.data / "stores.csv").store_id.sample(200, random_state=7))
    pool_ids = series[series.store_id.isin(test_stores) & (series.launch_day <= 150)].series_id
    ids = pool_ids.sample(min(a.n, len(pool_ids)), random_state=11).to_numpy()
    jobs = []
    for o in ORIGINS["test"]:
        for sid in ids:
            lo = int(series.launch_day[sid])
            jobs.append((int(sid), lo, np.asarray(sales[sid, lo:o + 1]), np.asarray(stock[sid, lo:o + 1]), o,
                         np.asarray(sales[sid, o + 1:o + 1 + H]), np.asarray(demand[sid, o + 1:o + 1 + H])))
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        res = list(pool.imap_unordered(run_one, jobs, chunksize=20))
    groups = {"all": res, "had_stockout_last_28d": [f for f in res if f["stockout_days_28"] > 0]}
    out = {"data_origin": "simulated", "addition": "post-protocol 4 (lost sales)", "folds": len(res), "results": {}}
    for g, folds in groups.items():
        out["results"][g] = {"folds": len(folds), **{f"{m}_{t}": {tgt: score(folds, f"{m}_{t}", tgt) for tgt in ("sales", "demand")}
                                                     for m in ("selected", "recent_mean") for t in ("raw", "fixed")}}
    out["runtime_s"] = round(time.time() - t0, 1); a.out.write_text(json.dumps(out, indent=1))
    for g, r in out["results"].items():
        print(g, r["folds"])
        for k, v in r.items():
            if k != "folds": print(f"  {k:20s} vs sales WAPE {v['sales']['wape_total']:.3f} bias {v['sales']['bias']:+.3f} | vs demand WAPE {v['demand']['wape_total']:.3f} bias {v['demand']['bias']:+.3f}")


if __name__ == "__main__":
    main()
