"""Separate integer/Fraction S4 arithmetic checker; no executor imports or simulation."""
import argparse
from collections import Counter
from fractions import Fraction
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/supplement/short-window-posthoc-v1'
S3=ROOT/'results/supplement/service-cost-posthoc-v1'
def digest(b): return hashlib.sha256(b).hexdigest()
def enc(v): return (json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
def write(p,v):
    p.parent.mkdir(parents=True,exist_ok=True); t=p.with_name(p.name+f'.{os.getpid()}.tmp')
    with t.open('xb') as f: f.write(enc(v)); f.flush(); os.fsync(f.fileno())
    os.replace(t,p)
def pair(f): return [f.numerator,f.denominator]

def endpoint(event,h,H):
    flag,t=event
    assert type(flag) is bool and type(t) is int and 0<=t<=H
    assert flag or t==H
    # Discrete survival-area identity: sum_{j=0}^{h-1} 1{T>j}.
    area=sum(1 for j in range(h) if t>j)
    risk=1 if flag and t<=h else 0
    return Fraction(area,h),Fraction(risk)

def check_parent(p,raw,cfg,evidence):
    a=json.loads(raw); H=12*p['node_count']
    assert digest(raw)==p['raw_sha256'] and len(raw)==p['raw_bytes']
    assert a['artifact_fingerprint']==p['artifact_fingerprint'] and a['result_fingerprint']==p['result_fingerprint']
    assert a['block']['node_count']==p['node_count'] and a['block']['parent_model']==p['parent_model'] and a['block']['parent_replicate']==p['parent_replicate']
    panels={r['source_variant_id']:r['binary_variant_ids'] for r in a['resource_panels']}
    assert panels==p['panels']
    assert all(1<=len(v)<=2 and len(v)==len(set(v)) for v in panels.values())
    saved={r['regime_id']:r for r in p['events']}
    runs={r['trace_seed']['regime_id']:r for r in a['held_out']}
    witnesses={r[0]:r for r in a['result_witness']['held_out']}
    assert len(saved)==7 and set(saved)==set(runs)==set(witnesses)
    assert Counter(r['scope'] for r in saved.values())=={'same_distribution':4,'distribution_shift':3}
    val=np.zeros((2,3,5,2),dtype=np.int64)
    for rid,run in runs.items():
        recorded=saved[rid]; wr=witnesses[rid]
        assert run['paired_manifest_fingerprint']==recorded['paired_manifest_fingerprint']==wr[3]
        ev={v['variant_id']:(v['tau_nopath']['observed'],v['tau_nopath']['request_index']) for v in run['variants']}
        assert ev=={v['variant_id']:(v['observed'],v['request_index']) for v in recorded['variants']}
        assert set(ev)==set(v['variant_id'] for v in a['variants'])==set(v[0] for v in wr[4])
        assert ev=={vid:tuple(sim[4]) for vid,sim in wr[4]}
        assert all(v['horizon']==H for v in run['variants'])
        scopes=[0,cfg['scopes'].index(recorded['scope'])]
        for w,mult in enumerate((6,12)):
            h=mult*p['node_count']; observations={v:endpoint(e,h,H) for v,e in ev.items()}
            for c,source in enumerate(cfg['families']+['demand-aware']):
                refs=panels[source] if c<4 else ['fhs5']
                for m in range(2):
                    delta=observations[source][m]-sum(observations[r][m] for r in refs)/len(refs)
                    integer=delta*2*(h if m==0 else 1); assert integer.denominator==1
                    for scope in scopes: val[w,scope,c,m]+=integer.numerator
                    if w==1 and c<4:
                        e=evidence[p['parent_graph_id'],rid,source,cfg['metrics'][m]]
                        assert delta==Fraction(*e['value']) and e['scope']==recorded['scope'] and e['horizon']==H
                        assert e['source_event']==ev[source][0] and dict(e['binary_arm_events'])=={r:ev[r][0] for r in refs}
    np.testing.assert_array_equal(val,np.asarray(p['integer_sums'],dtype=np.int64))
    return val

def selection(cfg,phase,n,rep):
    output=[]
    for g,model in enumerate(cfg['models']):
        seed=int(hashlib.sha256('|'.join(map(str,[cfg['bootstrap_seed'],phase,n,rep,model])).encode()).hexdigest(),16)
        rng=random.Random(seed)
        output.extend(g*20+rng.randrange(0,20) for _ in range(20))
    assert [sum(g*20<=i<(g+1)*20 for i in output) for g in range(3)]==[20,20,20]
    return output

def check_rows(cfg,phase,n,array,draws,result):
    def compare(row,num,den,vals):
        expected={'estimate':pair(Fraction(int(num),den))}
        if vals is not None:
            v=sorted(map(int,vals)); expected.update(lower=pair(Fraction(v[499],den)),upper=pair(Fraction(v[19499],den)))
        assert row['exact']==expected
        assert row['display']=={k:float(Fraction(*v)) for k,v in expected.items()}
        assert row['independent_parents']==60
    lookup={(r['window'],r['scope'],r['comparison'],r['metric']):r for r in result['contrasts'] if r['phase']==phase and r['node_count']==n}
    changes={(r['scope'],r['comparison'],r['metric']):r for r in result['window_changes'] if r['phase']==phase and r['node_count']==n}
    assert len(lookup)==60 and len(changes)==30
    sums=array.sum(axis=0)
    for scope,count in enumerate([7,4,3]):
        for c,name in enumerate(cfg['comparisons']):
            for m,metric in enumerate(cfg['metrics']):
                for w,window in enumerate(['half','full']):
                    h=(6 if w==0 else 12)*n; row=lookup[window,cfg['scopes'][scope],name,metric]
                    assert row['horizon']==h
                    compare(row,sums[w,scope,c,m],120*count*(h if m==0 else 1),draws[:,w,scope,c,m] if scope==0 else None)
                # Paired changes computed from normalized Fractions, not independent intervals.
                den=120*count*(12*n if m==0 else 1); factor=2 if m==0 else 1
                compare(changes[cfg['scopes'][scope],name,metric],factor*sums[0,scope,c,m]-sums[1,scope,c,m],den,
                        factor*draws[:,0,scope,c,m]-draws[:,1,scope,c,m] if scope==0 else None)

def run(args):
    cfgraw=(ROOT/'configs/supplement/short-window-posthoc-v1.json').read_bytes(); cfg=json.loads(cfgraw)
    result_bytes=(OUT/'results.json').read_bytes(); result=json.loads(result_bytes)
    assert len(result['contrasts'])==480 and len(result['window_changes'])==240
    assert result['new_simulations']==0 and result['prefix_costs_computed'] is False
    assert result['pointwise_intervals'] is True and result['multiplicity_adjusted'] is False
    inventory_bytes=(S3/'delivery-manifest.json').read_bytes(); assert digest(inventory_bytes)==cfg['s3_manifest_sha256']
    inventory={r['path']:r for r in json.loads(inventory_bytes)['files']}
    proof=(S3/'verification.json').read_bytes(); assert digest(proof)==cfg['s3_verification_sha256'] and json.loads(proof)['status']=='passed'
    bind={'checker_sha256':digest(Path(__file__).read_bytes()),'config_sha256':digest(cfgraw),'results_sha256':digest(result_bytes),
          's3_manifest_sha256':digest(inventory_bytes),'python':sys.version,'numpy':np.__version__}
    dest=OUT/'verification-checkpoints'; dest.mkdir(exist_ok=True)
    lock=OUT/'VERIFYING.lock'
    with lock.open('xb') as f: f.write(enc({'pid':os.getpid(),'argv':sys.argv}))
    parents_done=cells_done=units=0; began=time.monotonic()
    def status(state,**extra):
        write(OUT/'verification-progress.json',{'state':state,'parents_verified':parents_done,'total_parents':480,
              'cells_verified':cells_done,'total_cells':8,'elapsed_seconds_this_invocation':round(time.monotonic()-began,3),**extra})
    def stop(): return (OUT/'PAUSE').exists() or (args.stop_after_units is not None and units>=args.stop_after_units)
    try:
        if (dest/'binding.json').exists(): assert json.loads((dest/'binding.json').read_bytes())==bind
        else: write(dest/'binding.json',bind)
        arrays={}; parent_hashes={}
        for phase in ['formal','confirmation']:
            phasebytes=(ROOT/f'results/inference/{phase}-phase-evidence.json').read_bytes(); assert digest(phasebytes)==cfg['source_sha256'][phase]
            ev=json.loads(phasebytes); assert ev['status']=='complete-strict-replay'
            reg={r['block_key']:r for r in ev['block_registry']}; assert len(reg)==240
            evidence={(e['parent_graph_id'],e['regime_id'],e['source_family'],e['metric']):e for e in ev['trace_contrasts']}
            for n in cfg['node_counts']:
                array=[]; hashes=[]
                for model in cfg['models']:
                    for rep in range(20):
                        key=f'n{n:04d}-r{rep:04d}-{model}'; path=OUT/'parents'/f'{phase}-{key}.json'
                        pb=path.read_bytes(); envelope=json.loads(pb); p=envelope['payload']; assert digest(enc(p))==envelope['payload_sha256']
                        assert (p['phase'],p['parent_graph_id'],p['node_count'],p['parent_model'],p['parent_replicate'])==(phase,key,n,model,rep)
                        oldpath=S3/'parents'/path.name; oldbytes=oldpath.read_bytes(); item=inventory[oldpath.relative_to(ROOT).as_posix()]
                        assert digest(oldbytes)==item['sha256'] and len(oldbytes)==item['bytes']
                        old=json.loads(oldbytes); assert p['raw_sha256']==old['raw_sha256'] and p['raw_bytes']==old['raw_bytes']
                        assert reg[key]['artifact_fingerprint']==p['artifact_fingerprint'] and reg[key]['result_fingerprint']==p['result_fingerprint']
                        receipt=dest/path.name; expected={'parent_sha256':digest(pb),'raw_sha256':p['raw_sha256'],'integer_sums':p['integer_sums'],'status':'passed'}
                        if receipt.exists(): assert json.loads(receipt.read_bytes())==expected
                        else:
                            status('verifying-events',phase=phase,current_block=key)
                            rawpath=ROOT/f'outputs/{phase}/synthetic-{phase}-v1'/reg[key]['path']
                            assert rawpath.resolve().is_relative_to((ROOT/f'outputs/{phase}/synthetic-{phase}-v1/blocks').resolve())
                            check_parent(p,rawpath.read_bytes(),cfg,evidence); write(receipt,expected); units+=1
                        array.append(p['integer_sums']); hashes.append(digest(pb)); parents_done+=1
                        if stop(): status('paused-safe-checkpoint'); return
                arrays[phase,n]=np.asarray(array,dtype=np.int64); parent_hashes[phase,n]=hashes
        for (phase,n),array in arrays.items():
            paths=[OUT/'bootstrap'/f'{phase}-n{n:04d}-{start:05d}.bin.gz' for start in range(0,20000,500)]
            chunk_hashes=[digest(p.read_bytes()) for p in paths]
            receipt=dest/f'cell-{phase}-n{n:04d}.json'
            expected={'status':'passed','parent_hashes':parent_hashes[phase,n],'chunk_hashes':chunk_hashes,'replicates_checked':20000,'row_count':90}
            if receipt.exists(): assert json.loads(receipt.read_bytes())==expected
            else:
                all_draws=[]
                for start,path in zip(range(0,20000,500),paths):
                    status('verifying-bootstrap',phase=phase,node_count=n,start=start)
                    compressed=path.read_bytes(); meta=json.loads(path.with_suffix('.json').read_bytes())
                    assert meta=={'phase':phase,'node_count':n,'start':start,'shape':[500,2,3,5,2],'dtype':'<i8','sha256':digest(compressed)}
                    saved=np.frombuffer(gzip.decompress(compressed),dtype='<i8').reshape(500,2,3,5,2)
                    independent=np.stack([array[selection(cfg,phase,n,r)].sum(axis=0) for r in range(start,start+500)])
                    np.testing.assert_array_equal(saved,independent); all_draws.append(independent)
                check_rows(cfg,phase,n,array,np.concatenate(all_draws),result); write(receipt,expected); units+=1
            cells_done+=1
            if stop(): status('paused-safe-checkpoint'); return
        resume=json.loads((OUT/'resume-demonstration.json').read_bytes())
        assert resume['pause_state']['state']=='paused-safe-checkpoint' and resume['pause_state']['extracted_blocks']==4
        for p in resume['parents']:
            raw=(OUT/'parents'/p['path']).read_bytes(); assert digest(raw)==p['sha256'] and len(raw)==p['bytes']
        write(OUT/'verification.json',{'status':'passed','binding':bind,'parents_checked':480,'bootstrap_replicates_checked':160000,
             'contrasts_checked':480,'window_changes_checked':240,'intervals_checked':240,'exact_integer_checks':True,'resume_demonstration':'passed',
             'method':'Separate raw-event/witness check; discrete survival-area sum; direct-index bootstrap and exact Fraction row/quantile reconstruction.',
             'audit_scope':'Same-analyst separate implementation arithmetic verification, not blinded independent scientific review.'})
        status('passed')
    except BaseException as exc:
        status('stopped-on-error',error=repr(exc)); raise
    finally: lock.unlink()

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--stop-after-units',type=int); run(p.parse_args())
