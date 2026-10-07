"""Exact S4 half-window reanalysis from byte-bound saved event observations."""
import argparse
from collections import Counter
from fractions import Fraction
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'configs/supplement/short-window-posthoc-v1.json'
OUT=ROOT/'results/supplement/short-window-posthoc-v1'
S3=ROOT/'results/supplement/service-cost-posthoc-v1'

def sha(data): return hashlib.sha256(data).hexdigest()
def encode(value): return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    with tmp.open('xb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,path)
def save(path,value): atomic(path,encode(value))
def frac(v): return [v.numerator,v.denominator]

def observation(observed,t,original_h,h):
    assert type(observed) is bool and type(t) is int and 0<=t<=original_h and 0<h<=original_h
    assert observed or t==original_h
    return min(t,h),int(observed and t<=h)

def trace_difference(events,source,reference,h,original_h):
    assert 1<=len(reference)<=2 and len(set(reference))==len(reference)
    a=observation(*events[source],original_h,h)
    bs=[observation(*events[v],original_h,h) for v in reference]
    result=[]
    for col in range(2):
        delta=2*(Fraction(a[col])-sum(Fraction(b[col],len(bs)) for b in bs))
        assert delta.denominator==1
        result.append(delta.numerator)
    return result

def totals_from_events(p,config):
    totals=np.zeros((2,3,5,2),dtype=np.int64)
    for trace in p['events']:
        ev={v['variant_id']:(v['observed'],v['request_index']) for v in trace['variants']}
        scopes=[0,config['scopes'].index(trace['scope'])]
        for w,window in enumerate(config['windows']):
            h=config['requests_per_node'][window]*p['node_count']
            comparisons=[(f,p['panels'][f]) for f in config['families']]+[('demand-aware',['fhs5'])]
            for c,(source,reference) in enumerate(comparisons):
                delta=trace_difference(ev,source,reference,h,12*p['node_count'])
                for scope in scopes: totals[w,scope,c]+=delta
    return totals

def extract(raw,old,phase,evidence_lookup,config):
    assert sha(raw)==old['raw_sha256'] and len(raw)==old['raw_bytes'],'raw source no longer matches audited S3 bytes'
    a=json.loads(raw); key=old['parent_graph_id']; n=old['node_count']
    assert a['artifact_fingerprint']==old['artifact_fingerprint'] and a['result_fingerprint']==old['result_fingerprint']
    assert a['block']['node_count']==n and a['block']['parent_model']==old['parent_model'] and a['block']['parent_replicate']==old['parent_replicate']
    assert {p['source_variant_id']:p['binary_variant_ids'] for p in a['resource_panels']}==old['panels']
    witness={r[0]:r for r in a['result_witness']['held_out']}
    prior={t['regime_id']:t for t in old['traces']}
    events=[]
    for run in a['held_out']:
        regime=run['trace_seed']['regime_id']; wr=witness[regime]; sims=dict(wr[4])
        assert wr[3]==run['paired_manifest_fingerprint']==prior[regime]['paired_manifest_fingerprint']
        variants=[]
        for v in run['variants']:
            e=v['tau_nopath']; vid=v['variant_id']; assert v['horizon']==12*n
            assert [e['observed'],e['request_index']]==sims[vid][4]
            observation(e['observed'],e['request_index'],12*n,12*n)
            variants.append({'variant_id':vid,'family':v['family'],'observed':e['observed'],'request_index':e['request_index']})
        ev={v['variant_id']:(v['observed'],v['request_index']) for v in variants}
        assert set(ev)==set(sims)==set(v['variant_id'] for v in a['variants'])
        scope=prior[regime]['scope']
        for family in config['families']:
            ids=old['panels'][family]
            for col,metric in enumerate(config['metrics']):
                e=evidence_lookup[key,regime,family,metric]
                assert e['scope']==scope and e['paired_manifest_fingerprint']==wr[3] and e['horizon']==12*n
                assert e['source_event']==ev[family][0]
                assert dict(e['binary_arm_events'])=={v:ev[v][0] for v in ids}
                delta=trace_difference(ev,family,ids,12*n,12*n)[col]
                expected=Fraction(delta,2*(12*n if col==0 else 1))
                assert expected==Fraction(*e['value']),'full-window endpoint mismatch'
        events.append({'regime_id':regime,'scope':scope,'paired_manifest_fingerprint':wr[3],'variants':variants})
    assert len(events)==len({e['regime_id'] for e in events})==7
    assert Counter(t['scope'] for t in events)=={'same_distribution':4,'distribution_shift':3}
    p={k:old[k] for k in ('parent_graph_id','node_count','parent_model','parent_replicate','raw_sha256','raw_bytes','artifact_fingerprint','result_fingerprint','panels')}
    p.update({'phase':phase,'events':events}); p['integer_sums']=totals_from_events(p,config).tolist()
    return p

def samples(config,phase,n,rep):
    ids=[]
    for g,model in enumerate(config['models']):
        rng=random.Random(int.from_bytes(hashlib.sha256(f"{config['bootstrap_seed']}|{phase}|{n}|{rep}|{model}".encode()).digest(),'big'))
        ids.extend(g*20+rng.randrange(20) for _ in range(20))
    return ids

def bootstrap(config,phase,n,array,start):
    weights=np.zeros((500,60),dtype=np.int64)
    for i,rep in enumerate(range(start,start+500)):
        for index in samples(config,phase,n,rep): weights[i,index]+=1
    return (weights @ array.reshape(60,60)).reshape(500,2,3,5,2)

def result_item(phase,n,window,scope,comparison,metric,numerator,denominator,draws=None):
    exact={'estimate':frac(Fraction(int(numerator),denominator))}
    if draws is not None:
        order=np.sort(draws)
        exact['lower']=frac(Fraction(int(order[499]),denominator)); exact['upper']=frac(Fraction(int(order[19499]),denominator))
    return {'phase':phase,'node_count':n,'window':window,'scope':scope,'comparison':comparison,'metric':metric,
            'independent_parents':60,'exact':exact,'display':{k:float(Fraction(*v)) for k,v in exact.items()}}

def summarize(config,phase,n,array,draws):
    summed=array.sum(axis=0); results=[]; changes=[]
    for w,window in enumerate(config['windows']):
        h=config['requests_per_node'][window]*n
        for scope,count in enumerate(config['traces_per_scope']):
            for c,name in enumerate(config['comparisons']):
                for m,metric in enumerate(config['metrics']):
                    den=2*60*count*(h if m==0 else 1)
                    result=result_item(phase,n,window,config['scopes'][scope],name,metric,summed[w,scope,c,m],den,
                                       draws[:,w,scope,c,m] if scope==0 else None)
                    result['horizon']=h; results.append(result)
    for scope,count in enumerate(config['traces_per_scope']):
        for c,name in enumerate(config['comparisons']):
            for m,metric in enumerate(config['metrics']):
                factor=2 if m==0 else 1
                total=factor*summed[0,scope,c,m]-summed[1,scope,c,m]
                den=2*60*count*(12*n if m==0 else 1)
                values=factor*draws[:,0,scope,c,m]-draws[:,1,scope,c,m]
                changes.append(result_item(phase,n,'half-minus-full',config['scopes'][scope],name,metric,total,den,values if scope==0 else None))
    return results,changes

def run(args):
    config=json.loads(CONFIG.read_bytes()); out=args.output.resolve(); out.mkdir(parents=True,exist_ok=True)
    binding={'config_sha256':sha(CONFIG.read_bytes()),'script_sha256':sha(Path(__file__).read_bytes()),
             'python':platform.python_version(),'numpy':np.__version__,'source_sha256':config['source_sha256'],
             's3_manifest_sha256':config['s3_manifest_sha256'],'s3_verification_sha256':config['s3_verification_sha256']}
    lock=out/'RUNNING.lock'
    with lock.open('xb') as f: f.write(encode({'pid':os.getpid(),'argv':sys.argv}))
    blocks=chunks=units=0; started=time.monotonic()
    def status(state,**extras):
        save(out/'progress.json',{'state':state,'extracted_blocks':blocks,'total_blocks':480,'extraction_percent':round(blocks/480*100,3),
                                  'bootstrap_chunks':chunks,'total_bootstrap_chunks':320,'bootstrap_percent':round(chunks/320*100,3),
                                  'elapsed_seconds_this_invocation':round(time.monotonic()-started,3),**extras})
    def pause(): return (out/'PAUSE').exists() or (args.stop_after_units is not None and units>=args.stop_after_units)
    try:
        if (out/'binding.json').exists(): assert json.loads((out/'binding.json').read_bytes())==binding,'resume binding changed'
        else: save(out/'binding.json',binding)
        data=(S3/'delivery-manifest.json').read_bytes(); assert sha(data)==config['s3_manifest_sha256']
        inventory={r['path']:r for r in json.loads(data)['files']}
        proof=(S3/'verification.json').read_bytes(); assert sha(proof)==config['s3_verification_sha256'] and json.loads(proof)['status']=='passed'
        phases={}
        for phase in ('formal','confirmation'):
            raw=(ROOT/f'results/inference/{phase}-phase-evidence.json').read_bytes()
            assert sha(raw)==config['source_sha256'][phase]; e=json.loads(raw); assert e['status']=='complete-strict-replay'
            receipt=json.loads((ROOT/f'results/diagnostics/independent-replay/20260922-v1/{phase}-phase.success.json').read_bytes())
            assert receipt['exit_code']==0 and receipt['output_sha256']==sha(raw) and receipt['output_bytes']==len(raw)
            lookup={(r['parent_graph_id'],r['regime_id'],r['source_family'],r['metric']):r for r in e['trace_contrasts']}
            records=e['block_registry']; assert len(records)==len({r['block_key'] for r in records})==240
            parents=[]
            for record in sorted(records,key=lambda r:r['block_key']):
                key=record['block_key']; oldpath=S3/'parents'/f'{phase}-{key}.json'; oldraw=oldpath.read_bytes()
                registered=inventory[oldpath.relative_to(ROOT).as_posix()]
                assert sha(oldraw)==registered['sha256'] and len(oldraw)==registered['bytes']
                old=json.loads(oldraw); assert old['artifact_fingerprint']==record['artifact_fingerprint'] and old['result_fingerprint']==record['result_fingerprint']
                target=out/'parents'/f'{phase}-{key}.json'
                if target.exists():
                    envelope=json.loads(target.read_bytes()); assert envelope['payload_sha256']==sha(encode(envelope['payload']))
                    p=envelope['payload']; assert p['raw_sha256']==old['raw_sha256'] and p['parent_graph_id']==key
                    assert p['integer_sums']==totals_from_events(p,config).tolist()
                else:
                    status('extracting-events',phase=phase,current_block=key); began=time.monotonic()
                    rawpath=ROOT/f'outputs/{phase}/synthetic-{phase}-v1'/record['path']
                    assert rawpath.resolve().is_relative_to((ROOT/f'outputs/{phase}/synthetic-{phase}-v1/blocks').resolve())
                    p=extract(rawpath.read_bytes(),old,phase,lookup,config)
                    save(target,{'payload':p,'payload_sha256':sha(encode(p))}); units+=1
                    print(json.dumps({'stage':'event-extraction','phase':phase,'block':key,'seconds':round(time.monotonic()-began,3),'completed':blocks+1}),flush=True)
                parents.append(p); blocks+=1; status('event-checkpoint',phase=phase)
                if pause(): status('paused-safe-checkpoint'); return
            phases[phase]=parents
        s1raw=(ROOT/'results/supplement/da-fhs5-posthoc-v1/results.json').read_bytes(); assert sha(s1raw)==config['s1_results_sha256']
        s1={(r['phase'],r['node_count'],r['metric']):r for r in json.loads(s1raw)['comparisons']}
        rows=[]; changes=[]
        for phase,ps in phases.items():
            for n in config['node_counts']:
                parents=sorted((p for p in ps if p['node_count']==n),key=lambda p:(config['models'].index(p['parent_model']),p['parent_replicate']))
                assert [(p['parent_model'],p['parent_replicate']) for p in parents]==[(m,r) for m in config['models'] for r in range(20)]
                array=np.array([p['integer_sums'] for p in parents],dtype=np.int64); saved=[]
                for start in range(0,20000,500):
                    path=out/'bootstrap'/f'{phase}-n{n:04d}-{start:05d}.bin.gz'; receipt=path.with_suffix('.json')
                    if path.exists() and receipt.exists():
                        compressed=path.read_bytes(); meta=json.loads(receipt.read_bytes())
                        assert meta=={'phase':phase,'node_count':n,'start':start,'shape':[500,2,3,5,2],'dtype':'<i8','sha256':sha(compressed)}
                    else:
                        status('bootstrap',phase=phase,node_count=n,start=start)
                        compressed=gzip.compress(bootstrap(config,phase,n,array,start).astype('<i8').tobytes(),mtime=0)
                        atomic(path,compressed); save(receipt,{'phase':phase,'node_count':n,'start':start,'shape':[500,2,3,5,2],'dtype':'<i8','sha256':sha(compressed)}); units+=1
                    saved.append(np.frombuffer(gzip.decompress(compressed),dtype='<i8').reshape(500,2,3,5,2)); chunks+=1
                    status('bootstrap-checkpoint',phase=phase,node_count=n)
                    if pause(): status('paused-safe-checkpoint'); return
                windowrows,diffs=summarize(config,phase,n,array,np.concatenate(saved))
                for r in windowrows:
                    if r['window']=='full' and r['scope']=='combined' and r['comparison']=='DA-minus-FHS5':
                        assert r['exact']['estimate']==s1[phase,n,r['metric']]['exact']['estimate']
                rows.extend(windowrows); changes.extend(diffs)
        save(out/'results.json',{'schema':'S4-window-sensitivity-v1','interpretation':config['interpretation'],'contrasts':rows,'window_changes':changes,
                                  'pointwise_intervals':True,'multiplicity_adjusted':False,'new_simulations':0,'prefix_costs_computed':False})
        status('generated-pending-arithmetic-verification')
    except BaseException as exc:
        status('stopped-on-error',error=repr(exc)); raise
    finally: lock.unlink()

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,default=OUT); parser.add_argument('--stop-after-units',type=int)
    run(parser.parse_args())
