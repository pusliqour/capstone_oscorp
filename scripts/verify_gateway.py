"""Check session wrapping and account isolation through the public gateway."""
import json
import os
from pathlib import Path
import requests
URL=os.getenv('JIRAN_GATEWAY_URL','http://127.0.0.1:8787')
ROOT=Path(__file__).resolve().parents[1]
creds=json.loads((Path.home()/'Documents/Jiran/team-demo-credentials.json').read_text())
for email,account in creds.items():
    response=requests.post(URL+'/auth/v1/token?grant_type=password',json={'email':email,'password':account['password']},timeout=30)
    response.raise_for_status();session=response.json();headers={'authorization':'Bearer '+session['access_token'],'apikey':'sb_publishable_jiran_team_gateway'}
    user=requests.get(URL+'/auth/v1/user',headers=headers,timeout=30);user.raise_for_status()
    response=requests.get(URL+'/rest/v1/products?select=id,retailer_id',headers=headers,timeout=30);response.raise_for_status();rows=response.json()
    assert rows and all(r['retailer_id']==user.json()['id'] for r in rows)
    assert requests.get(URL+'/rest/v1/ml_inventory',headers=headers,timeout=30).status_code==403
    assert requests.get(URL+'/auth/v1/admin/users',headers=headers,timeout=30).status_code==403
    fresh=requests.post(URL+'/auth/v1/token?grant_type=refresh_token',json={'refresh_token':session['refresh_token']},timeout=30);fresh.raise_for_status()
    assert requests.get(URL+'/auth/v1/user',headers=headers,timeout=30).status_code==401
    newheaders={'authorization':'Bearer '+fresh.json()['access_token']}
    assert requests.post(URL+'/auth/v1/logout',headers=newheaders,timeout=30).status_code==204
    assert requests.get(URL+'/auth/v1/user',headers=newheaders,timeout=30).status_code==401
    print(email,'gateway login, isolation, refresh rotation and logout passed')
values=dict(line.split('=',1) for line in (ROOT/'ml_backend/.env').read_text().splitlines() if '=' in line)
# Even a correctly signed development service JWT cannot enter the gateway.
assert requests.get(URL+'/rest/v1/profiles',headers={'authorization':'Bearer '+values['SUPABASE_KEY']},timeout=30).status_code==401
assert requests.get(URL+'/rest/v1/products',timeout=30).status_code==401
print('Raw development JWT and anonymous access denied')
