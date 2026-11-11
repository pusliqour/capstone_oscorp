"""Transfer and restock planning, shared by the API (app.py) and the simulation.

Each input record is a dict with at least:
  store_id, product_id, product_name, stock_qty, demand_30d, label
Optional keys (the 12 Nov 2026 improvements; the old behaviour is kept when absent):
  group        transfers only happen between records with the same group
               (e.g. region or neighbourhood). Missing = one group per product.
  target_stock receiver target. Missing = OPTIMUM_TARGET_COVERAGE x demand_30d.
  keep_stock   units a donor must keep. Missing = the label-based rule below.

Output: (transfers, restocks) as plain dicts; app.py turns them into response models.
"""
from collections import defaultdict

# After a transfer, target coverage for the receiving store
OPTIMUM_TARGET_COVERAGE = 1.5   # 1.5x 30-day demand
# Minimum coverage a sending store must retain after donating stock
OPTIMUM_MIN_COVERAGE_AFTER = 0.9  # ~27 days of demand
DONOR_LABELS = {"Excess", "Slow", "Dead"}
RECEIVE_LABELS = {"Low"}
# Donor priority: Excess first, then Dead, then Slow
DONOR_TIER = {"Excess": 0, "Dead": 1, "Slow": 2}


def calc_available(donor: dict) -> float:
    """Units a donor can give without falling below its keep level."""
    if donor.get("keep_stock") is not None:
        return max(0.0, donor["sim_stock"] - donor["keep_stock"])
    if donor["label"] == "Dead" or donor["demand_30d"] <= 0:
        return donor["sim_stock"]
    if donor["label"] == "Excess":
        return max(0.0, donor["sim_stock"] - OPTIMUM_MIN_COVERAGE_AFTER * donor["demand_30d"])
    return max(0.0, donor["sim_stock"] - OPTIMUM_TARGET_COVERAGE * donor["demand_30d"])  # Slow


def _transfer(donor, recv, qty, mode, group_id, product_id):
    from_after, to_after = donor["sim_stock"] - qty, recv["sim_stock"] + qty
    t = {
        "from_store": donor["store_id"], "to_store": recv["store_id"], "product_id": product_id,
        "product_name": recv["product_name"], "transfer_qty": qty,
        "from_label": donor["label"], "to_label": recv["label"],
        "from_stock_before": round(donor["sim_stock"], 1), "from_stock_after": round(from_after, 1),
        "to_stock_before": round(recv["sim_stock"], 1), "to_stock_after": round(to_after, 1),
        "from_coverage_after": round(from_after / (donor["demand_30d"] + 0.1), 2),
        "to_coverage_after": round(to_after / (recv["demand_30d"] + 0.1), 2),
        "demand_30d": round(recv["demand_30d"], 1),
        "transfer_type": "macro" if qty >= recv["needed"] * 0.5 else "micro",
        "transfer_mode": mode, "group_id": group_id,
    }
    donor["sim_stock"] -= qty
    recv["sim_stock"] += qty
    return t


def plan_transfers(records):
    """Plan transfers per product (and per group when given).

    Per receiver, most urgent first:
      1. one donor covers the whole need -> single transfer (best tier, most available);
      2. otherwise draw from several donors, largest surplus first ("combined");
      3. any remaining shortfall -> restock recommendation.
    """
    groups = defaultdict(list)
    for r in records:
        groups[(r["product_id"], r.get("group"))].append(dict(r, sim_stock=float(r["stock_qty"])))
    transfers, restocks, counter = [], [], 0

    for (product_id, _), stores in groups.items():
        receivers = [s for s in stores if s["label"] in RECEIVE_LABELS]
        donors = [s for s in stores if s["label"] in DONOR_LABELS]
        if not receivers:
            continue
        for r in receivers:
            if r.get("target_stock") is None:
                r["target_stock"] = OPTIMUM_TARGET_COVERAGE * r["demand_30d"]
            r["needed"] = max(0.0, r["target_stock"] - r["sim_stock"])
        receivers.sort(key=lambda x: x["sim_stock"] / (x["demand_30d"] + 0.1))

        for recv in receivers:
            needed = recv["needed"]
            if needed <= 0:
                continue
            for d in donors:
                d["available"] = calc_available(d)
            donors.sort(key=lambda x: (DONOR_TIER.get(x["label"], 9), -x["available"]))
            counter += 1
            gid = f"{product_id}→{recv['store_id']}#{counter}"
            single = next((d for d in donors if d["available"] >= needed), None)
            if single:
                qty = min(max(1, round(needed)), int(single["available"]))
                if qty >= 1:
                    transfers.append(_transfer(single, recv, qty, "single", gid, product_id))
                continue
            still = needed
            for donor in donors:
                if still <= 0:
                    break
                # Whole units only: a donor with less than one spare unit gives nothing.
                qty = int(min(still, donor["available"]))
                if qty < 1:
                    continue
                transfers.append(_transfer(donor, recv, qty, "combined", gid, product_id))
                still -= qty
            if still > 1:
                restocks.append({
                    "store_id": recv["store_id"], "product_id": product_id, "product_name": recv["product_name"],
                    "restock_qty": round(still), "current_stock": round(float(recv["stock_qty"]), 1),
                    "target_stock": round(recv["target_stock"], 1), "demand_30d": round(recv["demand_30d"], 1),
                    "reason": ("No donor stores available — order from supplier" if not donors
                               else "Donor network insufficient — partial restock needed"),
                })
    return transfers, restocks
