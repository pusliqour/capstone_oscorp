"""Extract public business facts from official locators; replace only demo fillers.

No accounts are created for real companies, and no messages are sent. Each mapping
is explicitly a public-reference location/contact for a synthetic demonstration.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import uuid
from urllib.parse import urlsplit
import requests

ROOT=Path(__file__).resolve().parents[1]
ALMAYA='https://www.almaya.ae/supermarket.php'
ALMAYA_CONTACT='https://www.almaya.ae/contact-us.php'
CHOITHRAMS='https://choithramsgcc.com/en/storelocator/'
CHOITHRAMS_CONTACT='https://choithramsgcc.com/en/contactus'

class AlMayaParser(HTMLParser):
    def __init__(self):
        super().__init__();self.depth=0;self.row=None;self.pclass=None;self.rows=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='div':
            self.depth+=1
            if 'store_box' in a.get('class','').split():
                self.row={'city':a.get('data-country'),'name':'','phone':None,'map_link':None};self.startdepth=self.depth
        if self.row is not None:
            if tag=='p':self.pclass=a.get('class')
            if tag=='a':
                href=a.get('href','')
                if href.startswith('tel:') and self.row['phone'] is None:self.row['phone']=href[4:]
                if 'maps' in href and self.row['map_link'] is None:self.row['map_link']=href
    def handle_data(self,data):
        if self.row is not None and self.pclass=='sloc':self.row['name']+=data
    def handle_endtag(self,tag):
        if tag=='p':self.pclass=None
        if tag=='div':
            if self.row is not None and self.depth==self.startdepth:
                self.row['name']=' '.join(self.row['name'].split());self.rows.append(self.row);self.row=None
            self.depth-=1

class ChoithramsParser(HTMLParser):
    def __init__(self):super().__init__();self.rows=[];self.row=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='a' and a.get('data-src','').startswith('https://www.google.com/maps'):
            self.row={'name':'','map_link':a['data-src'].strip()}
    def handle_data(self,data):
        if self.row is not None:self.row['name']+=data
    def handle_endtag(self,tag):
        if tag=='a' and self.row is not None:
            self.row['name']=' '.join(self.row['name'].split());self.rows.append(self.row);self.row=None

def normalize_phone(raw):
    digits=re.sub(r'\D','',raw)
    if digits.startswith('0'):digits='971'+digits[1:]
    if not digits.startswith('971') or not 11<=len(digits)<=12:raise ValueError('Invalid UAE public phone')
    return '+'+digits

def collect():
    now=datetime.now(timezone.utc).isoformat();pages={}
    cache=ROOT/'.private/public-business-sources';cache.mkdir(parents=True,exist_ok=True)
    for index,url in enumerate((ALMAYA,ALMAYA_CONTACT,CHOITHRAMS,CHOITHRAMS_CONTACT)):
        response=requests.get(url,timeout=30,headers={'User-Agent':'Jiran research demo contact import'})
        response.raise_for_status();pages[url]=response.text
        (cache/f'{index}.html').write_text(response.text)
    if 'info@almaya.ae' not in pages[ALMAYA_CONTACT] or 'support@choithrams.com' not in pages[CHOITHRAMS_CONTACT]:raise ValueError('Official contact page format changed')
    a=AlMayaParser();a.feed(pages[ALMAYA]);c=ChoithramsParser();c.feed(pages[CHOITHRAMS]);rows=[]
    city_names={'AbuDhabi':'Abu Dhabi','AlAin':'Al Ain','RAK':'Ras Al Khaimah'}
    unique={r['name']:r for r in a.rows if r['name'] and r['phone'] and r['city'] in ('Dubai','Sharjah','Ajman','AlAin','AbuDhabi','RAK','Fujairah')}
    for name,r in sorted(unique.items()):
        city=city_names.get(r['city'],r['city'])
        rows.append({'business_name':name,'brand':'Al Maya Group','address':name+', '+city+', United Arab Emirates','city':city,'phone':normalize_phone(r['phone']),'phone_scope':'branch','contact_email':'info@almaya.ae','email_scope':'corporate','source_url':ALMAYA,'contact_source_url':ALMAYA_CONTACT,'map_link':r['map_link']})
    for r in sorted(c.rows,key=lambda row:row['name']):
        if len(rows)>=50:break
        if not r['name'].startswith('Choithrams') or not r['name'].endswith('Dubai'):continue
        # The source publishes no branch phone; explicitly use its store-support line.
        rows.append({'business_name':r['name'],'brand':'Choithrams','address':r['name']+', United Arab Emirates','city':'Dubai','phone':'+97142947250','phone_scope':'central store-support helpline','contact_email':'support@choithrams.com','email_scope':'central customer support','source_url':CHOITHRAMS,'contact_source_url':CHOITHRAMS_CONTACT,'map_link':r['map_link']})
    if len(rows)!=50:raise ValueError(f'Expected 50 usable public references, got {len(rows)}')
    for row in rows:
        row.update(id=str(uuid.uuid5(uuid.NAMESPACE_URL,row['source_url']+'#'+row['business_name'])),country='United Arab Emirates',address_precision='official branch/locality label; not verified full postal address',checked_at=now,source_hash=hashlib.sha256(pages[row['source_url']].encode()).hexdigest(),origin='public_official_listing')
        if row['map_link'] and urlsplit(row['map_link']).scheme!='https':raise ValueError('Invalid map URL')
    output=ROOT/'data/public-businesses.json';output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({'purpose':'Public business references only; not participating retailers or sources of synthetic stock','retrieved_at':now,'records':rows},indent=2,ensure_ascii=False)+'\n')
    return rows

def apply(rows):
    payload=json.dumps(rows).replace("'","''")
    sql="""begin;
select pg_advisory_xact_lock(hashtext('jiran-public-business-references'));
insert into public.business_references select * from jsonb_populate_recordset(null::public.business_references,'PAYLOAD'::jsonb)
on conflict(id) do update set checked_at=excluded.checked_at,source_hash=excluded.source_hash;
create temp table pairs as
select m.retailer_id,b.* from
 (select a.retailer_id,row_number() over(order by a.store_id) as n from jiran_archive_lab.store_accounts a join public.retailer_profiles r on r.id=a.retailer_id where r.data_origin='synthetic_generated')m
join (select x.*,row_number() over(order by x.business_name) as n from public.business_references x)b using(n);
update public.retailer_profiles r set reference_business_id=p.id,contact_email=case when r.contact_email like '%@example.invalid' or r.contact_email is null then p.contact_email else r.contact_email end
from pairs p where r.id=p.retailer_id and r.reference_business_id is null;
update public.profiles a set phone=p.phone from pairs p where a.id=p.retailer_id and (a.phone like '+000%' or a.phone is null);
update public.retailer_locations l set location_label='[PUBLIC REFERENCE] '||p.address,city=p.city,state=null,country=p.country,map_link=p.map_link
from pairs p where l.retailer_id=p.retailer_id and l.location_label like '[FICTIONAL DEMO]%';
commit;
select count(*) as linked_reference_stores from public.retailer_profiles where reference_business_id is not null;
""".replace('PAYLOAD',payload)
    result=subprocess.run(['docker','exec','-i','supabase_db_ISDIA','psql','-X','-U','postgres','-d','postgres','-v','ON_ERROR_STOP=1'],input=sql,text=True,capture_output=True)
    if result.returncode:raise RuntimeError(result.stderr)
    print(result.stdout)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    rows=collect();print('Extracted',len(rows),'public branch references; source facts saved to data/public-businesses.json')
    if args.apply:apply(rows)
