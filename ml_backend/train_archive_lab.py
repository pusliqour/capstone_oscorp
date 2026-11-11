"""Train and evaluate isolated models on the recovered GENERATED archive.

Never promotes models into the running three-store demonstration. Results are
synthetic research evidence, not independent real-world business accuracy.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import warnings
import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import classification_report, f1_score, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit, GroupKFold, cross_val_score
from forecasting import selected_forecast, forecast_daily
from inventory_policy import policy_metrics, stock_policy_label
from augmentation import PolicyAugmentedClassifier, simulate

FEATURES=['stock_qty','stock_value','forecast_7d','forecast_14d','forecast_30d','forecast_60d','forecast_acceleration','forecast_confidence_30d','is_trending_up','is_trending_down','is_stable','days_since_last_sale','velocity_trend','sales_volatility','is_active','is_dormant','recent_qty','recent_txns','recent_avg','recent_std','historical_qty','historical_txns','historical_avg','price_tier','is_perishable','is_budget','is_premium','category_encoded','retail_price','store_size_encoded','store_total_txns','sales_rank_in_store','is_top_10_in_store','is_top_50_in_store','total_sold','num_sales','price_velocity_interaction','coverage_30d_feat','days_since_over_90','days_of_stock_30d_feat','stockout_risk_7d']


def derived_features(frame):
    frame=frame.copy()
    frame['stock_value']=frame.stock_qty*frame.retail_price
    frame['forecast_acceleration']=(frame.forecast_7d/7)/(frame.forecast_30d/30+0.1)
    frame['forecast_confidence_30d']=0.0 # no calibrated intervals in this research snapshot
    frame['is_trending_up']=(frame.forecast_acceleration>1.1).astype(int)
    frame['is_trending_down']=(frame.forecast_acceleration<0.9).astype(int)
    frame['is_stable']=((frame.forecast_acceleration>=0.9)&(frame.forecast_acceleration<=1.1)).astype(int)
    frame['velocity_trend']=frame.recent_avg/(frame.historical_avg+0.1)
    frame['sales_volatility']=frame.recent_std/(frame.recent_avg+0.1)
    frame['is_active']=(frame.days_since_last_sale<=7).astype(int)
    frame['is_dormant']=frame['days_since_over_90']=(frame.days_since_last_sale>90).astype(int)
    frame['price_tier']=np.select([frame.retail_price<=3,frame.retail_price<=7,frame.retail_price<=15],[0,1,2],default=3)
    frame['is_perishable']=frame.category.isin(['produce','dairy','meat','bakery']).astype(int)
    frame['is_budget']=(frame.retail_price<5).astype(int);frame['is_premium']=(frame.retail_price>15).astype(int)
    frame['store_size_encoded']=np.select([frame.store_total_txns<=200000,frame.store_total_txns<=350000],[0,1],default=2)
    frame['is_top_10_in_store']=(frame.sales_rank_in_store<=10).astype(int)
    frame['is_top_50_in_store']=(frame.sales_rank_in_store<=50).astype(int)
    frame['price_velocity_interaction']=frame.retail_price*frame.velocity_trend
    metrics=frame.apply(lambda r:pd.Series(policy_metrics(stock_qty=r.stock_qty,forecast_30d=r.forecast_30d,forecast_7d=r.forecast_7d,recent_qty=r.recent_qty)),axis=1)
    for col in metrics:frame[col]=metrics[col]
    return frame


def load_features(db):
    # Use only complete days BEFORE the earliest stock snapshot. No later
    # transactions are allowed into snapshot features, even if present in CSV.
    cutoff=db.execute('select least((select min(cast(updated_at as date)) from stock),(select max(sales_date)+1 from daily_sales))').fetchone()[0]
    db.execute("create or replace temp view past as select * from daily_sales where sales_date < date '"+cutoff.isoformat()+"'")
    query='''with a as (
       select store_id,product_id,sum(quantity) total_sold,sum(transaction_count) num_sales,
       sum(quantity) filter(where sales_date>=cast(? as date)-30) recent_qty,
       sum(transaction_count) filter(where sales_date>=cast(? as date)-30) recent_txns,
       sum(quantity_squared_sum) filter(where sales_date>=cast(? as date)-30) recent_squares,
       sum(quantity) filter(where sales_date<cast(? as date)-30) historical_qty,
       sum(transaction_count) filter(where sales_date<cast(? as date)-30) historical_txns,
       sum(quantity) filter(where sales_date>=cast(? as date)-28) qty_28,
       date_diff('day',max(sales_date),cast(? as date)) days_since_last_sale
       from past group by store_id,product_id
     ), stats as (select store_id,sum(transaction_count) store_total_txns from past group by store_id)
     select s.store_id,s.product_id,p.product_name,p.category,p.retail_price,s.stock_qty,
       coalesce(a.total_sold,0) total_sold,coalesce(a.num_sales,0) num_sales,
       coalesce(a.recent_qty,0) recent_qty,coalesce(a.recent_txns,0) recent_txns,coalesce(a.recent_squares,0) recent_squares,
       coalesce(a.historical_qty,0) historical_qty,coalesce(a.historical_txns,0) historical_txns,
       coalesce(a.qty_28,0) qty_28,coalesce(a.days_since_last_sale,365) days_since_last_sale,
       coalesce(stats.store_total_txns,0) store_total_txns,
       dense_rank() over(partition by s.store_id order by coalesce(a.total_sold,0) desc) sales_rank_in_store
     from stock s join products p using(product_id) left join a using(store_id,product_id) left join stats using(store_id)'''
    frame=db.execute(query,[cutoff]*7).fetchdf()
    frame['recent_avg']=frame.recent_qty/np.maximum(frame.recent_txns,1)
    frame['historical_avg']=frame.historical_qty/np.maximum(frame.historical_txns,1)
    variance=(frame.recent_squares-frame.recent_qty**2/np.maximum(frame.recent_txns,1))/np.maximum(frame.recent_txns-1,1)
    frame['recent_std']=np.sqrt(np.maximum(variance,0))
    for h in (7,14,30,60):frame[f'forecast_{h}d']=frame.qty_28/28*h
    frame['forecast_method']='recent_mean'
    return frame,pd.Timestamp(cutoff)


def series_for(db,store,product,cutoff):
    data=db.execute('select sales_date,quantity from daily_sales where store_id=? and product_id=? and sales_date< ? order by sales_date',[store,product,cutoff.date()]).fetchdf()
    if data.empty:return None
    return pd.Series(data.quantity.to_numpy(),index=pd.DatetimeIndex(data.sales_date)).reindex(pd.date_range(data.sales_date.min(),cutoff-pd.Timedelta(days=1)),fill_value=0.0)


def forecast_experiments(db,frame,cutoff,output):
    # One high-volume series per store, chosen from historical data only.
    ranking=db.execute('select store_id,product_id,sum(quantity) selection_volume from daily_sales where sales_date < ? group by store_id,product_id',[ (cutoff-pd.Timedelta(days=28)).date() ]).fetchdf()
    pairs=frame.merge(ranking,on=['store_id','product_id'],how='inner').sort_values('selection_volume',ascending=False).drop_duplicates('store_id')
    rows=[];folds=[]
    for idx,row in enumerate(pairs.itertuples(index=False)):
        series=series_for(db,row.store_id,row.product_id,cutoff)
        if series is None or len(series)<56:continue
        selected=selected_forecast(series,60)
        mask=(frame.store_id==row.store_id)&(frame.product_id==row.product_id)
        frame.loc[mask,'forecast_method']=selected['method']
        record={'store_id':row.store_id,'product_id':row.product_id,'method':selected['method']}
        for h in (7,14,30,60):
            value=float(selected['values'][:h].sum());frame.loc[mask,f'forecast_{h}d']=value;record[f'forecast_{h}d']=value
        rows.append(record)
        for lag in (28,14):
            train=series.iloc[:-lag];actual=series.iloc[-lag:-lag+14] if lag>14 else series.iloc[-14:]
            candidate=selected_forecast(train,14)
            baseline=forecast_daily(train,14,'weekly_naive')
            folds.append({'store_id':row.store_id,'product_id':row.product_id,'training_end':str(train.index[-1].date()),'method':candidate['method'],'actual':actual.tolist(),'prediction':candidate['values'].tolist(),'baseline':baseline.tolist()})
        if (idx+1)%10==0:print('Forecast stores completed:',idx+1,flush=True)
    forecasts=frame[['store_id','product_id','forecast_method','forecast_7d','forecast_14d','forecast_30d','forecast_60d']]
    forecasts.to_csv(output/'forecasts.csv',index=False)
    actual=np.concatenate([f['actual'] for f in folds]);pred=np.concatenate([f['prediction'] for f in folds]);baseline=np.concatenate([f['baseline'] for f in folds])
    metrics={'data_origin':'synthetic_generated','series':len(rows),'folds':len(folds),'selected_mae':float(np.abs(actual-pred).mean()),'baseline_mae':float(np.abs(actual-baseline).mean()),'selected_rmse':float(np.sqrt(np.mean((actual-pred)**2))),'baseline_rmse':float(np.sqrt(np.mean((actual-baseline)**2))),'selected_wape':float(np.abs(actual-pred).sum()/actual.sum()),'method_counts':dict(Counter(f['method'] for f in folds)),'limitations':['Two rolling temporal origins; series ranking precedes the first outer test, method selection uses inner historical validation','Synthetic data cannot establish real-world accuracy']}
    (output/'forecast_metrics.json').write_text(json.dumps(metrics,indent=2));(output/'forecast_folds.json').write_text(json.dumps(folds,indent=2))
    return derived_features(frame),metrics


def recency_check(model,X_test,days=(60,95,120,180,365)):
    """Held-out-store rows with sales stopped for N days; model vs the rule."""
    out={}
    for d in days:
        rows=[simulate(r,{'recent_qty':0,'recent_avg':0,'recent_std':0,'days_since_last_sale':float(d)}) for r in X_test.to_dict('records')]
        frame=pd.DataFrame(rows,columns=X_test.columns);rule=frame.apply(stock_policy_label,axis=1)
        out[f'{d}_days']={'cases':len(frame),'agreement':float((model.predict(frame)==rule.to_numpy()).mean()),'rule_dead_share':float((rule=='Dead').mean())}
    return out


def train(lab):
    lab=Path(lab);output=lab/'models';output.mkdir(exist_ok=True)
    manifest=json.loads((lab/'recovery.json').read_text())
    if manifest['data_origin']!='synthetic_generated':raise ValueError('Expected the labelled synthetic recovery dataset')
    db=duckdb.connect(str(lab/'archive.duckdb'),read_only=True)
    frame,cutoff=load_features(db);print('Snapshot rows:',len(frame),'cutoff:',cutoff,flush=True)
    frame,forecast_metrics=forecast_experiments(db,frame,cutoff,output)
    target=frame.apply(stock_policy_label,axis=1);groups=frame.store_id
    train_idx,test_idx=next(GroupShuffleSplit(n_splits=1,test_size=0.2,random_state=42).split(frame,target,groups))
    categories=sorted(frame.iloc[train_idx].category.unique());encoding={v:i for i,v in enumerate(categories)}
    frame['category_encoded']=frame.category.map(encoding).fillna(-1)
    X=frame[FEATURES].fillna(0);y=target
    # Fold-local policy simulations (same as the live model). Without them the
    # generated data has 3 rows inactive >90 days, so the recency rule is unlearnable.
    # Class balancing is done by the wrapper's sample weights.
    models={
      'random_forest':PolicyAugmentedClassifier(RandomForestClassifier(n_estimators=160,max_depth=10,min_samples_leaf=5,random_state=42,n_jobs=2)),
      'hist_gradient_boosting':PolicyAugmentedClassifier(HistGradientBoostingClassifier(max_iter=120,max_leaf_nodes=15,l2_regularization=2,random_state=42)),
    }
    cv=GroupKFold(n_splits=3);scores={}
    for name,model in models.items():
        score=cross_val_score(model,X.iloc[train_idx],y.iloc[train_idx],groups=groups.iloc[train_idx],cv=cv,scoring='f1_macro',n_jobs=1,error_score='raise')
        scores[name]=score.tolist();print(name,'training-only grouped CV',score.tolist(),flush=True)
    chosen=max(scores,key=lambda name:np.mean(scores[name]));model=clone(models[chosen]).fit(X.iloc[train_idx],y.iloc[train_idx])
    pred=model.predict(X.iloc[test_idx]);labels=sorted(y.unique())
    baseline=DummyClassifier(strategy='most_frequent').fit(X.iloc[train_idx],y.iloc[train_idx])
    report={'data_origin':'synthetic_generated','target':'agreement with explicit inventory policy; not independent business ground truth','evaluation_status':'development research; re-evaluated after correcting temporal series selection','rule_baseline_macro_f1':1.0,'chosen_model':chosen,'validation_macro_f1':scores,'macro_f1':f1_score(y.iloc[test_idx],pred,average='macro',labels=labels,zero_division=0),'weighted_f1':f1_score(y.iloc[test_idx],pred,average='weighted',zero_division=0),'train_macro_f1':f1_score(y.iloc[train_idx],model.predict(X.iloc[train_idx]),average='macro',labels=labels,zero_division=0),'baseline_macro_f1':f1_score(y.iloc[test_idx],baseline.predict(X.iloc[test_idx]),average='macro',labels=labels,zero_division=0),'train_stores':sorted(groups.iloc[train_idx].unique()),'test_stores':sorted(groups.iloc[test_idx].unique()),'train_rows':len(train_idx),'test_rows':len(test_idx),'labels':labels,'confusion_matrix':confusion_matrix(y.iloc[test_idx],pred,labels=labels).tolist(),'classification_report':classification_report(y.iloc[test_idx],pred,labels=labels,output_dict=True,zero_division=0),'snapshot_cutoff':str(cutoff),'production_promoted':False}
    assert not set(report['train_stores'])&set(report['test_stores'])
    report['recency_check_test_stores']=recency_check(model,X.iloc[test_idx])
    joblib.dump({'model':model,'features':FEATURES,'categories':categories,'data_origin':'synthetic_generated','source_hashes':manifest['source_hashes']},output/'archive_model.joblib')
    (output/'classifier_metrics.json').write_text(json.dumps(report,indent=2))
    frame['policy_prediction']=target;frame['model_prediction']=model.predict(X)
    frame['model_support']=model.predict_proba(X).max(axis=1)
    frame.to_csv(output/'stock_predictions.csv',index=False)
    (output/'REPORT.md').write_text(f"# Recovered synthetic archive research\n\nGenerated data only; no production promotion.\n\n- Stores: {manifest['summary']['stores']}\n- Stock rows: {len(frame)}\n- Transaction lines: {manifest['summary']['transaction_lines']:,}\n- Store-held-out macro F1 against policy labels: {report['macro_f1']:.3f}\n- Train macro F1: {report['train_macro_f1']:.3f}\n- Majority baseline macro F1: {report['baseline_macro_f1']:.3f}\n- Forecast MAE: {forecast_metrics['selected_mae']:.3f}\n- Weekly baseline MAE: {forecast_metrics['baseline_mae']:.3f}\n\nThe classifier split holds out ten complete stores. Candidate selection uses only grouped validation within training stores. Forecast tests use future days outside model selection. The source is generated and labels are rule-based, so these results do not establish independent real-world accuracy.\n")
    print(json.dumps({k:v for k,v in report.items() if k not in ('classification_report','confusion_matrix')},indent=2));db.close()
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--lab',type=Path,required=True)
    args=parser.parse_args();train(args.lab)
