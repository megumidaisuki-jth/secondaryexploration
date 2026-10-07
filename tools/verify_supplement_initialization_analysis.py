"""Separate S5 arithmetic checker; never import four-arm generator or simulate.

Source events, scope aggregation, all shared-index bootstrap draws, direct
interaction and inverse-ECDF endpoints are checked. Same-analyst implementation
cross-check, not a new scientific blinded review.
"""
from collections import Counter,defaultdict
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time
from tools.supplement_initialization_common import ROOT,OUT as SOURCE,CONFIG,sha,encode,save,load

OUT=ROOT/'results/supplement/initialization-ablation-analysis-v1'

def differences(vector):
    a,b,c,d,e,f,g,h=vector
    return [a-b,c-d,(c-a)-(d-b),c-a,d-b,e-f,g-h,(g-e)-(h-f),g-e,h-f]

def require_complete():
    if any((SOURCE/name).exists() for name in ['RUNNING.lock','VERIFYING.lock','PIPELINE.lock','PAUSE']):
        raise RuntimeError('Simulation/replay/upload active or paused: no scientific endpoint access.')
    if not (SOURCE/'verification.json').exists(): raise RuntimeError('Complete separate simulation replay missing.')
    v=json.loads((SOURCE/'verification.json').read_bytes()); catalog=json.loads((SOURCE/'catalogue.json').read_bytes())
    p=json.loads((SOURCE/'pipeline-status.json').read_bytes())
    assert v['status']=='passed' and v['parents_verified']==480 and v['unique_units_verified']==catalog['unique_units']
    assert v['new_requests_replayed']==catalog['new_requests'] and p['state']=='verified-simulation-uploaded-awaiting-four-arm-statistics'
    assert p['upload']['status']=='uploaded-byte-verified' and p['upload']['commit']==p['upload']['remote_commit']
    assert p['upload']['manifest_sha256']==sha((SOURCE/'snapshot-verified-simulation.json').read_bytes())
    return catalog

def reconstruct(cfg,catalog):
    exported_traces,_=load(OUT/'traces.json.gz'); exported_parents,_=load(OUT/'parents.json.gz')
    traces={(t['phase'],t['parent_graph_id'],t['regime_id']):t for t in exported_traces}
    parents={(p['phase'],p['parent_graph_id']):p for p in exported_parents}
    assert len(traces)==len(exported_traces)==3360 and len(parents)==len(exported_parents)==480
    cache={}
    for u in catalog['units']:
        result,h=load(SOURCE/'runs'/u['unit_id']/'result.json.gz')
        proof=json.loads((SOURCE/'run-verification'/(u['unit_id']+'.json')).read_bytes())
        assert proof['result_payload_sha256']==h and proof['unit_payload_sha256']==u['payload_sha256']
        cache[u['unit_id']]=result['summary']['tau_nopath']
    for p in catalog['parents']:
        payload,h=load(SOURCE/p['path']); assert h==p['payload_sha256']; source=payload['parent']
        target=parents[source['phase'],source['parent_graph_id']]
        assert target['parent_payload_sha256']==h and target['horizon']==12*source['node_count']
        totals={scope:[0]*8 for scope in cfg['scopes']}; counts=Counter()
        for tr in source['traces']:
            target_trace=traces[source['phase'],source['parent_graph_id'],tr['regime_id']]
            ev={}
            for family,label in [('demand-aware','DA'),('fhs5','FHS5')]:
                ev[label+'-U']=cache[tr['uniform_units'][family]]
                ev[label+'-O']=tr['optimized'][family]['events']['tau_nopath']
            order=['DA-U','FHS5-U','DA-O','FHS5-O']; vector=[ev[k]['request_index'] for k in order]+[int(ev[k]['observed']) for k in order]
            assert target_trace['arm_events']==ev and target_trace['arm_integers']==vector and target_trace['contrast_integers']==differences(vector)
            assert target_trace['uniform_units']==tr['uniform_units'] and target_trace['paired_manifest_fingerprint']==tr['paired_manifest_fingerprint']
            assert target_trace['scope']==tr['scope'] and target_trace['horizon']==12*source['node_count']
            for scope in ['combined',tr['scope']]:
                counts[scope]+=1
                for col,v in enumerate(vector): totals[scope][col]+=v
        assert counts==dict(zip(cfg['scopes'],cfg['traces_per_scope'])) and totals==target['arm_totals']
        for key in ['phase','node_count','parent_model','parent_replicate','parent_graph_id']: assert target[key]==source[key]
    return list(parents.values())

