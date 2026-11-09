"""Shared inventory demand and stock-status policy.

Training and inference import this module so forecast fallbacks and label
thresholds cannot drift independently.
"""

from collections.abc import Mapping


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
