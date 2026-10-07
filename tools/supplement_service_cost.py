"""S3 archive extraction and parent-cluster bootstrap with safe checkpoints."""
import argparse
from collections import Counter
from fractions import Fraction
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'configs/supplement/service-cost-posthoc-v1.json'
OUT = ROOT / 'results/supplement/service-cost-posthoc-v1'
METRICS = ['accepted_request_count', 'accepted_value', 'traversed_hyperedge_count',
           'signaled_participant_slots', 'unique_signaled_participants',
           'quadratic_coordination_exposure', 'arity_log2_exposure']

def sha(data):
    return hashlib.sha256(data).hexdigest()

def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()

def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name+f'.{os.getpid()}.tmp')
    with temp.open('xb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(temp, path)

def save(path, value):
    atomic(path, encoded(value))

def fingerprint(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode())

def frac(value):
    return [value.numerator, value.denominator]

def summary_from_routes(edges, simulation):
    """Arithmetic over recorded routes, without search or simulation replay."""
    assert len(simulation) == 6
    members = {edge: set(nodes) for edge, nodes in edges}
    histogram, count, value, unique = Counter(), 0, 0, 0
    for index, outcome in enumerate(simulation[1], 1):
        assert len(outcome) == 7 and outcome[0] == index
        route = outcome[2]
        if route is None:
            continue
        assert route and outcome[1][0] != outcome[1][1]
        count += 1; value += outcome[1][2]
        touched = set()
        for edge, start, end in route:
            assert start in members[edge] and end in members[edge]
            histogram[len(members[edge])] += 1
            touched.update(members[edge])
        unique += len(touched)
    costs = {'traversed_hyperedge_count': sum(histogram.values()),
             'signaled_participant_slots': sum(k*v for k,v in histogram.items()),
             'quadratic_coordination_exposure': sum(k*k*v for k,v in histogram.items()),
             'unique_signaled_participants': unique,
             'route_arity_histogram': [[k,histogram[k]] for k in sorted(histogram)]}
    return count, value, costs

def extract_block(raw, record, phase, trace_lookup, config):
    artifact = json.loads(raw)
    stripped = {k:v for k,v in artifact.items() if k not in ('artifact_fingerprint','summary_fingerprint')}
    assert fingerprint(stripped) == artifact['artifact_fingerprint'] == record['artifact_fingerprint']
    witness = artifact['result_witness']
    assert fingerprint(witness) == artifact['result_fingerprint'] == record['result_fingerprint']
    assert witness['manifest_fingerprint'] == artifact['manifest_fingerprint']
    assert witness['seed_ledger_fingerprint'] == artifact['seed_ledger_fingerprint']
    meta = artifact['block']; n = meta['node_count']; key = record['block_key']
    assert key == f"n{n:04d}-r{meta['parent_replicate']:04d}-{meta['parent_model']}"
    topologies = {v[0]: v[2][1] for v in witness['variants']}
    registry = {v['variant_id']:v for v in artifact['variants']}
    assert len(registry) == len(witness['variants']) == len(topologies)
    panels = {p['source_variant_id']:p['binary_variant_ids'] for p in artifact['resource_panels']}
    assert set(panels) == set(config['families'])
    static = []
    for wid, family, topology, _ in witness['variants']:
        edges = topology[1]; sizes = [len(m) for _,m in edges]
        resources = dict(node_count=len(topology[0]), hyperedge_count=len(edges), incidence_count=sum(sizes),
                         maximum_arity=max(sizes), pairwise_member_exposure=sum(k*(k-1)//2 for k in sizes))
        assert registry[wid]['family'] == family and registry[wid]['resources'] == resources
        static.append({'variant_id':wid,'family':family,'resources':resources})
    rows=[]; seen=set(); held={r[0]:r for r in witness['held_out']}
    assert len(held) == len(artifact['held_out']) == 7
    for run in artifact['held_out']:
        regime=run['trace_seed']['regime_id']; wr=held[regime]
        assert regime not in seen; seen.add(regime)
        assert wr[3] == run['paired_manifest_fingerprint']
        reference = trace_lookup[key,regime,'demand-aware']
        assert reference['paired_manifest_fingerprint'] == wr[3]
        simulations = dict(wr[4]); assert set(simulations) == set(registry)
        requests = [o[1] for o in next(iter(simulations.values()))[1]]
        request_total=sum(r[2] for r in requests)
        arms=[]
        for variant in run['variants']:
            vid=variant['variant_id']; simulation=simulations[vid]
            assert len(simulation[1]) == variant['horizon'] == 12*n
            assert [o[1] for o in simulation[1]] == requests
            count,value,costs=summary_from_routes(topologies[vid],simulation)
            assert count == variant['accepted_request_count'] and value == variant['accepted_value']
            assert costs == variant['dynamic_costs']
            assert Fraction(*variant['success_rate']) == Fraction(count,12*n)
            for pos,name in enumerate(('tau_dep','tau_nopath','tau_rej'),3):
                assert variant[name] == {'observed':simulation[pos][0], 'request_index':simulation[pos][1]}
            if variant['family'] in panels:
                evidence=trace_lookup[key,regime,variant['family']]
                assert evidence['paired_manifest_fingerprint'] == wr[3] and evidence['scope'] == reference['scope']
                assert sorted(panels[vid]) == sorted(x[0] for x in evidence['binary_arm_events'])
                assert evidence['source_event'] == variant['tau_nopath']['observed']
                assert dict(evidence['binary_arm_events']) == {bid:simulations[bid][4][0] for bid in panels[vid]}
            capital=sum(balance for _,balances in simulation[0] for _,balance in balances)
            assert capital == 120*n
            vals=[count,value,costs['traversed_hyperedge_count'],costs['signaled_participant_slots'],
                  costs['unique_signaled_participants'],costs['quadratic_coordination_exposure']]
            logcost=sum(k*math.log2(k)*c for k,c in costs['route_arity_histogram'])
            assert all(type(v) is int and v>=0 for v in vals)
            arms.append({'variant_id':vid,'family':variant['family'],'values':vals,
                         'arity_log2_exposure':logcost,'route_arity_histogram':costs['route_arity_histogram'],
                         'locked_capital':capital})
        assert set(a['variant_id'] for a in arms) == set(registry)
        rows.append({'regime_id':regime,'scope':reference['scope'],'paired_manifest_fingerprint':wr[3],
                     'attempted_count':12*n,'attempted_value':request_total,'arms':arms})
    assert Counter(r['scope'] for r in rows) == {'same_distribution':4,'distribution_shift':3}
    assert all(1<=len(v)<=config['maximum_binary_arms'] and len(v)==len(set(v)) for v in panels.values())
    return {'phase':phase,'parent_graph_id':key,'node_count':n,'parent_model':meta['parent_model'],
            'parent_replicate':meta['parent_replicate'],'raw_bytes':len(raw),'raw_sha256':sha(raw),
            'artifact_fingerprint':artifact['artifact_fingerprint'],'result_fingerprint':artifact['result_fingerprint'],
            'panels':panels,'static':static,'traces':rows}

def parent_values(parent, families):
    """Totals over seven traces, scaled by two for bracket-arm averages."""
    totals=np.zeros((8,7),dtype=np.float64)
    for trace in parent['traces']:
        arms={a['variant_id']:a for a in trace['arms']}
        for i,family in enumerate(families):
            for j,ids in enumerate(([family],parent['panels'][family])):
                for vid in ids:
                    a=arms[vid]; totals[2*i+j]+=np.array(a['values']+[a['arity_log2_exposure']])*(2/len(ids))
    assert np.array_equal(totals[:,:6], np.rint(totals[:,:6]))
    assert np.max(totals[:,:6]) < 2**53/60
    return totals

def sample_indices(config,phase,n,rep):
    result=[]
    for offset,model in enumerate(config['models']):
        seed=f"{config['bootstrap_seed']}|{phase}|{n}|{rep}|{model}"
        rng=random.Random(int.from_bytes(hashlib.sha256(seed.encode()).digest(),'big'))
        result.extend(offset*20+rng.randrange(20) for _ in range(20))
    return result

def bootstrap(config,phase,n,parents,start,stop):
    counts=np.zeros((stop-start,60),dtype=np.int64)
    for j,rep in enumerate(range(start,stop)):
        for i in sample_indices(config,phase,n,rep): counts[j,i]+=1
    flat=parents.reshape(60,56)
    result=(counts @ flat).reshape(stop-start,8,7)
    assert np.array_equal(result[:,:,:6],np.rint(result[:,:,:6]))
    assert np.max(result[:,:,:6]) < 2**53
    return result

def interval(values):
    if not np.isfinite(values).all(): return None
    ordered=np.sort(values)
    return [float(ordered[499]),float(ordered[19499])]

def summarize(config,phase,n,parents,draws):
    array=np.array([parent_values(p,config['families']) for p in parents])
    totals=array.sum(axis=0)
    arms=[]; contrasts=[]
    for i,family in enumerate(config['families']):
        for j,role in enumerate(('source','binary_panel')):
            k=2*i+j; sums=totals[k]; ratios=[]
            zero_traces=0; zero_parents=0; staticmeans={}
            for parent in parents:
                parent_success=Fraction(0)
                for trace in parent['traces']:
                    mapping={a['variant_id']:a for a in trace['arms']}
                    ids=[family] if j==0 else parent['panels'][family]
                    success=sum(Fraction(mapping[v]['values'][0],len(ids)) for v in ids)
                    parent_success+=success; zero_traces+=success==0
                zero_parents+=parent_success==0
            for metric in ('hyperedge_count','incidence_count','maximum_arity','pairwise_member_exposure'):
                vals=[]
                for p in parents:
                    sm={v['variant_id']:v['resources'][metric] for v in p['static']}
                    ids=[family] if j==0 else p['panels'][family]
                    vals.append(sum(Fraction(sm[v],len(ids)) for v in ids))
                staticmeans[metric]=frac(sum(vals)/60)
            for col,name in enumerate(METRICS[2:],2):
                denominator=draws[:,k,0]; undefined=int(np.count_nonzero(denominator==0))
                samples=np.divide(draws[:,k,col],denominator,out=np.full(20000,np.nan),where=denominator!=0)
                estimate=None if sums[0]==0 else float(sums[col]/sums[0])
                exact=frac(Fraction(int(sums[col]),int(sums[0]))) if col<6 and sums[0]>0 else None
                ratios.append({'cost':name,'estimate':estimate,'exact_estimate':exact,
                               'pointwise_95_interval':interval(samples),'undefined_bootstrap_draws':undefined})
            arms.append({'phase':phase,'node_count':n,'family':family,'role':role,'independent_parents':60,
                         'parent_mean_totals':{name:(frac(Fraction(int(sums[c]),840)) if c<6 else float(sums[c]/840)) for c,name in enumerate(METRICS)},
                         'mean_per_attempt':{name:float(sums[c]/(840*12*n)) for c,name in enumerate(METRICS)},
                         'static_parent_means':staticmeans,'locked_capital':120*n,
                         'zero_service_trace_panels':int(zero_traces),'trace_panels':420,'zero_service_parents':int(zero_parents),
                         'cost_per_accepted_request':ratios})
    comparisons=[(2*i,2*i+1,f'{family}-minus-matched-binary') for i,family in enumerate(config['families'])]+[(0,4,'DA-minus-FHS5')]
    for a,b,name in comparisons:
        for col,cost in enumerate(METRICS[2:],2):
            sa,sb=draws[:,a,0],draws[:,b,0]; valid=(sa>0)&(sb>0)
            sample=np.full(20000,np.nan); sample[valid]=draws[valid,a,col]/sa[valid]-draws[valid,b,col]/sb[valid]
            exact=None
            if totals[a,0]>0 and totals[b,0]>0 and col<6:
                exact=frac(Fraction(int(totals[a,col]),int(totals[a,0]))-Fraction(int(totals[b,col]),int(totals[b,0])))
            estimate=None if totals[a,0]==0 or totals[b,0]==0 else float(totals[a,col]/totals[a,0]-totals[b,col]/totals[b,0])
            contrasts.append({'phase':phase,'node_count':n,'comparison':name,'cost':cost,'estimate':estimate,
                              'exact_estimate':exact,'pointwise_95_interval':interval(sample),'undefined_bootstrap_draws':int(np.count_nonzero(~valid))})
    return arms,contrasts

def run(args):
    config=json.loads(CONFIG.read_bytes()); output=args.output.resolve(); output.mkdir(parents=True,exist_ok=True)
    binding={'config_sha256':sha(CONFIG.read_bytes()),'script_sha256':sha(Path(__file__).read_bytes()),
             'source_sha256':config['source_sha256'],'python':platform.python_version(),'numpy':np.__version__}
    lock=output/'RUNNING.lock'
    with lock.open('xb') as f: f.write(encoded({'pid':os.getpid(),'argv':sys.argv}))
    start=time.monotonic(); blocks=chunks=0; newunits=0
    def status(state,**extra):
        save(output/'progress.json',{'state':state,'extracted_blocks':blocks,'total_blocks':480,
                                    'extraction_percent':round(blocks/480*100,3),'bootstrap_chunks':chunks,'total_bootstrap_chunks':320,
                                    'bootstrap_percent':round(chunks/320*100,3),'elapsed_seconds_this_invocation':round(time.monotonic()-start,3),**extra})
    def pause():
        return (output/'PAUSE').exists() or (args.stop_after_units is not None and newunits>=args.stop_after_units)
    try:
        if (output/'binding.json').exists(): assert json.loads((output/'binding.json').read_bytes())==binding,'resume binding changed'
        else: save(output/'binding.json',binding)
        phase_parents={}
        for phase in ('formal','confirmation'):
            raw=(ROOT/f'results/inference/{phase}-phase-evidence.json').read_bytes()
            assert sha(raw)==config['source_sha256'][phase]
            evidence=json.loads(raw); assert evidence['status']=='complete-strict-replay'
            receipt=json.loads((ROOT/f'results/diagnostics/independent-replay/20260922-v1/{phase}-phase.success.json').read_bytes())
            assert receipt['exit_code']==0 and receipt['output_sha256']==sha(raw) and receipt['output_bytes']==len(raw)
            lookup={(r['parent_graph_id'],r['regime_id'],r['source_family']):r for r in evidence['trace_contrasts'] if r['metric']=='failure_risk'}
            records=evidence['block_registry']; assert len(records)==len({r['block_key'] for r in records})==240
            parents=[]
            for record in sorted(records,key=lambda r:r['block_key']):
                target=output/'parents'/f"{phase}-{record['block_key']}.json"; seal=target.with_suffix('.sha256')
                if target.exists():
                    assert sha(target.read_bytes())==seal.read_text().strip()
                    parent=json.loads(target.read_bytes())
                    assert parent['artifact_fingerprint']==record['artifact_fingerprint'] and parent['result_fingerprint']==record['result_fingerprint']
                else:
                    status('extracting-block',phase=phase,current_block=record['block_key'])
                    began=time.monotonic()
                    source=ROOT/f'outputs/{phase}/synthetic-{phase}-v1'/record['path']
                    assert source.resolve().is_relative_to((ROOT/f'outputs/{phase}/synthetic-{phase}-v1/blocks').resolve())
                    parent=extract_block(source.read_bytes(),record,phase,lookup,config)
                    save(target,parent); atomic(seal,(sha(target.read_bytes())+'\n').encode()); newunits+=1
                    print(json.dumps({'stage':'extraction','phase':phase,'block':record['block_key'],'seconds':round(time.monotonic()-began,3),'completed':blocks+1}),flush=True)
                blocks+=1; parents.append(parent); status('extraction-checkpoint',phase=phase)
                if pause(): status('paused-safe-checkpoint'); return
            phase_parents[phase]=parents
        armresults=[]; comparisonresults=[]
        for phase,allparents in phase_parents.items():
            for n in config['node_counts']:
                parents=sorted((p for p in allparents if p['node_count']==n),key=lambda p:(config['models'].index(p['parent_model']),p['parent_replicate']))
                assert len(parents)==60
                assert [(p['parent_model'],p['parent_replicate']) for p in parents]==[(m,r) for m in config['models'] for r in range(20)]
                array=np.array([parent_values(p,config['families']) for p in parents]); draws=[]
                for begin in range(0,20000,500):
                    target=output/'bootstrap'/f'{phase}-n{n:04d}-{begin:05d}.bin.gz'; seal=target.with_suffix('.json')
                    if target.exists():
                        metadata=json.loads(seal.read_bytes()); compressed=target.read_bytes()
                        assert metadata=={'sha256':sha(compressed),'phase':phase,'nodes':n,'start':begin,'stop':begin+500,'shape':[500,8,7],'dtype':'<f8'}
                    else:
                        status('bootstrap',phase=phase,nodes=n,start=begin)
                        result=bootstrap(config,phase,n,array,begin,begin+500)
                        compressed=gzip.compress(result.astype('<f8').tobytes(),mtime=0)
                        atomic(target,compressed); save(seal,{'sha256':sha(compressed),'phase':phase,'nodes':n,'start':begin,'stop':begin+500,'shape':[500,8,7],'dtype':'<f8'}); newunits+=1
                    draws.append(np.frombuffer(gzip.decompress(compressed),dtype='<f8').reshape(500,8,7)); chunks+=1
                    status('bootstrap-checkpoint',phase=phase,nodes=n)
                    if pause(): status('paused-safe-checkpoint'); return
                a,c=summarize(config,phase,n,parents,np.concatenate(draws)); armresults.extend(a); comparisonresults.extend(c)
        save(output/'results.json',{'schema':'S3-descriptive-v1','interpretation':config['interpretation'],'arms':armresults,'contrasts':comparisonresults,
                                    'new_simulations':0,'pointwise_intervals':True,'multiplicity_adjusted':False})
        status('generated-pending-arithmetic-verification')
    except BaseException as exc:
        status('stopped-on-error',error=repr(exc)); raise
    finally:
        lock.unlink()

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--stop-after-units',type=int); run(parser.parse_args())
