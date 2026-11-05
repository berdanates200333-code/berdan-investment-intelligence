"""Archived end-of-day inputs for the separate 60-calendar-day experiment.

Yahoo OHLC are split-adjusted (not dividend-adjusted); use current-session raw
prices for execution, and retain each as-observed snapshot. Nasdaq and S&P
Global/StockAnalysis provide separately retrieved validation bars. No silent
fallback to unconfirmed data. This is delayed data, not an execution feed.
"""
from __future__ import annotations
import hashlib
import io
import json
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import exchange_calendars as xc
import numpy as np
import pandas as pd
import requests
from . import rules_v1_0 as rules

class DataError(ValueError): pass


def calendar(symbol):
    return xc.get_calendar('XETR' if symbol == rules.BENCH['symbol'] else 'XNYS')


def latest_complete(symbol, now):
    cal = calendar(symbol)
    now = pd.Timestamp(now)
    sessions = cal.sessions_in_range((now-pd.Timedelta(days=14)).date(), now.date())
    eligible = [d for d in sessions if cal.session_close(d)+pd.Timedelta(minutes=45) <= now]
    if not eligible: raise DataError('No completed session')
    return eligible[-1]


def next_open(symbol, now):
    cal=calendar(symbol); now=pd.Timestamp(now)
    for d in cal.sessions_in_range(now.date(), (now+pd.Timedelta(days=14)).date()):
        if cal.session_open(d) > now: return d, cal.session_open(d)
    raise DataError('No future exchange session')


def validate_frame(df, expected, symbol):
    if df.empty or df.index.has_duplicates or not df.index.is_monotonic_increasing:
        raise DataError(f'{symbol}: empty/duplicate/unsorted bars')
    if expected not in df.index: raise DataError(f'{symbol}: missing completed session {expected.date()}')
    d=df.loc[:expected].tail(10) if symbol == rules.BENCH['symbol'] else df.loc[:expected]
    if symbol != rules.BENCH['symbol'] and len(d)<rules.PARAMS['min_bars']: raise DataError(f'{symbol}: insufficient history')
    vals=d[['open','high','low','close','volume']].to_numpy()
    if not np.isfinite(vals).all() or (vals[:,:4]<=0).any() or (vals[:,4]<=0).any():
        raise DataError(f'{symbol}: nonfinite/nonpositive bar')
    if ((d.high < d[['open','low','close']].max(axis=1)-1e-6) | (d.low > d[['open','high','close']].min(axis=1)+1e-6)).any():
        raise DataError(f'{symbol}: inconsistent OHLC')
    required=calendar(symbol).sessions_in_range(d.index[max(0,len(d)-210)],expected)
    if len(required.difference(d.index)): raise DataError(f'{symbol}: missing exchange sessions')
    return d


def compare_bar(primary, secondary, tolerance=0.02):
    # Check the full execution bar, not only the close. Volume is vendor-specific.
    if any(not np.isfinite(float(secondary[k])) or float(secondary[k])<=0 for k in ('open','high','low','close')):
        raise DataError('Invalid secondary OHLC')
    deviations={k:abs(float(primary[k])/float(secondary[k])-1) for k in ('open','high','low','close')}
    if max(deviations.values())>tolerance: raise DataError(f'Independent OHLC discrepancy: {deviations}')
    return deviations


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=[]; self.cell=None; self.in_table=False
    def handle_starttag(self,tag,attrs):
        if tag=='table': self.in_table=True
        if not self.in_table: return
        if tag=='tr': self.row=[]
        if tag in ('td','th'): self.cell=''
    def handle_data(self,d):
        if self.cell is not None: self.cell+=d
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None: self.row.append(self.cell.strip()); self.cell=None
        if tag=='tr' and self.row: self.rows.append(self.row)
        if tag=='table': self.in_table=False


def parse_eunl(text):
    if 'ETR:EUNL' not in text or 'S&amp;P Global Market Intelligence' not in text:
        raise DataError('Unverified EUNL identity or secondary vendor')
    p=TableParser(); p.feed(text); rows={}
    for row in p.rows:
        if len(row)!=8 or row[0]=='Date': continue
        try:
            day=pd.Timestamp(datetime.strptime(row[0],'%b %d, %Y').date())
            rows[day]={k:float(row[i].replace(',','')) for i,k in enumerate(('open','high','low','close'),1)}
        except (ValueError,IndexError): continue
    if not rows: raise DataError('No secondary EUNL bars')
    return rows


