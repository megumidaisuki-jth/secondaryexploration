"""Seal S4 source and result artifacts, excluding the self-referential manifest."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/supplement/short-window-posthoc-v1'
def main():
    assert not any((OUT/p).exists() for p in ['RUNNING.lock','VERIFYING.lock','PAUSE'])
    check=json.loads((OUT/'verification.json').read_bytes()); assert check['status']=='passed'
    qa=json.loads((OUT/'figure-qa.json').read_bytes()); assert qa['status']=='passed-visual-and-source-QA'
    preflight=json.loads((OUT/'figure-source-preflight.json').read_bytes()); assert preflight['summary']['ready'] and preflight['summary']['counts']['FAIL']==0
    runtime=json.loads((OUT/'report-runtime.json').read_bytes())
    assert runtime['report_script_sha256']==hashlib.sha256((ROOT/'tools/report_supplement_short_window.py').read_bytes()).hexdigest()
    assert qa['QA_script_sha256']==hashlib.sha256((ROOT/'tools/qa_supplement_short_window.py').read_bytes()).hexdigest()
    for name,expected in qa['files'].items(): assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==expected
    source=[ROOT/'configs/supplement/short-window-posthoc-v1.json',ROOT/'tests/test_supplement_short_window.py']
    source.extend(ROOT/'tools'/name for name in ['supplement_short_window.py','verify_supplement_short_window.py','report_supplement_short_window.py','qa_supplement_short_window.py','seal_supplement_short_window.py'])
    proof=check['binding']
    assert hashlib.sha256(source[0].read_bytes()).hexdigest()==proof['config_sha256']
    assert hashlib.sha256((OUT/'results.json').read_bytes()).hexdigest()==proof['results_sha256']
    assert hashlib.sha256((ROOT/'tools/verify_supplement_short_window.py').read_bytes()).hexdigest()==proof['checker_sha256']
    binding=json.loads((OUT/'binding.json').read_bytes())
    assert binding['script_sha256']==hashlib.sha256((ROOT/'tools/supplement_short_window.py').read_bytes()).hexdigest()
    assert binding['config_sha256']==proof['config_sha256']
    (OUT/'delivery-status.json').write_text(json.dumps({'state':'computed-verified-reported-and-visual-QA-passed','extraction_percent':100,
         'bootstrap_percent':100,'verification_percent':100,'parents':480,'bootstrap_replicates':160000,
         'new_simulations':0,'next_simulation_phase_started':False,'upload_state':'pending-git-blob-and-remote-verification',
         'sealed_at_utc':datetime.now(timezone.utc).isoformat()},sort_keys=True,indent=2)+'\n',encoding='utf-8',newline='\n')
    files=source+sorted(p for p in OUT.rglob('*') if p.is_file() and p.name!='delivery-manifest.json')
    assert not any(p.name.endswith('.tmp') for p in files)
    records=[]
    for p in files:
        b=p.read_bytes(); records.append({'path':p.relative_to(ROOT).as_posix(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
    value={'schema':'S4-delivery-manifest-v1','interpretation':'Post-hoc exploratory paired window sensitivity; no new simulations or confirmatory decisions',
           'files':records,'file_count':len(records),'total_bytes':sum(r['bytes'] for r in records),
           'verification_sha256':hashlib.sha256((OUT/'verification.json').read_bytes()).hexdigest(),
           'scope':'S4 only; frozen full phase evidence, S3 inventory and S1 result are SHA-bound external inputs.'}
    (OUT/'delivery-manifest.json').write_text(json.dumps(value,sort_keys=True,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'file_count':value['file_count'],'total_bytes':value['total_bytes'],'state':'sealed-pending-git-byte-verification'}))

if __name__=='__main__': main()
