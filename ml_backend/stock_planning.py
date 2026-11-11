"""Explicit multi-horizon inventory targets, not statistical confidence intervals."""
import math

HORIZONS = (7, 14, 30, 60)

def stock_planning_matrix(forecasts, stock_qty, *, age_days=None, lead_time_days=None,
                          review_days=7, safety_days=3, on_order=0, policy_label=None):
    """Target on-hand = horizon demand + lead-time/safety demand.

    Upper bound additionally covers one ordering/review cycle. Defaults are
    visible policy assumptions, not fitted optimality or probability guarantees.
    Open orders are not credited without a confirmed arrival date.
    """
    values = {h: float(forecasts.get(f'forecast_{h}d', 0)) for h in HORIZONS}
    nums = [stock_qty, review_days, safety_days, on_order, *values.values()]
    if lead_time_days is not None:nums.append(lead_time_days)
    if any(not math.isfinite(float(x)) or float(x)<0 for x in nums):
        raise ValueError('Stock planning inputs must be finite and nonnegative')
    if age_days is not None and (not math.isfinite(float(age_days)) or age_days<0):
        raise ValueError('Invalid product age')
    rate = values[30] / 30
    lead = float(lead_time_days or 0)
    assumptions = {
        'range_type':'policy_target_not_prediction_interval',
        'lead_time_days':lead_time_days,'lead_time_known':lead_time_days is not None,
        'unconfirmed_lead_time_allowance_days':0 if lead_time_days is None else None,
        'safety_days':safety_days,'review_cycle_days':review_days,
        'buffer_daily_rate':rate,'open_orders_credited':False,
        'formula':'lower = ceil(horizon demand + daily rate × (lead time + safety days)); upper adds daily rate × review cycle',
    }
    warnings=[]
    if lead_time_days is None:warnings.append('Delivery time unknown: provisional range excludes delivery-time demand.')
    if on_order:warnings.append('Open orders shown separately; no stock credit without a confirmed arrival date.')
    if age_days is None:warnings.append('Product age unknown: minimum-history eligibility is unverified.')
    if policy_label in ('Dead','Slow'):warnings.append(f'Overall policy label is {policy_label}: review before replenishment.')
    new = age_days is not None and age_days<28
    rows=[]
    for horizon in HORIZONS:
        lower=math.ceil(values[horizon]+rate*(lead+safety_days))
        upper=math.ceil(values[horizon]+rate*(lead+safety_days+review_days))
        rows.append({
            'horizon_days':horizon,'forecast_units':round(values[horizon],3),
            'recommended_min':None if new else lower,'recommended_max':None if new else upper,
            'status':'Collecting data' if new else 'Below range' if stock_qty<lower else 'Above range' if stock_qty>upper else 'Within range',
            'add_to_min':None if new else math.ceil(max(lower-stock_qty,0)),
            'add_to_max':None if new else math.ceil(max(upper-stock_qty,0)),
            'above_max':None if new else math.floor(max(stock_qty-upper,0)),
        })
    return {'version':1,'stock_on_hand':stock_qty,'on_order_units':on_order,
            'eligible':not new,'assumptions':assumptions,'warnings':warnings,'rows':rows}
