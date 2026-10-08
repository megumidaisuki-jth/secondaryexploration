"""One-shot Windows Task Scheduler entry; no automatic restart or simulation change.

Runs the already-bound v3 supervisor in a process tree owned by Windows Task
Scheduler rather than an app-launched shell. Records identity and exit status.
"""
import ctypes
from ctypes import wintypes
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
DIAG=ROOT/'results/diagnostics/S5-initialization-pipeline-v1/task-launch-v1'
OUT=ROOT/'results/supplement/initialization-ablation-v1'

def save(path,value):
    data=(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf8')
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+f'.{os.getpid()}.{uuid.uuid4().hex}.tmp')
    with tmp.open('xb') as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
    os.replace(tmp,path)

def job_membership():
    if os.name!='nt': return None
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    kernel.IsProcessInJob.argtypes=[wintypes.HANDLE,wintypes.HANDLE,ctypes.POINTER(wintypes.BOOL)]
    kernel.IsProcessInJob.restype=wintypes.BOOL
    value=wintypes.BOOL()
    if not kernel.IsProcessInJob(kernel.GetCurrentProcess(),None,ctypes.byref(value)):
        raise ctypes.WinError(ctypes.get_last_error())
    return bool(value.value)

def launch(diag=DIAG,out=OUT,supervisor=None):
    supervisor=supervisor or ROOT/'tools/pipeline_supplement_initialization_v3.py'
    # Refuse unresolved work before Popen; no controls are removed by this entry.
    for name in ['PAUSE','PIPELINE.lock','RUNNING.lock','VERIFYING.lock']:
        assert not (out/name).exists(),f'Unresolved control {name}; no automatic recovery.'
    diag.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    receipt=diag/f'{stamp}-receipt.json'; lock=diag/'ENTRY.lock'
    environment=os.environ.copy()
    environment.update(PYTHONPATH='E:\\second-doc-runtime;'+str(ROOT),
                       PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
    value={'schema':'S5-task-entry-v1','state':'starting','pid':os.getpid(),
           'parent_pid':os.getppid(),'current_process_in_job':job_membership(),
           'updated_utc':datetime.now(timezone.utc).isoformat(),
           'entry_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'supervisor_sha256':hashlib.sha256(supervisor.read_bytes()).hexdigest(),
           'python':sys.executable,'restarts':0,
           'scope':'Existing two-worker generation, original separate replay, byte-verified upload; no inference'}
    with lock.open('xb') as stream: stream.write(json.dumps({'pid':os.getpid(),'receipt':str(receipt)}).encode())
    try:
        save(receipt,value)
        stdout=diag/f'{stamp}.stdout.txt'; stderr=diag/f'{stamp}.stderr.txt'
        with stdout.open('xb') as output,stderr.open('xb') as error:
            python=Path(sys.executable).with_name('python.exe') if os.name=='nt' else Path(sys.executable)
            child=subprocess.Popen([str(python),str(supervisor)],cwd=ROOT,env=environment,stdout=output,stderr=error,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            value.update(state='running',child_pid=child.pid,stdout=str(stdout),stderr=str(stderr))
            save(receipt,value)
            code=child.wait()
        value.update(state='finished' if code==0 else 'stopped-on-error',exit_code=code,
                     stdout_bytes=stdout.stat().st_size,stderr_bytes=stderr.stat().st_size,
                     updated_utc=datetime.now(timezone.utc).isoformat())
        save(receipt,value)
        return code
    except BaseException as exc:
        value.update(state='stopped-on-error',error=repr(exc),updated_utc=datetime.now(timezone.utc).isoformat())
        save(receipt,value)
        raise
    finally: lock.unlink()

if __name__=='__main__': sys.exit(launch())
