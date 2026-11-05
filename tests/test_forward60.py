"""Synthetic safety tests. These are not evidence of a live forward start."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import copy
import json
import pandas as pd
import pytest
from bii import journal
from bii.papertrading import forward60 as f, rules_v1_0 as rules
from bii.papertrading.verified_data import DataError, calendar, latest_complete, next_open, validate_frame, compare_bar, VerifiedProvider
from scripts import pt60_run

ROOT=Path(__file__).resolve().parents[1]
def at(s): return datetime.fromisoformat(s)

class Provider:
    def __init__(self,now):
        self.data={}; self.meta={}; self.actions={}; self.secondary={}
        for t in (*rules.UNIVERSE,'SPY',rules.BENCH['symbol']):
            d=latest_complete(t,now)
            idx=calendar(t).sessions_in_range('2025-10-01',d)
            df=pd.DataFrame({'open':100.,'high':101.,'low':99.,'close':100.,'volume':2e6},index=idx)
            self.data[t]=df;self.meta[t]={'source':'synthetic'};self.actions[t]={}
            self.secondary[t]={x:dict(df.loc[x]) for x in idx}
    def crosscheck(self,t,d,*args):
        compare_bar(self.data[t].loc[d],self.secondary[t][d]);return {'status':'bestaetigt'}
    def fx_at(self,*a,**kw): return 1.1
    def news(self,*a): return {'status':'geprueft','anzahl':1,'treffer':[]}

def state(now): return f.new_state(now,{'fixture':'synthetic'})

def test_config_enforces_60_and_no_money(tmp_path):
    p=tmp_path/'papertrading/forward60';p.mkdir(parents=True)
    cfg=f.load_config(ROOT);cfg['duration_calendar_days']=30
    (p/'config.json').write_text(json.dumps(cfg))
    with pytest.raises(DataError):f.load_config(tmp_path)

def test_start_is_not_backdated_and_calendar_duration():
    now=at('2026-10-10T22:00:00+00:00');s=state(now)
    assert pd.Timestamp(s['start'])==pd.Timestamp(now)
    start=datetime.fromisoformat(s['start']);end=datetime.fromisoformat(s['end_exclusive'])
    assert (end.date()-start.date()).days==60
    assert end.hour==start.hour

def test_holiday_and_early_close():
    assert latest_complete('SPY',at('2026-11-26T23:00:00+00:00'))==pd.Timestamp('2026-11-25')
    assert latest_complete('SPY',at('2026-11-27T18:44:00+00:00'))==pd.Timestamp('2026-11-25')
    assert latest_complete('SPY',at('2026-11-27T18:45:00+00:00'))==pd.Timestamp('2026-11-27')

def test_independent_exchange_calendars():
    now=at('2026-11-26T09:00:00+00:00')
    assert next_open('SPY',now)[0]==pd.Timestamp('2026-11-27')
    assert calendar(rules.BENCH['symbol']).is_session('2026-11-26')

@pytest.mark.parametrize('field',['open','high','low','close'])
def test_all_execution_prices_crosschecked(field):
    p=dict(open=100,high=102,low=98,close=101);q=p.copy();q[field]*=1.1
    with pytest.raises(DataError):compare_bar(p,q)

def test_missing_and_invalid_completed_bars():
    now=at('2026-11-02T23:00:00+00:00');p=Provider(now);d=latest_complete('SPY',now)
    df=p.data['AAPL'].copy();df.loc[d,'high']=1
    with pytest.raises(DataError):validate_frame(df,d,'AAPL')
    with pytest.raises(DataError):validate_frame(p.data['AAPL'].drop(p.data['AAPL'].index[-2]),d,'AAPL')

def test_benchmark_prospective_then_idempotent(tmp_path,monkeypatch):
    monkeypatch.setattr(f.engine,'_rejected',lambda *a:False)
    now=at('2026-11-02T23:00:00+00:00');s=state(now);jp=tmp_path/'j'
    f.step(s,Provider(now),now,jp,s['manifest'])
    assert s['bench'] is None and s['bench_pending']['execute_on']=='2026-11-03'
    nxt=now+timedelta(days=1)
    f.step(s,Provider(nxt),nxt,jp,s['manifest'])
    assert s['bench']['datum']=='2026-11-03' and s['bench']['cash_eur']>=0
    entries=journal.read(jp);types=[e['typ'] for e in entries]
    assert types.index('benchmark_order_plan')<types.index('benchmark_execution')
    before=jp.read_bytes();saved=copy.deepcopy(s)
    assert not f.step(s,Provider(nxt),nxt,jp,s['manifest'])['changed']
    assert saved==s and before==jp.read_bytes()

def test_missing_session_never_backfills(tmp_path):
    now=at('2026-11-02T23:00:00+00:00');s=state(now);s['last_date']='2026-10-29'
    with pytest.raises(DataError,match='Missed'):f.step(s,Provider(now),now,tmp_path/'j',s['manifest'])

def test_end_cancels_without_extension(tmp_path):
    now=at('2026-11-02T23:00:00+00:00');s=state(now);s['pending']=[{'id':'never'}]
    end=at(s['end_exclusive']);result=f.step(s,Provider(now),end,tmp_path/'j',s['manifest'])
    assert result['status']=='finished' and not s['pending'] and not s['bench_pending']
    assert s['end_exclusive']==state(now)['end_exclusive']

def test_manifest_change_blocks(tmp_path):
    now=at('2026-11-02T23:00:00+00:00')
    with pytest.raises(DataError,match='Frozen'):f.step(state(now),Provider(now),now,tmp_path/'j',{'changed':1})

def position():
    return dict(plan_id='x',ticker='AAPL',stueck=10,einstieg=100.,einstieg_datum='2026-10-30',stop=95.,stop_start=95.,ziel=110.,risiko_je_stueck=5.,letzter_kurs=100.,fx_einstieg=1.1,einstieg_eur=912.,kosten_eur=3.,tage=1,exit_zeitstopp=False,grund='synthetic')

@pytest.mark.parametrize('opening,low,high,expected',[(115.,90.,116.,'Target gap'),(90.,85.,110.,'Stop gap'),(100.,90.,115.,'Stop touched')])
def test_gap_order_and_ambiguous_path(opening,low,high,expected,tmp_path):
    now=at('2026-11-02T23:00:00+00:00');s=state(now);s['positions']['AAPL']=position()
    f.process_exits(s,{'AAPL':{'open':opening,'low':low,'high':high}},1.1,pd.Timestamp('2026-11-02'),tmp_path/'j',now)
    assert s['closed'][0]['grund'].startswith(expected)

def test_unverified_corporate_action_blocks(tmp_path):
    now=at('2026-11-02T23:00:00+00:00');s=state(now);s['positions']['AAPL']=position();p=Provider(now)
    p.actions['AAPL']={'dividends':{'x':{'date':int(pd.Timestamp('2026-11-02T14:30Z').timestamp()),'amount':1}}}
    with pytest.raises(DataError,match='independent'):f.apply_actions(s,p,pd.Timestamp('2026-11-02'),tmp_path/'j',now)
    assert not s['receivables']

def test_dividend_receivable_not_spendable_and_once(tmp_path):
    now=at('2026-11-02T23:00:00+00:00');s=state(now);s['positions']['AAPL']=position();p=Provider(now)
    p.actions['AAPL']={'dividends':{'x':{'date':int(pd.Timestamp('2026-11-02T14:30Z').timestamp()),'amount':1,'verified_source':'synthetic issuer notice','verified_at':'2026-10-30T00:00Z'}}}
    for _ in range(2):f.apply_actions(s,p,pd.Timestamp('2026-11-02'),tmp_path/'j',now)
    assert s['cash_eur']==10000 and len(s['receivables'])==1 and s['receivables'][0]['usd']==10

def test_fx_never_uses_same_day_reference(tmp_path):
    p=VerifiedProvider(tmp_path/'data');p.fx_data=pd.Series([1.1,1.9],index=pd.to_datetime(['2026-10-30','2026-11-02']))
    assert p.fx_at('2026-11-02')==1.1
    with pytest.raises(DataError):p.fx_at('2026-11-20')

def test_live_failure_cannot_create_start(tmp_path,monkeypatch):
    def fail(self):raise DataError('synthetic network failure')
    monkeypatch.setattr(VerifiedProvider,'load',fail)
    assert pt60_run.main(['--execute','--output',str(tmp_path)])==2
    assert not (tmp_path/'CURRENT').exists()
    assert json.loads((tmp_path/'ops_status.json').read_text())['start_created'] is False
