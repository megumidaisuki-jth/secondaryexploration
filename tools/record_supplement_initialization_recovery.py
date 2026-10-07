"""Metadata-only evidence for an explicitly requested S5 restart after reboot.

Does not remove locks, move files, read scientific endpoints or restart work.
The caller checks process identities, then archives exact files in PowerShell.
"""
import argparse
import json
from pathlib import Path
from tools.supplement_initialization_common import ROOT,OUT,sha,encode,save,core_snapshot,runtime
from tools.pipeline_supplement_initialization import validate_preflight_snapshot
from tools.run_supplement_initialization import execution_context

def main(args):
    archive=Path(args.archive).resolve()
    expected=(ROOT/'results/diagnostics/S5-initialization-pipeline-v1').resolve()
    assert archive.parent==expected and archive.name.startswith('recovery-')
    assert archive.is_dir()
    receipt=archive/'recovery.json'
    if args.check_archived:
        record=json.loads(receipt.read_bytes())
        for row in record['files_to_archive']:
            old=ROOT/row['path']; new=archive/row['name']
            assert not old.exists() and new.is_file()
            data=new.read_bytes(); assert len(data)==row['bytes'] and sha(data)==row['sha256']
        record['archived_files_byte_verified']=True
        save(receipt,record); print('Stale controls and temporary diagnostic file archived byte-exactly.'); return
    assert not receipt.exists()
    validate_preflight_snapshot(json.loads((OUT/'snapshot-preflight.json').read_bytes()))
    context,catalog=execution_context()
    scheduler=json.loads((OUT/'scheduler-v2-binding.json').read_bytes())
    assert scheduler['frozen_worker_context_sha256']==sha(encode(context))
    assert scheduler['scheduler_sha256']==sha((ROOT/'tools/schedule_supplement_initialization_v2.py').read_bytes())
    files=[]
    paths=[OUT/'PIPELINE.lock',OUT/'RUNNING.lock',*sorted((OUT/'run-progress').glob('*.tmp'))]
    assert all(p.is_file() for p in paths[:2])
    for p in paths:
        assert p.resolve().is_relative_to(OUT.resolve())
        data=p.read_bytes(); files.append({'path':p.relative_to(ROOT).as_posix(),'name':p.name,'bytes':len(data),'sha256':sha(data)})
    progress=json.loads((OUT/'progress.json').read_bytes())
    save(receipt,{'reason':'User requested continuation; OS reboot and absent old process identities independently observed in PowerShell.',
        'boot_time_client_zone':args.boot_time,'old_controls':{p.name:json.loads(p.read_bytes()) for p in paths[:2]},
        'old_scheduler_progress':progress,'files_to_archive':files,'archived_files_byte_verified':False,
        'core_snapshot':core_snapshot(),'runtime':runtime(),'frozen_worker_context_sha256':sha(encode(context)),
        'unique_units_total':catalog['unique_units'],'new_requests_total':catalog['new_requests'],
        'new_simulations_started_by_recorder':0,'scientific_endpoints_read':0,
        'recovery_rule':'Keep every scientific chunk and result unchanged. Resume existing v2 supervisor; v1 worker checks hash/state chains and skips saved simulation chunks.'})
    print('Frozen sources, preflight bytes and worker context passed; recovery evidence recorded.')

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--archive',required=True); p.add_argument('--boot-time'); p.add_argument('--check-archived',action='store_true')
    main(p.parse_args())
