"""Frozen stage A: all-input preflight -> training -> selection -> held-out runs.

Two bounded workers, immutable 50-request chunks, OS lease and fail-closed resume.
Never changes engineering outputs or the existing frozen simulation core.
"""
from __future__ import annotations

import argparse
import gzip
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from fractions import Fraction
from functools import lru_cache
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

from tools import structure_robustness_engineering as eng
from tools.supplement_initialization_common import ROOT, encode, sha, save, store, load, atomic, uniform, spec, core_snapshot, runtime
from tools.run_supplement_initialization import simulate, merge
from tools.verify_supplement_initialization import manual_uniform
from secondaryexploration.topology import fixed_hyperedge_size, ParentGraph
from secondaryexploration.topology.random_graphs import matched_synthetic_parent_graphs
from secondaryexploration.experiments.study import load_study_design_manifest, build_study_seed_ledger, generate_declared_parent_ensemble

CONFIG=ROOT/'configs/supplement/structure-robustness-A-v1.json'
CANDIDATES=['b0','random0','random1','random2','random3','random4','volume','reciprocity']


def atomic(path,data):
    """Windows readers may briefly deny replacement; keep old file and retry."""
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+f'.{os.getpid()}.{uuid.uuid4().hex}.tmp')
    with tmp.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    deadline=time.monotonic()+10
    while True:
        try:
            os.replace(tmp,path); return
        except PermissionError:
            if time.monotonic()>=deadline: raise
            time.sleep(.05)


def save(path,value): atomic(path,encode(value))


def store(path,payload):
    digest=sha(encode(payload))
    atomic(path,gzip.compress(encode({'payload':payload,'payload_sha256':digest}),mtime=0))
    return digest


def read_json(path):
    deadline=time.monotonic()+10
    while True:
        try: return json.loads(path.read_bytes())
        except PermissionError:
            if time.monotonic()>=deadline: raise
            time.sleep(.05)


def config(): return json.loads(CONFIG.read_bytes())


def context_for(cfg):
    files=[CONFIG, Path(__file__), ROOT/'tools/preflight_structure_robustness_A.py',
           ROOT/'tools/structure_robustness_engineering.py', ROOT/'tools/supplement_initialization_common.py',
           ROOT/'tools/run_supplement_initialization.py', ROOT/'tools/verify_supplement_initialization.py',
           ROOT/'tests/test_structure_robustness_A.py', ROOT/cfg['parameter_source'], ROOT/cfg['design_source'],
           ROOT/cfg['preflight_report']]
    return {'schema':'structure-A-execution.v1','files':{p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in files},
            'core':core_snapshot(),'runtime':runtime(),'python_executable':sys.executable,
            'chunk_requests':cfg['chunk_requests'],'horizon':cfg['horizon']}


def immutable_json(path,value):
    if path.exists():
        assert json.loads(path.read_bytes())==value, f'Immutable record mismatch: {path}'
    else: save(path,value)


def set_status(out,state,**fields):
    path=out/'progress.json'; value=read_json(path) if path.exists() else {}
    value.update(fields); value.update(state=state,pid=os.getpid(),updated_utc=eng.now(),module='A',
                                     paper_results_permission='pending separate replay and frozen inference')
    save(path,value)
    atomic(out/'progress.md', ('# 结构稳健性补充实验 A：实时进度\n\n'
        f'状态：{state}；更新时间（UTC）：{value["updated_utc"]}。\n\n'
        f'输入父图：{value.get("prepared_parents",0)}/{value.get("total_parents",180)}。\n\n'
        f'当前阶段：{value.get("stage","preparation")}；工作进程：{value.get("workers",0)}。\n\n'
        f'当前阶段已保存请求：{value.get("checkpointed_requests",0)}/{value.get("stage_requests",0)}'
        f'（{value.get("request_percent",0):.3f}%）。\n\n'
        f'当前阶段完成轨迹：{value.get("completed_units",0)}/{value.get("stage_units",0)}。\n\n'
        '训练与测试进度分开计数；不是论文总体完成率。阶段完成后仍需独立重放及统计。\n\n'
        '暂停/恢复：`tools/structure-robustness-control.ps1 pause` / `resume`。'
        '每50请求提交原子断点；暂停时停止派发，等待当前小段保存后退出。'
        '输入准备按父图保存。不要删除运行锁或修改冻结代码。\n'
    ).encode('utf-8'))


