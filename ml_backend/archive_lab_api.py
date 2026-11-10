"""Read-only local API for recovered synthetic archive models.

Start with ARCHIVE_LAB_DIR=/absolute/path/to/lab and bind to 127.0.0.1 only.
No production accounts or application tables are modified.
"""
import json
import os
from pathlib import Path
import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from train_archive_lab import derived_features
from inventory_policy import stock_policy_label

LAB=Path(os.environ['ARCHIVE_LAB_DIR']).resolve()
manifest=json.loads((LAB/'recovery.json').read_text())
if manifest['data_origin']!='synthetic_generated':raise RuntimeError('Unexpected dataset provenance')
artifact=joblib.load(LAB/'models/archive_model.joblib')
if artifact['data_origin']!='synthetic_generated' or artifact['source_hashes']!=manifest['source_hashes']:raise RuntimeError('Model/source fingerprints disagree')
snapshot=pd.read_csv(LAB/'models/stock_predictions.csv')
lookup=snapshot.set_index(['store_id','product_id'],verify_integrity=True)
app=FastAPI(title='Jiran Archive Research Lab',description='Recovered GENERATED data and isolated models. Experimental research only; separate from the three team stores.')

@app.exception_handler(RequestValidationError)
async def invalid_request(request,exc):
    return JSONResponse(status_code=422,content={'detail':[{'loc':list(error['loc']),'msg':error['msg'],'type':error['type']} for error in exc.errors()]})

class Scenario(BaseModel):
    model_config={'allow_inf_nan':False,'extra':'forbid'}
    store_id:str=Field(min_length=1,max_length=120)
    product_id:str=Field(min_length=1,max_length=120)
    stock_qty:float|None=Field(None,ge=0,le=1e9)
    retail_price:float|None=Field(None,ge=0,le=1e9)
    demand_30d:float|None=Field(None,ge=0,le=1e12)
    days_since_last_sale:float|None=Field(None,ge=0,le=1e6)

@app.get('/')
def health():
    return {'status':'ready','data_origin':'synthetic_generated','summary':manifest['summary'],'production_model_replaced':False,'inventory_endpoint':'/inventory','interactive_docs':'/docs'}

@app.get('/stores')
def stores():
    return {'data_origin':'synthetic_generated','stores':snapshot.groupby('store_id').size().rename('products').reset_index().to_dict('records')}

@app.get('/inventory')
def inventory(store_id:str,limit:int=Query(25,ge=1,le=100),offset:int=Query(0,ge=0)):
    rows=snapshot.loc[snapshot.store_id==store_id]
    if rows.empty:raise HTTPException(404,'Store not found in recovered snapshot')
    cols=['store_id','product_id','product_name','category','stock_qty','retail_price','forecast_30d','forecast_method','policy_prediction','model_prediction']
    return {'data_origin':'synthetic_generated','total':len(rows),'items':rows.iloc[offset:offset+limit][cols].to_dict('records')}

@app.get('/evaluation')
def evaluation():
    return {'data_origin':'synthetic_generated','classifier':json.loads((LAB/'models/classifier_metrics.json').read_text()),'forecast':json.loads((LAB/'models/forecast_metrics.json').read_text())}

@app.post('/predict-stock')
def predict(scenario:Scenario):
    key=(scenario.store_id,scenario.product_id)
    if key not in lookup.index:raise HTTPException(404,'Store/product pair not found in the recovered snapshot')
    row=lookup.loc[key].to_dict();row['store_id'],row['product_id']=key
    for name in ('stock_qty','retail_price','days_since_last_sale'):
        value=getattr(scenario,name)
        if value is not None:row[name]=value
    if scenario.demand_30d is not None:
        for h in (7,14,30,60):row[f'forecast_{h}d']=scenario.demand_30d*h/30
        row['forecast_method']='scenario_override'
    frame=derived_features(pd.DataFrame([row]))
    encoding={value:i for i,value in enumerate(artifact['categories'])}
    frame['category_encoded']=frame.category.map(encoding).fillna(-1)
    X=frame[artifact['features']].fillna(0)
    probabilities=artifact['model'].predict_proba(X)[0]
    model_label=str(artifact['model'].classes_[probabilities.argmax()])
    policy=stock_policy_label(frame.iloc[0])
    return {'data_origin':'synthetic_generated','store_id':scenario.store_id,'product_id':scenario.product_id,'product_name':row['product_name'],'policy_prediction':policy,'decision_source':'inventory_policy','model_prediction':model_label,'model_support':float(probabilities.max()),'agrees_with_policy':model_label==policy,'review_required':model_label!=policy,'stock_qty':row['stock_qty'],'demand_30d':float(frame.iloc[0].forecast_30d),'forecast_method':row['forecast_method'],'simulation':bool(scenario.model_fields_set-{'store_id','product_id'}),'saved_to_database':False}
