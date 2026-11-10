"""Local team gateway. Never forwards development JWTs or admin endpoints publicly.

Run with .venv/bin/uvicorn scripts.team_gateway:app --host 127.0.0.1 --port 8787
Point an HTTPS tunnel only at this gateway, never at the Supabase development port.
"""
import asyncio
import base64
from collections import defaultdict, deque
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

ROOT=Path(__file__).resolve().parents[1]
def read_env(path):return dict(line.split('=',1) for line in path.read_text().splitlines() if '=' in line)
backend=read_env(ROOT/'ml_backend/.env')
frontend=read_env(ROOT/'frontend/.env.local')
UPSTREAM=backend['SUPABASE_URL']
ANON=frontend['VITE_SUPABASE_ANON_KEY']
SECRET=secrets.token_bytes(32)
PUBLIC_KEY='sb_publishable_jiran_team_gateway'
TABLES={'account_activity','profiles','retailer_profiles','retailer_locations','pos_connections','products','product_variations','product_inventory','orders','order_items','retailer_listings','exchange_requests','exchange_request_dismissals','ml_inventory_predictions','ml_inventory_transfer_recommendations','connection_intelligence'}
RPCS={'my_sales_summary','retailer_directory','archive_overview','archive_inventory','archive_sales','exchange_action','get_retailer_names','get_retailer_contact','save_my_profile','create_my_store','save_my_location','remove_my_location','delete_my_store','save_my_product','delete_my_product'}
SESSIONS={}
REFRESH={}
LOGIN_ATTEMPTS=defaultdict(deque)
LOCK=asyncio.Lock()
app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
app.add_middleware(CORSMiddleware,allow_origins=['https://pusliqour.github.io','http://127.0.0.1:5173','http://localhost:5173'],allow_methods=['GET','HEAD','POST','PUT','PATCH','DELETE','OPTIONS'],allow_headers=['authorization','apikey','content-type','prefer','range','range-unit','x-client-info','x-supabase-api-version','accept-profile','content-profile'],expose_headers=['content-range','range-unit','preference-applied'],allow_credentials=False)

def encode(data):return base64.urlsafe_b64encode(data).rstrip(b'=').decode()
def issue(data):
    expires=int(time.time())+min(int(data.get('expires_in',3600)),3600)
    refresh=secrets.token_urlsafe(40)
    claims={'sub':data['user']['id'],'role':'authenticated','exp':expires,'iat':int(time.time()),'jti':secrets.token_urlsafe(24)}
    unsigned=encode(b'{"alg":"HS256","typ":"JWT"}')+'.'+encode(json.dumps(claims).encode())
    token=unsigned+'.'+encode(hmac.new(SECRET,unsigned.encode(),hashlib.sha256).digest())
    record={'access':data['access_token'],'refresh':data['refresh_token'],'exp':expires,'user':data['user'],'gateway_refresh':refresh}
    SESSIONS[token]=record;REFRESH[refresh]=token
    return {'access_token':token,'refresh_token':refresh,'token_type':'bearer','expires_in':expires-int(time.time()),'expires_at':expires,'user':data['user']}

def error(message,status):return JSONResponse({'error':message,'message':message},status_code=status)
def session(request):
    token=request.headers.get('authorization','').removeprefix('Bearer ').strip()
    record=SESSIONS.get(token)
    return (token,record) if record and record['exp']>time.time() else (None,None)

def forget(token):
    record=SESSIONS.pop(token,None)
    if record:REFRESH.pop(record['gateway_refresh'],None)

@app.get('/health')
async def health():return {'status':'ok','mode':'local-team-gateway','data_provenance':'unverified three-store import plus explicitly synthetic Jiran.zip archive'}

