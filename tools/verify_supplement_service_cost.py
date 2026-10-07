"""Separate arithmetic implementation: saved routes, resampling, and S3 ratios.

Does not import the S3 executor. This is an arithmetic crosscheck by the same
analyst, not a blinded scientific replay or routing-optimality audit.
"""
from collections import Counter
import argparse
import ast
from fractions import Fraction
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import random
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/supplement/service-cost-posthoc-v1'
CFG=ROOT/'configs/supplement/service-cost-posthoc-v1.json'

def digest(data): return hashlib.sha256(data).hexdigest()

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    with tmp.open('xb') as f:
        f.write((json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()); f.flush(); os.fsync(f.fileno())
    tmp.replace(path)

def verify_raw(parent):
    phase=parent['phase']; key=parent['parent_graph_id']
    raw=(ROOT/f'outputs/{phase}/synthetic-{phase}-v1/blocks/{key}.json').read_bytes()
    assert digest(raw)==parent['raw_sha256'] and len(raw)==parent['raw_bytes']
    a=json.loads(raw); witness=a['result_witness']
    topology={v[0]:{edge:members for edge,members in v[2][1]} for v in witness['variants']}
    static={s['variant_id']:s for s in parent['static']}
    for variant in witness['variants']:
        sizes=[len(m) for m in topology[variant[0]].values()]
        expected={'node_count':len(variant[2][0]),'hyperedge_count':len(sizes),'incidence_count':sum(sizes),
                  'maximum_arity':max(sizes),'pairwise_member_exposure':sum(len([(i,j) for i in range(k) for j in range(i+1,k)]) for k in sizes)}
        assert static[variant[0]]['resources']==expected
        assert static[variant[0]]['family']==variant[1]
    traces={t['regime_id']:t for t in parent['traces']}
    runs={r[0]:dict(r[4]) for r in witness['held_out']}
    for run in a['held_out']:
        regime=run['trace_seed']['regime_id']; trace=traces[regime]
        assert trace['paired_manifest_fingerprint']==run['paired_manifest_fingerprint']
        data={v['variant_id']:v for v in trace['arms']}
        for variant in run['variants']:
            vid=variant['variant_id']; simulation=runs[regime][vid]
            service=value=traversal=slots=quadratic=unique=0; logcost=0.0; hist=Counter()
            for outcome in simulation[1]:
                if outcome[2] is None: continue
                service+=1; value+=outcome[1][2]; signaled=[]
                for step in outcome[2]:
                    members=topology[vid][step[0]]; arity=len(members)
                    traversal+=1; slots+=arity; quadratic+=arity**2; hist[arity]+=1
                    signaled.extend(members)
                unique+=len(set(signaled))
            # Nonlinear histogram transform calculated separately from the core costs.
            logcost=math.fsum(hist[k]*k*math.log2(k) for k in sorted(hist))
            actual=[service,value,traversal,slots,unique,quadratic]
            assert actual==data[vid]['values']
            assert data[vid]['locked_capital']==sum(balance for _,members in simulation[0] for _,balance in members)==120*parent['node_count']
            assert np.isclose(logcost,data[vid]['arity_log2_exposure'],rtol=0,atol=1e-8)
            assert data[vid]['route_arity_histogram']==[[k,hist[k]] for k in sorted(hist)]
    assert parent['panels']=={p['source_variant_id']:p['binary_variant_ids'] for p in a['resource_panels']}
    return sum(len(t['arms']) for t in parent['traces'])

def build_array(parents,families):
    arr=[]
    for p in parents:
        rows=[]
        for family in families:
            for role in ('source','binary_panel'):
                exact=[Fraction(0) for _ in range(6)]; logsum=0.0
                ids=[family] if role=='source' else p['panels'][family]
                for t in p['traces']:
                    values={v['variant_id']:v for v in t['arms']}
                    for vid in ids:
                        for col,val in enumerate(values[vid]['values']): exact[col]+=Fraction(val,len(ids))
                        logsum+=values[vid]['arity_log2_exposure']/len(ids)
                assert all((2*v).denominator==1 for v in exact)
                rows.append([int(2*v) for v in exact]+[logsum*2])
        arr.append(rows)
    return np.array(arr,dtype=np.float64)

def draws_for_chunk(config,phase,n,arr,start):
    ids=[]
    for rep in range(start,start+500):
        one=[]
        for stratum,model in enumerate(config['models']):
            msg='|'.join(map(str,(config['bootstrap_seed'],phase,n,rep,model))).encode()
            rng=random.Random(int(hashlib.sha256(msg).hexdigest(),16))
            one.extend(stratum*20+rng.randrange(20) for _ in range(20))
        ids.append(one)
    return arr[np.array(ids)].sum(axis=1)

def ci(values):
    if not np.isfinite(values).all(): return None
    return np.quantile(values,[.025,.975],method='inverted_cdf').tolist()

def equal_interval(actual,expected):
    if expected is None: assert actual is None
    else: np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-8)

