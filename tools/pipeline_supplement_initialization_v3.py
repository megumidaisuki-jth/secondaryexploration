"""Explicit v3 operational overlay; preserve original preflight/supervisor bytes."""
from pathlib import Path
import json
from tools import pipeline_supplement_initialization as pipeline
from tools.schedule_supplement_initialization_v3 import overlay_binding
from tools.supplement_initialization_common import ROOT,OUT,sha,save

EXTRA=['tools/schedule_supplement_initialization_v3.py',
       'tools/pipeline_supplement_initialization_v3.py',
       'tests/test_supplement_initialization_scheduler_v3.py',
       'tools/recover_supplement_initialization_v3.py',
       'docs/plans/.gitattributes',
       'docs/plans/2026-10-08-S5-diagnostic-write-recovery.md']

def main():
    incident=pipeline.DIAG/'recovery-write-20261008-v3'
    validation=json.loads((incident/'validation.json').read_bytes())
    assert validation['status']=='passed' and validation['v3_overlay']==overlay_binding()
    tests=json.loads((incident/'tests.json').read_bytes()); assert tests['exit_code']==0
    for source,h in tests['source_hashes'].items(): assert sha((ROOT/source).read_bytes())==h
    binding={'schema':'S5-supervisor-overlay-v3','scheduler':overlay_binding(),
             'sources':{p:sha((ROOT/p).read_bytes()) for p in EXTRA},
             'original_supervisor_sha256':sha((ROOT/'tools/pipeline_supplement_initialization.py').read_bytes())}
    path=OUT/'pipeline-v3-binding.json'
    if path.exists(): assert json.loads(path.read_bytes())==binding
    else: save(path,binding)
    original_invoke=pipeline.invoke; original_paths=pipeline.source_paths
    def invoke(stage,script,args=()):
        if script=='schedule_supplement_initialization_v2.py': script='schedule_supplement_initialization_v3.py'
        return original_invoke(stage,script,args)
    def source_paths(): return sorted(set(original_paths()+[ROOT/p for p in EXTRA]))
    pipeline.invoke=invoke; pipeline.source_paths=source_paths
    try: pipeline.run_pipeline()
    finally: pipeline.invoke=original_invoke; pipeline.source_paths=original_paths

if __name__=='__main__': main()
