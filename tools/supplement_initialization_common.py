"""S5 immutable envelopes and saved-input helpers; no artifact replay loader."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import uuid
from secondaryexploration.model import HypergraphState
from secondaryexploration.topology import HypergraphTopology,node_budget_capital_state,node_capital_totals

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/supplement/initialization-ablation-v1'
CONFIG=ROOT/'configs/supplement/initialization-ablation-v1.json'
def encode(v): return (json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_name(path.name+f'.{os.getpid()}.{uuid.uuid4().hex}.tmp')
    with tmp.open('xb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,path)
def save(path,v): atomic(path,encode(v))
def store(path,payload):
    env={'payload':payload,'payload_sha256':sha(encode(payload))}
    atomic(path,gzip.compress(encode(env),mtime=0)); return env['payload_sha256']
def load(path):
    env=json.loads(gzip.decompress(path.read_bytes())); assert sha(encode(env['payload']))==env['payload_sha256']
    return env['payload'],env['payload_sha256']
def state_payload(state): return [[e.hyperedge_id,[[n,b] for n,b in e.balances]] for e in state.hyperedges]
def state_object(nodes,payload): return HypergraphState.from_balances(nodes,{e:dict(b) for e,b in payload})
def uniform(nodes,edges,budget=120):
    top=HypergraphTopology.from_edges(nodes,{e:m for e,m in edges})
    state=node_budget_capital_state(top,{n:budget for n in nodes})
    assert node_capital_totals(state)==tuple((n,budget) for n in sorted(nodes))
    assert all(b>0 for e in state.hyperedges for _,b in e.balances)
    return state_payload(state)
def spec(nodes,initial,requests,routing_seed):
    # Edge memberships are fully encoded by the canonical state; no topology-specific labels are used by the router.
    return {'nodes':nodes,'initial_state':initial,'requests':requests,'routing_root_seed':routing_seed}
def core_snapshot(): return {p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted((ROOT/'secondaryexploration').rglob('*.py'))}
def runtime(): return {'python':platform.python_version(),'implementation':platform.python_implementation(),'system':platform.system(),'machine':platform.machine()}
def config(): return json.loads(CONFIG.read_bytes())
def fraction_pair(f): return [f.numerator,f.denominator]
