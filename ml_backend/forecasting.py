"""Forecast selection using a historical inner holdout; no future test access."""
import numpy as np
import pandas as pd
from prophet import Prophet

METHODS=('weekly_naive','recent_mean','prophet')
# Inner validation window. 28 days was chosen on early tuning origins only
# (latest-120d/-90d); the reported test origins were not used for this choice.
VALIDATION_DAYS=28
MIN_TRAIN_DAYS=28


def daily_series(frame, as_of):
    """Assumes a complete sales export: absent calendar days represent zero sales."""
    values=frame.groupby('ds').y.sum().sort_index()
    return values.reindex(pd.date_range(values.index.min(),as_of,freq='D'),fill_value=0.0).astype(float)


def forecast_daily(series,horizon,method):
    values=np.asarray(series,dtype=float)
    if len(values)==0:return np.zeros(horizon)
    if method=='weekly_naive':return np.resize(values[-7:],horizon)
    if method=='recent_mean':return np.full(horizon,values[-28:].mean())
    if method!='prophet':raise ValueError('Unknown forecast method')
    model=Prophet(daily_seasonality=False,weekly_seasonality=len(series)>=28,yearly_seasonality=False,changepoint_prior_scale=0.01,uncertainty_samples=0)
    model.fit(pd.DataFrame({'ds':series.index,'y':values}))
    future=pd.date_range(series.index[-1]+pd.Timedelta(days=1),periods=horizon)
    return model.predict(pd.DataFrame({'ds':future})).yhat.clip(lower=0).to_numpy()


def selected_forecast(series,horizon,methods=METHODS):
    """Choose on the last VALIDATION_DAYS past days, then refit on all supplied history."""
    if len(series)<MIN_TRAIN_DAYS+VALIDATION_DAYS:
        return {'method':'recent_mean','values':forecast_daily(series,horizon,'recent_mean'),'validation_mae':None,'daily_error':None}
    train,valid=series.iloc[:-VALIDATION_DAYS],series.iloc[-VALIDATION_DAYS:]
    candidates=[]
    for method in methods:
        try:
            pred=forecast_daily(train,len(valid),method)
            errors=np.abs(valid.to_numpy()-pred)
            candidates.append((float(errors.mean()),METHODS.index(method),method,float(np.quantile(errors,0.9))))
        except (ValueError,RuntimeError):
            continue
    if not candidates:raise ValueError('No usable forecasting candidate')
    mae,_,method,error=min(candidates)
    return {'method':method,'values':forecast_daily(series,horizon,method),'validation_mae':mae,'daily_error':error}


def uncensor(values,stock,window=28):
    """Lost-sales correction: on stock-out days (end-of-day stock 0) the shelf was
    empty for part or all of the day, so recorded sales under-state demand. Replace
    each such day with the mean of the in-stock days in the trailing window (needs at
    least 7 in-stock days; otherwise the day is left as recorded)."""
    v=np.asarray(values,dtype=float); out=np.asarray(stock)<=0; fixed=v.copy()
    for i in np.flatnonzero(out):
        lo=max(0,i-window+1); ok=~out[lo:i+1]
        if ok.sum()>=7:fixed[i]=max(v[i],v[lo:i+1][ok].mean())
    return fixed
