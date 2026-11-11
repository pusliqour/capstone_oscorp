"""Forecast evaluation on the 1,000-store simulation (PROTOCOL.md, "Forecasts").

3,000 series from held-out stores; tuning origins day 244/274, test origins 304/334;
30-day horizon scored at 7/14/30 days. Target = observed sales (what Jiran sees).
"""
import argparse, json, logging, os, sys, time
from multiprocessing import Pool
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
H, HORIZONS = 30, (7, 14, 30)
ORIGINS = {"tuning": (244, 274), "test": (304, 334)}
START = pd.Timestamp("2025-01-01")


def sba(y, h, alpha=0.1):
    nz = np.flatnonzero(y > 0)
    if len(nz) == 0: return np.zeros(h)
    z, p, last = y[nz[0]], 1.0, nz[0]
    for i in nz[1:]:
        z += alpha * (y[i] - z); p += alpha * ((i - last) - p); last = i
    return np.full(h, (1 - alpha / 2) * z / p)


def demand_class(y):
    nz = y[y > 0]
    adi = len(y) / max(len(nz), 1); cv2 = (nz.std() / nz.mean()) ** 2 if len(nz) > 1 else 0.0
    return ("smooth" if cv2 < 0.49 else "erratic") if adi < 1.32 else ("intermittent" if cv2 < 0.49 else "lumpy")


def run_one(job):
    for n in ("cmdstanpy", "prophet"): logging.getLogger(n).setLevel(logging.ERROR)
    import forecasting
    from forecasting import forecast_daily, selected_forecast
    sid, launch, hist_vals, actual, origin = job
    idx = pd.date_range(START + pd.Timedelta(days=int(launch)), periods=len(hist_vals))
    train = pd.Series(hist_vals.astype(float), index=idx)
    out = {"series_id": sid, "origin": origin, "class": demand_class(hist_vals), "actual": actual.tolist(),
           "scale_mase": float(np.mean(np.abs(hist_vals[7:] - hist_vals[:-7]))),
           "scale_rmsse": float(np.mean(np.diff(hist_vals) ** 2))}
    sel = selected_forecast(train, H); out["selected"] = sel["values"].tolist(); out["selected_method"] = sel["method"]
    forecasting.VALIDATION_DAYS = 14
    try: out["selected_previous_14d"] = selected_forecast(train, H)["values"].tolist()
    finally: forecasting.VALIDATION_DAYS = 28
    for m in ("prophet", "weekly_naive", "recent_mean"): out[m] = np.asarray(forecast_daily(train, H, m)).tolist()
    out["sba"] = sba(hist_vals, H).tolist(); out["zero_forecast"] = [0.0] * H
    return out


METHODS = ("selected", "selected_previous_14d", "prophet", "weekly_naive", "recent_mean", "sba", "zero_forecast")


def score(folds, key, h):
    a = np.array([f["actual"][:h] for f in folds], float); p = np.array([f[key][:h] for f in folds], float)
    ta, tp = a.sum(1), p.sum(1); nz = a > 0
    sm = np.array([f["scale_mase"] for f in folds]); sr = np.array([f["scale_rmsse"] for f in folds])
    mase = np.abs(a - p).mean(1)[sm > 0] / sm[sm > 0]; rmsse = np.sqrt(((a - p) ** 2).mean(1)[sr > 0] / sr[sr > 0])
    return {"h": h, "series": len(folds), "zero_day_share": float(1 - nz.mean()),
            "mape_daily_nonzero": float(np.mean(np.abs(a[nz] - p[nz]) / a[nz])) if nz.any() else None,
            "mape_total": float(np.mean(np.abs(ta - tp)[ta > 0] / ta[ta > 0])) if (ta > 0).any() else None,
            "wape_daily": float(np.abs(a - p).sum() / a.sum()) if a.sum() else None,
            "wape_total": float(np.abs(ta - tp).sum() / ta.sum()) if ta.sum() else None,
            "bias": float((p.sum() - a.sum()) / a.sum()) if a.sum() else None,
            "mase_mean": float(mase.mean()), "mase_median": float(np.median(mase)),
            "rmsse_mean": float(rmsse.mean()), "mae": float(np.abs(a - p).mean())}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data", type=Path, default=HERE / "output/sim1000_v1")
    ap.add_argument("--out", type=Path, default=HERE / "output/results/forecasts.json"); ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args(); a.out.parent.mkdir(parents=True, exist_ok=True); t0 = time.time()
    series = pd.read_csv(a.data / "series.csv"); sales = np.load(a.data / "sales.npy", mmap_mode="r")
    test_stores = set(pd.read_csv(a.data / "stores.csv").store_id.sample(200, random_state=7))
    pool_ids = series[series.store_id.isin(test_stores) & (series.launch_day <= 150)].series_id
    ids = pool_ids.sample(min(a.n, len(pool_ids)), random_state=11).to_numpy()
    jobs = []
    for phase, origins in ORIGINS.items():
        for o in origins:
            for sid in ids:
                lo = int(series.launch_day[sid]); row = np.asarray(sales[sid])
                jobs.append((int(sid), lo, row[lo:o + 1], row[o + 1:o + 1 + H], o))
    print(len(jobs), "forecast jobs on", a.workers, "workers", flush=True)
    with Pool(a.workers) as pool:
        res = []
        for i, r in enumerate(pool.imap_unordered(run_one, jobs, chunksize=20)):
            res.append(r)
            if (i + 1) % 2000 == 0: print(i + 1, f"{time.time() - t0:.0f}s", flush=True)
    phase_of = {o: ph for ph, os_ in ORIGINS.items() for o in os_}
    out = {"data_origin": "simulated", "protocol": "PROTOCOL.md", "series_sampled": len(ids), "origins": ORIGINS, "results": {}}
    for ph in ORIGINS:
        folds = [r for r in res if phase_of[r["origin"]] == ph]
        classes = sorted({f["class"] for f in folds})
        out["results"][ph] = {"folds": len(folds), "class_counts": {c: sum(f["class"] == c for f in folds) for c in classes},
                              "selected_method_counts": pd.Series([f["selected_method"] for f in folds]).value_counts().to_dict(),
                              "all": {m: [score(folds, m, h) for h in HORIZONS] for m in METHODS},
                              "by_class": {c: {m: [score([f for f in folds if f["class"] == c], m, h) for h in HORIZONS] for m in METHODS} for c in classes}}
    out["runtime_s"] = round(time.time() - t0, 1)
    a.out.write_text(json.dumps(out, indent=1))
    (a.out.parent / "forecast_folds_test.json").write_text(json.dumps([r for r in res if phase_of[r["origin"]] == "test"]))
    for ph in ORIGINS:
        print(ph)
        for m, rows in out["results"][ph]["all"].items():
            print(f"  {m:22s}", " | ".join(f"h{r['h']}: MAPEnz {r['mape_daily_nonzero']:.3f} totMAPE {r['mape_total']:.3f} WAPE {r['wape_daily']:.3f} totWAPE {r['wape_total']:.3f} MASE {r['mase_mean']:.2f} RMSSE {r['rmsse_mean']:.2f} bias {r['bias']:+.2f}" for r in rows))
    print("runtime", out["runtime_s"])


if __name__ == "__main__":
    main()