def parent_specs(cfg):
    return [(n,rep,model) for n in cfg['node_counts'] for rep in range(cfg['replicates_per_model_per_size'])
            for model in ['er_gnm','barabasi_albert','sbm_fixed_count']]


def parent_id(n,rep,model): return f'n{n:04d}-r{rep:04d}-{model}'


@lru_cache(maxsize=4)
def manifest_at(path): return load_study_design_manifest(path)


def generate_parent(cfg,n,rep,model):
    manifest=manifest_at(str(ROOT/cfg['parameter_source'])); cell=manifest.size_cell(n)
    ns=cfg['seed_namespace']; key=parent_id(n,rep,model)
    ensemble=matched_synthetic_parent_graphs(node_count=n,attachment_count=cell.attachment_count,
        block_count=cell.block_count,sbm_within_edge_count=cell.sbm_within_edge_count,
        base_seed=eng.seed(ns,'parents',n,rep),replicate_index=0,max_attempts=1000)
    draw=next(d for d in ensemble.draws if d.model.value==model); graph=draw.graph
    training={rid:{'requests':eng.requests_for(manifest,cell,manifest.regime(rid),ns,key,cfg['horizon']),
                   'routing_root_seed':eng.seed(ns,key,'routing',rid)} for rid in cfg['training_regimes']}
    test={rid:{'requests':eng.requests_for(manifest,cell,manifest.regime(rid),ns,key,cfg['horizon']),
               'routing_root_seed':eng.seed(ns,key,'routing',rid)} for rid in cfg['test_regimes']}
    families={}; structure_report={}
    for family in cfg['families']:
        source=fixed_hyperedge_size(graph,int(family[-1])); L=source.resources.incidence_count
        candidates=eng.candidate_topologies(graph,source,ns,[key,family],[training[r]['requests'] for r in cfg['training_regimes']])
        assert list(candidates)==CANDIDATES
        tops={'source':[source],**candidates}; states={}; degrees=[]
        for name,brackets in tops.items():
            states[name]=[]
            for top in brackets:
                edges=eng.topology_payload(top)
                state=uniform(list(graph.nodes),edges,cfg['per_node_capital'])
                assert state==manual_uniform(list(graph.nodes),edges,cfg['per_node_capital'])
                assert top.is_connected
                if name!='source': assert all(len(members)==2 for _,members in edges)
                states[name].append(state)
                degrees.append(max(Counter(node for _,b in state for node,_ in b).values()))
            if name!='source':
                counts=[sum(len(b) for _,b in s) for s in states[name]]
                assert counts==([L] if L%2==0 else [L-1,L+1])
        families[family]=states
        structure_report[family]={'source_incidence':L,'max_degree_all_candidates':max(degrees),
                                  'budget60_feasible_all_candidates':max(degrees)<=60}
    return {'parent_id':key,'node_count':n,'model':model,'replicate':rep,'nodes':list(graph.nodes),
            'parent_edges':[list(edge.endpoints) for edge in graph.edges],
            'draw_root_seed':draw.root_seed,'accepted_attempt':draw.accepted_attempt,
            'training':training,'test':test,'families':families,'structure_report':structure_report}


def identity(nodes,edges): return sha(encode([list(nodes),[list(p) for p in edges]]))


def historical_identities(cfg,out):
    path=out/'historical-parent-identities.json'
    if path.exists(): return json.loads(path.read_bytes())
    identities={}
    for phase in ['formal','confirmation']:
        manifest=manifest_at(str(ROOT/f'configs/{phase}/synthetic-{phase}-v1.json'))
        for record in build_study_seed_ledger(manifest).parent_seeds:
            if record.node_count not in cfg['node_counts']: continue
            if (out/'PAUSE').exists(): return None
            ensemble=generate_declared_parent_ensemble(manifest,record)
            for draw in ensemble.draws:
                key=identity(draw.graph.nodes,[edge.endpoints for edge in draw.graph.edges])
                identities[key]=f'{phase}:{record.node_count}:{record.parent_replicate}:{draw.model.value}'
    engineering=ROOT/cfg['engineering_output']
    for path in sorted((engineering/'parents').glob('*.json.gz')):
        p,_=load(path); identities[identity(p['nodes'],p['parent_edges'])]='engineering:'+p['parent_id']
    immutable_json(out/'historical-parent-identities.json',identities)
    return identities


