"""Transfer (decision-quality) test on the 1,000-store simulation. Paper RQ3.

Question: when Jiran moves stock from stores with too much to stores running low,
do stock-outs and dead stock go down, without leaving the giving store short?

Method: paired replay. Every arm re-runs the same year with the *same* customer
demand (demand.npy), the same supplier ordering policy and the same delivery
delays as generate.py. The only difference between arms is the transfer policy,
so any change in lost sales is caused by the transfers.

Arms
  none         no transfers (reference)
  current      Jiran's engine as shipped: current stock rule (forecast = 28-day
               mean of sales), receivers = "Low", target 1.5 x 30-day demand,
               donors = Excess/Slow/Dead, any store in the network
  region       current + transfers only between stores in the same region
  improved     region + the 12 Nov fixes: in-stock sales rate (lost-sales fix),
               "Low" = runs out before its next supplier delivery, receivers
               only topped up until that delivery, donors keep enough for their
               own next delivery (x2 reserve, chosen on development seed 1001),
               products under 28 days old left out
Single-fix arms (ablation) isolate each change.

Transfers: weekly rounds on days 182-357, arriving next morning. Results are
measured on days 183-364. Everything is simulated.
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from inventory_policy import (DONOR_RESERVE_MULT, MIN_HISTORY_DAYS, SAFETY_DAYS, donor_reserve, policy_metrics,  # noqa: E402
                              receiver_target_stock, stock_policy_label)
from transfer_policy import plan_transfers  # noqa: E402

DAYS = 365
START = pd.Timestamp("2025-01-01")
ROUNDS = list(range(182, 358, 7))
WINDOW = (183, 365)
ARMS = {
    "none":     dict(transfers=False),
    "current":  dict(transfers=True, region=False, rate="all", low="rule", target="rule", keep="rule", new=False),
    "region":   dict(transfers=True, region=True, rate="all", low="rule", target="rule", keep="rule", new=False),
    "improved": dict(transfers=True, region=True, rate="instock", low="delivery", target="delivery", keep="delivery", new=True),
    "improved_reserve_x1": dict(transfers=True, region=True, rate="instock", low="delivery", target="delivery", keep="delivery", new=True, keep_mult=1.0),
    # donor-protection variant rejected on development seed 1001 (halved the benefit)
    "improved+no_excess_donors": dict(transfers=True, region=True, rate="instock", low="delivery", target="delivery", keep="delivery", new=True, donors=("Slow", "Dead")),
    # Task P1 (concern A8): thresholds chosen on validation in evaluate_tuning.py, 6/6 worlds
    "improved+slow2.5": dict(transfers=True, region=True, rate="instock", low="delivery", target="delivery", keep="delivery", new=True, slow_cov=2.5),
    "improved+dead30": dict(transfers=True, region=True, rate="instock", low="delivery", target="delivery", keep="delivery", new=True, dead_days=30.0),
    "improved+slow2.5+dead30": dict(transfers=True, region=True, rate="instock", low="delivery", target="delivery", keep="delivery", new=True, slow_cov=2.5, dead_days=30.0),
    # ablations: region + one fix
    "region+instock_rate": dict(transfers=True, region=True, rate="instock", low="rule", target="rule", keep="rule", new=False),
    "region+delivery_low": dict(transfers=True, region=True, rate="all", low="delivery", target="rule", keep="rule", new=False),
    "region+delivery_targets": dict(transfers=True, region=True, rate="all", low="rule", target="delivery", keep="delivery", new=False),
}


def rule_labels_vec(stock, f30, f7, recent, velocity, accel, days_since, slow_cov=4.0, dead_cov=8.0, dead_days=90.0):
    """Vectorised inventory_policy.stock_policy_label (checked against it in check_rule at the defaults).
    slow_cov / dead_cov / dead_days are the thresholds swept in evaluate_tuning.py (concern A8, task P1);
    the "or coverage > 0.75 x cut-off with low velocity" clauses scale with them (3 = 0.75 x 4, 6 = 0.75 x 8)."""
    d30 = np.where(f30 > 0, f30, np.maximum(recent, 1.0)); d7 = np.where(f7 > 0, f7, np.maximum(recent / 4.0, 1.0))
    cov = stock / (d30 + 1); ds = stock / (d30 / 30 + 0.1); risk = stock < d7
    lab = np.full(stock.shape, "Optimum", dtype=object)
    excess = (cov > 2.0) & (cov <= slow_cov) & (velocity > 0.5); lab[excess] = "Excess"
    low = (cov < 0.6) | (ds < 14) | ((cov < 0.8) & (accel > 1.2)) | risk; lab[low] = "Low"
    slow = (cov > slow_cov) | (ds > 120) | ((cov > 0.75 * slow_cov) & (velocity < 0.5)); lab[slow] = "Slow"
    dead = (cov > dead_cov) | (ds > 180) | (days_since > dead_days) | ((cov > 0.75 * dead_cov) & (velocity < 0.2)); lab[dead] = "Dead"
    return lab


def check_rule(rng):
    n = 20000
    a = dict(stock=rng.integers(0, 400, n).astype(float), f30=rng.gamma(1, 30, n) * (rng.random(n) > .1), recent=rng.gamma(1, 30, n),
             velocity=rng.gamma(2, .5, n), accel=rng.gamma(2, .6, n), days_since=rng.integers(0, 200, n).astype(float))
    a["f7"] = a["f30"] * 7 / 30
    vec = rule_labels_vec(**a)
    for i in range(n):
        r = {"velocity_trend": a["velocity"][i], "forecast_acceleration": a["accel"][i], "days_since_last_sale": a["days_since"][i]}
        r.update(policy_metrics(stock_qty=a["stock"][i], forecast_30d=a["f30"][i], forecast_7d=a["f7"][i], recent_qty=a["recent"][i]))
        assert stock_policy_label(r) == vec[i], i


def load(data, subset):
    series = pd.read_csv(data / "series.csv"); stores = pd.read_csv(data / "stores.csv")
    keep = np.ones(len(series), bool) if subset is None else series.store_id.isin(subset).to_numpy()
    series = series[keep].reset_index(drop=True)
    demand = np.load(data / "demand.npy", mmap_mode="r")[keep].astype(np.int64)
    lam = np.load(data / "expected_demand.npy", mmap_mode="r")[keep]
    sales0 = np.load(data / "sales.npy", mmap_mode="r")[keep]; txns0 = np.load(data / "txns.npy", mmap_mode="r")[keep]
    # Orders (customer visits) are not saved; recover them from the recorded data. Exact when
    # nothing was lost; when the shelf ran out, scale recorded visits up by demand / sales.
    with np.errstate(divide="ignore", invalid="ignore"):
        orders = np.where(sales0 > 0, np.rint(txns0 * demand / np.maximum(sales0, 1)), np.ceil(demand / 1.6)).astype(np.int64)
    expected0 = np.array([l[l > 0][:28].mean() if (l > 0).any() else 0.0 for l in lam])
    st = stores.set_index("store_id").loc[series.store_id]
    return dict(series=series, demand=demand, orders=orders, expected0=expected0, pack=series.pack.to_numpy(),
                lead=st.lead_time.to_numpy(), review=st.review_weekday.to_numpy(),
                cover=7 + st.lead_time.to_numpy() + st.safety_days.to_numpy(),
                bias=st.order_bias.to_numpy() * series.item_order_bias.to_numpy(), launch=series.launch_day.to_numpy(),
                region=series.region.to_numpy(), price=series.retail_price.to_numpy(),
                store=series.store_id.to_numpy(), product=series.product_id.to_numpy())


def transfer_round(T, W, cfg, S, ST, TX, on_hand, on_order, last_sale):
    n = len(on_hand); idx = np.arange(n)
    active = (W["launch"] <= T) & ((ST[:, T - 27:T + 1].max(1) > 0) | (on_hand > 0))
    s28 = S[:, T - 27:T + 1].sum(1); so28 = (ST[:, T - 27:T + 1] == 0).sum(1)
    rate = s28 / 28.0 if cfg["rate"] == "all" else s28 / np.maximum(28 - so28, 7)
    age = T - W["launch"]
    recent = S[:, T - 29:T + 1].sum(1); rtx = TX[:, T - 29:T + 1].sum(1)
    hist = S[:, :T - 29].sum(1); htx = TX[:, :T - 29].sum(1)
    velocity = (recent / np.maximum(rtx, 1)) / (hist / np.maximum(htx, 1) + 0.1)
    f30, f7 = rate * 30, rate * 7
    days_since = np.where(last_sale >= 0, T - last_sale, np.maximum(T - W["launch"], 0))
    lab = rule_labels_vec(on_hand.astype(float), f30, f7, recent.astype(float), velocity, (f7 / 7) / (f30 / 30 + 0.1), days_since,
                          **{k: cfg[k] for k in ("slow_cov", "dead_cov", "dead_days") if k in cfg})
    dow = (START + pd.Timedelta(days=T + 1)).day_of_week
    to_next_order = (W["review"] - dow) % 7 + 1          # tomorrow counts as 1
    until_delivery = to_next_order + W["lead"] + 0.5     # + mean delivery jitter
    if cfg["low"] == "delivery":
        position_cover = (on_hand + on_order) / np.maximum(rate, 1e-9)
        low = (rate > 0) & (position_cover < until_delivery + SAFETY_DAYS)
        lab = np.where(np.isin(lab, ["Dead", "Slow"]), lab, np.where(low, "Low", np.where(lab == "Excess", "Excess", "Optimum")))
    if cfg["new"]:
        lab = np.where(age < MIN_HISTORY_DAYS, "New", lab)
    lab = np.where(active, lab, "Inactive")
    donors = cfg.get("donors", ("Excess", "Slow", "Dead"))
    lab = np.where(np.isin(lab, ["Excess", "Slow", "Dead"]) & ~np.isin(lab, donors), "Optimum", lab)
    use = np.isin(lab, ["Low", "Excess", "Slow", "Dead"])
    # Only groups that have both a receiver and a donor can produce transfers.
    grp = W["region"] if cfg["region"] else np.zeros(n, int)
    key = pd.Series(W["product"]).astype(str) + "|" + pd.Series(grp).astype(str)
    has_low = pd.Series(lab == "Low").groupby(key).transform("any").to_numpy()
    has_donor = pd.Series(np.isin(lab, ["Excess", "Slow", "Dead"])).groupby(key).transform("any").to_numpy()
    sel = idx[use & has_low & has_donor]
    recs = []
    for i in sel:
        r = {"store_id": int(i), "product_id": W["product"][i], "product_name": "", "stock_qty": float(on_hand[i]),
             "demand_30d": float(f30[i]), "label": lab[i], "group": int(grp[i])}
        if cfg["target"] == "delivery" and lab[i] == "Low":
            r["target_stock"] = receiver_target_stock(rate[i], until_delivery[i], on_order[i])
        if cfg["keep"] == "delivery" and lab[i] != "Low":
            r["keep_stock"] = donor_reserve(rate[i], W["lead"][i] + 0.5, mult=cfg.get("keep_mult", DONOR_RESERVE_MULT))
        recs.append(r)
    transfers, restocks = plan_transfers(recs)
    labels = pd.Series(lab[active]).value_counts().to_dict()
    return [(t["from_store"], t["to_store"], int(t["transfer_qty"])) for t in transfers], labels


def simulate(W, cfg, jitter):
    n = len(W["pack"]); D = W["demand"]
    S = np.zeros((n, DAYS), np.int64); ST = np.zeros((n, DAYS), np.int64); TX = np.zeros((n, DAYS), np.int64)
    arrivals = np.zeros((n, DAYS + 14), np.int64); transfer_in = np.zeros((n, DAYS + 1), np.int64)
    csum = np.zeros((n, DAYS + 1), np.int64); last_sale = np.full(n, -1)
    on_hand = (np.ceil(W["bias"] * W["expected0"] * W["cover"] / W["pack"]) * W["pack"] * (W["launch"] == 0)).astype(np.int64)
    on_order = np.zeros(n, np.int64); log = []; label_log = {}
    rows = np.arange(n)
    for d in range(DAYS):
        on_hand += arrivals[:, d] + transfer_in[:, d]; on_order -= arrivals[:, d]
        sold = np.minimum(D[:, d], on_hand); sold[d < W["launch"]] = 0
        on_hand -= sold; S[:, d] = sold; ST[:, d] = on_hand; csum[:, d + 1] = csum[:, d] + sold
        with np.errstate(divide="ignore", invalid="ignore"):
            TX[:, d] = np.where(D[:, d] > 0, np.rint(W["orders"][:, d] * sold / np.maximum(D[:, d], 1)), 0)
        last_sale[sold > 0] = d
        due = (W["review"] == (START + pd.Timedelta(days=d)).day_of_week) & (d >= W["launch"])
        if due.any():
            lo = np.maximum(W["launch"], d - 27); hist = d - lo + 1
            trailing = (csum[rows, d + 1] - csum[rows, lo]) / np.maximum(hist, 1)
            est = np.where(hist >= 7, trailing, W["expected0"])
            target = W["bias"] * est * W["cover"]; pos = on_hand + on_order
            q = np.where(due & (pos < target), np.ceil((target - pos) / W["pack"]) * W["pack"], 0).astype(np.int64)
            arrive = d + W["lead"] + jitter[:, d]
            nz = np.nonzero(q)[0]; arrivals[nz, arrive[nz]] += q[nz]; on_order += q
        if cfg["transfers"] and d in ROUNDS:
            moves, labels = transfer_round(d, W, cfg, S, ST, TX, on_hand, on_order, last_sale); label_log[d] = labels
            for frm, to, qty in moves:
                assert on_hand[frm] >= qty, "transfer would make stock negative"
                on_hand[frm] -= qty; transfer_in[to, d + 1] += qty; log.append((d, frm, to, qty))
        assert on_hand.min() >= 0
    return S, ST, log, label_log


def summarise(W, S, ST, log, base=None):
    a, b = WINDOW; D = W["demand"][:, a:b]; s = S[:, a:b]; lost = D - s; price = W["price"]
    end_dead = (S[:, DAYS - 60:].sum(1) == 0) & (ST[:, DAYS - 1] > 0)
    out = {"demand_units": int(D.sum()), "units_sold": int(s.sum()), "lost_units": int(lost.sum()),
           "fill_rate": float(s.sum() / D.sum()), "stockout_days": int((lost > 0).sum()),
           "mean_stock_units": float(ST[:, a:b].sum(0).mean()), "mean_stock_value": float((ST[:, a:b] * price[:, None]).sum(0).mean()),
           "dead_stock_units_end": int(ST[end_dead, DAYS - 1].sum()), "dead_stock_value_end": float((ST[end_dead, DAYS - 1] * price[end_dead]).sum()),
           "transfers": len(log), "units_moved": int(sum(q for *_, q in log)), "value_moved": float(sum(q * price[f] for _, f, _, q in log))}
    if base is not None and log:
        Sb, STb = base
        lost_arm = W["demand"] - S; lost_base = W["demand"] - Sb
        recv = {(d, t) for d, _, t, _ in log}; donor = {(d, f) for d, f, _, _ in log}
        win = lambda L, d, i: int(L[i, d + 1:d + 15].sum())
        out["receivers_lost_14d"] = {"without": sum(win(lost_base, d, i) for d, i in recv), "with": sum(win(lost_arm, d, i) for d, i in recv)}
        out["donors_lost_14d"] = {"without": sum(win(lost_base, d, i) for d, i in donor), "with": sum(win(lost_arm, d, i) for d, i in donor)}
        out["transfers_to_items_that_would_not_have_run_out"] = float(np.mean([win(lost_base, d, i) == 0 for d, i in recv]))
        out["donor_events_that_caused_a_new_stockout"] = float(np.mean([win(lost_arm, d, i) > 0 and win(lost_base, d, i) == 0 for d, i in donor]))
        ls = pd.DataFrame({"store": W["store"], "arm": lost_arm[:, a:b].sum(1), "base": lost_base[:, a:b].sum(1)}).groupby("store").sum()
        out["stores_with_more_lost_sales"] = int((ls.arm > ls.base).sum()); out["stores"] = int(len(ls))
        out["worst_store_lost_increase_units"] = int((ls.arm - ls.base).max())
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data", type=Path, default=HERE / "output/sim1000_v1")
    ap.add_argument("--out", type=Path, default=HERE / "output/results/transfers.json")
    ap.add_argument("--stores", choices=["all", "test200"], default="all")
    ap.add_argument("--arms", default=",".join(ARMS))
    a = ap.parse_args(); t0 = time.time(); a.out.parent.mkdir(parents=True, exist_ok=True)
    check_rule(np.random.default_rng(1))
    subset = None
    if a.stores == "test200":
        subset = set(pd.read_csv(a.data / "stores.csv").store_id.sample(200, random_state=7))
    W = load(a.data, subset); n = len(W["pack"])
    jitter = np.random.default_rng(99).integers(0, 2, (n, DAYS))
    res = {"data_origin": "simulated", "data": str(a.data.name), "stores": a.stores, "series": n, "rounds": ROUNDS,
           "window_days": list(WINDOW), "arms": {}}
    base = None
    for name in ["none"] + [x for x in a.arms.split(",") if x != "none"]:
        S, ST, log, labels = simulate(W, ARMS[name], jitter)
        if name == "none":
            base = (S, ST)
        res["arms"][name] = {"config": ARMS[name], **summarise(W, S, ST, log, None if name == "none" else base),
                             "mean_labels_per_round": ({k: float(np.mean([l.get(k, 0) for l in labels.values()])) for k in
                                                        ["Low", "Optimum", "Excess", "Slow", "Dead", "New"]} if labels else None)}
        r = res["arms"][name]
        print(f"{name:26s} fill {r['fill_rate']:.4f} lost {r['lost_units']:>10,} stock {r['mean_stock_units']:>12,.0f} "
              f"dead {r['dead_stock_units_end']:>8,} transfers {r['transfers']:>7,} units {r['units_moved']:>9,} {time.time() - t0:.0f}s", flush=True)
    res["runtime_s"] = round(time.time() - t0, 1)
    a.out.write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
