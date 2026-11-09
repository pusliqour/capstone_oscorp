"""Forecast selection using a historical inner holdout; no future test access."""
import numpy as np
import pandas as pd
from prophet import Prophet

METHODS=('weekly_naive','recent_mean','prophet')


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


def selected_forecast(series,horizon):
    """Choose on the last 14 past days, then refit on all supplied history."""
    if len(series)<42:
        return {'method':'recent_mean','values':forecast_daily(series,horizon,'recent_mean'),'validation_mae':None,'daily_error':None}
    train,valid=series.iloc[:-14],series.iloc[-14:]
    candidates=[]
    for method in METHODS:
        try:
            pred=forecast_daily(train,len(valid),method)
            errors=np.abs(valid.to_numpy()-pred)
            candidates.append((float(errors.mean()),METHODS.index(method),method,float(np.quantile(errors,0.9))))
        except (ValueError,RuntimeError):
            continue
    if not candidates:raise ValueError('No usable forecasting candidate')
    mae,_,method,error=min(candidates)
    return {'method':method,'values':forecast_daily(series,horizon,method),'validation_mae':mae,'daily_error':error}