def comparison_registry(cfg):
    return [{'id':f'A-n{n}-{family}-{baseline}-{endpoint}','node_count':n,'family':family,'baseline':baseline,
             'endpoint':endpoint,'orientation':'H-B' if endpoint=='Y' else 'B-H','horizon':cfg['horizon'],
             'independent_unit':'parent','model_weights':[1,1,1],'regime_weights':[1]*7,
             'bonferroni_family_size':80,'bootstrap_replicates':200000}
            for n in cfg['node_counts'] for family in cfg['families']
            for baseline in cfg['test_baselines'] for endpoint in ['Y','F']]


def prepare(out,cfg,context):
    set_status(out,'preparing-inputs',stage='historical-identity-preflight',workers=0)
    old=historical_identities(cfg,out)
    if old is None: return None
    seen=set(); rows=[]; binding_hash=sha(encode(context)); total=len(parent_specs(cfg))
    for n,rep,model in parent_specs(cfg):
        if (out/'PAUSE').exists(): return None
        key=parent_id(n,rep,model); path=out/'parents'/(key+'.json.gz')
        set_status(out,'preparing-inputs',stage='preparation',active_parent=key,prepared_parents=len(rows),total_parents=total)
        if path.exists():
            saved,h=load(path); assert saved['binding_sha256']==binding_hash; parent=saved['parent']
        else:
            parent=generate_parent(cfg,n,rep,model)
            h=store(path,{'binding_sha256':binding_hash,'parent':parent})
        assert (parent['node_count'],parent['replicate'],parent['model'])==(n,rep,model)
        graph_id=identity(parent['nodes'],parent['parent_edges'])
        assert graph_id not in old and graph_id not in seen, 'Parent identity collision; do not silently redraw'
        seen.add(graph_id)
        rows.append({'parent_id':key,'path':path.relative_to(out).as_posix(),'payload_sha256':h,
                     'graph_identity':graph_id,'structure_report':parent['structure_report']})
    index={'binding_sha256':binding_hash,'parents':rows}
    immutable_json(out/'parent-index.json',index)
    immutable_json(out/'comparisons.json',comparison_registry(cfg))
    freeze={'schema':'structure-A-input-freeze.v1','context_sha256':binding_hash,
            'parent_index_sha256':sha((out/'parent-index.json').read_bytes()),
            'comparison_registry_sha256':sha((out/'comparisons.json').read_bytes()),
            'parent_count':len(rows),'historical_graphs_checked':len(old),
            'positive_balance_all_A_arms':True,'parent_collisions':0,
            'C1_budget60_infeasible_parent_count':sum(any(not r['budget60_feasible_all_candidates'] for r in p['structure_report'].values()) for p in rows),
            'C1_status':'metadata only; C requires separate freeze before execution',
            'training_and_test_inputs_bound_before_any_simulation':True}
    immutable_json(out/'input-freeze.json',freeze)
    set_status(out,'inputs-frozen',prepared_parents=len(rows),total_parents=total,active_parent=None)
    return index


def read_parent(out,row):
    saved,h=load(out/row['path']); assert h==row['payload_sha256']; return saved['parent']


def make_spec(parent,split,regime,family,arm,side):
    tr=parent[split][regime]
    return spec(parent['nodes'],parent['families'][family][arm][side],tr['requests'],tr['routing_root_seed'])


def make_catalog(out,index,cfg,stage,selections=None):
    unique={}; logical=[]
    for pr in index['parents']:
        if (out/'PAUSE').exists(): return None
        parent=read_parent(out,pr)
        for family in cfg['families']:
            if stage=='training': arms=[(c,c) for c in CANDIDATES]; regimes=cfg['training_regimes']
            else:
                chosen=selections[parent['parent_id']][family]['winner']
                arms=[('source','source'),('b0','b0'),('random0','random0'),('selected',chosen)]; regimes=cfg['test_regimes']
            for label,arm in arms:
                for regime in regimes:
                    for side in range(len(parent['families'][family][arm])):
                        s=make_spec(parent,stage,regime,family,arm,side); uid=sha(encode(s))
                        unique.setdefault(uid,{'unit_id':uid,'parent':pr,'split':stage,'regime':regime,
                             'family':family,'arm':arm,'side':side,'horizon':cfg['horizon']})
                        logical.append({'parent_id':parent['parent_id'],'family':family,'arm_label':label,
                                        'candidate':arm,'regime':regime,'side':side,'unit_id':uid})
    catalog={'stage':stage,'input_freeze_sha256':sha((out/'input-freeze.json').read_bytes()),
             'units':list(unique.values()),'logical':logical,'total_requests':len(unique)*cfg['horizon']}
    immutable_json(out/(stage+'-catalogue.json'),catalog)
    return catalog