class VerifiedProvider:
    def __init__(self, folder: Path, now=None):
        self.folder=Path(folder); self.folder.mkdir(parents=True,exist_ok=False)
        self.now=now or datetime.now(timezone.utc)
        self.data={}; self.secondary={}; self.meta={}; self.actions={}; self.log=[]; self.requests=[]
        self.fx_data=None; self.news_cache={}

    def get(self,url):
        started=datetime.now(timezone.utc).isoformat()
        r=requests.get(url,headers={'User-Agent':'Mozilla/5.0 (Berdan personal paper research)'},timeout=25)
        body=r.content; sha=hashlib.sha256(body).hexdigest(); path=self.folder/(sha+'.raw')
        try:
            with path.open('xb') as f: f.write(body)
        except FileExistsError: pass
        self.requests.append({'url':url,'requested_at':started,'received_at':datetime.now(timezone.utc).isoformat(),'status':r.status_code,'sha256':sha,'file':path.name})
        r.raise_for_status(); return r,sha

    def load_symbol(self,symbol):
        try:
            r,sha=self.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=2y&interval=1d&events=div%2Csplits')
            j=r.json()['chart']['result'][0]; m=j['meta']
            currency='EUR' if symbol==rules.BENCH['symbol'] else 'USD'
            if m['symbol']!=symbol or m.get('currency')!=currency or not m.get('exchangeName'):
                raise DataError(f'{symbol}: identity/currency/venue mismatch')
            idx=pd.to_datetime(j['timestamp'],unit='s',utc=True).tz_convert(m['exchangeTimezoneName']).normalize().tz_localize(None)
            q=j['indicators']['quote'][0]
            df=pd.DataFrame({k:q[k] for k in ('open','high','low','close','volume')},index=idx,dtype=float)
            d=latest_complete(symbol,self.now)
            # Exclude provisional rows before validation; never drop bad completed rows.
            df=validate_frame(df.loc[:d],d,symbol)
            self.data[symbol]=df
            self.meta[symbol]={'symbol':symbol,'currency':currency,'exchange':m['exchangeName'],'timezone':m['exchangeTimezoneName'],'raw_sha256':sha,'last_complete':str(d.date()),'observed_at':datetime.now(timezone.utc).isoformat(),'bar_timestamp_utc':pd.Timestamp(j['timestamp'][list(idx).index(d)],unit='s',tz='UTC').isoformat(),'session_close_utc':calendar(symbol).session_close(d).isoformat(),'price_basis':'split-adjusted, dividends excluded'}
            self.actions[symbol]=j.get('events',{})
            if symbol==rules.BENCH['symbol']:
                r,secondary_sha=self.get('https://stockanalysis.com/quote/etr/EUNL/history/')
                second=parse_eunl(r.text); vendor='S&P Global via StockAnalysis, Xetra'
            else:
                kind='etf' if symbol=='SPY' else 'stocks'
                start=(d-pd.Timedelta(days=14)).strftime('%Y-%m-%d')
                r,secondary_sha=self.get(f'https://api.nasdaq.com/api/quote/{symbol}/historical?assetclass={kind}&fromdate={start}&todate={d:%Y-%m-%d}&limit=100')
                js=r.json(); rows=js['data']['tradesTable']['rows']
                if js['data']['symbol']!=symbol: raise DataError('Nasdaq symbol mismatch')
                second={pd.Timestamp(datetime.strptime(x['date'],'%m/%d/%Y').date()):{k:float(x[k].replace('$','').replace(',','')) for k in ('open','high','low','close')} for x in rows}
                vendor='Nasdaq historical'
            self.secondary[symbol]=second
            if d not in second: raise DataError(f'{symbol}: secondary missing {d.date()}')
            cc=compare_bar(df.loc[d],second[d],rules.PARAMS['crosscheck_tol'])
            self.meta[symbol].update(secondary_vendor=vendor,secondary_sha256=secondary_sha,comparison=cc)
        except Exception as e:
            self.log.append(f'{symbol}: {type(e).__name__}: {str(e)[:200]}')

    def load(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(self.load_symbol,[*rules.UNIVERSE,rules.REGIME,rules.BENCH['symbol']]))
        try:
            r,sha=self.get('https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?format=csvdata&startPeriod=2026-09-01')
            df=pd.read_csv(io.StringIO(r.text)); fx=pd.Series(df.OBS_VALUE.to_numpy(),index=pd.to_datetime(df.TIME_PERIOD),dtype=float)
            if fx.index.has_duplicates or not fx.index.is_monotonic_increasing or not np.isfinite(fx).all() or (fx<=0).any(): raise DataError('Invalid ECB series')
            self.fx_data=fx
            self.meta['FX']={'source':'ECB EUR/USD reference; USD per EUR','raw_sha256':sha,'execution_policy':'strictly prior date, maximum 7 calendar days; reference rate plus model FX fee, not tradable quote'}
            self.fx_at(latest_complete('SPY',self.now),before=True)
        except Exception as e: self.log.append(f'FX: {type(e).__name__}: {str(e)[:200]}')
        self.save_manifest()
        if self.log: raise DataError('; '.join(self.log))
        return self

    def save_manifest(self):
        (self.folder/'manifest.json').write_text(json.dumps({'observed_at':self.now.isoformat(),'requests':self.requests,'metadata':self.meta,'errors':self.log,'actions':self.actions},indent=2))

    def fx_at(self,d,before=True):
        if self.fx_data is None: raise DataError('No ECB data')
        d=pd.Timestamp(d); s=self.fx_data[self.fx_data.index<d] if before else self.fx_data[self.fx_data.index<=d]
        if s.empty or (d-s.index[-1]).days>7: raise DataError('Missing/stale point-in-time ECB rate')
        return float(s.iloc[-1])

    def ohlcv(self,symbol): return self.data[symbol]
    def crosscheck(self,symbol,d,close,tol):
        d=pd.Timestamp(d)
        if d not in self.secondary[symbol]: raise DataError(f'{symbol}: missing secondary execution date')
        dev=compare_bar(self.data[symbol].loc[d],self.secondary[symbol][d],tol)
        return {'status':'bestaetigt','quelle':self.meta[symbol]['secondary_vendor'],'abweichung':max(dev.values()),'ohlc_deviations':dev,'raw_sha256':self.meta[symbol]['raw_sha256'],'secondary_sha256':self.meta[symbol]['secondary_sha256']}

    def prepare_news(self):
        # Fetch before decision timestamp; later engine reads this fixed snapshot.
        def fetch(symbol):
            return symbol, self.fetch_news(symbol,rules.PARAMS['news_days'],rules.NEG_NEWS)
        # Bounded concurrency; decisions still wait for the entire snapshot.
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(fetch,rules.UNIVERSE))
        self.news_cache=dict(results)

    def news(self,symbol,days,neg):
        if symbol not in self.news_cache: raise DataError('News not archived before decision')
        return self.news_cache[symbol]

    def fetch_news(self,symbol,days,neg):
        import re, xml.etree.ElementTree as ET
        r,sha=self.get(f'https://news.google.com/rss/search?q={symbol}+stock+when:{days}d&hl=en-US&gl=US&ceid=US:en')
        root=ET.fromstring(r.content)
        if root.tag!='rss': raise DataError('Invalid news feed')
        items=root.findall('.//item')
        if not items: raise DataError(f'{symbol}: empty news feed, coverage unproven')
        for item in items:
            published=parsedate_to_datetime(item.findtext('pubDate',''))
            if published.tzinfo is None or published>datetime.now(timezone.utc):
                raise DataError('News has unverified/future publication time')
        titles=[x.findtext('title','') for x in items]
        hits=[t for t in titles if any(re.search(r'\b'+re.escape(w),t,re.I) for w in neg)]
        return {'status':'geprueft','anzahl':len(items),'treffer':hits,'quellen':[x.findtext('link') for x in items[:5]],'raw_sha256':sha}
