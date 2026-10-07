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
    names=['tests.test_supplement_initialization','tests.test_supplement_initialization_pipeline']
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
    save(OUT/'preflight.json',{'status':'passed','parents_reconstructed':480,'real_pilots':pilots,'retained_first_chunks':matched,
        'unique_units':catalog['unique_units'],'reused_optimized_units':catalog['reused_optimized_units'],'new_units':catalog['new_units'],'new_requests':catalog['new_requests'],
        'new_requests_by_n':dict(workload),'pilot_projected_generation_cpu_hours':round(cpu_estimate/3600,3),
        'timing_warning':'Metadata-only convenience pilot: n30 has 3 models, larger n has only one BA parent/trace. Projection is not a deadline; late failure/search complexity and system load may differ. Separate replay, I/O, sealing and upload are additional.',
        'tests_exit_code':0,'config_sha256':sha(CONFIG.read_bytes()),'catalogue_sha256':sha((OUT/'catalogue.json').read_bytes()),
        'core_snapshot':core_snapshot(),'scientific_inference':'not_started; post-hoc supplement, not blinded scientific review'})
    print(json.dumps({'status':'passed','projected_generation_cpu_hours':round(cpu_estimate/3600,3),'workload':dict(workload)}),flush=True)

if __name__=='__main__': main()
