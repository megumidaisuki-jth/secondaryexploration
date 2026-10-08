"""Explicit diagnostic incident receipt and metadata-selected recovery smoke test."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from tools.supplement_initialization_common import ROOT,OUT,sha,encode,save
from tools.run_supplement_initialization import execution_context
from tools.pipeline_supplement_initialization import validate_preflight_snapshot,ensure_idle,DIAG
from tools.schedule_supplement_initialization_v3 import execute_record,overlay_binding

UID='e5c0e4acf543ddba3b4f6a022b820996cf087e9eb5af331d4dd0a1f86219787a'
INCIDENT=DIAG/'recovery-write-20261008-v3'
STDERR=DIAG/'20261007T100336817678Z-generating-uniform-runs.stderr.txt'

def idle():
    ensure_idle(); assert not (OUT/'PIPELINE.lock').exists()
    validate_preflight_snapshot(json.loads((OUT/'snapshot-preflight.json').read_bytes()))
    return execution_context()

def record():
    context,catalog=idle(); assert (OUT/'PAUSE').exists()
    assert not (INCIDENT/'incident.json').exists()
    paths=[OUT/'PAUSE',OUT/'pipeline-status.json',OUT/'progress.json',STDERR,
           *sorted((OUT/'run-progress').glob('*.tmp'))]
    rows=[]
    for path in paths:
        data=path.read_bytes(); rows.append({'path':path.relative_to(ROOT).as_posix(),
            'name':path.name,'bytes':len(data),'sha256':sha(data),
            'operation':'move' if path.name=='PAUSE' or path.name.endswith('.tmp') else 'copy'})
    chunks={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted((OUT/'runs'/UID/'chunks').glob('*.gz'))}
    save(INCIDENT/'incident.json',{'reason':'User explicitly authorized diagnostic write fix and recovery; process absence checked by caller',
        'error_scope':'Permission denial replacing per-unit operational progress JSON; not a scientific validation failure',
        'files_to_preserve':rows,'saved_affected_unit_chunks':chunks,'selected_unit_by_error_identity':UID,
        'worker_context_sha256':sha(encode(context)),'v3_overlay':overlay_binding(),
        'prior_progress':json.loads((OUT/'progress.json').read_bytes()),'science_unchanged':True})
    print('Incident recorded; caller must archive exact controls and copy diagnostic files byte-exactly.')

def validate_archive():
    incident=json.loads((INCIDENT/'incident.json').read_bytes()); idle()
    for row in incident['files_to_preserve']:
        data=(INCIDENT/row['name']).read_bytes(); assert len(data)==row['bytes'] and sha(data)==row['sha256']
        if row['operation']=='move': assert not (ROOT/row['path']).exists()
    for path,h in incident['saved_affected_unit_chunks'].items(): assert sha((ROOT/path).read_bytes())==h
    assert not (OUT/'PAUSE').exists()
    return incident

def exercise():
    incident=validate_archive(); context,catalog=execution_context()
    row=next(r for r in catalog['units'] if r['unit_id']==UID); generated=0
    # Bounded segment calls are exactly those used by the two-process scheduler.
    while True:
        receipt=execute_record(row,context,1); generated+=receipt['new_chunks']
        print(json.dumps(receipt),flush=True)
        if receipt['state']=='computed': break
        assert not (OUT/'PAUSE').exists()
    for path,h in incident['saved_affected_unit_chunks'].items(): assert sha((ROOT/path).read_bytes())==h
    assert generated==(row['horizon']+99)//100-len(incident['saved_affected_unit_chunks'])
    with (INCIDENT/'selected-replay.stdout.txt').open('xb') as stdout,(INCIDENT/'selected-replay.stderr.txt').open('xb') as stderr:
        proc=subprocess.run([sys.executable,str(ROOT/'tools/verify_supplement_initialization.py'),'--unit',UID],
                            cwd=ROOT,stdout=stdout,stderr=stderr)
    assert proc.returncode==0
    proof=json.loads((OUT/'run-verification'/(UID+'.json')).read_bytes())
    assert proof['status']=='passed-separate-common-ticket-replay' and proof['new_requests_replayed']==row['horizon']
    save(INCIDENT/'validation.json',{'status':'passed','selected_unit_by_error_identity':UID,
        'previous_chunks_byte_unchanged':len(incident['saved_affected_unit_chunks']),
        'new_chunks_generated':generated,'separate_replay_requests':row['horizon'],
        'replay_proof_sha256':sha(encode(proof)), 'v3_overlay':overlay_binding(),
        'scope':'Operational recovery smoke test only; full-stage replay and four-arm inference remain pending'})
    print('Affected unit resumed without rewriting old chunks; original separate checker passed.')

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['record','validate-archive','exercise']); args=p.parse_args()
    {'record':record,'validate-archive':validate_archive,'exercise':exercise}[args.action]()
