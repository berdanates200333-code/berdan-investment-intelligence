"""Prospective 60-calendar-day run. Reuses frozen v1.0 signals and sizing.

Separate state and transaction journal; no legacy history is edited. Each
successful transaction is immutable and CURRENT is replaced atomically.
Known cash dividends accrue as non-spendable receivables until a verified
payment date is available. Unsupported/ambiguous corporate actions fail closed.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
import importlib.metadata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
from .. import journal
from . import engine, rules_v1_0 as signals
from .verified_data import DataError, calendar, latest_complete, next_open

VERSION='signal1.0-execution60-v1'
RULE_HASH='43b29a9918f72dc35e2de0beb7f5a4fa33a01cc1d458639880b6ade0ce0eeb0d'


def frozen_manifest(root):
    paths=['bii/papertrading/rules_v1_0.py','bii/papertrading/engine.py','bii/papertrading/verified_data.py','bii/papertrading/forward60.py','scripts/pt60_run.py','requirements-pt60.lock','papertrading/forward60/config.json','bii/journal.py','bii/papertrading/report.py']
    load_config(root)
    for line in (root/'requirements-pt60.lock').read_text().splitlines():
        if not line.strip() or line.startswith('#'): continue
        package,version=line.strip().split('==')
        if importlib.metadata.version(package)!=version:
            raise DataError(f'Unpinned runtime dependency: {package}')
    hashes={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}
    if hashes[paths[0]]!=RULE_HASH: raise DataError('Frozen signal rules changed')
    return hashes


def load_config(root):
    cfg=json.loads((root/'papertrading/forward60/config.json').read_text())
    required={'experiment':VERSION,'duration_calendar_days':60,'capital_eur':10000,
              'benchmark_capital_eur':10000,'automatic_extension':False,
              'automatic_real_money':False,'broker_access':False,
              'resume_drawdown_pause_automatically':False}
    if any(type(cfg.get(k)) is not type(v) or cfg.get(k)!=v for k,v in required.items()):
        raise DataError('Invalid frozen 60-day configuration')
    return cfg


def new_state(now, manifest):
    state=engine.new_state(signals)
    start=now.astimezone(ZoneInfo('Europe/Berlin'))
    state.update(version=VERSION,start=start.isoformat(),end_exclusive=(start+timedelta(days=60)).isoformat(),manifest=manifest,
                 last_date=None,bench_pending=None,bench_last_date=None,receivables=[],corporate_processed=[],snapshots=[],finished=False)
    return state


def event(jpath, now, kind, **kw):
    return journal.append({'typ':kind,'experiment':VERSION,**kw},path=jpath,now=now)


def event_date(raw, symbol):
    return pd.Timestamp(raw['date'],unit='s',tz='UTC').tz_convert('Europe/Berlin' if symbol==signals.BENCH['symbol'] else 'America/New_York').date().isoformat()


def apply_actions(state, provider, d, jpath, now):
    """Apply only to shares held before the ex-date. Missing payment -> receivable."""
    day=str(pd.Timestamp(d).date())
    for ticker,pos in list(state['positions'].items()):
        events=provider.actions.get(ticker,{})
        if set(events)-{'splits','dividends'}: raise DataError(f'{ticker}: unsupported corporate action')
        for kind in ('splits','dividends'):
            for key,raw in sorted(events.get(kind,{}).items()):
                ex=event_date(raw,ticker); eid=f'{ticker}:{kind}:{key}'
                if ex>day or ex<=pos['einstieg_datum'] or eid in state['corporate_processed']: continue
                if ex!=day: raise DataError(f'{ticker}: late corporate action requires reconciliation, no retrospective rewrite')
                # A split is externally checked against the independently obtained
                # price discontinuity before any position/stop transformation.
                if not raw.get('verified_source') or not raw.get('verified_at'):
                    raise DataError(f'{ticker}: corporate action lacks independent terms confirmation')
                if pd.Timestamp(raw['verified_at'])>pd.Timestamp(now):
                    raise DataError('Future corporate action confirmation')
                if kind=='splits':
                    ratio=float(raw['numerator'])/float(raw['denominator'])
                    if not math.isfinite(ratio) or ratio<=0: raise DataError('Invalid split ratio')
                    prev=calendar(ticker).previous_session(d)
                    second=provider.secondary[ticker]
                    if prev not in second or d not in second: raise DataError('Split has no independent before/after prices')
                    movement=second[prev]['close']/second[d]['open']
                    if abs(movement/ratio-1)>.25: raise DataError('Split not consistent with independent prices')
                    count=pos['stueck']*ratio
                    if abs(count-round(count))>1e-8: raise DataError('Fractional split cash-in-lieu unresolved')
                    pos['stueck']=round(count)
                    for k in ('einstieg','stop','stop_start','ziel','risiko_je_stueck','letzter_kurs'): pos[k]/=ratio
                    event(jpath,now,'split',ticker=ticker,datum=day,ratio=ratio,stueck=pos['stueck'],source=raw)
                else:
                    amount=float(raw['amount'])
                    if not math.isfinite(amount) or amount<=0: raise DataError('Invalid dividend')
                    rec={'id':eid,'ticker':ticker,'ex_date':ex,'usd':pos['stueck']*amount,'paid':False,'payment_date':raw.get('payment_date'),'payment_source':raw.get('payment_source')}
                    state['receivables'].append(rec)
                    event(jpath,now,'dividend_receivable',**rec,source=raw,assumption='gross before tax; excluded from spendable cash until verified payment')
                state['corporate_processed'].append(eid)
    for rec in state['receivables']:
        if not rec['paid'] and rec.get('payment_date') and rec['payment_date']<=day:
            # Payment date is only accepted when supplied with an independently
            # verified reference; Yahoo by itself does not expose it.
            if not rec.get('payment_source'): continue
            fx=provider.fx_at(d,before=True); credited=rec['usd']/fx*(1-signals.PARAMS['fx_fee'])
            state['cash_eur']+=credited; rec['paid']=True
            event(jpath,now,'dividend_payment',id=rec['id'],eur=credited,fx=fx,source=rec['payment_source'])


def plan_benchmark(state,now,jpath):
    d,opening=next_open(signals.BENCH['symbol'],now)
    if opening>=pd.Timestamp(state['end_exclusive']): return
    plan={'id':'BENCH-'+now.isoformat(),'execute_on':str(d.date()),'created_at':now.isoformat(),'open_at':opening.isoformat(),'budget_eur':10000.}
    event(jpath,now,'benchmark_order_plan',**plan,orderart='market at next Xetra open; deterministic rejection; retry only via a new prospective plan')
    state['bench_pending']=plan


def process_benchmark(state,provider,now,jpath):
    symbol=signals.BENCH['symbol']; df=provider.data[symbol]; p=state['bench_pending']; P=signals.PARAMS
    if p:
        d=pd.Timestamp(p['execute_on'])
        if d<=df.index[-1]:
            if d not in df.index: raise DataError('Benchmark execution bar absent')
            if pd.Timestamp(p['created_at'])>=calendar(symbol).session_open(d): raise DataError('Late benchmark plan')
            provider.crosscheck(symbol,d,float(df.loc[d,'close']),P['crosscheck_tol'])
            if engine._rejected(p['id'],P['reject_rate']):
                event(jpath,now,'benchmark_order_rejected',plan_id=p['id'],datum=str(d.date()))
            else:
                engine._bench_buy(state,df,signals,d)
                state['bench']['plan_id']=p['id']
                event(jpath,now,'benchmark_execution',plan_id=p['id'],datum=str(d.date()),**{k:v for k,v in state['bench'].items() if k not in ('plan_id','datum')},evidence=provider.meta[symbol])
            state['bench_pending']=None
    # The benchmark is accumulating; any external distribution or split during
    # the holding period is quarantined until reconciled, never silently ignored.
    b=state['bench']
    if b:
        for kind,actions in provider.actions.get(symbol,{}).items():
            if any(event_date(v,symbol)>b['datum'] for v in actions.values()): raise DataError('Benchmark corporate action requires reconciliation')
        state['bench_last_date']=str(df.index[-1].date())
        b['last_close']=float(df.close.iloc[-1]); b['value_eur']=b['stueck']*b['last_close']+b['cash_eur']
    elif state['bench_pending'] is None: plan_benchmark(state,now,jpath)


def step(state, provider, now, jpath, manifest):
    if state['manifest']!=manifest: raise DataError('Frozen execution/data environment changed; create separate experiment')
    if not journal.verify(jpath)[0]: raise DataError('Invalid journal')
    if state['finished']: return {'status':'finished','changed':False}
    if pd.Timestamp(now)>=pd.Timestamp(state['end_exclusive']):
        state['finished']=True
        state['pending']=[]; state['bench_pending']=None
        event(jpath,now,'experiment_finished',end_exclusive=state['end_exclusive'],last_valuation_date=state['last_date'],open_positions=state['positions'],policy='No post-window orders or extension; open holdings reported separately at last confirmed valuation')
        return {'status':'finished','changed':True}
    d=latest_complete('SPY',now); day=str(d.date()); P=signals.PARAMS
    if state['last_date']==day: return {'status':'duplicate_session','changed':False}
    if state['last_date'] and d!=calendar('SPY').next_session(pd.Timestamp(state['last_date'])):
        raise DataError('Missed US session: reconcile archived inputs before continuing; never backfill plans')
    # Validate every actual execution bar and FX before any mutation.
    for ticker in (*signals.UNIVERSE,signals.REGIME):
        provider.crosscheck(ticker,d,float(provider.data[ticker].loc[d,'close']),P['crosscheck_tol'])
    fx=provider.fx_at(d,before=True); valuation_fx=provider.fx_at(d,before=True)
    bars={t:provider.data[t].loc[d] for t in signals.UNIVERSE}
    apply_actions(state,provider,d,jpath,now)
    process_benchmark(state,provider,now,jpath)
    for o in list(state['pending']):
        od=pd.Timestamp(o['execute_on'])
        if od>d: continue
        state['pending'].remove(o)
        reason=None
        if od!=d: reason='Expired: not executed on intended session'
        elif state['paused']: reason='Drawdown pause'
        elif pd.Timestamp(o['journal_utc'])>=calendar(o['ticker']).session_open(d): reason='Late plan'
        elif any(event_date(a,o['ticker'])==day for kind in provider.actions.get(o['ticker'],{}).values() for a in kind.values()): reason='Corporate action on execution date: replan prospectively'
        # Recheck full cost-aware sizing at today's FX and pre-open portfolio estimate.
        equity_open=engine.equity_eur(state,{t:float(b['open']) for t,b in bars.items()},fx)
        if equity_open/state['peak']-1<=-P['drawdown_pause']:
            state['paused']=True; state['pause_seit']=state['pause_seit'] or day; reason='Drawdown pause at open'
        size=engine.size_position(equity_open,o['limit'],o['limit'],o['stop'],fx,state['cash_eur'],signals)
        if o['stueck']>size['stueck']: reason='Risk/cash/weight budget changed; no unplanned resizing'
        if reason:
            state['failed'].append({'plan_id':o['id'],'datum':day,'ticker':o['ticker'],'grund':reason})
            event(jpath,now,'ausfuehrung_fehlgeschlagen',plan_id=o['id'],datum=day,ticker=o['ticker'],grund=reason)
        else: engine._execute_entry(state,o,bars[o['ticker']],fx,signals,d,jpath,False,now)
    before_exits=copy.deepcopy(state['positions']); nclosed=len(state['closed'])
    process_exits(state,bars,fx,d,jpath,now)
    for tr in state['closed'][nclosed:]:
        p=before_exits[tr['ticker']]
        # Exact FX decomposition relative to initial conversion, net of modeled costs.
        tr['fx_exit']=fx; tr['fx_entry']=p['fx_einstieg']
        tr['fx_effect_eur']=round(tr['stueck']*tr['ausstieg_usd']*(1/fx-1/p['fx_einstieg']),2)
        tr['mae_price_pct_bound']=min(p.get('mae_price_pct_bound',0),float(bars[tr['ticker']]['low'])/p['einstieg']-1)
        tr['mae_note']='Daily-low adverse bound; low may occur after same-day exit, not exact intraday MAE'
        event(jpath,now,'trade_attribution',**tr)
    engine._end_of_day_updates(state,bars,signals,d,jpath,False,now)
    for t,p in state['positions'].items():
        p['mae_price_pct_bound']=min(p.get('mae_price_pct_bound',0),float(bars[t]['low'])/p['einstieg']-1)
    receivables=sum(x['usd'] for x in state['receivables'] if not x['paid'])/valuation_fx
    eq=engine.equity_eur(state,{t:float(b['close']) for t,b in bars.items()},valuation_fx)+receivables
    state['peak']=max(state['peak'],eq)
    if eq/state['peak']-1<=-P['drawdown_pause']:
        state['paused']=True; state['pause_seit']=state['pause_seit'] or day
        event(jpath,now,'risk_pause',datum=day,equity=eq,peak=state['peak'])
    be=state['bench']['value_eur'] if state['bench'] else 10000.
    state['equity'].append({'datum':day,'observed_at':now.isoformat(),'aktiv_eur':round(eq,2),'bench_eur':round(be,2),'cash_eur':round(state['cash_eur'],2),'receivables_eur':round(receivables,2),'positionen':len(state['positions']),'daten_ok':True})
    # No post-window fills, no automatic restart and no automatic pause release.
    nd,no=next_open('SPY',now)
    if no<pd.Timestamp(state['end_exclusive']):
        engine._plan_entries(state,provider.data_for_universe if hasattr(provider,'data_for_universe') else {t:provider.data[t] for t in signals.UNIVERSE},provider.data['SPY'],valuation_fx,signals,d,jpath,provider,[],now,False)
        for order in state['pending']:
            if 'execute_on' not in order:
                order['execute_on']=str(nd.date())
                event(jpath,now,'order_schedule',plan_id=order['id'],execute_on=order['execute_on'],open_at=no.isoformat())
    state['last_date']=day
    event(jpath,now,'valuation',datum=day,active_eur=eq,benchmark_eur=be,fx=valuation_fx,receivables_eur=receivables,evidence=provider.meta)
    return {'status':'processed','changed':True,'session':day}


def process_exits(state,bars,fx,d,jpath,now):
    """Known open precedes unknown intraday path; if both touched later, stop first."""
    P=signals.PARAMS
    for t in list(state['positions']):
        p=state['positions'][t]; b=bars[t]; slip=1-P['half_spread']-P['slippage']
        if p['exit_zeitstopp']:
            fill=b['open']*slip; reason='Time stop at open'
        elif b['open']<=p['stop']:
            fill=b['open']*slip; reason='Stop gap at open'
        elif b['open']>=p['ziel']:
            fill=max(p['ziel'],b['open']*slip); reason='Target gap at open (limit respected)'
        elif b['low']<=p['stop']:
            fill=p['stop']*slip; reason='Stop touched; conservative stop-first if both touched'
        elif b['high']>=p['ziel']:
            fill=p['ziel']; reason='Target limit touched'
        else: continue
        engine._close_position(state,t,float(fill),d,fx,reason,signals,jpath,False,now)