def load_result(out,uid,context_hash):
    result,h=load(out/'runs'/uid/'result.json.gz')
    assert result['unit_id']==uid and result['context_sha256']==context_hash
    return result,h


def unit_execute(out_string,row,context,min_free_bytes,max_new_chunks=None):
    out=Path(out_string); uid=row['unit_id']; ch=sha(encode(context))
    parent=read_parent(out,row['parent']); s=make_spec(parent,row['split'],row['regime'],row['family'],row['arm'],row['side'])
    assert sha(encode(s))==uid and len(s['requests'])==row['horizon']
    directory=out/'runs'/uid; progress=out/'unit-progress'/(uid+'.json')
    result_path=directory/'result.json.gz'
    if result_path.exists():
        result,_=load_result(out,uid,ch)
        for item in result['chunk_files']:
            raw=(directory/'chunks'/item['file']).read_bytes()
            assert sha(raw)==item['file_sha256'], 'Stored completed chunk was modified'
        assert result['prefix']['completed_requests']==row['horizon']
        save(progress,{'completed_requests':row['horizon'],'state':'computed-pending-replay','updated_utc':eng.now()})
        return {'unit_id':uid,'complete':True,'reused':True}
    offset=0; H=row['horizon']; state=s['initial_state']; prefix=None; previous=None; chunk_files=[]; new=0
    while offset<H:
        if (out/'PAUSE').exists(): return {'unit_id':uid,'complete':False}
        end=min(offset+context['chunk_requests'],H); path=directory/'chunks'/f'{offset:06d}.json.gz'
        if path.exists():
            chunk,payload_hash=load(path)
            assert chunk['context_sha256']==ch and chunk['unit_id']==uid
            assert (chunk['start'],chunk['end'],chunk['previous_sha256'])==(offset,end,previous)
            sim=chunk['simulation']; assert sim[0]==state
            assert [x[0] for x in sim[1]]==list(range(1,end-offset+1))
            assert [x[1] for x in sim[1]]==s['requests'][offset:end]
            eng.check_arithmetic(sim); expected=merge(prefix,sim,offset,s['nodes']); assert expected==chunk['prefix']
        else:
            if max_new_chunks is not None and new>=max_new_chunks: return {'unit_id':uid,'complete':False}
            if shutil.disk_usage(out).free<min_free_bytes: raise RuntimeError('Disk reserve below threshold; pause safely')
            begin=time.monotonic(); sim=simulate(s['nodes'],state,s['requests'][offset:end],s['routing_root_seed'],offset)
            eng.check_arithmetic(sim); expected=merge(prefix,sim,offset,s['nodes'])
            chunk={'context_sha256':ch,'unit_id':uid,'start':offset,'end':end,'previous_sha256':previous,
                   'simulation':sim,'prefix':expected,'generation_seconds':time.monotonic()-begin}
            payload_hash=store(path,chunk); new+=1
        chunk_files.append({'file':path.name,'payload_sha256':payload_hash,'file_sha256':sha(path.read_bytes())})
        prefix=expected; state=sim[2]; previous=payload_hash; offset=end
        save(progress,{'completed_requests':offset,'state':'checkpoint','last_chunk_sha256':previous,'updated_utc':eng.now()})
    result={'context_sha256':ch,'unit_id':uid,'prefix':prefix,'final_state':state,'last_chunk_sha256':previous,
            'chunk_files':chunk_files,'status':'computed-pending-separate-replay','split':row['split']}
    store(result_path,result)
    save(progress,{'completed_requests':H,'state':'computed-pending-replay','updated_utc':eng.now()})
    return {'unit_id':uid,'complete':True,'reused':False}


