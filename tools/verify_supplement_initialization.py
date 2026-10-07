"""S5 separate saved-input reconstruction and common-ticket chunk replay, without executor imports."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
import time
from tools.supplement_initialization_common import ROOT,OUT,CONFIG,sha,encode,save,store,load,core_snapshot,runtime,config,state_object,atomic
from secondaryexploration.model import PaymentRequest
from secondaryexploration.experiments.paired import route_choice_rng
from secondaryexploration.experiments.pipeline import _simulation_payload
from secondaryexploration.simulation import run_core_trace_with_request_rngs

def manual_uniform(nodes,edges,budget):
    incident={n:[] for n in nodes}; allocations={e:{} for e,m in edges}
    for e,members in edges:
        for node in members: incident[node].append(e)
    for node,edge_ids in incident.items():
        assert edge_ids and budget>=len(edge_ids)
        q,r=divmod(budget,len(edge_ids))
        for index,edge in enumerate(sorted(edge_ids)): allocations[edge][node]=q+int(index<r)
    return [[e,[[n,allocations[e][n]] for n in sorted(allocations[e])]] for e in sorted(allocations)]

def verify_parent(row,cfg):
    p,phash=load(OUT/row['path']); assert phash==row['payload_sha256']; parent=p['parent']
    rawpath=ROOT/f"outputs/{parent['phase']}/synthetic-{parent['phase']}-v1/blocks/{parent['parent_graph_id']}.json"
    assert rawpath.resolve().is_relative_to((ROOT/f"outputs/{parent['phase']}/synthetic-{parent['phase']}-v1/blocks").resolve())
    raw=rawpath.read_bytes(); assert sha(raw)==parent['raw_sha256'] and len(raw)==parent['raw_bytes']; a=json.loads(raw)
    assert a['artifact_fingerprint']==parent['artifact_fingerprint'] and a['result_fingerprint']==parent['result_fingerprint']
    assert a['code_revision']==cfg['source_code_revision']
    variants={v[0]:v for v in a['result_witness']['variants']}; oldruns={r[0]:r for r in a['result_witness']['held_out']}
    assert len(parent['traces'])==7 and {t['regime_id'] for t in parent['traces']}==set(oldruns)
    for trace in parent['traces']:
        r=oldruns[trace['regime_id']]; sims=dict(r[4]); requests=[v[1] for v in sims['fhs5'][1]]
        assert r[3]==trace['paired_manifest_fingerprint'] and r[2][6]==trace['trace_seed']['routing_root_seed']
        assert len(requests)==12*parent['node_count']
        for family in cfg['families']:
            nodes,edges=variants[family][2]; ustate=manual_uniform(nodes,edges,120)
            assert parent['nodes']==nodes and parent['variants'][family]['topology']==edges and parent['variants'][family]['uniform_initial_state']==ustate
            uid=trace['uniform_units'][family]; unit,_=load(OUT/'inputs'/(uid+'.json.gz'))
            expected={'nodes':nodes,'initial_state':ustate,'requests':requests,'routing_root_seed':r[2][6]}
            assert unit['spec']==expected and sha(encode(expected))==uid
            optimized=trace['optimized'][family]; assert optimized['initial_state']==sims[family][0] and optimized['simulation_witness_sha256']==sha(encode(sims[family]))
            assert [o[1] for o in sims[family][1]]==requests
            for name,col in [('tau_dep',3),('tau_nopath',4),('tau_rej',5)]:
                assert optimized['events'][name]=={'observed':sims[family][col][0],'request_index':sims[family][col][1]}
            if unit['reuse_optimized_family'] is not None:
                assert sims[unit['reuse_optimized_family']][0]==ustate
    return {'status':'passed-input-reconstruction','parent_payload_sha256':phash,'raw_sha256':parent['raw_sha256'],
            'unit_payload_sha256':{uid:load(OUT/'inputs'/(uid+'.json.gz'))[1] for uid in p['units']}}

def replay_unit(row,context):
    uid=row['unit_id']; unit,uhash=load(OUT/row['path']); assert uhash==row['payload_sha256']
    result_path=OUT/'runs'/uid/'result.json.gz'; result,rhash=load(result_path); assert result['unit_id']==uid and result['context']==context
    s=unit['spec']; H=len(s['requests']); assert H==row['horizon']
    if unit['reuse_optimized_family'] is not None:
        ref=unit['reference']; parent,_=load(OUT/'parents'/f"{ref['phase']}-{ref['parent_graph_id']}.json.gz")
        tr=next(t for t in parent['parent']['traces'] if t['regime_id']==ref['regime_id']); opt=tr['optimized'][unit['reuse_optimized_family']]
        assert opt['initial_state']==s['initial_state'] and result['summary']==opt['summary'] and result['source_simulation_witness_sha256']==opt['simulation_witness_sha256']
        return {'status':'passed-existing-O-reuse','result_payload_sha256':rhash,'unit_payload_sha256':uhash,'chunks':0,'new_requests_replayed':0}
    offset=0; state=s['initial_state']; previous=None; first={'tau_dep':None,'tau_nopath':None,'tau_rej':None}; accepted=value=0
    costs={'traversed_hyperedge_count':0,'signaled_participant_slots':0,'quadratic_coordination_exposure':0,'unique_signaled_participants':0}; hist=Counter(); chunk_hashes=[]
    while offset<H:
        if (OUT/'PAUSE').exists(): return None
        path=OUT/'runs'/uid/'chunks'/f'{offset:06d}.json.gz'; chunk,chash=load(path); end=chunk['end']
        assert chunk['context']==context and chunk['unit_id']==uid and chunk['start']==offset and end==min(offset+context['chunk_requests'],H) and chunk['previous_sha256']==previous
        receipt=OUT/'replay-checkpoints'/uid/f'{offset:06d}.json'
        expected_receipt={'chunk_payload_sha256':chash,'unit_payload_sha256':uhash,'status':'passed-common-ticket-core-replay'}
        if receipt.exists(): assert json.loads(receipt.read_bytes())==expected_receipt
        else:
            simulation=run_core_trace_with_request_rngs(state_object(s['nodes'],state),tuple(PaymentRequest(*q) for q in s['requests'][offset:end]),
                         (route_choice_rng(s['routing_root_seed'],i+1) for i in range(offset,end)))
            assert json.loads(encode(_simulation_payload(simulation)))==chunk['simulation']
            save(receipt,expected_receipt)
        sim=chunk['simulation']; assert sim[0]==state and [o[1] for o in sim[1]]==s['requests'][offset:end]
        assert [o[0] for o in sim[1]]==list(range(1,end-offset+1))
        edge_members={e:set(n for n,b in balances) for e,balances in state}
        for outcome in sim[1]:
            if outcome[2] is None: continue
            accepted+=1; value+=outcome[1][2]; participants=set()
            for eid,payer,payee in outcome[2]:
                members=edge_members[eid]; assert payer in members and payee in members
                arity=len(members); participants.update(members); hist[arity]+=1
                costs['traversed_hyperedge_count']+=1; costs['signaled_participant_slots']+=arity; costs['quadratic_coordination_exposure']+=arity*arity
            costs['unique_signaled_participants']+=len(participants)
        for name,col in [('tau_dep',3),('tau_nopath',4),('tau_rej',5)]:
            flag,t=sim[col]
            if first[name] is None and flag: first[name]=offset+t
        prefix={'completed_requests':end,'accepted_request_count':accepted,'accepted_value':value,'first_events':first,
                'costs':costs,'route_arity_histogram':[[k,hist[k]] for k in sorted(hist)]}
        assert prefix==chunk['prefix']; state=sim[2]; previous=chash; offset=end; chunk_hashes.append(chash)
    summary={'horizon':H,'initial_state_sha256':sha(encode(s['initial_state'])),'final_state_sha256':sha(encode(state)),
        'accepted_request_count':accepted,'accepted_value':value,'dynamic_costs':{**costs,'route_arity_histogram':[[k,hist[k]] for k in sorted(hist)]}}
    for name,t in first.items(): summary[name]={'observed':t is not None,'request_index':H if t is None else t}
    assert result['summary']==summary and result['final_state']==state and result['last_chunk_sha256']==previous
    return {'status':'passed-separate-common-ticket-replay','result_payload_sha256':rhash,'unit_payload_sha256':uhash,
            'chunks':len(chunk_hashes),'chunk_payload_sha256':chunk_hashes,'new_requests_replayed':H}

def run(args):
    cfg=config(); raw=(OUT/'catalogue.json').read_bytes(); catalog=json.loads(raw); core=core_snapshot()
    assert catalog['binding']['core_snapshot']==core and catalog['binding']['config_sha256']==sha(CONFIG.read_bytes()) and catalog['binding']['runtime']==runtime()
    context=None if args.inputs_only else json.loads((OUT/'executor-binding.json').read_bytes())
    if context is not None:
        assert context['catalogue_sha256']==sha(raw) and context['core_snapshot']==core and context['config_sha256']==sha(CONFIG.read_bytes())
        assert context['executor_sha256']==sha((ROOT/'tools/run_supplement_initialization.py').read_bytes())
    binding={'checker_sha256':sha(Path(__file__).read_bytes()),'catalogue_sha256':sha(raw),'config_sha256':sha(CONFIG.read_bytes()),'core_snapshot':core,'runtime':runtime()}
    bp=OUT/'replay-binding.json'
    if bp.exists(): assert json.loads(bp.read_bytes())==binding
    else: save(bp,binding)
    lock=OUT/'VERIFYING.lock'
    with lock.open('xb') as f: f.write(encode({'pid':os.getpid(),'argv':sys.argv}))
    parents=units=0; start=time.monotonic()
    def status(state,**kw):
        save(OUT/'replay-progress.json',{'state':state,'inputs_verified':parents,'total_inputs':480,'input_percent':round(parents/480*100,3),
            'units_verified':units,'total_units':catalog['unique_units'],'unit_percent':round(units/catalog['unique_units']*100,3),'elapsed_seconds_this_invocation':round(time.monotonic()-start,3),**kw})
        if not args.inputs_only:
            atomic(OUT/'progress.md',f'''# S5 实时进度

当前阶段：单独重放核验；状态：{state}。

| 阶段 | 已完成 / 总量 | 比例 |
|---|---:|---:|
| 输入准备 | 480 / 480父图 | 100% |
| 单独输入重建 | {parents} / 480父图 | {parents/480*100:.2f}% |
| 单独公共票据重放 | {units} / {catalog['unique_units']}唯一运行 | {units/catalog['unique_units']*100:.2f}% |
| 统计及图表 | 尚未开始 | — |

单独重放不等于新增独立科学盲审；只校验保存输入、U分配、票据、路径、状态和汇总的执行一致性。四臂推断尚未完成。

暂停仍通过本目录PAUSE文件，在最多100请求的重放段后退出并保留已通过段的收据。
'''.encode('utf-8'))
    try:
        for row in catalog['parents']:
            path=OUT/'input-verification'/f"{row['phase']}-{row['parent_graph_id']}.json"
            if path.exists():
                proof=json.loads(path.read_bytes()); assert proof['parent_payload_sha256']==row['payload_sha256']
                for uid,h in proof['unit_payload_sha256'].items(): assert load(OUT/'inputs'/(uid+'.json.gz'))[1]==h
            else:
                status('verifying-saved-inputs',phase=row['phase'],parent_graph_id=row['parent_graph_id']); save(path,verify_parent(row,cfg))
            parents+=1
            if (OUT/'PAUSE').exists(): status('paused-safe-checkpoint'); return
        if args.inputs_only:
            save(OUT/'input-verification.json',{'status':'passed','parents':480,'binding':binding,'method':'Separate reconstruction from byte-bound raw topology/requests/tickets, manual integer U allocation, O witness identity.'})
            status('inputs-passed'); return
        selected=[r for r in catalog['units'] if not args.unit or r['unit_id'] in args.unit]
        if args.unit: assert len(selected)==len(set(args.unit))
        if args.maximum_units is not None: selected=selected[:args.maximum_units]
        for row in selected:
            path=OUT/'run-verification'/(row['unit_id']+'.json'); result_path=OUT/'runs'/row['unit_id']/'result.json.gz'
            if not result_path.exists(): status('waiting-for-generation',unit_id=row['unit_id']); return
            if path.exists():
                proof=json.loads(path.read_bytes()); assert proof['result_payload_sha256']==load(result_path)[1] and proof['unit_payload_sha256']==load(OUT/row['path'])[1]
                for i,h in enumerate(proof.get('chunk_payload_sha256',[])): assert load(OUT/'runs'/row['unit_id']/'chunks'/f"{i*context['chunk_requests']:06d}.json.gz")[1]==h
            else:
                status('replaying-new-uniform-run',unit_id=row['unit_id']); proof=replay_unit(row,context)
                if proof is None: status('paused-safe-checkpoint'); return
                save(path,proof)
            units+=1
        status('selected-replay-passed' if args.unit or args.maximum_units is not None else 'all-replay-passed')
        if not args.unit and args.maximum_units is None:
            save(OUT/'verification.json',{'status':'passed','binding':binding,'parents_verified':480,'unique_units_verified':units,
                 'new_requests_replayed':catalog['new_requests'],'scope':'Same-analyst separate input reconstruction and execution replay, not blinded scientific review; analysis remains pending.'})
    except BaseException as exc: status('stopped-on-error',error=repr(exc)); raise
    finally: lock.unlink()

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--inputs-only',action='store_true'); p.add_argument('--unit',action='append'); p.add_argument('--maximum-units',type=int); run(p.parse_args())
