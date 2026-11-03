"""Adversarial safety checks added during technical takeover."""
import runpy
from pathlib import Path
import pytest
import pandas as pd
from bii.papertrading import engine, report, rules_v1_0 as rules
from bii import journal

fixture = runpy.run_path(str(Path(__file__).with_name('test_papertrading.py')))
make, now_at = fixture['make'], fixture['now_at']

def test_unconfirmed_source_cannot_create_plan(tmp_path):
    state = engine.new_state(rules)
    engine.run(state, make(cc='ungeprueft'), rules, tmp_path/'j', now=now_at('2026-11-04'))
    assert not state['pending']

@pytest.mark.parametrize('fault', ['logged_quality', 'missing_symbol', 'stale'])
def test_bad_data_prevents_all_execution(tmp_path, fault):
    p = make()
    now = now_at('2026-11-04')
    if fault == 'logged_quality': p.log.append('AAPL: invalid OHLC')
    if fault == 'missing_symbol': p.data['AAPL'] = None
    if fault == 'stale':
        p.data = {k:v.loc[:'2026-11-04'] for k,v in p.data.items()}
        now = now_at('2026-11-13')
    state=engine.new_state(rules)
    result=engine.run(state,p,rules,tmp_path/'j',now=now)
    assert result['probleme']
    assert not state['pending'] and not state['positions'] and state['bench'] is None

@pytest.mark.parametrize('lookup', [engine._fx_before, engine._fx_upto])
def test_future_fx_is_not_available(lookup):
    with pytest.raises(ValueError):
        lookup(pd.Series([1.2],index=pd.to_datetime(['2026-11-10'])),pd.Timestamp('2026-11-04'))

def test_limit_is_hard_price_ceiling(tmp_path):
    o={'id':'limit-test','ticker':'AAPL','limit':100.,'stop':90.,'ziel':125.,'stueck':5,'grund_kurz':'test'}
    while engine._rejected(o['id'],rules.PARAMS['reject_rate']): o['id']+='x'
    state=engine.new_state(rules)
    engine._execute_entry(state,o,{'open':100.,'close':100.},1.1,rules,pd.Timestamp('2026-11-05'),tmp_path/'j',False,now_at('2026-11-05'))
    assert state['positions']['AAPL']['einstieg'] <= 100.

def test_drawdown_includes_initial_capital():
    state=engine.new_state(rules)
    state['equity']=[{'aktiv_eur':9900.,'bench_eur':9950.,'cash_eur':9900.,'daten_ok':True}]
    m=report.metrics(state)
    assert m['maxdd_aktiv']==pytest.approx(-.01)
    assert m['maxdd_bench']==pytest.approx(-.005)

def test_corrupt_journal_blocks_mutation(tmp_path):
    jp=tmp_path/'j'; journal.append({'typ':'test'},jp)
    jp.write_text(jp.read_text().replace('"typ": "test"','"typ": "changed"'))
    original=jp.read_bytes(); state=engine.new_state(rules)
    result=engine.run(state,make(),rules,jp,now=now_at('2026-11-04'))
    assert result['probleme'] and jp.read_bytes()==original and state['bench'] is None
