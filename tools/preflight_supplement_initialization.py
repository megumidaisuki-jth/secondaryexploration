"""Seal metadata-only S5 pilot, real pause/resume identity and test receipts."""
from collections import defaultdict
import json
import subprocess
import sys
import time
from tools.supplement_initialization_common import ROOT,OUT,CONFIG,sha,save,load,core_snapshot

def main():
    assert json.loads((OUT/'input-verification.json').read_bytes())['status']=='passed'
    assert not any((OUT/p).exists() for p in ['RUNNING.lock','VERIFYING.lock','PAUSE'])
    cfg=json.loads(CONFIG.read_bytes())
    subprocess.run(['git','diff','--quiet',cfg['source_code_revision'],'--','secondaryexploration'],cwd=ROOT,check=True)
    started=time.monotonic()
    names=['tests.test_supplement_initialization','tests.test_supplement_initialization_pipeline','tests.test_supplement_initialization_scheduler_v2']
    test=subprocess.run([sys.executable,'-m','unittest',*names,'-v'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    save(OUT/'unit-test-receipt.json',{'exit_code':test.returncode,'stdout':test.stdout,'stderr':test.stderr,'seconds':round(time.monotonic()-started,3),'test_sha256':{name:sha((ROOT/(name.replace('.','/')+'.py')).read_bytes()) for name in names}})
    assert test.returncode==0
    catalog=json.loads((OUT/'catalogue.json').read_bytes()); selection=json.loads((OUT/'preflight-selection.json').read_bytes())
    before=json.loads((OUT/'real-pause-before-resume.json').read_bytes())
    records=[dict(v,unit_id=k,path=f'runs/{k}/chunks/000000.json.gz') for k,v in before['first_chunk_bytes'].items()]
    matched=[]
    for record in records:
        path=ROOT/record['path'] if record['path'].startswith('results/') else OUT/record['path']
        data=path.read_bytes()
        assert len(data)==record['bytes'] and sha(data)==record['sha256']
        matched.append(record)
    assert len(matched)==6
    workload=defaultdict(int); rates=defaultdict(list); pilots=[]
    for row in catalog['units']:
        if not row['reused_optimized']: workload[row['node_count']]+=row['horizon']
    for row in selection['units']:
        uid=row['unit_id']; proof=json.loads((OUT/'run-verification'/(uid+'.json')).read_bytes())
        assert proof['status']=='passed-separate-common-ticket-replay'
        result,rhash=load(OUT/'runs'/uid/'result.json.gz'); assert rhash==proof['result_payload_sha256']
        seconds=0.0; count=0
        for p in sorted((OUT/'runs'/uid/'chunks').glob('*.json.gz')):
            chunk,_=load(p); seconds+=chunk['generation_seconds']; count+=chunk['end']-chunk['start']
        assert count==row['horizon']
        rates[row['node_count']].append(seconds/count)
        pilots.append({'unit_id':uid,'node_count':row['node_count'],'horizon':count,'generation_chunk_seconds':round(seconds,6),'separate_replay_status':proof['status']})
    cpu_estimate=sum(workload[n]*sum(rates[n])/len(rates[n]) for n in workload)
    scheduler_proof=None
    if (OUT/'scheduler-v2-binding.json').exists():
        binding=json.loads((OUT/'scheduler-v2-binding.json').read_bytes())
        assert binding['scheduler_sha256']==sha((ROOT/'tools/schedule_supplement_initialization_v2.py').read_bytes())
        statuses=[]
        for row in catalog['units'][:100]:
            proof=json.loads((OUT/'run-verification'/(row['unit_id']+'.json')).read_bytes())
            result,h=load(OUT/'runs'/row['unit_id']/'result.json.gz')
            assert proof['result_payload_sha256']==h and proof['status'] in ['passed-existing-O-reuse','passed-separate-common-ticket-replay']
            statuses.append(proof['status'])
        scheduler_proof={'status':'passed-real-100-unit-generation-and-separate-replay','binding':binding,
            'units':100,'new_runs_replayed':statuses.count('passed-separate-common-ticket-replay'),
            'source_reuses_checked':statuses.count('passed-existing-O-reuse'),'scientific_context':'Original v1 worker context retained; no scientific worker edits or old chunk resimulation',
            'generation_progress_receipt':json.loads((OUT/'progress.json').read_bytes())}
        save(OUT/'scheduler-v2-validation.json',scheduler_proof)
        failures={}
        diag=ROOT/'results/diagnostics/S5-initialization-pipeline-v1'
        for name in ['20261007T033627800962Z-generating-uniform-runs.stderr.txt','20261007T113626-supervisor.stderr.txt','PAUSE-after-v1-progress-read-error.json']:
            data=(diag/name).read_bytes(); failures[name]={'bytes':len(data),'sha256':sha(data),'content':data.decode('utf-8',errors='replace')}
        save(OUT/'scheduler-v1-operational-failure.json',{'incident':'Concurrent diagnostic progress read PermissionError; 27 completed units preserved; same scientific v1 context reused after segment-dispatch scheduler fix. No endpoint selection or scientific changes.',
            'diagnostics':failures,'recovery':'100 ordered units subsequently passed original separate checker; all first six pilot chunks remained byte-identical.'})
    save(OUT/'preflight.json',{'status':'passed','parents_reconstructed':480,'real_pilots':pilots,'retained_first_chunks':matched,
        'unique_units':catalog['unique_units'],'reused_optimized_units':catalog['reused_optimized_units'],'new_units':catalog['new_units'],'new_requests':catalog['new_requests'],
        'new_requests_by_n':dict(workload),'pilot_projected_generation_cpu_hours':round(cpu_estimate/3600,3),
        'timing_warning':'Metadata-only convenience pilot: n30 has 3 models, larger n has only one BA parent/trace. Projection is not a deadline; late failure/search complexity and system load may differ. Separate replay, I/O, sealing and upload are additional.',
        'tests_exit_code':0,'config_sha256':sha(CONFIG.read_bytes()),'catalogue_sha256':sha((OUT/'catalogue.json').read_bytes()),
        'core_snapshot':core_snapshot(),'scheduler_validation':scheduler_proof,'scientific_inference':'not_started; post-hoc supplement, not blinded scientific review'})
    print(json.dumps({'status':'passed','projected_generation_cpu_hours':round(cpu_estimate/3600,3),'workload':dict(workload)}),flush=True)

if __name__=='__main__': main()