def check_summary(cfg,rows,arms,phase,n,parents,draws):
    H=12*n; checked=0
    for scope,count in zip(cfg['scopes'],cfg['traces_per_scope']):
        vectors=[p['arm_totals'][scope] for p in parents]
        aggregate=[sum(v[k] for v in vectors) for k in range(8)]; nums=differences(aggregate)
        for mi,metric in enumerate(cfg['metrics']):
            denominator=60*count*(H if mi==0 else 1)
            for ai,arm in enumerate(['DA-U','FHS5-U','DA-O','FHS5-O']):
                r=arms[phase,n,scope,metric,arm]; assert Fraction(*r['estimate'])==Fraction(aggregate[4*mi+ai],denominator)
                assert r['display']==float(Fraction(*r['estimate']))
            for ci,comparison in enumerate(cfg['comparisons']):
                r=rows[phase,n,scope,metric,comparison]; col=5*mi+ci
                assert Fraction(*r['exact']['estimate'])==Fraction(nums[col],denominator)
                assert r['independent_parents']==60 and r['traces_per_parent']==count and r['parents_by_model']=={m:20 for m in cfg['models']}
                vals=[differences(v)[col] for v in vectors]
                assert r['parent_sign_counts']=={'negative':sum(v<0 for v in vals),'zero':sum(v==0 for v in vals),'positive':sum(v>0 for v in vals)}
                if scope=='combined':
                    order=sorted(differences(v)[col] for v in draws); assert len(order)==20000
                    for key,index in [('lower',499),('upper',19499)]: assert Fraction(*r['exact'][key])==Fraction(order[index],denominator)
                    assert r['interval_status']=='pointwise-unadjusted-95-percent' and r['degenerate_empirical_bootstrap']==(order[0]==order[-1])
                else: assert set(r['exact'])=={'estimate'} and r['interval_status']=='descriptive-only-no-interval'
                for key,value in r['exact'].items(): assert r['display'][key]==float(Fraction(*value))
                checked+=1
        for metric in cfg['metrics']:
            for comparison in cfg['comparisons']:
                points={s:Fraction(*rows[phase,n,s,metric,comparison]['exact']['estimate']) for s in cfg['scopes']}
                assert points['combined']==Fraction(4,7)*points['same_distribution']+Fraction(3,7)*points['distribution_shift']
    return checked

