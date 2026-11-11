"""Shared inventory demand and stock-status policy.

Training and inference import this module so forecast fallbacks and label
thresholds cannot drift independently.
"""

from collections.abc import Mapping

# A product with no recorded sale has gone at least the whole observed history
# without selling. Encoding it as 0 days would mean "sold today".
def no_sale_days(history_days: float) -> float:
    """Censored days-since-last-sale for items never sold in the history window."""
    return float(max(history_days, 0.0))


def policy_metrics(
    *,
    stock_qty: float,
    forecast_30d: float,
    forecast_7d: float,
    recent_qty: float,
) -> dict[str, float | int]:
    """Compute policy metrics with a shared fallback for missing forecasts."""
    demand_30d = forecast_30d if forecast_30d > 0 else max(recent_qty, 1.0)
    demand_7d = forecast_7d if forecast_7d > 0 else max(recent_qty / 4.0, 1.0)
    return {
        "coverage_30d_feat": stock_qty / (demand_30d + 1),
        "days_of_stock_30d_feat": stock_qty / (demand_30d / 30 + 0.1),
        "stockout_risk_7d": int(stock_qty < demand_7d),
    }


def stock_policy_label(feature_row: Mapping[str, float | int]) -> str:
    """Return the authoritative inventory label for one feature row."""
    coverage = float(feature_row["coverage_30d_feat"])
    days_stock = float(feature_row["days_of_stock_30d_feat"])
    velocity = float(feature_row["velocity_trend"])
    trend = float(feature_row["forecast_acceleration"])
    days_since = float(feature_row["days_since_last_sale"])

    if (
        coverage > 8
        or days_stock > 180
        or days_since > 90
        or (coverage > 6 and velocity < 0.2)
    ):
        return "Dead"
    if coverage > 4 or days_stock > 120 or (coverage > 3 and velocity < 0.5):
        return "Slow"
    if (
        coverage < 0.6
        or days_stock < 14
        or (coverage < 0.8 and trend > 1.2)
        or int(feature_row["stockout_risk_7d"]) == 1
    ):
        return "Low"
    if 2.0 < coverage <= 4.0 and velocity > 0.5:
        return "Excess"
    return "Optimum"


# ---------------------------------------------------------------------------
# Additions (12 Nov 2026). Each is opt-in: when its input is missing, the
# label and rate are exactly what they were before.
# ---------------------------------------------------------------------------

# A product needs this many days on sale in *this* store before it gets a
# demand estimate. Until then it is labelled "New" and is left out of transfers.
# Other stores' sales are never used as a stand-in.
MIN_HISTORY_DAYS = 28
# Extra days of cover kept on top of "until the next delivery arrives".
SAFETY_DAYS = 3.0


def is_new_product(age_days: float | None) -> bool:
    """True while a product has been on sale for fewer than MIN_HISTORY_DAYS here."""
    return age_days is not None and age_days < MIN_HISTORY_DAYS


def in_stock_rate(units_sold: float, days: float, stockout_days: float = 0.0) -> float:
    """Daily sales rate counting only days the item was on the shelf.

    On a day the shelf was empty, sales show 0 (or a partial day) even when
    customers wanted the item, so averaging over all days under-states demand.
    Units sold on the stock-out days themselves are tiny, so they stay in the
    numerator. At least 7 in-stock days are required to divide by.
    """
    available = max(float(days) - float(stockout_days), 0.0)
    return float(units_sold) / max(available, min(7.0, float(days)), 1.0)


def days_until_next_delivery(lead_time_days: float, days_to_next_order: float) -> float:
    """Days until a new supplier order could arrive if placed at the next ordering day."""
    return float(days_to_next_order) + float(lead_time_days)


def runs_out_before_delivery(stock_qty: float, on_order: float, daily_rate: float,
                             lead_time_days: float, days_to_next_order: float,
                             safety_days: float = SAFETY_DAYS) -> bool:
    """Low = stock plus open orders will not last until the next delivery (+ safety)."""
    if daily_rate <= 0:
        return False
    cover = (float(stock_qty) + float(on_order)) / float(daily_rate)
    return cover < days_until_next_delivery(lead_time_days, days_to_next_order) + safety_days


def stock_policy_label_v2(feature_row: Mapping[str, float | int]) -> str:
    """Stock label with the three additions applied when their inputs are present.

    - ``age_days`` < MIN_HISTORY_DAYS -> "New" (collecting data).
    - ``lead_time_days`` (+ optional ``days_to_next_order``, default 7 = weekly
      ordering, and ``on_order``) -> Low means "runs out before the next
      delivery", replacing the fixed 14-day / 7-day tests.
    - ``daily_rate`` should already be the in-stock rate when stock-out days are known.
    Dead / Slow / Excess thresholds are unchanged.
    """
    if is_new_product(feature_row.get("age_days")):
        return "New"
    if feature_row.get("lead_time_days") is None:
        return stock_policy_label(feature_row)
    label = stock_policy_label(feature_row)
    if label in {"Dead", "Slow"}:
        return label
    low = runs_out_before_delivery(
        float(feature_row["stock_qty"]), float(feature_row.get("on_order", 0.0) or 0.0),
        float(feature_row["daily_rate"]), float(feature_row["lead_time_days"]),
        float(feature_row.get("days_to_next_order", 7.0) if feature_row.get("days_to_next_order") is not None else 7.0))
    if low:
        return "Low"
    return "Excess" if label == "Excess" else "Optimum"


# Transfer sizing (used by app.py and the simulation when delivery timing is known).
# A donor keeps DONOR_RESERVE_MULT x the stock it needs until its own next delivery.
# The multiplier was chosen on a separate development simulation (seed 1001), not on
# the reported test worlds: x2 cut new stock-outs at donors by ~30% for ~1 point less benefit.
DONOR_RESERVE_MULT = 2.0


def receiver_target_stock(daily_rate: float, days_until_delivery: float, on_order: float = 0.0) -> float:
    """Top a Low store up only until its own next supplier delivery (+ safety days)."""
    return max(float(daily_rate) * (float(days_until_delivery) + SAFETY_DAYS) - float(on_order), 0.0)


def donor_reserve(daily_rate: float, lead_time_days: float, order_cycle_days: float = 7.0,
                  mult: float = DONOR_RESERVE_MULT) -> float:
    """Units a giving store must keep: mult x demand until its next delivery + safety days."""
    return float(mult) * float(daily_rate) * (float(order_cycle_days) + float(lead_time_days) + SAFETY_DAYS)
