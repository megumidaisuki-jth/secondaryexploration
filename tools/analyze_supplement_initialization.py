"""Gated S5 four-arm paired inference. No simulation or raw-block reader.

May be prepared/tested while S5 runs, but real endpoints require completed
generation, complete separate replay and byte-verified Git upload first.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time
from tools.supplement_initialization_common import ROOT,OUT as SOURCE,CONFIG,encode,sha,save,atomic,load,store

OUT=ROOT/'results/supplement/initialization-ablation-analysis-v1'
ARMS=['DA-U','FHS5-U','DA-O','FHS5-O']
COEFFICIENTS=[[1,-1,0,0],[0,0,1,-1],[-1,1,1,-1],[-1,0,1,0],[0,-1,0,1]]

def event_vector(events,H):
    assert set(events)==set(ARMS)
    times=[]; risks=[]
    for arm in ARMS:
        event=events[arm]; flag=event['observed']; index=event['request_index']
        assert type(flag) is bool and type(index) is int and 1<=index<=H
        assert flag or index==H
        times.append(index); risks.append(int(flag))
    return times+risks

def contrast(vector):
    assert len(vector)==8 and all(type(x) is int for x in vector)
    return [sum(c*v for c,v in zip(coeff,vector[base:base+4])) for base in (0,4) for coeff in COEFFICIENTS]

def ensure_ready(source=SOURCE):
    # Gate BEFORE any parent, trace or result endpoint is opened.
    if any((source/name).exists() for name in ['RUNNING.lock','VERIFYING.lock','PIPELINE.lock','PAUSE']):
        raise RuntimeError('Waiting: S5 generation/replay/upload is active or paused; do not read partial endpoints.')
    if not (source/'verification.json').exists(): raise RuntimeError('Waiting: full S5 separate replay witness is missing.')
    proof=json.loads((source/'verification.json').read_bytes())
    catalog=json.loads((source/'catalogue.json').read_bytes())
    status=json.loads((source/'pipeline-status.json').read_bytes())
    assert proof['status']=='passed' and proof['parents_verified']==480
    assert proof['unique_units_verified']==catalog['unique_units'] and proof['new_requests_replayed']==catalog['new_requests']
    assert status['state']=='verified-simulation-uploaded-awaiting-four-arm-statistics','S5 validated data upload not yet complete'
    upload=status['upload']; assert upload['status']=='uploaded-byte-verified' and upload['commit']==upload['remote_commit']
    assert upload['manifest_sha256']==sha((source/'snapshot-verified-simulation.json').read_bytes())
    return catalog,proof

def collect(cfg):
    catalog,proof=ensure_ready()
    assert catalog['binding']['config_sha256']==sha(CONFIG.read_bytes())
    unit_rows={r['unit_id']:r for r in catalog['units']}; summaries={}
    for uid,row in unit_rows.items():
        result,h=load(SOURCE/'runs'/uid/'result.json.gz')
        receipt=json.loads((SOURCE/'run-verification'/(uid+'.json')).read_bytes())
        assert receipt['result_payload_sha256']==h and receipt['unit_payload_sha256']==row['payload_sha256']
        assert receipt['status'] in ['passed-existing-O-reuse','passed-separate-common-ticket-replay']
        summaries[uid]=result['summary']
    parents=[]; traces=[]
    for record in catalog['parents']:
        saved,phash=load(SOURCE/record['path']); assert phash==record['payload_sha256']; parent=saved['parent']
        input_proof=json.loads((SOURCE/'input-verification'/f"{parent['phase']}-{parent['parent_graph_id']}.json").read_bytes())
        assert input_proof['parent_payload_sha256']==phash
        H=12*parent['node_count']; scope_rows={scope:[] for scope in cfg['scopes']}
        assert len(parent['traces'])==7 and len({t['regime_id'] for t in parent['traces']})==7
        assert Counter(t['scope'] for t in parent['traces'])=={'same_distribution':4,'distribution_shift':3}
        for tr in parent['traces']:
            events={}
            for family,short in [('demand-aware','DA'),('fhs5','FHS5')]:
                uid=tr['uniform_units'][family]; assert uid in unit_rows
                row=unit_rows[uid]
                assert row['phase']==parent['phase'] and row['parent_graph_id']==parent['parent_graph_id'] and row['regime_id']==tr['regime_id'] and row['horizon']==H
                events[short+'-U']=summaries[uid]['tau_nopath']
                events[short+'-O']=tr['optimized'][family]['events']['tau_nopath']
            vector=event_vector(events,H)
            scope_rows['combined'].append(vector); scope_rows[tr['scope']].append(vector)
            traces.append({**{k:parent[k] for k in ['phase','node_count','parent_model','parent_replicate','parent_graph_id']},
                'regime_id':tr['regime_id'],'scope':tr['scope'],'horizon':H,'paired_manifest_fingerprint':tr['paired_manifest_fingerprint'],
                'uniform_units':tr['uniform_units'],'arm_events':events,'arm_integers':vector,'contrast_integers':contrast(vector)})
        totals={}
        for scope,count in zip(cfg['scopes'],cfg['traces_per_scope']):
            assert len(scope_rows[scope])==count
            totals[scope]=[sum(v[k] for v in scope_rows[scope]) for k in range(8)]
        assert totals['combined']==[a+b for a,b in zip(totals['same_distribution'],totals['distribution_shift'])]
        parents.append({**{k:parent[k] for k in ['phase','node_count','parent_model','parent_replicate','parent_graph_id']},
            'horizon':H,'parent_payload_sha256':phash,'arm_totals':totals})
    assert len(parents)==480 and len(traces)==3360
    assert len({(p['phase'],p['parent_graph_id']) for p in parents})==480
    for phase in cfg['phases']:
        for n in cfg['node_counts']:
            for model in cfg['models']:
                rows=[p for p in parents if (p['phase'],p['node_count'],p['parent_model'])==(phase,n,model)]
                assert len(rows)==20 and sorted(p['parent_replicate'] for p in rows)==list(range(20))
    return sorted(parents,key=lambda p:(p['phase'],p['node_count'],p['parent_model'],p['parent_replicate'])),traces

def indices(cfg,phase,n,replicate,model):
    key=f'{cfg["bootstrap_seed"]}|{phase}|{n}|{replicate}|{model}'
    rng=random.Random(int.from_bytes(hashlib.sha256(key.encode()).digest(),'big'))
    return [rng.randrange(20) for _ in range(20)]

def bootstrap(cfg,phase,n,strata,start,stop):
    draws=[]
    for rep in range(start,stop):
        total=[0]*8
        for model in cfg['models']:
            for index in indices(cfg,phase,n,rep,model):
                for col,v in enumerate(strata[model][index]): total[col]+=v
        draws.append(total)
    return draws

def checkpoint(cfg,phase,n,strata,start,binding,out=OUT):
    path=out/'checkpoints'/f'{phase}-n{n:04d}-{start:05d}.json.gz'
    meta={'binding_sha256':sha(encode(binding)),'phase':phase,'node_count':n,'start':start,'stop':start+500}
    if path.exists():
        chunk,_=load(path); assert chunk['meta']==meta; values=chunk['arm_draws']; created=False
    else:
        values=bootstrap(cfg,phase,n,strata,start,start+500); store(path,{'meta':meta,'arm_draws':values}); created=True
    assert len(values)==500 and all(len(v)==8 and all(type(x) is int for x in v) for v in values)
    return values,created

def summaries(cfg,phase,n,parents,draws):
    summaries=[]; arms=[]
    H=12*n
    for scope,count in zip(cfg['scopes'],cfg['traces_per_scope']):
        totals=[p['arm_totals'][scope] for p in parents]
        aggregate=[sum(v[k] for v in totals) for k in range(8)]; numerators=contrast(aggregate)
        parent_contrasts=[contrast(v) for v in totals]
        for metric_index,metric in enumerate(cfg['metrics']):
            denominator=60*count*(H if metric_index==0 else 1)
            for arm_index,arm in enumerate(ARMS):
                f=Fraction(aggregate[4*metric_index+arm_index],denominator)
                arms.append({'phase':phase,'node_count':n,'scope':scope,'metric':metric,'arm':arm,'estimate':[f.numerator,f.denominator],'display':float(f)})
            for comparison_index,name in enumerate(cfg['comparisons']):
                column=5*metric_index+comparison_index; value=Fraction(numerators[column],denominator)
                exact={'estimate':[value.numerator,value.denominator]}
                row={'phase':phase,'node_count':n,'scope':scope,'metric':metric,'comparison':name,'independent_parents':60,
                    'parents_by_model':{m:20 for m in cfg['models']},'traces_per_parent':count,'exact':exact,'display':{'estimate':float(value)},
                    'parent_sign_counts':{label:sum(test(v[column]) for v in parent_contrasts) for label,test in [('negative',lambda x:x<0),('zero',lambda x:x==0),('positive',lambda x:x>0)]},
                    'interval_status':'pointwise-unadjusted-95-percent' if scope=='combined' else 'descriptive-only-no-interval'}
                if scope=='combined':
                    ordered=sorted(contrast(d)[column] for d in draws); assert len(ordered)==20000
                    for key,rank in [('lower',500),('upper',19500)]:
                        f=Fraction(ordered[rank-1],denominator); exact[key]=[f.numerator,f.denominator]; row['display'][key]=float(f)
                    row['degenerate_empirical_bootstrap']=ordered[0]==ordered[-1]
                summaries.append(row)
    return summaries,arms

def match_s1(cfg,rows):
    raw=(ROOT/'results/supplement/da-fhs5-posthoc-v1/results.json').read_bytes()
    assert sha(raw)==cfg['s1_results_sha256']
    old=json.loads(raw)['comparisons']; assert len(old)==16
    for r in old:
        current=next(v for v in rows if (v['phase'],v['node_count'],v['metric'],v['scope'],v['comparison'])==(r['phase'],r['node_count'],r['metric'],'combined','DA-O-minus-FHS5-O'))
        assert current['exact']['estimate']==r['exact']['estimate'],'Original optimized effect changed'

def run(args):
    cfg=json.loads(CONFIG.read_bytes())
    if args.record_preparation:
        # Synthetic-only tests; this mode never calls collect/ensure_ready.
        tests=subprocess.run([sys.executable,'-m','unittest','tests.test_supplement_initialization_analysis','-v'],
            cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        assert tests.returncode==0,tests.stderr
        sources={name:sha((ROOT/name).read_bytes()) for name in ['tools/analyze_supplement_initialization.py',
            'tools/verify_supplement_initialization_analysis.py','tests/test_supplement_initialization_analysis.py',
            'docs/plans/2026-10-07-S5-statistics-preparation.md','results/supplement/initialization-ablation-analysis-v1/.gitattributes']}
        save(OUT/'preparation.json',{'status':'prepared-and-synthetic-tests-passed-not-real-analysis','sources_sha256':sources,
            'config_sha256':sha(CONFIG.read_bytes()),'tests_exit_code':tests.returncode,'test_log':tests.stderr,
            'real_endpoints_read':0,'new_simulations':0,'bootstrap_real_data':'not_started','figures':'not_started'})
        print('Statistics preparation recorded; no real endpoints read.'); return
    if args.check_ready:
        try: ensure_ready()
        except RuntimeError as exc: print(str(exc)); return
        print('Full S5 verified simulation and byte-verified upload are ready; no endpoints read.'); return
    catalog,proof=ensure_ready()
    assert cfg['bootstrap_replicates']==20000 and cfg['bootstrap_chunk']==500
    assert cfg['arms']==ARMS and len(cfg['comparisons'])==5
    OUT.mkdir(parents=True,exist_ok=True)
    binding={'schema':'S5-four-arm-statistics-v1','analysis_sha256':sha(Path(__file__).read_bytes()),'config_sha256':sha(CONFIG.read_bytes()),
        'catalogue_sha256':sha((SOURCE/'catalogue.json').read_bytes()),'simulation_verification_sha256':sha((SOURCE/'verification.json').read_bytes()),
        'simulation_manifest_sha256':sha((SOURCE/'snapshot-verified-simulation.json').read_bytes()),'common_sha256':sha((ROOT/'tools/supplement_initialization_common.py').read_bytes()),
        's1_results_sha256':cfg['s1_results_sha256'],'python_version':platform.python_version()}
    bp=OUT/'binding.json'
    if bp.exists(): assert json.loads(bp.read_bytes())==binding
    else: save(bp,binding)
    lock=OUT/'RUNNING.lock'
    with lock.open('xb') as f: f.write(encode({'pid':os.getpid(),'argv':sys.argv}))
    start_time=time.monotonic(); completed=newly=0
    def status(state,**kw):
        save(OUT/'progress.json',{'state':state,'completed_bootstrap_chunks':completed,'total_bootstrap_chunks':320,
            'bootstrap_percent':round(completed/320*100,3),'elapsed_seconds':round(time.monotonic()-start_time,3),**kw})
    try:
        parents,traces=collect(cfg)
        for name,values in [('parents',parents),('traces',traces)]:
            target=OUT/(name+'.json.gz')
            if target.exists(): assert load(target)[0]==values
            else: store(target,values)
        results=[]; arm_results=[]
        for phase in cfg['phases']:
            for n in cfg['node_counts']:
                selected=[p for p in parents if (p['phase'],p['node_count'])==(phase,n)]
                strata={m:[p['arm_totals']['combined'] for p in selected if p['parent_model']==m] for m in cfg['models']}
                draws=[]
                for start in range(0,20000,500):
                    if (OUT/'PAUSE').exists(): status('paused-safe-checkpoint'); return
                    values,created=checkpoint(cfg,phase,n,strata,start,binding); newly+=int(created)
                    draws.extend(values); completed+=1; status('bootstrapping',phase=phase,node_count=n,replicates_completed=start+500)
                    if args.stop_after_chunks and newly>=args.stop_after_chunks: status('paused-safe-checkpoint'); return
                rows,arm_rows=summaries(cfg,phase,n,selected,draws); results.extend(rows); arm_results.extend(arm_rows)
        assert len(results)==240 and len(arm_results)==192
        match_s1(cfg,results)
        save(OUT/'results.json',{'binding':binding,'comparisons':results,'arm_means':arm_results,
            'intervals':'80 combined pointwise unadjusted 95% percentile intervals; 160 subscope descriptive estimates with no intervals; no family-wise coverage or p values.',
            'scope':'Post-hoc four-arm fixed-topology/initialization supplement; no new blinded confirmation or pure-topology causal identification.',
            'original_S1_optimized_estimates_exactly_reproduced':16})
        status('generated-pending-separate-arithmetic-verification')
    except BaseException as exc: status('stopped-on-error',error=repr(exc)); raise
    finally: lock.unlink()

if __name__=='__main__':
    parser=argparse.ArgumentParser(); modes=parser.add_mutually_exclusive_group(); modes.add_argument('--check-ready',action='store_true')
    modes.add_argument('--record-preparation',action='store_true'); parser.add_argument('--stop-after-chunks',type=int,default=0)
    run(parser.parse_args())
