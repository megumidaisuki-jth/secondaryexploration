"""Local S5 generation -> separate replay -> scoped byte-verified Git upload.

No inference, plotting, retraining or simulation of original O arms is performed here.
PAUSE is respected at safe boundaries; errors never trigger an automatic retry.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from tools.supplement_initialization_common import ROOT,OUT,sha,save,encode,atomic,load,core_snapshot

DIAG=ROOT/'results/diagnostics/S5-initialization-pipeline-v1'
EXCLUDE={'PAUSE','RUNNING.lock','VERIFYING.lock','PIPELINE.lock','pipeline-status.json',
         'progress.json','progress.md','replay-progress.json','preparation-progress.json'}
SOURCES=['.gitattributes','configs/supplement/initialization-ablation-v1.json',
    'docs/plans/2026-10-07-S5-initialization-ablation.md','docs/plans/2026-10-07-S5-running.md',
    'tests/test_supplement_initialization.py','tests/test_supplement_initialization_pipeline.py',
    'tools/supplement_initialization_common.py','tools/prepare_supplement_initialization.py',
    'tools/run_supplement_initialization.py','tools/verify_supplement_initialization.py',
    'tools/preflight_supplement_initialization.py','tools/pipeline_supplement_initialization.py']

def git(*args,input=None):
    return subprocess.run(['git',*args],cwd=ROOT,input=input,capture_output=True,check=True).stdout

def source_paths():
    files=[ROOT/p for p in SOURCES]
    for p in OUT.rglob('*'):
        if p.is_file() and p.name not in EXCLUDE and not p.name.endswith(('.tmp','.lock')) and not p.name.startswith('snapshot-'):
            assert p.resolve().is_relative_to(OUT.resolve())
            files.append(p)
    return sorted(set(files))

def check_git_bytes(rows,revision):
    for start in range(0,len(rows),128):
        batch=rows[start:start+128]
        raw=git('cat-file','--batch',input=''.join(f"{revision}:{r['path']}\n" for r in batch).encode())
        offset=0
        for r in batch:
            end=raw.index(b'\n',offset); header=raw[offset:end].split(); assert header[1]==b'blob'
            size=int(header[2]); begin=end+1; data=raw[begin:begin+size]
            assert size==r['bytes'] and sha(data)==r['sha256'],r['path']
            assert raw[begin+size:begin+size+1]==b'\n'; offset=begin+size+1
        assert offset==len(raw)

def ensure_idle():
    for name in ['RUNNING.lock','VERIFYING.lock']:
        assert not (OUT/name).exists(),f'Active or unresolved stale lock: {name}; do not delete it blindly.'

def validate_preflight_snapshot(snapshot):
    for row in snapshot['files']:
        # These are operational receipts (PID, invocation duration), overwritten on
        # legitimate cache reuse. Their old bytes remain in Git, but are not frozen
        # scientific inputs. Chunk/results/replay proofs and all sources remain bound.
        local=Path(row['path']).parts
        if 'run-progress' in local or 'execution-receipts' in local: continue
        data=(ROOT/row['path']).read_bytes()
        assert len(data)==row['bytes'] and sha(data)==row['sha256'],f"Preflight snapshot changed: {row['path']}"

def validate_verified():
    catalog=json.loads((OUT/'catalogue.json').read_bytes()); v=json.loads((OUT/'verification.json').read_bytes())
    assert v['status']=='passed' and v['parents_verified']==480
    assert v['unique_units_verified']==catalog['unique_units'] and v['new_requests_replayed']==catalog['new_requests']
    for row in catalog['units']:
        proof=json.loads((OUT/'run-verification'/(row['unit_id']+'.json')).read_bytes())
        result,rhash=load(OUT/'runs'/row['unit_id']/'result.json.gz')
        assert proof['result_payload_sha256']==rhash and proof['unit_payload_sha256']==row['payload_sha256']
        assert proof['status'] in ['passed-existing-O-reuse','passed-separate-common-ticket-replay']
        for index,h in enumerate(proof.get('chunk_payload_sha256',[])):
            assert load(OUT/'runs'/row['unit_id']/'chunks'/f'{index*100:06d}.json.gz')[1]==h
    return catalog

def seal_upload(stage):
    ensure_idle()
    preflight=json.loads((OUT/'preflight.json').read_bytes())
    assert preflight['status']=='passed' and preflight['core_snapshot']==core_snapshot()
    if stage=='verified-simulation': validate_verified()
    assert git('branch','--show-current').decode().strip()=='codex/research-contract'
    assert git('remote','get-url','origin').decode().strip().removesuffix('.git')=='https://github.com/megumidaisuki-jth/secondaryexploration'
    assert not git('diff','--cached','--name-only').strip(),'Unrelated staged changes must be preserved, not included.'
    rows=[]
    for p in source_paths():
        data=p.read_bytes(); rows.append({'path':p.relative_to(ROOT).as_posix(),'bytes':len(data),'sha256':sha(data)})
    # A verified snapshot also retains the original preflight manifest unchanged.
    prior=OUT/'snapshot-preflight.json'
    if stage!='preflight' and prior.exists():
        data=prior.read_bytes(); rows.append({'path':prior.relative_to(ROOT).as_posix(),'bytes':len(data),'sha256':sha(data)})
    manifest=OUT/f'snapshot-{stage}.json'
    value={'stage':stage,'scope':'S5 only; scientific inference and manuscript integration not yet performed',
        'file_count':len(rows),'files':rows,'total_bytes':sum(r['bytes'] for r in rows)}
    if manifest.exists(): assert json.loads(manifest.read_bytes())==value,'Snapshot changed; do not silently replace sealed manifest.'
    else: save(manifest,value)
    data=manifest.read_bytes(); rows.append({'path':manifest.relative_to(ROOT).as_posix(),'bytes':len(data),'sha256':sha(data)})
    DIAG.mkdir(parents=True,exist_ok=True)
    paths=DIAG/f'git-{stage}-paths.nul'
    atomic(paths,b''.join(r['path'].encode()+b'\0' for r in rows))
    git('--literal-pathspecs','add',f'--pathspec-from-file={paths}','--pathspec-file-nul')
    staged=set(git('diff','--cached','--name-only','-z').decode().strip('\0').split('\0'))-{''}
    assert staged.issubset({r['path'] for r in rows}),'Concurrent unrelated staging detected; do not commit it.'
    check_git_bytes(rows,'')
    if git('diff','--cached','--name-only').strip(): git('commit','-m',f'S5: preserve {stage} inputs, checkpoints and execution evidence')
    check_git_bytes(rows,'HEAD')
    head=git('rev-parse','HEAD').decode().strip()
    git('push','origin','HEAD:refs/heads/codex/research-contract')
    remote=git('ls-remote','origin','refs/heads/codex/research-contract').decode().split()[0]
    assert remote==head
    receipt={'stage':stage,'status':'uploaded-byte-verified','commit':head,'remote_commit':remote,'files_checked':len(rows),'manifest_sha256':sha(manifest.read_bytes())}
    save(DIAG/f'upload-{stage}.json',receipt)
    print(json.dumps(receipt),flush=True)
    return receipt

def status(state,**kw):
    save(OUT/'pipeline-status.json',{'state':state,'pid':os.getpid(),'updated_utc':datetime.now(timezone.utc).isoformat(),
        'scientific_inference':'not_started','notification':'Only meaningful completion, error or user action; no repeated unchanged updates',**kw})

def invoke(stage,script,args=()):
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=DIAG/f'{stamp}-{stage}.stdout.txt'; err=DIAG/f'{stamp}-{stage}.stderr.txt'
    with out.open('xb') as stdout,err.open('xb') as stderr:
        child=subprocess.Popen([sys.executable,str(ROOT/'tools'/script),*args],cwd=ROOT,stdout=stdout,stderr=stderr)
        status(stage,child_pid=child.pid,child_argv=[script,*args],stdout=str(out),stderr=str(err))
        code=child.wait()
    save(DIAG/f'{stamp}-{stage}-receipt.json',{'stage':stage,'exit_code':code,'stdout':str(out),'stderr':str(err),'stdout_bytes':out.stat().st_size,'stderr_bytes':err.stat().st_size})
    assert code==0,f'{stage} failed with exit code {code}; see {err}'

def run_pipeline():
    ensure_idle(); DIAG.mkdir(parents=True,exist_ok=True)
    assert json.loads((OUT/'preflight.json').read_bytes())['status']=='passed'
    snapshot=json.loads((OUT/'snapshot-preflight.json').read_bytes())
    validate_preflight_snapshot(snapshot)
    with (OUT/'PIPELINE.lock').open('xb') as f: f.write(encode({'pid':os.getpid(),'argv':sys.argv}))
    try:
        if (OUT/'PAUSE').exists(): status('paused-safe-checkpoint'); return
        invoke('generating-uniform-runs','run_supplement_initialization.py',['--workers','2'])
        if (OUT/'PAUSE').exists(): status('paused-safe-checkpoint'); return
        p=json.loads((OUT/'progress.json').read_bytes()); catalog=json.loads((OUT/'catalogue.json').read_bytes())
        assert p['state']=='computed-pending-separate-replay' and p['unique_units_computed']==catalog['unique_units']
        invoke('separate-input-and-common-ticket-replay','verify_supplement_initialization.py')
        if (OUT/'PAUSE').exists(): status('paused-safe-checkpoint'); return
        validate_verified(); status('verified-simulation-uploading')
        receipt=seal_upload('verified-simulation')
        status('verified-simulation-uploaded-awaiting-four-arm-statistics',upload=receipt,
               next_step='Frozen paired four-arm bootstrap, separate arithmetic checks, scientific plots and manuscript update; not performed by this compute supervisor.')
    except BaseException as exc:
        status('stopped-on-error',error=repr(exc),action='Preserve all files. Do not auto-retry, delete locks or restart simulation.')
        raise
    finally: (OUT/'PIPELINE.lock').unlink()

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--seal-upload',choices=['preflight','verified-simulation']); a=p.parse_args()
    if a.seal_upload: seal_upload(a.seal_upload)
    else: run_pipeline()
