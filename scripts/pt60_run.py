"""Validated forward run. Default is preflight; --execute is paper-only.

Each transaction contains the entire state and hash-chained journal. CURRENT
moves only after both are fsynced. An advisory lock and Actions concurrency
prevent concurrent writers; snapshot/run folders are never overwritten.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pandas as pd
from bii import journal
from bii.papertrading import forward60 as f60, report
from bii.papertrading.verified_data import VerifiedProvider, DataError, calendar


def atomic_write(path, text):
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with tmp.open('w') as h:
        h.write(text); h.flush(); os.fsync(h.fileno())
    os.replace(tmp,path)
    fd=os.open(path.parent,os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument('--execute',action='store_true'); ap.add_argument('--output',type=Path,default=ROOT/'papertrading'/'forward60'/'runtime')
    args=ap.parse_args(argv); base=args.output; base.mkdir(parents=True,exist_ok=True)
    now=datetime.now(timezone.utc); rid=now.strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:12]
    with (base/'writer.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: print('Writer busy');return 4
        snapshot=base/'snapshots'/rid; snapshot.parent.mkdir(exist_ok=True)
        provider=VerifiedProvider(snapshot,now); state=None; stage=None
        try:
            provider.load()
            provider.prepare_news()
            # Data retrieval must finish before the recorded decision time.
            now=datetime.now(timezone.utc)
            # Never launch a decision against yesterday's data during today's market or settlement buffer.
            cal=calendar('SPY'); today=pd.Timestamp(now.date())
            if args.execute and cal.is_session(today) and cal.session_open(today)<=pd.Timestamp(now)<cal.session_close(today)+pd.Timedelta(minutes=45):
                raise DataError('Current session not yet fully settled; no forward start')
            manifest=f60.frozen_manifest(ROOT)
            if not args.execute:
                result={'status':'preflight_passed','start_created':False,'symbols':len(provider.data),'snapshot':str(snapshot.relative_to(base))}
            else:
                current=base/'CURRENT'; old=None
                if current.exists():
                    name=current.read_text().strip()
                    if '/' in name or '..' in name: raise DataError('Invalid transaction pointer')
                    old=base/'runs'/name
                    if not journal.verify(old/'journal.jsonl')[0]: raise DataError('Broken stored journal')
                    state=json.loads((old/'state.json').read_text())
                    # A previous local write is not evidence of durable prior publication.
                    for path in (current,old/'journal.jsonl',old/'state.json'):
                        try:
                            rel=path.resolve().relative_to(ROOT)
                            committed=subprocess.check_output(['git','show',f'HEAD:{rel}'],cwd=ROOT,stderr=subprocess.DEVNULL)
                        except (ValueError,subprocess.CalledProcessError) as exc:
                            raise DataError('Previous transaction must be committed before executions') from exc
                        if committed!=path.read_bytes(): raise DataError('Uncommitted prior transaction')
                else: state=f60.new_state(now,manifest)
                stage=base/'runs'/('.pending-'+rid);stage.mkdir(parents=True)
                jp=stage/'journal.jsonl'
                if old: shutil.copyfile(old/'journal.jsonl',jp)
                else: f60.event(jp,now,'experiment_start',start=state['start'],end_exclusive=state['end_exclusive'],manifest=manifest,snapshot=str(snapshot.relative_to(base)),capital_eur=10000,benchmark_capital_eur=10000)
                result=f60.step(state,provider,now,jp,manifest)
                if result['changed']:
                    state['snapshots'].append(str(snapshot.relative_to(base)))
                    atomic_write(stage/'state.json',json.dumps(state,indent=2,ensure_ascii=False))
                    if not journal.verify(jp)[0]: raise DataError('Invalid generated journal')
                    with jp.open('rb') as h: os.fsync(h.fileno())
                    dest=base/'runs'/rid;os.rename(stage,dest);stage=None
                    # CURRENT is advanced only after all evidence/report writes.
                    m=report.metrics(state)
                    atomic_write(base/'latest.md',f"# Paper-Trading 60 Tage\n\nStatus: {result['status']}\nStart: {state['start']}\nEnde exklusiv: {state['end_exclusive']}\nLetzte Bewertung: {state['last_date']}\n\n"+json.dumps(m,indent=2,ensure_ascii=False)+'\n\nDividendenforderungen sind nicht verfügbares Bargeld. Offene Positionen sind bewertet, nicht fiktiv liquidiert. Kein Echtgeld.\n')
                else:
                    shutil.rmtree(stage);stage=None
                result['start_created']=old is None and result['changed']
                if result['changed']:
                    write_review(base,state,rid,now)
            provider.save_manifest()
            if args.execute and result['changed']:
                atomic_write(current,rid+'\n')
            result.update(run_id=rid,observed_at=now.isoformat(),paper_only=True)
            atomic_write(base/'ops_status.json',json.dumps(result,indent=2))
            print(json.dumps(result));return 0
        except Exception as exc:
            provider.save_manifest()
            failure={'status':'failed','run_id':rid,'observed_at':now.isoformat(),'error':type(exc).__name__+': '+str(exc),'start_created':False,'snapshot':str(snapshot.relative_to(base))}
            atomic_write(base/'ops_status.json',json.dumps(failure,indent=2))
            print(json.dumps(failure));return 2
        finally:
            if stage and stage.exists(): shutil.rmtree(stage)

def write_review(base,state,rid,now):
    m=report.metrics(state)
    text='# Paper-Trading: Wochen-/Abschlussprüfung\n\n'
    text+=f"Test: {f60.VERSION}\nStart: {state['start']}\nEnde exklusiv: {state['end_exclusive']}\n"
    text+='\n'+json.dumps(m,indent=2,ensure_ascii=False)+'\n'
    text+='\nNur Ergebnisprüfung. Keine automatische Verlängerung oder Echtgeldfreigabe. '
    text+='Offene Positionen separat bewertet; Tagesdaten erlauben nur MAE-Grenzen. '
    text+='Netto nach Modellkosten, vor Steuern; FX ist Referenzkurs-Modell.\n'
    if state['finished']:
        atomic_write(base/'final-review.md',text)
    elif now.weekday()==6:
        path=base/'weekly'/f'{now.date()}-{rid}.md'; path.parent.mkdir(exist_ok=True)
        atomic_write(path,text)


if __name__=='__main__': raise SystemExit(main())
