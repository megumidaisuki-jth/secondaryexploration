"""Bounded two-process S5 executor using unchanged validated core, <=100-request checkpoints."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
import json
import os
from pathlib import Path
import sys
import time
from tools.supplement_initialization_common import (ROOT,OUT,CONFIG,encode,sha,save,store,load,state_object,core_snapshot,runtime,config)
from secondaryexploration.model import PaymentRequest
from secondaryexploration.experiments.paired import route_choice_rng
from secondaryexploration.simulation import run_core_trace_with_request_rngs
from secondaryexploration.experiments.pipeline import _simulation_payload

def simulate(nodes,state,requests,routing_seed,offset):
    sim=run_core_trace_with_request_rngs(state_object(nodes,state),tuple(PaymentRequest(*q) for q in requests),
        (route_choice_rng(routing_seed,offset+i+1) for i in range(len(requests))))
    return json.loads(encode(_simulation_payload(sim)))

def merge(prefix,simulation,offset,nodes):
    if prefix is None:
        prefix={'completed_requests':0,'accepted_request_count':0,'accepted_value':0,
                'first_events':{'tau_dep':None,'tau_nopath':None,'tau_rej':None},
                'costs':{'traversed_hyperedge_count':0,'signaled_participant_slots':0,'unique_signaled_participants':0,'quadratic_coordination_exposure':0},
                'route_arity_histogram':[]}
    assert prefix['completed_requests']==offset
    result=json.loads(encode(prefix)); members={e:set(n for n,_ in balances) for e,balances in simulation[0]}
    hist=Counter(dict(prefix['route_arity_histogram']))
    for index,outcome in enumerate(simulation[1],start=1):
        assert outcome[0]==index
        route=outcome[2]
        if route is None: continue
        result['accepted_request_count']+=1; result['accepted_value']+=outcome[1][2]
        unique=set()
        for edge,_,_ in route:
            arity=len(members[edge]); hist[arity]+=1; unique.update(members[edge])
            result['costs']['traversed_hyperedge_count']+=1
            result['costs']['signaled_participant_slots']+=arity
            result['costs']['quadratic_coordination_exposure']+=arity*arity
        result['costs']['unique_signaled_participants']+=len(unique)
    result['route_arity_histogram']=[[k,hist[k]] for k in sorted(hist)]
    result['completed_requests']=offset+len(simulation[1])
    for name,j in [('tau_dep',3),('tau_nopath',4),('tau_rej',5)]:
        flag,t=simulation[j]
        assert type(flag) is bool and type(t) is int and 0<=t<=len(simulation[1])
        assert flag or t==len(simulation[1])
        if result['first_events'][name] is None and flag:
            assert t>0 or offset==0
            result['first_events'][name]=offset+t
    return result

def execute_record(row,context,max_new_chunks=None,out=OUT):
    out=Path(out); uid=row['unit_id']; unit,unit_hash=load(out/row['path'])
    assert unit_hash==row['payload_sha256'] and sha(encode(unit['spec']))==uid
    spec=unit['spec']; H=len(spec['requests']); assert H==row['horizon']
    result_path=out/'runs'/uid/'result.json.gz'; current=out/'run-progress'/(uid+'.json')
    if result_path.exists():
        saved,_=load(result_path); assert saved['context']==context and saved['unit_id']==uid
        save(current,{'state':'computed-reused-O' if saved['method']=='reused-byte-bound-optimized-witness' else 'computed-pending-separate-replay',
                      'completed_requests':H,'horizon':H,'percent':100,'pid':os.getpid()})
        return {'unit_id':uid,'state':'computed','new_chunks':0,'seconds':0.0}
    began=time.monotonic()
    if unit['reuse_optimized_family'] is not None:
        ref=unit['reference']; parent,_=load(out/'parents'/f"{ref['phase']}-{ref['parent_graph_id']}.json.gz")
        trace=next(t for t in parent['parent']['traces'] if t['regime_id']==ref['regime_id']); family=unit['reuse_optimized_family']; opt=trace['optimized'][family]
        assert opt['initial_state']==spec['initial_state']
        value={'context':context,'unit_id':uid,'method':'reused-byte-bound-optimized-witness','source':ref,'optimized_family':family,
               'source_simulation_witness_sha256':opt['simulation_witness_sha256'],'summary':opt['summary'],'audited_S3_cost':opt['audited_S3_cost']}
        store(result_path,value); save(current,{'state':'computed-reused-O','completed_requests':H,'horizon':H,'percent':100,'pid':os.getpid()})
        return {'unit_id':uid,'state':'computed','new_chunks':0,'seconds':round(time.monotonic()-began,3)}
    offset=0; initial=spec['initial_state']; prefix=None; previous=None; new_chunks=0
    while offset<H:
        end=min(offset+context['chunk_requests'],H); path=out/'runs'/uid/'chunks'/f'{offset:06d}.json.gz'
        if path.exists():
            chunk,chash=load(path)
            assert chunk['context']==context and chunk['unit_id']==uid and chunk['start']==offset and chunk['end']==end and chunk['previous_sha256']==previous
            simulation=chunk['simulation']; assert simulation[0]==initial and len(simulation[1])==end-offset
            assert [x[1] for x in simulation[1]]==spec['requests'][offset:end]
            expected=merge(prefix,simulation,offset,spec['nodes']); assert expected==chunk['prefix']
        else:
            if (out/'PAUSE').exists():
                save(current,{'state':'paused-safe-checkpoint','completed_requests':offset,'horizon':H,'percent':round(offset/H*100,3),'pid':os.getpid()})
                return {'unit_id':uid,'state':'paused-safe-checkpoint','new_chunks':new_chunks,'seconds':round(time.monotonic()-began,3)}
            started=time.monotonic(); simulation=simulate(spec['nodes'],initial,spec['requests'][offset:end],spec['routing_root_seed'],offset)
            assert simulation[0]==initial
            expected=merge(prefix,simulation,offset,spec['nodes'])
            chunk={'context':context,'unit_id':uid,'start':offset,'end':end,'previous_sha256':previous,
                   'simulation':simulation,'prefix':expected,'generation_seconds':round(time.monotonic()-started,6),
                   'validation':'Frozen CoreSimulationResult internal full-search/state replay; pending separate common-ticket replay'}
            chash=store(path,chunk); new_chunks+=1
        prefix=expected; initial=simulation[2]; offset=end; previous=chash
        save(current,{'state':'chunk-checkpoint','completed_requests':offset,'horizon':H,'percent':round(offset/H*100,3),'last_chunk_sha256':previous,'pid':os.getpid(),
                      'elapsed_seconds_this_invocation':round(time.monotonic()-began,3)})
        if max_new_chunks is not None and new_chunks>=max_new_chunks and offset<H:
            save(current,{'state':'paused-safe-checkpoint','completed_requests':offset,'horizon':H,'percent':round(offset/H*100,3),'pid':os.getpid()})
            return {'unit_id':uid,'state':'paused-safe-checkpoint','new_chunks':new_chunks,'seconds':round(time.monotonic()-began,3)}
    summary={'horizon':H,'initial_state_sha256':sha(encode(spec['initial_state'])),'final_state_sha256':sha(encode(initial)),
             'accepted_request_count':prefix['accepted_request_count'],'accepted_value':prefix['accepted_value'],
             'dynamic_costs':{**prefix['costs'],'route_arity_histogram':prefix['route_arity_histogram']}}
    for name,index in prefix['first_events'].items(): summary[name]={'observed':index is not None,'request_index':H if index is None else index}
    store(result_path,{'context':context,'unit_id':uid,'method':'new-uniform-simulation','summary':summary,'final_state':initial,'last_chunk_sha256':previous,
                      'generated_seconds_this_invocation':round(time.monotonic()-began,3),'separate_replay_status':'pending'})
    save(current,{'state':'computed-pending-separate-replay','completed_requests':H,'horizon':H,'percent':100,'pid':os.getpid()})
    return {'unit_id':uid,'state':'computed','new_chunks':new_chunks,'seconds':round(time.monotonic()-began,3)}

def execution_context():
    cfg=config(); raw=(OUT/'catalogue.json').read_bytes(); catalog=json.loads(raw)
    preparation=json.loads((OUT/'preparation-binding.json').read_bytes())
    assert preparation==catalog['binding'] and preparation['core_snapshot']==core_snapshot() and preparation['runtime']==runtime()
    assert preparation['config_sha256']==sha(CONFIG.read_bytes()) and preparation['common_sha256']==sha((ROOT/'tools/supplement_initialization_common.py').read_bytes())
    assert preparation['preparer_sha256']==sha((ROOT/'tools/prepare_supplement_initialization.py').read_bytes())
    context={'schema':'S5-chunk-execution-v1','config_sha256':sha(CONFIG.read_bytes()),'catalogue_sha256':sha(raw),
        'executor_sha256':sha(Path(__file__).read_bytes()),'common_sha256':preparation['common_sha256'],
        'core_snapshot':preparation['core_snapshot'],'runtime':runtime(),'chunk_requests':cfg['chunk_requests']}
    path=OUT/'executor-binding.json'
    if path.exists(): assert json.loads(path.read_bytes())==context
    else: save(path,context)
    return context,catalog

def run(args):
    context,catalog=execution_context(); cfg=config()
    assert 1<=args.workers<=cfg['maximum_workers']
    if args.unit:
        selected=[r for r in catalog['units'] if r['unit_id'] in args.unit]; assert len(selected)==len(set(args.unit))
    else: selected=catalog['units']
    if args.maximum_units is not None: selected=selected[:args.maximum_units]
    lock=OUT/'RUNNING.lock'
    with lock.open('xb') as f: f.write(encode({'pid':os.getpid(),'argv':sys.argv,'context_sha256':sha(encode(context))}))
    started=time.monotonic(); completed_invocation=0
    def progress(state,active=(),**kw):
        measurements=[]
        for p in (OUT/'run-progress').glob('*.json') if (OUT/'run-progress').exists() else []:
            item=json.loads(p.read_bytes()); measurements.append(item)
        computed=sum(x['state'].startswith('computed') for x in measurements)
        reused=sum(x['state']=='computed-reused-O' for x in measurements)
        new_requests=sum(x['completed_requests'] for x in measurements if x['state']!='computed-reused-O')
        save(OUT/'progress.json',{'state':state,'unique_units_computed':computed,'unique_units_total':catalog['unique_units'],
            'unit_percent':round(computed/catalog['unique_units']*100,3),'optimized_reuses':reused,
            'new_requests_checkpointed':new_requests,'new_requests_total':catalog['new_requests'],
            'request_percent':round(new_requests/catalog['new_requests']*100,3) if catalog['new_requests'] else 100,
            'active_units':list(active),'workers':args.workers,'elapsed_seconds_this_invocation':round(time.monotonic()-started,3),
            'separate_replay':'not_started','statistical_analysis':'not_started',**kw})
        checked=len(list((OUT/'run-verification').glob('*.json'))) if (OUT/'run-verification').exists() else 0
        text=f'''# S5 实时进度

状态：{state}；计算进程：{args.workers}；本次运行已用时：{round(time.monotonic()-started)} 秒。

| 阶段 | 已完成 / 总量 | 进度 |
|---|---:|---:|
| 原始输入准备 | 480 / 480 父图 | 100% |
| 唯一四臂补充运行 | {computed} / {catalog['unique_units']} | {computed/catalog['unique_units']*100:.2f}% |
| 新模拟请求断点 | {new_requests} / {catalog['new_requests']} | {(new_requests/catalog['new_requests']*100 if catalog['new_requests'] else 100):.2f}% |
| 单独实现重放核验 | {checked} / {catalog['unique_units']} | {checked/catalog['unique_units']*100:.2f}% |
| 配对统计及图表 | 尚未开始 | — |

已复用 {reused} 个输入完全相同的原O运行；缓存不算新增模拟。6720个逻辑U臂保留完整映射，不是6720个独立父图。

当前工作单元：{', '.join(str(u)[:12] for u in active) or '无'}。

暂停：请让我创建本目录的PAUSE控制文件；两个进程当前最多100请求的小段写入成功后退出。不要直接删除运行锁。恢复时保留源码/参数/运行时，已保存小段不重新计算。

比例按各阶段真实工作量分别报告，不代表论文总体完成率。数据仍属事后补充，计算完成也必须通过单独重放与统计核验后才能引用。
'''
        __import__('tools.supplement_initialization_common',fromlist=['atomic']).atomic(OUT/'progress.md',text.encode('utf-8'))
    try:
        pending=iter(selected); active={}; exhausted=False
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            while active or not exhausted:
                if (OUT/'PAUSE').exists(): exhausted=True
                while not exhausted and len(active)<args.workers:
                    try: row=next(pending)
                    except StopIteration: exhausted=True; break
                    future=pool.submit(execute_record,row,context,args.stop_after_chunks); active[future]=row['unit_id']
                progress('running' if not (OUT/'PAUSE').exists() else 'pausing',active.values())
                if not active: break
                done,_=wait(active,timeout=5,return_when=FIRST_COMPLETED)
                for future in done:
                    uid=active.pop(future)
                    try: record=future.result()
                    except BaseException as exc:
                        save(OUT/'PAUSE',{'reason':'worker-error','unit_id':uid,'error':repr(exc)}); raise
                    completed_invocation+=int(record['state']=='computed')
                    save(OUT/'execution-receipts'/(uid+'.json'),record); print(json.dumps(record),flush=True)
            progress('paused-safe-checkpoint' if (OUT/'PAUSE').exists() or args.stop_after_chunks is not None else
                     'selected-batch-computed-pending-separate-replay' if args.unit or args.maximum_units is not None else 'computed-pending-separate-replay',
                     completed_this_invocation=completed_invocation)
    except BaseException as exc:
        save(OUT/'PAUSE',{'reason':'executor-error','error':repr(exc)})
        progress('stopped-on-error',error=repr(exc)); raise
    finally: lock.unlink()

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--workers',type=int,default=2); p.add_argument('--unit',action='append')
    p.add_argument('--maximum-units',type=int); p.add_argument('--stop-after-chunks',type=int); run(p.parse_args())
