"""Seal complete S5 arithmetic-verified four-arm statistics, then scoped Git upload."""
import json
from pathlib import Path
from tools.supplement_initialization_common import ROOT,sha,encode,save,atomic
from tools.analyze_supplement_initialization import OUT,ensure_ready
from tools.pipeline_supplement_initialization import git,check_git_bytes

DIAG=ROOT/'results/diagnostics/S5-four-arm-statistics-v1'
SOURCES=['tools/analyze_supplement_initialization.py','tools/verify_supplement_initialization_analysis.py',
         'tools/seal_supplement_initialization_analysis.py','tests/test_supplement_initialization_analysis.py',
         'tools/report_supplement_initialization_analysis.py',
         'tests/test_supplement_initialization_seal.py',
         'docs/plans/2026-10-07-S5-statistics-preparation.md','configs/supplement/initialization-ablation-v1.json']

def validate():
    ensure_ready()
    assert not any((OUT/name).exists() for name in ['PAUSE','RUNNING.lock','VERIFYING.lock'])
    proof=json.loads((OUT/'verification.json').read_bytes())
    assert proof['status']=='passed'
    for key,n in [('parents_verified',480),('traces_verified',3360),('bootstrap_replicates_verified',160000),
                  ('bootstrap_chunks_verified',320),('contrast_rows_verified',240),('arm_mean_rows_verified',192),
                  ('optimized_S1_estimates_reproduced',16),('new_simulations',0),('raw_blocks_read',0)]: assert proof[key]==n
    binding=json.loads((OUT/'binding.json').read_bytes()); checker=json.loads((OUT/'arithmetic-binding.json').read_bytes())
    assert proof['binding']==checker and checker['analysis_binding_sha256']==sha(encode(binding))
    assert checker['results_sha256']==sha((OUT/'results.json').read_bytes())
    assert checker['checker_sha256']==sha((ROOT/'tools/verify_supplement_initialization_analysis.py').read_bytes())
    assert binding['analysis_sha256']==sha((ROOT/'tools/analyze_supplement_initialization.py').read_bytes())
    from tools.supplement_initialization_common import load
    checkpoints=sorted((OUT/'checkpoints').glob('*.json.gz')); assert len(checkpoints)==320
    for p in checkpoints:
        value,h=load(p); receipt=json.loads((OUT/'arithmetic-checkpoints'/(p.name.removesuffix('.json.gz')+'.json')).read_bytes())
        assert receipt=={'checker_binding_sha256':sha(encode(checker)),'checkpoint_payload_sha256':h,'status':'passed-500-shared-parent-draws'}
        assert value['meta']['binding_sha256']==sha(encode(binding))
    return proof

def main():
    proof=validate()
    assert git('branch','--show-current').decode().strip()=='codex/research-contract'
    assert git('remote','get-url','origin').decode().strip().removesuffix('.git')=='https://github.com/megumidaisuki-jth/secondaryexploration'
    assert not git('diff','--cached','--name-only').strip(),'Do not include unrelated staged work.'
    paths=[ROOT/p for p in SOURCES]
    paths.extend(p for p in OUT.rglob('*') if p.is_file() and p.name not in ['progress.json','verification-progress.json','PAUSE']
                 and not p.name.endswith(('.tmp','.lock')) and not p.name.startswith('snapshot-'))
    paths.extend(p for p in DIAG.rglob('*') if p.is_file() and p.name not in ['upload.json','manifest.json','git-paths.nul'])
    rows=[]
    for p in sorted(set(paths)):
        data=p.read_bytes(); rows.append({'path':p.relative_to(ROOT).as_posix(),'bytes':len(data),'sha256':sha(data)})
    manifest=DIAG/'manifest.json'
    value={'stage':'S5-four-arm-arithmetic-verified','scope':'Post-hoc paired inference; 80 pointwise unadjusted intervals, 160 descriptive scope effects; not new blinded confirmation',
           'verification_sha256':sha((OUT/'verification.json').read_bytes()),'files':rows,'file_count':len(rows),'total_bytes':sum(r['bytes'] for r in rows)}
    if manifest.exists(): assert json.loads(manifest.read_bytes())==value,'Do not replace an already sealed changed manifest.'
    else: save(manifest,value)
    rows.append({'path':manifest.relative_to(ROOT).as_posix(),'bytes':manifest.stat().st_size,'sha256':sha(manifest.read_bytes())})
    pathspec=DIAG/'git-paths.nul'
    atomic(pathspec,b''.join(r['path'].encode('utf8')+b'\0' for r in rows))
    git('--literal-pathspecs','add',f'--pathspec-from-file={pathspec}','--pathspec-file-nul')
    staged=set(git('diff','--cached','--name-only','-z').decode().strip('\0').split('\0'))-{''}
    assert staged.issubset({r['path'] for r in rows})
    check_git_bytes(rows,'')
    if staged: git('commit','-m','S5: archive paired four-arm inference and separate arithmetic verification')
    check_git_bytes(rows,'HEAD')
    git('push','origin','HEAD:refs/heads/codex/research-contract')
    head=git('rev-parse','HEAD').decode().strip(); remote=git('ls-remote','origin','refs/heads/codex/research-contract').decode().split()[0]
    assert head==remote
    receipt={'status':'uploaded-byte-verified','commit':head,'remote_commit':remote,'files_checked':len(rows),
             'manifest_sha256':sha(manifest.read_bytes()),'verification_sha256':sha((OUT/'verification.json').read_bytes())}
    save(DIAG/'upload.json',receipt); print(json.dumps(receipt),flush=True)

if __name__=='__main__': main()