def run(routes_only=False):
    config=json.loads(CFG.read_bytes()); binding=json.loads((OUT/'binding.json').read_bytes())
    assert binding['config_sha256']==digest(CFG.read_bytes())
    assert binding['script_sha256']==digest((ROOT/'tools/supplement_service_cost.py').read_bytes())
    assert binding['numpy']==np.__version__
    parents=[]; checked_runs=0; reused_route_receipts=0
    previous=ROOT/'tools/verify_supplement_service_cost_v1.py'
    oldsource=previous.read_text(encoding='utf-8'); newsource=Path(__file__).read_text(encoding='utf-8')
    oldfn=next(n for n in ast.parse(oldsource).body if isinstance(n,ast.FunctionDef) and n.name=='verify_raw')
    newfn=next(n for n in ast.parse(newsource).body if isinstance(n,ast.FunctionDef) and n.name=='verify_raw')
    assert ast.get_source_segment(oldsource,oldfn)==ast.get_source_segment(newsource,newfn)
    # Only the floating bootstrap gate changed; exact route arithmetic is identical.
    oldrevision=digest(previous.read_bytes())
    max_log_absolute_difference=max_log_relative_difference=0.0
    epsilon=np.finfo(np.float64).eps
    gamma160=160*epsilon/(1-160*epsilon)
    for i,path in enumerate(sorted((OUT/'parents').glob('*.json')),1):
        raw=path.read_bytes(); assert digest(raw)==path.with_suffix('.sha256').read_text().strip()
        p=json.loads(raw); target=OUT/'verification-checkpoints-v2'/f"parent-{path.name}"
        header={'parent_sha256':digest(raw),'raw_sha256':p['raw_sha256'],'verifier_sha256':digest(Path(__file__).read_bytes())}
        if target.exists():
            old=json.loads(target.read_bytes()); assert all(old[k]==v for k,v in header.items())
            source=ROOT/f"outputs/{p['phase']}/synthetic-{p['phase']}-v1/blocks/{p['parent_graph_id']}.json"
            assert digest(source.read_bytes())==p['raw_sha256']
            runs=old['variant_runs']
        else:
            oldpath=OUT/'verification-checkpoints'/f"parent-{path.name}"
            if oldpath.exists():
                prior=json.loads(oldpath.read_bytes())
                assert prior['verifier_sha256']==oldrevision and prior['status']=='arithmetic-passed'
                assert prior['parent_sha256']==digest(raw) and prior['raw_sha256']==p['raw_sha256']
                source=ROOT/f"outputs/{p['phase']}/synthetic-{p['phase']}-v1/blocks/{p['parent_graph_id']}.json"
                assert digest(source.read_bytes())==p['raw_sha256']
                runs=prior['variant_runs']; reused_route_receipts+=1
                save(target,header|{'variant_runs':runs,'status':'arithmetic-passed','reused_exact_route_receipt_sha256':digest(oldpath.read_bytes())})
            else:
                runs=verify_raw(p); save(target,header|{'variant_runs':runs,'status':'arithmetic-passed'})
        checked_runs+=runs; parents.append(p)
        if i%30==0: print(json.dumps({'stage':'independent-route-arithmetic','blocks':i,'total':480}),flush=True)
        save(OUT/'verification-progress.json',{'stage':'route-arithmetic','blocks':i,'total_blocks':480,'bootstrap_cells':0})
        if (OUT/'PAUSE').exists():
            save(OUT/'verification-progress.json',{'stage':'paused-safe-checkpoint','blocks':i,'total_blocks':480}); return
    if routes_only:
        print(json.dumps({'stage':'route-prefix-complete','blocks':len(parents),'variant_runs':checked_runs}),flush=True); return
    assert len(parents)==480
    resultbytes=(OUT/'results.json').read_bytes(); results=json.loads(resultbytes)
    assert len(results['arms'])==64 and len(results['contrasts'])==200
    completed_cells=0
    for phase in ('formal','confirmation'):
        for n in config['node_counts']:
            seal=OUT/'verification-checkpoints-v2'/f'bootstrap-{phase}-n{n:04d}.json'
            parents_files=sorted((OUT/'parents').glob(f'{phase}-n{n:04d}-*.json'))
            bootstrap_files=sorted((OUT/'bootstrap').glob(f'{phase}-n{n:04d}-*'))
            cellheader={'results_sha256':digest(resultbytes),'verifier_sha256':digest(Path(__file__).read_bytes()),
                        'inputs':{p.name:digest(p.read_bytes()) for p in parents_files+bootstrap_files}}
            if seal.exists():
                assert json.loads(seal.read_bytes())==cellheader|{'status':'all-20000-replicates-and-intervals-passed'}
                completed_cells+=1; continue
            ps=sorted((p for p in parents if p['phase']==phase and p['node_count']==n),key=lambda p:(config['models'].index(p['parent_model']),p['parent_replicate']))
            arr=build_array(ps,config['families']); chunks=[]
            for start in range(0,20000,500):
                path=OUT/'bootstrap'/f'{phase}-n{n:04d}-{start:05d}.bin.gz'
                raw=path.read_bytes(); meta=json.loads(path.with_suffix('.json').read_bytes())
                assert meta['sha256']==digest(raw)
                old=np.frombuffer(gzip.decompress(raw),dtype='<f8').reshape(500,8,7)
                new=draws_for_chunk(config,phase,n,arr,start)
                np.testing.assert_array_equal(old[:,:,:6],new[:,:,:6])
                # For nonnegative operands, gamma_k = k*eps/(1-k*eps) bounds
                # summation error relative to their sum. A conservative 160
                # rounded operations covers both 60-parent accumulation orders,
                # two seven-trace folds, bracket averaging and multiplications.
                # This scale-based bound is independent of observed differences.
                difference=np.abs(old[:,:,6]-new[:,:,6])
                bound=gamma160*np.maximum(np.abs(old[:,:,6]),np.abs(new[:,:,6]))+1e-10
                assert np.all(difference<=bound),'log2 accumulation exceeds forward-error bound'
                max_log_absolute_difference=max(max_log_absolute_difference,float(difference.max()))
                relative=np.divide(difference,np.maximum(np.abs(old[:,:,6]),np.abs(new[:,:,6])),out=np.zeros_like(difference),where=new[:,:,6]!=0)
                max_log_relative_difference=max(max_log_relative_difference,float(relative.max()))
                chunks.append(new)
            draw=np.concatenate(chunks); mean=arr.mean(axis=0)/14
            for r in (r for r in results['arms'] if r['phase']==phase and r['node_count']==n):
                k=2*config['families'].index(r['family'])+(r['role']=='binary_panel')
                zero_traces=zero_parents=0
                for p in ps:
                    ids=[r['family']] if r['role']=='source' else p['panels'][r['family']]
                    zeros=0
                    for trace in p['traces']:
                        data={a['variant_id']:a for a in trace['arms']}
                        zeros+=all(data[vid]['values'][0]==0 for vid in ids)
                    zero_traces+=zeros; zero_parents+=zeros==7
                assert r['zero_service_trace_panels']==zero_traces and r['zero_service_parents']==zero_parents
                assert r['independent_parents']==60 and r['trace_panels']==420
                for field,value in r['static_parent_means'].items():
                    total=Fraction(0)
                    for p in ps:
                        sm={v['variant_id']:v['resources'][field] for v in p['static']}
                        ids=[r['family']] if r['role']=='source' else p['panels'][r['family']]
                        total+=sum(Fraction(sm[vid],len(ids)) for vid in ids)
                    assert Fraction(*value)==total/60
                for col,name in enumerate(config['metrics']):
                    v=r['parent_mean_totals'][name]; actual=float(Fraction(*v)) if col<6 else v
                    assert math.isclose(actual,mean[k,col],rel_tol=0,abs_tol=1e-8)
                    assert math.isclose(r['mean_per_attempt'][name],actual/(12*n),rel_tol=0,abs_tol=1e-8)
                for col,v in enumerate(r['cost_per_accepted_request'],2):
                    sample=np.divide(draw[:,k,col],draw[:,k,0],out=np.full(20000,np.nan),where=draw[:,k,0]>0)
                    equal_interval(v['pointwise_95_interval'],ci(sample))
                    assert v['undefined_bootstrap_draws']==int(np.count_nonzero(draw[:,k,0]==0))
                    if mean[k,0]>0: assert math.isclose(v['estimate'],mean[k,col]/mean[k,0],rel_tol=0,abs_tol=1e-8)
                    if v['exact_estimate'] is not None: assert math.isclose(float(Fraction(*v['exact_estimate'])),v['estimate'],rel_tol=0,abs_tol=1e-8)
            pairs={f'{family}-minus-matched-binary':(2*i,2*i+1) for i,family in enumerate(config['families'])}
            pairs['DA-minus-FHS5']=(0,4)
            for r in (r for r in results['contrasts'] if r['phase']==phase and r['node_count']==n):
                a,b=pairs[r['comparison']]; col=config['metrics'].index(r['cost'])
                valid=(draw[:,a,0]>0)&(draw[:,b,0]>0); sample=np.full(20000,np.nan)
                sample[valid]=draw[valid,a,col]/draw[valid,a,0]-draw[valid,b,col]/draw[valid,b,0]
                equal_interval(r['pointwise_95_interval'],ci(sample))
                assert r['undefined_bootstrap_draws']==int(np.count_nonzero(~valid))
                estimate=mean[a,col]/mean[a,0]-mean[b,col]/mean[b,0]
                assert math.isclose(estimate,r['estimate'],rel_tol=0,abs_tol=1e-8)
            print(json.dumps({'stage':'bootstrap-recomputed','phase':phase,'nodes':n,'replicates':20000}),flush=True)
            save(seal,cellheader|{'status':'all-20000-replicates-and-intervals-passed'}); completed_cells+=1
            save(OUT/'verification-progress.json',{'stage':'bootstrap-arithmetic','blocks':480,'total_blocks':480,'bootstrap_cells':completed_cells,'total_bootstrap_cells':8})
            if (OUT/'PAUSE').exists():
                save(OUT/'verification-progress.json',{'stage':'paused-safe-checkpoint','blocks':480,'bootstrap_cells':completed_cells,'total_bootstrap_cells':8}); return
    verification={'status':'passed','blocks':480,'saved_variant_runs':checked_runs,'bootstrap_replicates':160000,
                  'bootstrap_chunks':320,'arm_ratios_checked':320,'paired_ratios_checked':200,
                  'integer_bootstrap_columns':'exact equality','log2_float_error_bound':'gamma160*max(abs(old),abs(new))+1e-10; gamma160=160*eps/(1-160*eps)',
                  'gamma160':gamma160,'max_log_absolute_difference':max_log_absolute_difference,
                  'max_log_relative_difference':max_log_relative_difference,'reused_exact_route_receipts':reused_route_receipts,
                  'interval_estimate_absolute_tolerance':1e-8,'results_sha256':digest(resultbytes),
                  'verifier_sha256':digest(Path(__file__).read_bytes()),'scope':'same-analyst separate arithmetic implementation; not blinded scientific replay',
                  'new_simulations':0}
    data=(json.dumps(verification,sort_keys=True,separators=(',',':'))+'\n').encode()
    temp=OUT/'verification.json.tmp'; temp.write_bytes(data); temp.replace(OUT/'verification.json')
    progress=json.loads((OUT/'progress.json').read_bytes()); progress['state']='complete-arithmetic-verified'
    temp=OUT/'progress.json.tmp'; temp.write_text(json.dumps(progress,sort_keys=True)+'\n',encoding='utf-8'); temp.replace(OUT/'progress.json')
    print(json.dumps(verification),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--routes-only',action='store_true'); args=parser.parse_args()
    lock=OUT/'VERIFYING.lock'
    with lock.open('xb') as f: f.write((str(os.getpid())+'\n').encode())
    try: run(args.routes_only)
    finally: lock.unlink()