@app.api_route('/{path:path}',methods=['GET','HEAD','POST','PUT','PATCH','DELETE'])
async def proxy(path:str,request:Request):
    length=request.headers.get('content-length')
    if length and int(length)>2_000_000:return error('Request too large',413)
    body=await request.body()
    if len(body)>2_000_000:return error('Request too large',413)
    async with httpx.AsyncClient(timeout=30,follow_redirects=False) as client:
        if path=='auth/v1/token' and request.method=='POST':
            grant=request.query_params.get('grant_type')
            try:payload=json.loads(body)
            except (ValueError,TypeError):return error('Invalid JSON',400)
            if grant=='password':
                identity=request.headers.get('cf-connecting-ip',request.client.host)
                now=time.time();attempts=LOGIN_ATTEMPTS[identity]
                while attempts and attempts[0]<now-60:attempts.popleft()
                if len(attempts)>=20:return error('Too many login attempts; try again shortly',429)
                attempts.append(now)
                payload={'email':payload.get('email',''),'password':payload.get('password','')}
                response=await client.post(UPSTREAM+'/auth/v1/token?grant_type=password',headers={'apikey':ANON},json=payload)
                if response.status_code!=200:return error('Incorrect email or password',400)
                # Purge old sessions to bound memory. Expired access may still refresh for 24h.
                for token,record in list(SESSIONS.items()):
                    if record['exp']<now-86400:forget(token)
                if len(SESSIONS)>500:return error('Demo session capacity reached',503)
                return JSONResponse(issue(response.json()))
            if grant=='refresh_token':
                async with LOCK:
                    old=REFRESH.get(payload.get('refresh_token'))
                    record=SESSIONS.get(old)
                    if not record or record['exp']<time.time()-86400:return error('Session expired; sign in again',401)
                    response=await client.post(UPSTREAM+'/auth/v1/token?grant_type=refresh_token',headers={'apikey':ANON},json={'refresh_token':record['refresh']})
                    if response.status_code!=200:forget(old);return error('Session expired; sign in again',401)
                    forget(old)
                    return JSONResponse(issue(response.json()))
            return error('Unsupported authentication method',403)
        token,record=session(request)
        if not record:return error('Sign in required',401)
        if path=='auth/v1/user' and request.method=='GET':return JSONResponse(record['user'])
        if path=='auth/v1/user' and request.method=='PUT':
            try: payload=json.loads(body)
            except (ValueError,TypeError): return error('Invalid JSON',400)
            if not isinstance(payload,dict) or set(payload)!={'password'}:
                return error('Only password updates are available here',400)
            password=payload.get('password')
            if not isinstance(password,str) or len(password)<10 or len(password)>128:
                return error('Use a password between 10 and 128 characters',400)
            response=await client.put(UPSTREAM+'/auth/v1/user',headers={'apikey':ANON,'authorization':'Bearer '+record['access']},json={'password':password})
            if response.status_code!=200:return error('Could not update password',response.status_code)
            record['user']=response.json()
            return JSONResponse(record['user'])
        if path=='auth/v1/logout' and request.method=='POST':
            await client.post(UPSTREAM+'/auth/v1/logout',headers={'apikey':ANON,'authorization':'Bearer '+record['access']})
            forget(token);return Response(status_code=204)
        parts=path.split('/')
        allowed=(len(parts)==3 and parts[:2]==['rest','v1'] and parts[2] in TABLES)
        allowed=allowed or (len(parts)==4 and parts[:3]==['rest','v1','rpc'] and parts[3] in RPCS)
        if not allowed:return error('Endpoint is not available in the team demo',403)
        # Only gateway-issued sessions get upstream credentials. Browser-supplied keys are ignored.
        headers={'apikey':ANON,'authorization':'Bearer '+record['access']}
        for key in ('content-type','prefer','range','range-unit','accept'):
            if key in request.headers:headers[key]=request.headers[key]
        response=await client.request(request.method,UPSTREAM+'/'+path,params=request.query_params.multi_items(),headers=headers,content=body)
        output_headers={k:v for k,v in response.headers.items() if k in ('content-type','content-range','range-unit','preference-applied')}
        output_headers['cache-control']='no-store'
        return Response(response.content,status_code=response.status_code,headers=output_headers)
