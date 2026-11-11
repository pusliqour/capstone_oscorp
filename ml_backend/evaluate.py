"""Reproducible forecast backtesting and API stress tests; never tune on results.

python evaluate.py --data-dir training/data --output evaluation
Classification metrics from train.py measure policy imitation, not human labels.
Synthetic perturbations are robustness checks, not extra independent test data.
"""
import argparse
import json
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from prophet import Prophet
from forecasting import selected_forecast
from sklearn.metrics import classification_report, f1_score

logging.getLogger('cmdstanpy').setLevel(logging.WARNING)


def forecast_backtest(transactions, top_pairs=None, horizon=14):
    transactions=transactions.copy()
    transactions['day']=pd.to_datetime(transactions['timestamp'],utc=True).dt.tz_localize(None).dt.normalize()
    latest=transactions.day.max()
    folds=[]
    for lag in (horizon*2,horizon):
        cutoff=latest-pd.Timedelta(days=lag)
        history=transactions[transactions.day<=cutoff]
        # Select series using training history only. Default: every series with
        # past sales. "Top N by past volume" over-weights recent spikes and
        # makes forecasts look biased upward (regression to the mean).
        volume=history.groupby(['store_id','product_id']).quantity.sum()
        pairs=volume.index if top_pairs is None else volume.nlargest(top_pairs).index
        for store,product in pairs:
            series=transactions[(transactions.store_id==store)&(transactions.product_id==product)].groupby('day').quantity.sum()
            train=series.reindex(pd.date_range(series.index.min(),cutoff),fill_value=0)
            if len(train)<28:continue
            future_days=pd.date_range(cutoff+pd.Timedelta(days=1),periods=horizon)
            actual=series.reindex(future_days,fill_value=0).to_numpy()
            model=Prophet(daily_seasonality=False,weekly_seasonality=True,yearly_seasonality=False,uncertainty_samples=0)
            model.fit(pd.DataFrame({'ds':train.index,'y':train.values}))
            predicted=model.predict(pd.DataFrame({'ds':future_days})).yhat.clip(lower=0).to_numpy()
            selected=selected_forecast(train,horizon)
            selected_values=selected["values"]
            naive=np.resize(train.tail(7).to_numpy(),horizon)
            scale=np.mean(np.abs(train.to_numpy()[7:]-train.to_numpy()[:-7]))
            folds.append({'store':store,'product':product,'cutoff':str(cutoff.date()),'horizon':horizon,
                'actual':actual.tolist(),'predicted':predicted.tolist(),'selected':selected_values.tolist(),'selected_method':selected['method'],'seasonal_naive':naive.tolist(),
                'mae':float(np.abs(actual-predicted).mean()),'naive_mae':float(np.abs(actual-naive).mean()),
                'mase':float(np.abs(actual-predicted).mean()/scale) if scale>0 else None})
    if not folds:raise ValueError('Not enough dated sales history for backtesting')
    actual=np.concatenate([r['actual'] for r in folds]);pred=np.concatenate([r['predicted'] for r in folds]);naive=np.concatenate([r['seasonal_naive'] for r in folds])
    chosen=np.concatenate([r['selected'] for r in folds])
    return {'selected_mae':float(np.abs(actual-chosen).mean()),'selected_rmse':float(np.sqrt(np.mean((actual-chosen)**2))),'selected_wape':float(np.abs(actual-chosen).sum()/actual.sum()) if actual.sum()>0 else None,'method':'two rolling origins; 14-day unseen future; training-only series selection; daily zero fill assumes complete transaction capture',
        'series_folds':len(folds),'mae':float(np.abs(actual-pred).mean()),'rmse':float(np.sqrt(np.mean((actual-pred)**2))),
        'wape':float(np.abs(actual-pred).sum()/actual.sum()) if actual.sum()>0 else None,
        'seasonal_naive_mae':float(np.abs(actual-naive).mean()),
        'beats_seasonal_naive':bool(np.abs(actual-pred).mean()<np.abs(actual-naive).mean()),'folds':folds}


