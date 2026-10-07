"""Byte-bound S5 input extraction only: never train, route or simulate."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time
from tools.supplement_initialization_common import (ROOT,OUT,CONFIG,encode,sha,save,store,load,uniform,spec,core_snapshot,runtime,config,state_object)
from secondaryexploration.topology import node_capital_totals

def extract(a,old,s4,phase,cfg):
    key=old['parent_graph_id']; n=old['node_count']; H=12*n
    assert a['artifact_fingerprint']==old['artifact_fingerprint'] and a['result_fingerprint']==old['result_fingerprint']
    assert a['code_revision']==cfg['source_code_revision']
    vs={v[0]:v for v in a['result_witness']['variants']}
    assert not any(v['variant_id'].endswith('-U') for run in a['held_out'] for v in run['variants'])
    nodes=None; variants={}
    for family in cfg['families']:
        v=vs[family]; vertex,edges=v[2]
        assert v[1]==family and len(vertex)==n
        if nodes is None: nodes=vertex
        else: assert vertex==nodes
        variants[family]={'topology':edges,'uniform_initial_state':uniform(vertex,edges,cfg['per_node_capital'])}
    oldtraces={t['regime_id']:t for t in old['traces']}; observations={t['regime_id']:t for t in s4['events']}
    runsummary={r['trace_seed']['regime_id']:r for r in a['held_out']}
    traces=[]; unit_sources={}
    for wr in a['result_witness']['held_out']:
        rid=wr[0]; original=oldtraces[rid]; r=runsummary[rid]; summary={v['variant_id']:v for v in r['variants']}
        sims=dict(wr[4]); requests=[x[1] for x in sims['fhs5'][1]]
        assert len(requests)==H and all([x[1] for x in sim[1]]==requests for sim in sims.values())
        assert all([x[0] for x in sim[1]]==list(range(1,H+1)) for sim in sims.values())
        assert wr[3]==r['paired_manifest_fingerprint']==original['paired_manifest_fingerprint']==observations[rid]['paired_manifest_fingerprint']
        assert wr[2][2]=='test' and wr[2][3]==rid and wr[2][0]==n and wr[2][1]==old['parent_replicate']
        assert wr[2][6]==r['trace_seed']['routing_root_seed'] and wr[2][5]==r['trace_seed']['trace_root_seed']
        optimized={}; old_specs={}
        for family in cfg['families']:
            sim=sims[family]; initial=sim[0]; graph=variants[family]['topology']
            assert [[e,[m for m,_ in balances]] for e,balances in initial]==graph
            totals=node_capital_totals(state_object(nodes,initial)); assert totals==tuple((v,120) for v in nodes)
            events={q:{'observed':sim[j][0],'request_index':sim[j][1]} for q,j in [('tau_dep',3),('tau_nopath',4),('tau_rej',5)]}
            assert all(events[q]==summary[family][q] for q in events)
            ev=next(v for v in observations[rid]['variants'] if v['variant_id']==family)
            assert [ev['observed'],ev['request_index']]==sim[4]
            arm=next(v for v in original['arms'] if v['variant_id']==family)
            assert arm['values'][:2]==[summary[family]['accepted_request_count'],summary[family]['accepted_value']]
            optimized[family]={'initial_state':initial,'events':events,'summary':summary[family],
                'simulation_witness_sha256':sha(encode(sim)),'audited_S3_cost':arm}
            ospec=spec(nodes,initial,requests,wr[2][6]); old_specs[sha(encode(ospec))]=family
        uniform_units={}
        for family in cfg['families']:
            uspec=spec(nodes,variants[family]['uniform_initial_state'],requests,wr[2][6]); uid=sha(encode(uspec))
            uniform_units[family]=uid
            source={'spec':uspec,'reuse_optimized_family':old_specs.get(uid),
                    'reference':{'phase':phase,'parent_graph_id':key,'regime_id':rid,'raw_sha256':old['raw_sha256']}}
            if uid in unit_sources: assert unit_sources[uid]['spec']==uspec
            else: unit_sources[uid]=source
        traces.append({'regime_id':rid,'scope':original['scope'],'paired_manifest_fingerprint':wr[3],
                       'trace_seed':r['trace_seed'],'optimized':optimized,'uniform_units':uniform_units})
    assert len(traces)==7 and Counter(t['scope'] for t in traces)=={'same_distribution':4,'distribution_shift':3}
    p={k:old[k] for k in ['parent_graph_id','node_count','parent_model','parent_replicate','raw_sha256','raw_bytes','artifact_fingerprint','result_fingerprint']}
    p.update({'phase':phase,'nodes':nodes,'variants':variants,'traces':traces})
    return p,unit_sources

def run(args):
    cfg=config(); OUT.mkdir(parents=True,exist_ok=True)
    binding={'config_sha256':sha(CONFIG.read_bytes()),'preparer_sha256':sha(Path(__file__).read_bytes()),
        'common_sha256':sha((ROOT/'tools/supplement_initialization_common.py').read_bytes()),'core_snapshot':core_snapshot(),'runtime':runtime()}
    lock=OUT/'PREPARING.lock'
    with lock.open('xb') as f: f.write(encode({'pid':__import__('os').getpid(),'argv':sys.argv}))
    began=time.monotonic(); count=new=0
    def status(state,**kw): save(OUT/'preparation-progress.json',{'state':state,'parents_prepared':count,'total_parents':480,'percent':round(count/480*100,3),'elapsed_seconds_this_invocation':round(time.monotonic()-began,3),**kw})
    try:
        bp=OUT/'preparation-binding.json'
        if bp.exists(): assert json.loads(bp.read_bytes())==binding
        else: save(bp,binding)
        s3=ROOT/'results/supplement/service-cost-posthoc-v1'; s4=ROOT/'results/supplement/short-window-posthoc-v1'
        inventories={}
        for name,base in [('s3',s3),('s4',s4)]:
            raw=(base/'delivery-manifest.json').read_bytes(); assert sha(raw)==cfg[name+'_manifest_sha256']
            inventories[name]={r['path']:r for r in json.loads(raw)['files']}
        proof=(s3/'verification.json').read_bytes(); assert sha(proof)==cfg['s3_verification_sha256'] and json.loads(proof)['status']=='passed'
        catalogue={}; all_parents=[]
        for phase in cfg['phases']:
            evbytes=(ROOT/f'results/inference/{phase}-phase-evidence.json').read_bytes(); assert sha(evbytes)==cfg['source_sha256'][phase]
            ev=json.loads(evbytes); assert ev['status']=='complete-strict-replay' and len(ev['block_registry'])==240
            phase_manifest=json.loads((ROOT/f'configs/{phase}/synthetic-{phase}-v1.json').read_bytes())
            assert phase_manifest['per_node_capital']==120 and phase_manifest['requests_per_node']==12 and phase_manifest['code_revision']==cfg['source_code_revision']
            for reg in sorted(ev['block_registry'],key=lambda r:r['block_key']):
                key=reg['block_key']; name=f'{phase}-{key}.json'; oldpath=s3/'parents'/name; oldbytes=oldpath.read_bytes()
                record=inventories['s3'][oldpath.relative_to(ROOT).as_posix()]; assert sha(oldbytes)==record['sha256'] and len(oldbytes)==record['bytes']
                old=json.loads(oldbytes); assert old['artifact_fingerprint']==reg['artifact_fingerprint'] and old['result_fingerprint']==reg['result_fingerprint']
                s4path=s4/'parents'/name; s4bytes=s4path.read_bytes(); record=inventories['s4'][s4path.relative_to(ROOT).as_posix()]
                assert sha(s4bytes)==record['sha256'] and len(s4bytes)==record['bytes']
                s4envelope=json.loads(s4bytes); assert sha(encode(s4envelope['payload']))==s4envelope['payload_sha256']
                path=OUT/'parents'/(name+'.gz')
                rawpath=ROOT/f'outputs/{phase}/synthetic-{phase}-v1'/reg['path']
                assert rawpath.resolve().is_relative_to((ROOT/f'outputs/{phase}/synthetic-{phase}-v1/blocks').resolve())
                if path.exists():
                    payload,phash=load(path); p=payload['parent']; units=payload['units']
                    assert p['raw_sha256']==old['raw_sha256'] and payload['binding']==binding
                else:
                    status('preparing',phase=phase,current_parent=key)
                    raw=rawpath.read_bytes(); assert sha(raw)==old['raw_sha256'] and len(raw)==old['raw_bytes']
                    p,units=extract(json.loads(raw),old,s4envelope['payload'],phase,cfg)
                    phash=store(path,{'binding':binding,'parent':p,'units':units}); new+=1
                assert p['phase']==phase and p['parent_graph_id']==key
                all_parents.append({'phase':phase,'parent_graph_id':key,'node_count':p['node_count'],'path':path.relative_to(OUT).as_posix(),'payload_sha256':phash})
                for uid,unit in units.items():
                    assert sha(encode(unit['spec']))==uid
                    up=OUT/'inputs'/(uid+'.json.gz')
                    if up.exists(): prior,uhash=load(up); assert prior==unit
                    else: uhash=store(up,unit)
                    assert uid not in catalogue
                    catalogue[uid]={'unit_id':uid,'node_count':p['node_count'],'horizon':len(unit['spec']['requests']),
                        'path':up.relative_to(OUT).as_posix(),'payload_sha256':uhash,'reused_optimized':unit['reuse_optimized_family'] is not None,
                        **unit['reference']}
                count+=1; status('input-checkpoint')
                if (OUT/'PAUSE').exists() or (args.stop_after_parents is not None and new>=args.stop_after_parents): status('paused-safe-checkpoint'); return
        rows=sorted(catalogue.values(),key=lambda r:(r['node_count'],r['parent_graph_id'],r['phase'],r['regime_id'],r['unit_id']))
        save(OUT/'catalogue.json',{'binding':binding,'parents':all_parents,'units':rows,'logical_uniform_runs':6720,
            'unique_units':len(rows),'reused_optimized_units':sum(r['reused_optimized'] for r in rows),
            'new_units':sum(not r['reused_optimized'] for r in rows),'new_requests':sum(r['horizon'] for r in rows if not r['reused_optimized'])})
        status('prepared-pending-executor-tests',unique_units=len(rows),new_units=sum(not r['reused_optimized'] for r in rows))
    except BaseException as exc: status('stopped-on-error',error=repr(exc)); raise
    finally: lock.unlink()

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--stop-after-parents',type=int); run(p.parse_args())
