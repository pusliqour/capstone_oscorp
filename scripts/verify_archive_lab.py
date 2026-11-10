"""Check the local recovered ML API and write an honest scenario report."""
import argparse
import json
from pathlib import Path
import requests

def verify(url,output):
    health=requests.get(url+'/',timeout=20);health.raise_for_status()
    assert health.json()['data_origin']=='synthetic_generated'
    response=requests.get(url+'/stores',timeout=20);response.raise_for_status();stores=response.json()['stores']
    rows=[]
    for entry in stores[:10]:
        response=requests.get(url+'/inventory',params={'store_id':entry['store_id'],'limit':1},timeout=20);response.raise_for_status();product=response.json()['items'][0]
        key={name:product[name] for name in ('store_id','product_id')}
        for name,override in [('snapshot',{}),('stockout',{'stock_qty':0,'demand_30d':10000}),('huge_stock',{'stock_qty':1e7}),('inactive_365_days',{'days_since_last_sale':365}),('demand_surge',{'stock_qty':10,'demand_30d':1e5})]:
            response=requests.post(url+'/predict-stock',json={**key,**override},timeout=20);response.raise_for_status();result=response.json()
            assert result['saved_to_database'] is False and result['data_origin']=='synthetic_generated'
            assert result['review_required'] is (not result['agrees_with_policy'])
            assert 0<=result['model_support']<=1
            if name=='stockout':assert result['policy_prediction']=='Low'
            if name=='inactive_365_days':assert result['policy_prediction']=='Dead'
            rows.append({'store_id':entry['store_id'],'scenario':name,'policy':result['policy_prediction'],'model':result['model_prediction'],'agrees':result['agrees_with_policy']})
        assert requests.post(url+'/predict-stock',json={**key,'stock_qty':-1},timeout=20).status_code==422
    for value in (float('nan'),float('inf'),float('-inf')):
        response=requests.post(url+'/predict-stock',data=json.dumps({**key,'stock_qty':value}),headers={'content-type':'application/json'},timeout=20)
        assert response.status_code==422
    assert requests.post(url+'/predict-stock',json={'store_id':'missing','product_id':'missing'},timeout=20).status_code==404
    summary={name:{'cases':len(group:=[row for row in rows if row['scenario']==name]),'model_policy_agreement':sum(row['agrees'] for row in group)/len(group)} for name in sorted({row['scenario'] for row in rows})}
    report={'data_origin':'synthetic_generated','cases':len(rows),'scenarios':summary,'results':rows,'production_writes':False,'limitations':['Model disagreement on stress cases is reported, not hidden by API success','Synthetic rule labels do not establish business effectiveness']}
    Path(output).write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2));return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--url',default='http://127.0.0.1:8003');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();verify(args.url,args.output)