def stress_api(api, inventory, count=1000):
    rng=np.random.default_rng(42)
    base=inventory.to_dict('records')
    scenarios={
        'zero_stock':{'stock_qty':0.0},
        'huge_stock':{'stock_qty':1e7},
        'demand_surge':{'recent_qty':1e5,'recent_avg':1000.0,'recent_std':500.0},
        'no_sales':{'recent_qty':0.0,'recent_avg':0.0,'historical_avg':0.0,'days_since_last_sale':365.0},
        'unseen_store_and_product':{'store_id':'UNSEEN_STORE','product_id':'UNSEEN_PRODUCT','category':'unseen_category'},
        'high_price':{'retail_price':1e6},
    }
    fields=('store_id','product_id','product_name','category','stock_qty','retail_price','recent_qty','recent_txns','recent_avg','recent_std','historical_qty','historical_txns','historical_avg','total_sold','num_sales','days_since_last_sale','store_total_txns')
    reports=[]
    for name,changes in scenarios.items():
        payload=[]
        for idx in rng.choice(len(base),size=min(len(base),max(1,count//len(scenarios))),replace=False):
            p={k:base[idx][k] for k in fields};p.update(changes)
            if name=='unseen_store_and_product':p['product_id']='UNSEEN_'+str(idx)
            payload.append(p)
        start=time.monotonic();res=requests.post(api+'/recommend',json={'products':payload},timeout=120);res.raise_for_status();data=res.json()
        predictions=data['predictions']
        for p in predictions:
            assert np.isfinite(p['confidence']) and 0<=p['confidence']<=1
            assert abs(sum(p['probabilities'].values())-1)<0.002
        for t in data['transfers']:
            assert t['transfer_qty']>0 and t['from_store']!=t['to_store']
            assert t['from_stock_after']>=0 and t['to_stock_after']>=0
            assert abs((t['from_stock_before']-t['from_stock_after'])-(t['to_stock_after']-t['to_stock_before']))<1e-6
        labels=[p['prediction'] for p in predictions];learned=[p['model_prediction'] for p in predictions]
        reports.append({'scenario':name,'rows':len(payload),'seconds':time.monotonic()-start,
            'policy_model_agreement':float(np.mean(np.array(labels)==np.array(learned))),
            'macro_f1_against_policy':f1_score(labels,learned,average='macro',labels=['Dead','Excess','Low','Optimum','Slow'],zero_division=0),
            'class_report':classification_report(labels,learned,output_dict=True,zero_division=0)})
    p={k:base[0][k] for k in fields}
    invalid=[]
    for field,value in [('stock_qty',-1),('retail_price',-5),('recent_qty',-10),('days_since_last_sale',-1)]:
        response=requests.post(api+'/predict-stock',json={'products':[{**p,field:value}]},timeout=30)
        invalid.append({'field':field,'status':response.status_code});assert response.status_code==422
    for value in ('NaN','Infinity','-Infinity'):
        body=json.dumps({'products':[p]}).replace('"stock_qty": '+str(p['stock_qty']),'"stock_qty": '+value)
        response=requests.post(api+'/predict-stock',data=body,headers={'content-type':'application/json'},timeout=30)
        invalid.append({'field':'stock_qty '+value,'status':response.status_code});assert response.status_code==422
    for payload in ([p,p], [p]*5001, [{**p,'stock_qty':1e100}]):
        response=requests.post(api+'/predict-stock',json={'products':payload},timeout=30)
        assert response.status_code==422
    response=requests.post(api+'/predict-stock',json={'products':[]},timeout=30);assert response.status_code==422
    return {'seed':42,'description':'Synthetic stress against policy labels; not independent real-world F1','scenarios':reports,'invalid_inputs':invalid,'empty_batch_status':response.status_code}


def randomized_stress(api,count=1000,seed=20261109):
    rng=np.random.default_rng(seed)
    products=[]
    for i in range(count):
        recent=float(rng.lognormal(3,2))
        products.append({'store_id':'NEW_'+str(i%11),'product_id':'UNSEEN_'+str(i),'product_name':'Random stress case','category':str(rng.choice(['dairy','pantry','unknown'])),'stock_qty':float(rng.lognormal(4,3)), 'retail_price':float(rng.lognormal(2,2)), 'recent_qty':recent,'recent_avg':float(rng.lognormal(1,1.5)),'recent_std':float(rng.lognormal(1,2)), 'historical_avg':float(rng.lognormal(1,1.5)),'days_since_last_sale':float(rng.uniform(0,365)),'total_sold':recent+float(rng.lognormal(4,2)),'num_sales':float(rng.integers(1,1000)),'store_total_txns':float(rng.integers(1,1000000))})
    r=requests.post(api+'/recommend',json={'products':products},timeout=60);r.raise_for_status();data=r.json()
    assert len(data['predictions'])==count
    agreement=float(np.mean([p['prediction']==p['model_prediction'] for p in data['predictions']]))
    report={'seed':seed,'cases':count,'distribution':'lognormal stock, demand, price and velocity; uniform inactivity; unseen store/product IDs','policy_model_agreement':agreement,'limitation':'synthetic robustness check; not real-world model F1'}
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=Path('training/data'))
    parser.add_argument('--inventory',type=Path,default=Path('integration_data/ml_inventory.csv'))
    parser.add_argument('--output',type=Path,default=Path('evaluation'))
    parser.add_argument('--models-dir',type=Path,default=Path('saved_models'))
    parser.add_argument('--api',default='http://127.0.0.1:8001')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    stress=stress_api(args.api,pd.read_csv(args.inventory))
    (args.output/'stress.json').write_text(json.dumps(stress,indent=2))
    random_result=randomized_stress(args.api)
    (args.output/'random_stress.json').write_text(json.dumps(random_result,indent=2))
    forecast=forecast_backtest(pd.read_csv(args.data_dir/'transactions.csv'))
    (args.output/'forecast_backtest.json').write_text(json.dumps(forecast,indent=2))
    classification=json.loads((args.models_dir/'evaluation.json').read_text())
    summary=f'''# Jiran evaluation\n\nClassification target: agreement with policy-generated labels, not human outcomes. This is a development re-evaluation after prior test results were inspected; independent final validation is still required.\n\n- Product-held-out macro F1: {classification['macro_f1']:.3f}\n- Weighted F1: {classification['weighted_f1']:.3f}\n- Train macro F1: {classification['train_macro_f1']:.3f}\n- Majority baseline macro F1: {classification['baseline_macro_f1']:.3f}\n- Forecast MAE: {forecast['mae']:.3f}\n- Selected forecast MAE: {forecast['selected_mae']:.3f}\n- Seasonal naive MAE: {forecast['seasonal_naive_mae']:.3f}\n- Selected forecast WAPE: {forecast['selected_wape']:.3f}\n- Selected forecast beats naive on MAE: {forecast['selected_mae'] < forecast['seasonal_naive_mae']}\n- Selected forecast RMSE: {forecast['selected_rmse']:.3f}\n- Prophet-only RMSE: {forecast['rmse']:.3f}\n\nThere are only three stores and one stock snapshot. The development split has already been inspected; scores cannot establish independent generalization. Forecast folds overlap and are not independent samples. Zero-sales days assume complete source capture. Stress results are synthetic robustness evidence only. Classifier holdout must not be reused for tuning; further model selection requires new held-out products or future snapshots.\n'''
    summary += "\n## Synthetic stress: model agreement with stock policy\n\n"
    summary += "| Scenario | Cases | Agreement |\n|---|---:|---:|\n"
    for scenario in stress['scenarios']:
        summary += f"| {scenario['scenario']} | {scenario['rows']} | {scenario['policy_model_agreement']:.1%} |\n"
    summary += f"\nAdditional randomized stress: {random_result['cases']} cases, {random_result['policy_model_agreement']:.1%} policy agreement. Simulations cover known rule boundaries and are not independent business labels. The API continues to return the explicit policy decision, with separate model support. These tests do not establish production quality.\n"
    (args.output/'REPORT.md').write_text(summary)
    print(summary)

if __name__=='__main__':main()
