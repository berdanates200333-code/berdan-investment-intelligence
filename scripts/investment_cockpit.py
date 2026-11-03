"""Read-only, commit-pinned cockpit snapshot. Never infer a test start from registry."""
import argparse, base64, json, urllib.request
from datetime import datetime, timezone
REPO='berdanates200333-code/berdan-investment-intelligence'
def fetch(path):
    req=urllib.request.Request('https://api.github.com/repos/'+REPO+path,headers={'Accept':'application/vnd.github+json','User-Agent':'Berdan-Cockpit'})
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
def snapshot():
    repo=fetch(''); branch=repo['default_branch']; tree=fetch('/git/trees/'+branch+'?recursive=1'); sha=tree['sha']; paths={x['path'] for x in tree['tree']}
    if tree.get('truncated'):raise ValueError('Incomplete repository inventory')
    def read(path):
        d=fetch('/contents/'+path+'?ref='+sha)
        return base64.b64decode(d['content']).decode()
    ops=json.loads(read('papertrading/ops_status.json')); research=json.loads(read('research/db/ops.json'))
    ptr='papertrading/forward60/runtime/CURRENT'
    state=None
    if ptr in paths:
        run=read(ptr).strip()
        if not run or '/' in run or '..' in run:raise ValueError('Invalid state pointer')
        state=json.loads(read('papertrading/forward60/runtime/runs/'+run+'/state.json'))
    return {'retrieved_at':datetime.now(timezone.utc).isoformat(),'commit':sha,'branch':branch,
      'paper_status':'state_present_requires_integrity_review' if state else 'not_started',
      'planned_capital_eur':10000,'planned_benchmark_eur':10000,'duration_calendar_days':60,
      'portfolio':None,'positions':None,'start':None,'remaining_days':None,
      'paper_ops':ops,'research_ops':research,'raw_state':state,
      'pending_research':[p for p in paths if p.startswith('research/queue/') and p.endswith('.json') and '/erledigt/' not in p],
      'analyses':[p for p in paths if p.startswith('research/analyses/') and p.endswith('.md')],
      'runs':[{'name':r['name'],'status':r['status'],'conclusion':r['conclusion'],'created_at':r['created_at'],'url':r['html_url']} for r in fetch('/actions/runs?per_page=10')['workflow_runs']]}
if __name__=='__main__':
    # stdout is deliberately the only output; caller controls any persistence.
    print(json.dumps(snapshot(),ensure_ascii=False,indent=2))
