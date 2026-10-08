"""Operational overlay: bounded retry of per-unit diagnostic rename only.

Scientific executor, simulation, storage and v2 dispatch source stay unchanged.
No simulation is retried by this adapter. A persistent write failure still stops.
"""
import argparse
import json
import os
from pathlib import Path
import time
import uuid
from tools import run_supplement_initialization as worker
from tools import schedule_supplement_initialization_v2 as scheduler
from tools.supplement_initialization_common import OUT,ROOT,encode,sha,save

RENAME_TIMEOUT=10.0

def diagnostic_save(path,value,timeout=RENAME_TIMEOUT):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+f'.{os.getpid()}.{uuid.uuid4().hex}.tmp')
    # Serialize and fsync once. Retry the SAME bytes and SAME rename, not the
    # worker or a scientific chunk. Failed temporary data remain recoverable.
    with tmp.open('xb') as stream:
        stream.write(encode(value)); stream.flush(); os.fsync(stream.fileno())
    began=time.monotonic()
    while True:
        try:
            os.replace(tmp,path)
            return
        except PermissionError as exc:
            if getattr(exc,'winerror',None) not in (None,5,32,33): raise
            if time.monotonic()-began>=timeout: raise
            time.sleep(.05)

def execute_record(row,context,max_new_chunks=None,out=OUT):
    root=(Path(out)/'run-progress').resolve()
    original=worker.save
    def scoped_save(path,value):
        candidate=Path(path).resolve()
        if candidate.parent==root and candidate.name==row['unit_id']+'.json':
            return diagnostic_save(candidate,value)
        return original(path,value)
    # ProcessPool runs one task at a time in each process. Restore in finally;
    # store() and the common module's scientific atomic writer are NOT patched.
    worker.save=scoped_save
    try: return worker.execute_record(row,context,max_new_chunks,out)
    finally: worker.save=original

def overlay_binding():
    context,_=worker.execution_context()
    return {'schema':'S5-operational-overlay-v3',
        'overlay_sha256':sha(Path(__file__).read_bytes()),
        'v2_scheduler_sha256':sha((ROOT/'tools/schedule_supplement_initialization_v2.py').read_bytes()),
        'frozen_worker_context_sha256':sha(encode(context)),
        'diagnostic_rename_timeout_seconds':RENAME_TIMEOUT,
        'scope':'Only exact per-unit run-progress JSON rename; frozen scientific worker, tickets, chunks, inputs and replay unchanged'}

def run(args):
    value=overlay_binding(); path=OUT/'scheduler-v3-binding.json'
    if path.exists(): assert json.loads(path.read_bytes())==value
    else: save(path,value)
    original=scheduler.execute_record
    scheduler.execute_record=execute_record
    try: scheduler.run(args)
    finally: scheduler.execute_record=original

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--workers',type=int,default=2)
    p.add_argument('--unit',action='append'); p.add_argument('--maximum-units',type=int)
    p.add_argument('--stop-after-chunks',type=int); run(p.parse_args())
