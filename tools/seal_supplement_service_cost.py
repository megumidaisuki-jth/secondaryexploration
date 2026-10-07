"""Seal every S3 input binding, output, checkpoint, and figure source."""
import csv
import hashlib
import json
from pathlib import Path
import platform
import matplotlib
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/supplement/service-cost-posthoc-v1'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

verification=json.loads((OUT/'verification.json').read_bytes())
assert verification['status']=='passed' and verification['results_sha256']==sha(OUT/'results.json')
assert verification['verifier_sha256']==sha(ROOT/'tools/verify_supplement_service_cost.py')
assert len(list((OUT/'parents').glob('*.json')))==480
assert len(list((OUT/'bootstrap').glob('*.bin.gz')))==320
assert not list(OUT.rglob('*.tmp')) and not list(OUT.rglob('*.lock'))
with (OUT/'figure-s3-arms.csv').open(encoding='utf-8',newline='') as f: arms=list(csv.DictReader(f))
with (OUT/'figure-s3-contrasts.csv').open(encoding='utf-8',newline='') as f: contrasts=list(csv.DictReader(f))
with (OUT/'parent-source-data.csv').open(encoding='utf-8',newline='') as f: parents=list(csv.DictReader(f))
assert (len(arms),len(contrasts),len(parents))==(64,200,3840)
results=json.loads((OUT/'results.json').read_bytes())
for row,r in zip(arms,results['arms']):
    assert (row['phase'],int(row['node_count']),row['family'],row['role'])==(r['phase'],r['node_count'],r['family'],r['role'])
    for item in r['cost_per_accepted_request']:
        prefix=item['cost']; assert float(row[prefix+'_per_success'])==item['estimate']
        assert float(row[prefix+'_lower'])==item['pointwise_95_interval'][0]
        assert float(row[prefix+'_upper'])==item['pointwise_95_interval'][1]
for row,r in zip(contrasts,results['contrasts']):
    assert row['comparison']==r['comparison'] and row['cost']==r['cost']
    assert float(row['estimate'])==r['estimate'] and [float(row['lower']),float(row['upper'])]==r['pointwise_95_interval']
for name in ('figure-s3-service-cost','figure-s3-paired-cost'):
    assert '<text' in (OUT/f'{name}.svg').read_text(encoding='utf-8')
preflight=json.loads((OUT/'figure-preflight.json').read_bytes())
assert preflight['summary']['counts']['FAIL']==0
qa=json.loads((OUT/'qa.json').read_bytes()); assert qa['visual_review']=='passed'
sources=[ROOT/'configs/supplement/service-cost-posthoc-v1.json',ROOT/'tools/supplement_service_cost.py',
         ROOT/'tools/verify_supplement_service_cost.py',ROOT/'tools/report_supplement_service_cost.py',
         ROOT/'tools/verify_supplement_service_cost_v1.py',Path(__file__),ROOT/'tests/test_supplement_service_cost.py']
files=sources+sorted(p for p in OUT.rglob('*') if p.is_file() and p.name!='delivery-manifest.json')
manifest={'date':'2026-10-07','completed':['S3 descriptive joint service-cost analysis'],
          'new_simulations':0,'raw_blocks_arithmetically_checked':480,'bootstrap_replicates':160000,
          'checkpoint_counts':{'parents':480,'bootstrap_chunks':320},
          'runtime':{'python':platform.python_version(),'numpy':np.__version__,'matplotlib':matplotlib.__version__},
          'intervals':'unadjusted pointwise 95%; not simultaneous or confirmatory',
          'verification':verification,'qa':qa,
          'files':[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]}
(OUT/'delivery-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
print(f'Sealed {len(files)} files, {sum(p.stat().st_size for p in files)/1e6:.3f} MB.')
