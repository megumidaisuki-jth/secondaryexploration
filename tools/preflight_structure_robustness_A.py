"""Historical-variance planning and archived-engineering checks; no new endpoints."""
from collections import defaultdict
import json
from math import sqrt
from pathlib import Path
from statistics import NormalDist, variance
import zipfile

from tools.supplement_initialization_common import ROOT, encode, sha, save, load
from tools.structure_robustness_engineering import check_arithmetic, merge


def run():
    cfg=json.loads((ROOT/'configs/supplement/structure-robustness-A-v1.json').read_bytes())
    out=ROOT/'results/diagnostics/structure-robustness-A-v1'; out.mkdir(parents=True,exist_ok=True)
    engineering=ROOT/cfg['engineering_output']
    receipt=json.loads((engineering/'engineering-receipt.json').read_bytes())
    catalog=json.loads((engineering/'catalogue.json').read_bytes())
    assert receipt['status']=='completed-engineering-only'
    assert receipt['catalogue_sha256']==sha((engineering/'catalogue.json').read_bytes())
    assert receipt['units']==len(catalog['units'])==104 and receipt['requests']==24960
    archived=[engineering/'binding.json',engineering/'catalogue.json',engineering/'engineering-receipt.json']
    archived+=sorted((engineering/'parents').glob('*.json.gz'))
    checkpoint_count=0
    for row in catalog['units']:
        up=engineering/row['path']; unit,h=load(up); assert h==row['payload_sha256']; archived.append(up)
        s=unit['spec']; state=s['initial_state']; prefix=None; previous=None
        for start in range(0,row['horizon'],10):
            path=engineering/'runs'/row['unit_id']/'chunks'/f'{start:06d}.json.gz'
            c,h=load(path); assert c['context']==receipt['binding'] and c['unit_id']==row['unit_id']
            assert c['start']==start and c['end']==min(start+10,row['horizon']) and c['previous_sha256']==previous
            sim=c['simulation']; assert sim[0]==state and [x[1] for x in sim[1]]==s['requests'][start:c['end']]
            check_arithmetic(sim); prefix=merge(prefix,sim,start,s['nodes']); assert prefix==c['prefix']
            state=sim[2]; previous=h; archived.append(path); checkpoint_count+=1
        rp=engineering/'runs'/row['unit_id']/'result.json.gz'; result,_=load(rp)
        assert result['context']==receipt['binding'] and result['final_state']==state and result['prefix']==prefix
        assert result['last_chunk_sha256']==previous; archived.append(rp)
    manifest=[{'path':p.relative_to(engineering).as_posix(),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size}
              for p in sorted(set(archived))]
    archive=ROOT/'results/archives/structure-robustness-engineering-v1.zip'; archive.parent.mkdir(parents=True,exist_ok=True)
    if not archive.exists():
        # Create once; preserve a partial archive on failure, never silently replace it.
        with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_STORED) as z:
            z.writestr('MANIFEST.json',encode(manifest))
            for item in manifest: z.write(engineering/item['path'],item['path'])
    with zipfile.ZipFile(archive) as z:
        assert json.loads(z.read('MANIFEST.json'))==manifest
        for item in manifest: assert sha(z.read(item['path']))==item['sha256']

    historical=ROOT/'results/supplement/short-window-posthoc-v1'
    assert json.loads((historical/'verification.json').read_bytes())['status']=='passed'
    samples=defaultdict(list); sources=[]
    for path in sorted((historical/'parents').glob('*.json')):
        env=json.loads(path.read_bytes()); p=env['payload']
        if p['node_count'] not in [60,120]: continue
        assert sha(encode(p))==env['payload_sha256']
        sources.append({'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path.read_bytes())})
        H=12*p['node_count']
        for family in ['fhs3','fhs5']:
            values=[]
            for tr in p['events']:
                arms={a['variant_id']:a for a in tr['variants']}; binary=[arms[k] for k in p['panels'][family]]
                dY=arms[family]['request_index']/H-sum(a['request_index']/H for a in binary)/len(binary)
                dF=sum(int(a['observed']) for a in binary)/len(binary)-int(arms[family]['observed'])
                values.append((dY,dF))
            assert len(values)==7
            for j,endpoint in enumerate(['Y','F']):
                samples[p['phase'],p['node_count'],family,endpoint,p['parent_model']].append(sum(v[j] for v in values)/7)
    z=NormalDist().inv_cdf(1-.05/(2*80)); z80=NormalDist().inv_cdf(.8); planning=[]
    models=['barabasi_albert','er_gnm','sbm_fixed_count']
    for phase in ['formal','confirmation']:
        for n in [60,120]:
            for family in ['fhs3','fhs5']:
                for endpoint in ['Y','F']:
                    rows=[samples[phase,n,family,endpoint,m] for m in models]
                    assert all(len(r)==20 for r in rows)
                    variances=[variance(r) for r in rows]; se=sqrt(sum(variances)/(9*30))
                    planning.append({'historical_phase':phase,'node_count':n,'family':family,'endpoint':endpoint,
                        'old_n_per_model':20,'new_n_per_model':30,'model_variances':dict(zip(models,variances)),
                        'normal_halfwidth_if_variance_transports':z*se,
                        'normal_80pct_positive_detection_scale_if_variance_transports':(z+z80)*se,
                        'variance_multiplier_sensitivity':[{'variance_multiplier':v,'normal_halfwidth':z*se*sqrt(v)} for v in [1,2,4]]})
    seconds=sum(r['seconds'] for r in receipt['chunk_timings']); rate=seconds/24960
    report={'schema':'structure-A-preflight.v1','status':'passed-engineering-and-bounded-planning',
        'engineering':{'units':104,'requests':24960,'verified_chunks':checkpoint_count,'seconds_per_request_240_only':rate,
            'archive':archive.relative_to(ROOT).as_posix(),'archive_sha256':sha(archive.read_bytes()),'archive_bytes':archive.stat().st_size},
        'precision_planning':planning,'historical_sources':sources,
        'limits':['Historical optimized source/original binary and H=12n are variance proxies, not new U/U Bstar power.',
                  'Normal approximation is for planning only; frozen final analysis uses paired stratified bootstrap.',
                  'No achieved power guarantee; keep 30 independent parents/model/size; no outcome-adaptive addition.',
                  '240-request engineering timing is not a forecast for late 1440-request depleted states.'],
        'A_request_upper_before_dedup':(17640+23040)*1440,
        'linear_engineering_scale_hours_single_worker':(17640+23040)*1440*rate/3600,
        'linear_engineering_scale_hours_ideal_two_workers':(17640+23040)*1440*rate/7200,
        'disk_plan':'50-request chunks; retain full traces; stop safely below 8 GiB free; packing/upload separate from active runs',
        'remaining_automatic_gates':['all 180 A inputs feasible and bound','old/new parent identity collision check','tests bound to code','training only selection before test']}
    save(out/'preflight.json',report)
    print(json.dumps({'status':report['status'],'engineering_archive_bytes':archive.stat().st_size,
                      'historical_planning_cells':len(planning),'engineering_chunks_verified':checkpoint_count}))


if __name__=='__main__': run()
