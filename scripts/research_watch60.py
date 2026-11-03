"""Isolated 30-company intake. Rule-based triage, never an AI investment verdict.

Does not write legacy queues/theses or any trading state. ChatGPT's research
schedule reads this inbox and validates facts against primary sources.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bii.research import feeds,news,sec
from bii.papertrading.rules_v1_0 import UNIVERSE
from scripts.pt60_run import atomic_write
import requests


def priority(ticker,title,held=()):
    score=(5 if ticker in held else 0)+(3 if ticker in ('NVDA','AMD','MSFT') else 0)
    return score+len(news.keyword_hits(title))+ (3 if any(x in title.lower() for x in ('earnings','results','guidance','offering')) else 0)


def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=ROOT/'research/watch60');args=ap.parse_args(argv)
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    now=datetime.now(timezone.utc);rid=now.strftime('%Y%m%dT%H%M%S%fZ');errors={};collected=[]
    held=[]
    ptr=ROOT/'papertrading/forward60/runtime/CURRENT'
    if ptr.exists():
        name=ptr.read_text().strip()
        if '/' in name or '..' in name: raise ValueError('Invalid state pointer')
        held=list(json.loads((ptr.parent/'runs'/name/'state.json').read_text())['positions'])
    previous=json.loads((out/'seen.json').read_text()) if (out/'seen.json').exists() else []
    seen=set(previous);new=[]
    def scan(t):
        rows=[];issues=[]
        for label,fn in [('google',lambda:feeds.google_news(t+' stock')),('yahoo',lambda:feeds.yahoo_news(t))]:
            try:
                items=fn()
                if not items: raise ValueError('empty feed; coverage not confirmed')
                rows.extend(dict(x,ticker=t,intake_source=label) for x in items)
            except Exception as exc:issues.append(label+': '+str(exc)[:160])
        return t,rows,issues
    with ThreadPoolExecutor(max_workers=4) as pool:
        for t,rows,issues in pool.map(scan,UNIVERSE):
            collected.extend(rows)
            if issues:errors[t]=issues
    # SEC identity map is obtained, never guessed. Missing contact remains a failure.
    if not os.environ.get('SEC_USER_AGENT'):
        errors['SEC']='SEC_USER_AGENT missing; no primary filing coverage'
    else:
        try:
            response=requests.get('https://www.sec.gov/files/company_tickers.json',headers={'User-Agent':os.environ['SEC_USER_AGENT']},timeout=25);response.raise_for_status()
            mapping={v['ticker']:v['cik_str'] for v in response.json().values()}
            for t in UNIVERSE:
                try:
                    filings=sec.recent_filings(sec.submissions(mapping[t]))
                    for filing in filings:
                        if filing['filingDate']<(now-timedelta(days=3)).date().isoformat():continue
                        collected.append({'ticker':t,'titel':filing['form']+' '+filing.get('items',''),'url':sec.filing_url(mapping[t],filing),'veroeffentlicht':filing.get('acceptanceDateTime') or filing['filingDate'],'intake_source':'SEC EDGAR'})
                except Exception as exc:errors['SEC:'+t]=str(exc)[:160]
        except Exception as exc:errors['SEC']=str(exc)[:160]
    for row in collected:
        identity=row['ticker']+'|'+news.normalize_title(row.get('titel',''))+'|'+str(row.get('veroeffentlicht',''))[:10]
        eid=hashlib.sha256(identity.encode()).hexdigest()
        if eid in seen:continue
        seen.add(eid)
        row.update(id=eid,observed_at=now.isoformat(),priority=priority(row['ticker'],row.get('titel',''),held),analysis_status='unreviewed',thesis_path=f"research/theses/{row['ticker']}.json",source_status='primary filing' if row['intake_source']=='SEC EDGAR' else 'secondary discovery; primary verification required')
        new.append(row)
    new.sort(key=lambda x:(-x['priority'],x['ticker'],x['id']))
    run={'observed_at':now.isoformat(),'universe':list(UNIVERSE),'covered':sorted(set(x['ticker'] for x in collected)),'errors':errors,'new_events':new,'ai_analysis':False}
    folder=out/'runs';folder.mkdir(exist_ok=True)
    atomic_write(folder/(rid+'.json'),json.dumps(run,indent=2,ensure_ascii=False))
    atomic_write(out/'seen.json',json.dumps(sorted(seen)))
    atomic_write(out/'ops_status.json',json.dumps({'status':'failed' if errors else 'success','observed_at':now.isoformat(),'new_events':len(new),'coverage_count':len(run['covered']),'errors':errors},indent=2))
    print(json.dumps({'run':rid,'new_events':len(new),'coverage':len(run['covered']),'errors':errors}))
    return 2 if errors else 0

if __name__=='__main__':raise SystemExit(main())
