"""S5 segment-dispatch scheduler: read worker progress only after that worker returns.

Frozen v1 execute_record and scientific envelopes remain unchanged. At most one
100-request segment per submission; the parent owns the live progress snapshot.
It never opens the diagnostic file of a concurrently active unit on Windows.
"""
import argparse
from collections import deque
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
import json
import os
from pathlib import Path
import sys
import time
from tools.supplement_initialization_common import OUT,sha,encode,save,atomic,config
from tools.run_supplement_initialization import execution_context,execute_record

def shared_read(path):
    return Path(path).read_bytes()

def read_progress(path,timeout=2.0):
    began=time.monotonic()
    while True:
        try: return json.loads(shared_read(path))
        except OSError as exc:
            # A pending rename/open race may transiently deny access. Do not
            # skip a record, swallow malformed JSON or retry unrelated I/O errors.
            if getattr(exc,'winerror',None) not in (2,5,32,33) and not isinstance(exc,(PermissionError,FileNotFoundError)): raise
            if time.monotonic()-began>=timeout: raise
            time.sleep(.01)

def publish_progress(path,data,timeout=2.0):
    # Only parent-owned live displays: a viewer may briefly hold a Windows read
    # handle. Never apply retries to scientific chunk writes or validation.
    began=time.monotonic()
    while True:
        try: atomic(path,data); return
        except PermissionError:
            if time.monotonic()-began>=timeout: raise
            time.sleep(.01)

def run(args):
    context,catalog=execution_context(); cfg=config()
    assert 1<=args.workers<=cfg['maximum_workers']
    selected=[r for r in catalog['units'] if not args.unit or r['unit_id'] in args.unit]
    if args.unit: assert len(selected)==len(set(args.unit))
    if args.maximum_units is not None: selected=selected[:args.maximum_units]
    scheduler={'scheduler_sha256':sha(Path(__file__).read_bytes()),'frozen_worker_context_sha256':sha(encode(context)),
        'scientific_worker':'Unmodified tools.run_supplement_initialization.execute_record; v1 context and all saved chunks retained',
        'change_scope':'Submit one existing <=100-request segment at a time, read progress only after unit returns; parent caches diagnostic counts. Scientific simulation, ticket indexing, envelopes and validation unchanged'}
    binding=OUT/'scheduler-v2-binding.json'
    if binding.exists(): assert json.loads(binding.read_bytes())==scheduler
    else: save(binding,scheduler)
    lock=OUT/'RUNNING.lock'
    with lock.open('xb') as f: f.write(encode({'pid':os.getpid(),'argv':sys.argv,**scheduler}))
    start=time.monotonic(); completed=0; last_update=-2.0
    # Startup is idle: no scientific worker is writing these files yet.
    measurements={p.stem:read_progress(p) for p in (OUT/'run-progress').glob('*.json')}
    def progress(state,active=(),force=False,**kw):
        nonlocal last_update
        now=time.monotonic()-start
        if not force and now-last_update<1: return
        computed=sum(x['state'].startswith('computed') for x in measurements.values())
        reused=sum(x['state']=='computed-reused-O' for x in measurements.values())
        requests=sum(x['completed_requests'] for x in measurements.values() if x['state']!='computed-reused-O')
        checked=len(list((OUT/'run-verification').glob('*.json')))
        value={'state':state,'unique_units_computed':computed,'unique_units_total':catalog['unique_units'],
            'unit_percent':round(computed/catalog['unique_units']*100,3),'optimized_reuses':reused,
            'new_requests_checkpointed':requests,'new_requests_total':catalog['new_requests'],
            'request_percent':round(requests/catalog['new_requests']*100,3),'active_units':list(active),'workers':args.workers,
            'elapsed_seconds_this_invocation':round(now,3),'scheduler':'v2-segment-dispatch-no-active-progress-read','separate_replay':'full-stage-not-started','statistical_analysis':'not_started',**kw}
        publish_progress(OUT/'progress.json',encode(value))
        report=f'''# S5 实时进度

当前阶段：U 初态补充计算；状态：{state}；计算进程：{args.workers}。

| 阶段 | 已完成 / 总量 | 比例 |
|---|---:|---:|
| 输入准备及单独重建 | 480 / 480 父图 | 100% |
| 唯一 U 臂运行（含精确 O 复用） | {computed} / {catalog['unique_units']} | {computed/catalog['unique_units']*100:.2f}% |
| 新模拟请求已保存断点 | {requests} / {catalog['new_requests']} | {requests/catalog['new_requests']*100:.2f}% |
| 单独重放已核验运行 | {checked} / {catalog['unique_units']} | {checked/catalog['unique_units']*100:.2f}% |
| 配对统计及图表 | 尚未开始 | — |

已复用 {reused} 个输入完全相同的 O 见证。当前单元：{', '.join(str(x)[:12] for x in active) or '无'}。
本次调用用时 {now:.0f} 秒，不包含之前已保存断点的运行时间。

暂停请让我创建本目录 PAUSE 文件；最多100请求的小段写入后退出。科学 worker/票据/段见证仍使用冻结 v1，不因调度器修复重算已保存段。
阶段比例不代表论文总体进度；计算完成仍需单独重放及四臂统计，补充研究不等于新盲确认。
'''
        publish_progress(OUT/'progress.md',report.encode('utf-8')); last_update=now
    try:
        pending=deque(selected); active={}; invocation_chunks={}
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            while active or pending:
                if (OUT/'PAUSE').exists(): pending.clear()
                while pending and len(active)<args.workers:
                    row=pending.popleft()
                    active[pool.submit(execute_record,row,context,1)]=row
                try:
                    progress('pausing' if (OUT/'PAUSE').exists() else 'running',[r['unit_id'] for r in active.values()])
                    if not active: break
                    done,_=wait(active,timeout=5,return_when=FIRST_COMPLETED)
                    for future in done:
                        row=active.pop(future); uid=row['unit_id']; record=future.result(); completed+=int(record['state']=='computed')
                        # The future has returned and closed its file handles. This
                        # unit is not dispatched again until the read is complete.
                        measurements[uid]=read_progress(OUT/'run-progress'/(uid+'.json'))
                        invocation_chunks[uid]=invocation_chunks.get(uid,0)+record['new_chunks']
                        save(OUT/'execution-receipts'/(uid+'.json'),record); print(json.dumps(record),flush=True)
                        limit=args.stop_after_chunks
                        if record['state']=='paused-safe-checkpoint' and not (OUT/'PAUSE').exists() and (limit is None or invocation_chunks[uid]<limit):
                            pending.appendleft(row)
                except BaseException as exc:
                    save(OUT/'PAUSE',{'reason':'scheduler-v2-error','error':repr(exc)}); raise
        progress('paused-safe-checkpoint' if (OUT/'PAUSE').exists() or args.stop_after_chunks is not None else
            'selected-batch-computed-pending-separate-replay' if args.unit or args.maximum_units is not None else 'computed-pending-separate-replay',
            force=True,completed_this_invocation=completed)
    except BaseException as exc:
        save(OUT/'PAUSE',{'reason':'scheduler-v2-error','error':repr(exc)})
        progress('stopped-on-error',force=True,error=repr(exc)); raise
    finally: lock.unlink()

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--workers',type=int,default=2); p.add_argument('--unit',action='append')
    p.add_argument('--maximum-units',type=int); p.add_argument('--stop-after-chunks',type=int); run(p.parse_args())