def run():
    catalog=require_complete(); cfg=json.loads(CONFIG.read_bytes())
    assert not (OUT/'RUNNING.lock').exists(),'Statistics generator is still active'
    binding=json.loads((OUT/'binding.json').read_bytes())
    assert binding['analysis_sha256']==sha((ROOT/'tools/analyze_supplement_initialization.py').read_bytes())
    assert binding['config_sha256']==sha(CONFIG.read_bytes()) and binding['catalogue_sha256']==sha((SOURCE/'catalogue.json').read_bytes())
    assert binding['simulation_verification_sha256']==sha((SOURCE/'verification.json').read_bytes())
    assert binding['simulation_manifest_sha256']==sha((SOURCE/'snapshot-verified-simulation.json').read_bytes())
    assert binding['common_sha256']==sha((ROOT/'tools/supplement_initialization_common.py').read_bytes())
    results=json.loads((OUT/'results.json').read_bytes()); assert results['binding']==binding
    rows={(r['phase'],r['node_count'],r['scope'],r['metric'],r['comparison']):r for r in results['comparisons']}
    arms={(r['phase'],r['node_count'],r['scope'],r['metric'],r['arm']):r for r in results['arm_means']}
    assert len(rows)==len(results['comparisons'])==240 and len(arms)==len(results['arm_means'])==192
    checker_binding={'checker_sha256':sha(Path(__file__).read_bytes()),'analysis_binding_sha256':sha(encode(binding)),
        'results_sha256':sha((OUT/'results.json').read_bytes())}
    path=OUT/'arithmetic-binding.json'
    if path.exists(): assert json.loads(path.read_bytes())==checker_binding
    else: save(path,checker_binding)
    with (OUT/'VERIFYING.lock').open('xb') as stream: stream.write(encode({'pid':os.getpid(),'argv':sys.argv}))
    began=time.monotonic(); chunks=replicates=checked_rows=0
    def status(state,**kw):
        save(OUT/'verification-progress.json',{'state':state,'checked_chunks':chunks,'total_chunks':320,'percent':round(chunks/320*100,3),
            'elapsed_seconds':round(time.monotonic()-began,3),**kw})
    try:
        parents=reconstruct(cfg,catalog)
        for phase in cfg['phases']:
            for n in cfg['node_counts']:
                selected=[p for p in parents if (p['phase'],p['node_count'])==(phase,n)]
                strata={m:sorted([p for p in selected if p['parent_model']==m],key=lambda p:p['parent_replicate']) for m in cfg['models']}
                assert all(len(v)==20 and [p['parent_replicate'] for p in v]==list(range(20)) for v in strata.values())
                draws=[]
                for start in range(0,20000,500):
                    if (OUT/'PAUSE').exists(): status('paused-safe-checkpoint'); return
                    checkpoint,chash=load(OUT/'checkpoints'/f'{phase}-n{n:04d}-{start:05d}.json.gz')
                    assert checkpoint['meta']=={'binding_sha256':sha(encode(binding)),'phase':phase,'node_count':n,'start':start,'stop':start+500}
                    receipt_path=OUT/'arithmetic-checkpoints'/f'{phase}-n{n:04d}-{start:05d}.json'
                    receipt={'checker_binding_sha256':sha(encode(checker_binding)),'checkpoint_payload_sha256':chash,'status':'passed-500-shared-parent-draws'}
                    values=checkpoint['arm_draws']; assert len(values)==500
                    if receipt_path.exists(): assert json.loads(receipt_path.read_bytes())==receipt
                    else:
                        for offset,value in enumerate(values):
                            assert len(value)==8 and all(type(v) is int for v in value)
                            expected=[0]*8
                            for model in cfg['models']:
                                key=f'{cfg["bootstrap_seed"]}|{phase}|{n}|{start+offset}|{model}'
                                rng=random.Random(int(hashlib.sha256(key.encode()).hexdigest(),16))
                                frequencies=Counter(rng.randrange(20) for _ in range(20))
                                for i,frequency in frequencies.items():
                                    vector=strata[model][i]['arm_totals']['combined']
                                    for col,x in enumerate(vector): expected[col]+=frequency*x
                            assert expected==value
                        save(receipt_path,receipt)
                    draws.extend(values); chunks+=1; replicates+=500; status('checking-shared-parent-bootstrap',phase=phase,node_count=n)
                checked_rows+=check_summary(cfg,rows,arms,phase,n,selected,draws)
        oldraw=(ROOT/'results/supplement/da-fhs5-posthoc-v1/results.json').read_bytes(); assert sha(oldraw)==cfg['s1_results_sha256']
        old=json.loads(oldraw)['comparisons']; assert len(old)==16
        for r in old: assert rows[r['phase'],r['node_count'],'combined',r['metric'],'DA-O-minus-FHS5-O']['exact']['estimate']==r['exact']['estimate']
        save(OUT/'verification.json',{'status':'passed','binding':checker_binding,'parents_verified':480,'traces_verified':3360,
            'bootstrap_replicates_verified':replicates,'bootstrap_chunks_verified':chunks,'contrast_rows_verified':checked_rows,'arm_mean_rows_verified':192,
            'optimized_S1_estimates_reproduced':16,'scope':'Separate source-event reconstruction and scalar/Counter arithmetic; same analyst, not new blinded scientific review.',
            'new_simulations':0,'raw_blocks_read':0})
        status('complete-arithmetic-verified')
    except BaseException as exc: status('stopped-on-error',error=repr(exc)); raise
    finally: (OUT/'VERIFYING.lock').unlink()

if __name__=='__main__': run()