def run_stage(out,catalog,cfg,context):
    rows=catalog['units']; stage=catalog['stage']; counters={}; done=set()
    for row in rows:
        path=out/'unit-progress'/(row['unit_id']+'.json')
        counters[row['unit_id']]=read_json(path)['completed_requests'] if path.exists() else 0
    active={}; cursor=iter(rows); exhausted=False; start=time.monotonic(); previous_count=sum(counters.values())
    with ProcessPoolExecutor(max_workers=cfg['workers']) as pool:
        try:
            while active or not exhausted:
                if (out/'PAUSE').exists(): exhausted=True
                while not exhausted and len(active)<cfg['workers']:
                    try: row=next(cursor)
                    except StopIteration: exhausted=True; break
                    assert context_for(cfg)==context, 'Frozen execution sources changed'
                    future=pool.submit(unit_execute,str(out),row,context,cfg['minimum_free_disk_bytes'])
                    active[future]=row['unit_id']
                for uid in active.values():
                    pp=out/'unit-progress'/(uid+'.json')
                    if pp.exists(): counters[uid]=read_json(pp)['completed_requests']
                count=sum(counters.values()); elapsed=time.monotonic()-start
                set_status(out,'pausing' if (out/'PAUSE').exists() else 'running',stage=stage,workers=cfg['workers'],
                    stage_units=len(rows),stage_requests=catalog['total_requests'],completed_units=len(done),
                    checkpointed_requests=count,request_percent=100*count/catalog['total_requests'],
                    active_units=list(active.values()),seconds_this_invocation=round(elapsed,3),
                    new_requests_this_invocation=count-previous_count)
                if not active: break
                completed,_=wait(active,timeout=3,return_when=FIRST_COMPLETED)
                for future in completed:
                    uid=active.pop(future); result=future.result()
                    if result['complete']: done.add(uid); counters[uid]=cfg['horizon']
            if (out/'PAUSE').exists(): return False
        except BaseException as exc:
            save(out/'PAUSE',{'kind':'error','error':repr(exc),'at':eng.now()}); raise
    assert len(done)==len(rows)
    immutable_json(out/(stage+'-completion.json'),{'context_sha256':sha(encode(context)),
        'catalogue_sha256':sha((out/(stage+'-catalogue.json')).read_bytes()),'units':len(rows),
        'requests':catalog['total_requests'],'status':'computed-pending-separate-replay'})
    return True


def score_candidates(candidate_metrics,candidate_fingerprints):
    """Input is ONLY four training regime panels, each a one/two-side metric list."""
    scores={}
    for name in CANDIDATES:
        regimes=candidate_metrics[name]; assert len(regimes)==4
        means=[]
        for sides in regimes:
            assert len(sides) in [1,2]
            means.append(tuple(sum((Fraction(s[j]) for s in sides),Fraction(0))/len(sides) for j in range(3)))
        scores[name]=tuple(sum((v[j] for v in means),Fraction(0))/4 for j in range(3))
    best=max(scores.values())
    winner=min((c for c in CANDIDATES if scores[c]==best),key=lambda c:(candidate_fingerprints[c],CANDIDATES.index(c)))
    return winner,scores


def select_all(out,index,catalog,cfg,context):
    lookup={(r['parent_id'],r['family'],r['candidate'],r['regime'],r['side']):r['unit_id'] for r in catalog['logical']}
    ch=sha(encode(context)); selections={}; bound_results={}
    for pr in index['parents']:
        if (out/'PAUSE').exists(): return None
        parent=read_parent(out,pr); key=parent['parent_id']; selected={}
        for family in cfg['families']:
            metrics={}; fingerprints={}
            for candidate in CANDIDATES:
                fingerprints[candidate]=sha(encode(parent['families'][family][candidate])); panels=[]
                for rid in cfg['training_regimes']:
                    sides=[]
                    for side in range(len(parent['families'][family][candidate])):
                        uid=lookup[key,family,candidate,rid,side]; result,h=load_result(out,uid,ch)
                        assert result['split']=='training'; prefix=result['prefix']; H=cfg['horizon']
                        assert prefix['completed_requests']==H
                        event=prefix['first_events']['tau_nopath']
                        sides.append((Fraction(H if event is None else event,H),Fraction(-int(event is not None)),
                                      Fraction(prefix['accepted_request_count'],H)))
                        bound_results[uid]=h
                    panels.append(sides)
                metrics[candidate]=panels
            winner,scores=score_candidates(metrics,fingerprints)
            selected[family]={'winner':winner,'candidate_state_hashes':fingerprints,
                              'scores':{c:[[f.numerator,f.denominator] for f in scores[c]] for c in CANDIDATES}}
        immutable_json(out/'selections'/(key+'.json'),{'parent_sha256':pr['payload_sha256'],
             'context_sha256':ch,'selected':selected,'training_catalogue_sha256':sha((out/'training-catalogue.json').read_bytes())})
        selections[key]=selected
    immutable_json(out/'selection-freeze.json',{'context_sha256':ch,'selections':selections,
        'training_result_payload_sha256':bound_results,'test_results_used':False})
    return selections


def run(cfg,resume=False):
    out=ROOT/cfg['output_root']
    with eng.exclusive(out):
        context=context_for(cfg); eng.check_binding(out,context)
        qa=json.loads((ROOT/'results/diagnostics/structure-robustness-A-v1/tests.json').read_bytes())
        assert qa['context_sha256']==sha(encode(context)) and qa['returncode']==0
        report=json.loads((ROOT/cfg['preflight_report']).read_bytes())
        assert report['status']=='passed-engineering-and-bounded-planning'
        if resume and (out/'PAUSE').exists():
            request=json.loads((out/'PAUSE').read_bytes())
            if request.get('kind')!='user-pause': raise RuntimeError('Error gate requires diagnosis')
            dest=out/'control-history'/f'pause-{time.time_ns()}.json'; dest.parent.mkdir(parents=True,exist_ok=True)
            os.replace(out/'PAUSE',dest)
        if (out/'PAUSE').exists(): set_status(out,'paused-safe-checkpoint'); return
        save(out/'owner.json',{'pid':os.getpid(),'started_utc':eng.now(),'argv':sys.argv})
        try:
            index=prepare(out,cfg,context)
            if index is None: set_status(out,'paused-safe-checkpoint'); return
            training=make_catalog(out,index,cfg,'training')
            if training is None: set_status(out,'paused-safe-checkpoint'); return
            if not run_stage(out,training,cfg,context): set_status(out,'paused-safe-checkpoint'); return
            set_status(out,'selecting-training-only',stage='selection')
            selections=select_all(out,index,training,cfg,context)
            if selections is None: set_status(out,'paused-safe-checkpoint'); return
            test=make_catalog(out,index,cfg,'test',selections)
            if test is None: set_status(out,'paused-safe-checkpoint'); return
            if not run_stage(out,test,cfg,context): set_status(out,'paused-safe-checkpoint'); return
            set_status(out,'A-computed-awaiting-separate-replay',stage='test',active_units=[])
        except BaseException as exc:
            save(out/'PAUSE',{'kind':'error','error':repr(exc),'at':eng.now()})
            set_status(out,'stopped-on-error',error=repr(exc)); raise


def selftest(cfg):
    command=[sys.executable,'-X','utf8','-m','unittest','tests.test_structure_robustness_A',
             'tests.test_structure_robustness_engineering','tests.test_supplement_initialization','-v']
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    out=ROOT/'results/diagnostics/structure-robustness-A-v1'
    save(out/'tests.json',{'command':command,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
                          'context_sha256':sha(encode(context_for(cfg)))})
    print(result.stderr); return result.returncode


def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['run','resume','pause','status','selftest']); args=p.parse_args()
    if not __debug__: raise RuntimeError('Do not disable assertions with -O')
    cfg=config(); out=ROOT/cfg['output_root']
    if args.command=='selftest': raise SystemExit(selftest(cfg))
    if args.command=='pause':
        if not (out/'PAUSE').exists(): save(out/'PAUSE',{'kind':'user-pause','at':eng.now()})
        print('Pause requested; wait for safe checkpoint and released lease.'); return
    if args.command=='status':
        value=read_json(out/'progress.json') if (out/'progress.json').exists() else {'state':'not-started'}
        try:
            with eng.exclusive(out): value['runner_lock_live']=False
        except OSError: value['runner_lock_live']=True
        if not value['runner_lock_live'] and value['state'] in ['running','preparing-inputs','pausing','selecting-training-only']:
            value['live_status']='not-running-resume-required'
        print(json.dumps(value,ensure_ascii=False,indent=2)); return
    run(cfg,args.command=='resume')


if __name__=='__main__': main()
