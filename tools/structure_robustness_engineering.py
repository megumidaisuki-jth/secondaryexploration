"""Isolated structural-robustness pilot: atomic checkpoints, safe pause, bound resume.

No old outputs or running experiments are modified. This is NOT the A/B/C
confirmation runner. Existing R0 core is reused without modifying its semantics.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from itertools import combinations
import json
import os
from pathlib import Path
import sys
import time

from tools.supplement_initialization_common import (
    ROOT, encode, sha, save, store, load, uniform, spec, core_snapshot, runtime, atomic,
)
from tools.run_supplement_initialization import simulate, merge
from secondaryexploration.experiments.study import load_study_design_manifest, traffic_kernel_for
from secondaryexploration.topology import fixed_hyperedge_size, match_binary_to_topology, HypergraphTopology
from secondaryexploration.topology.random_graphs import matched_synthetic_parent_graphs
from secondaryexploration.traffic import AmountDistribution, generate_request_trace

CONFIG = ROOT / 'configs/supplement/structure-robustness-engineering-v1.json'


def now():
    return datetime.now(timezone.utc).isoformat()


def seed(namespace, *parts):
    return int.from_bytes(bytes.fromhex(sha(encode([namespace, *parts])))[:8], 'big')


@contextmanager
def exclusive(out):
    """OS-held lock survives stale metadata, releases automatically on process death."""
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'RUNNING.lock').open('a+b') as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def binding(cfg):
    files = [Path(__file__), CONFIG, ROOT / cfg['historical_parameter_source'],
             ROOT / 'tools/run_supplement_initialization.py',
             ROOT / 'tools/supplement_initialization_common.py']
    return {'schema': 'structure-engineering-binding.v1', 'runtime': runtime(),
            'python_executable': sys.executable, 'core': core_snapshot(),
            'files': {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in files},
            'chunk_requests': cfg['chunk_requests'], 'scientific_confirmation': False}


def check_binding(out, expected):
    path = out / 'binding.json'
    if path.exists():
        if json.loads(path.read_bytes()) != expected:
            raise RuntimeError('Code/config/runtime changed: resume refused; preserve old artifacts.')
    else:
        save(path, expected)


def topology_payload(top):
    return [[edge.hyperedge_id, list(edge.members)] for edge in top.hyperedges]


def ranked_binary(nodes, incidence, priority):
    """One full pair order: Kruskal backbone then fill; adjacent budgets nested."""
    pairs = list(combinations(nodes, 2))
    order = sorted(pairs, key=lambda pair: (priority(pair), pair))
    roots = {node: node for node in nodes}
    def root(node):
        while roots[node] != node:
            roots[node] = roots[roots[node]]; node = roots[node]
        return node
    tree = []
    for a, b in order:
        left, right = root(a), root(b)
        if left != right:
            roots[right] = left; tree.append((a, b))
    tree_set = set(tree)
    ordered_edges = tree + [p for p in order if p not in tree_set]
    index = {node: i for i, node in enumerate(nodes)}
    answer = []
    for target in sorted({incidence // 2, (incidence + 1) // 2}):
        if not len(nodes) - 1 <= target <= len(pairs):
            raise ValueError('Infeasible connected simple binary budget')
        top = HypergraphTopology.from_edges(nodes, {
            f'b{index[a]:08d}-{index[b]:08d}': (a, b) for a, b in ordered_edges[:target]})
        assert top.is_connected and top.resources.incidence_count == 2 * target
        answer.append(top)
    return answer


def candidate_topologies(parent, source, ns, key, training_requests):
    """Eight predeclared candidates, with no held-out requests in this interface."""
    original = match_binary_to_topology(parent, source, root_seed=seed(ns, key, 'b0'))
    candidates = {'b0': [original.lower] if original.is_exact else [original.lower, original.upper]}
    for j in range(5):
        candidates[f'random{j}'] = ranked_binary(parent.nodes, source.resources.incidence_count,
            lambda pair, j=j: seed(ns, key, 'pair-priority', j, *pair))
    volume = Counter()
    for requests in training_requests:
        for payer, payee, amount in requests:
            volume[payer, payee] += amount
    for name in ['volume', 'reciprocity']:
        def priority(pair, name=name):
            a, b = pair
            score = volume[a, b] + volume[b, a] if name == 'volume' else 2 * min(volume[a, b], volume[b, a])
            return (-score, seed(ns, key, name, *pair))
        candidates[name] = ranked_binary(parent.nodes, source.resources.incidence_count, priority)
    return candidates


def requests_for(manifest, cell, regime, ns, key, horizon):
    trace = generate_request_trace(traffic_kernel_for(cell, regime),
        AmountDistribution.from_weights(manifest.amount_weights), horizon,
        root_seed=seed(ns, key, 'requests', regime.regime_id))
    return [[q.source, q.destination, q.amount] for q in trace.requests]


def update(out, state, **fields):
    path = out / 'progress.json'
    value = json.loads(path.read_bytes()) if path.exists() else {}
    value.update(fields)
    value.update(state=state, updated_utc=now(), pid=os.getpid(),
                 phase='isolated-engineering-pilot', scientific_results_eligible=False)
    save(path, value)
    total = value.get('total_requests', 0)
    count = value.get('checkpointed_requests', 0)
    percent = round(100 * count / total, 3) if total else None
    value['request_percent'] = percent
    save(path, value)
    atomic(out / 'progress.md', (
        '# 超图结构补充实验：工程验证进度\n\n'
        f'状态：{state}；更新时间（UTC）：{value["updated_utc"]}。\n\n'
        f'输入父图：{value.get("prepared_parents", 0)}/6。\n\n'
        f'模拟请求断点：{count}/{total}（{percent if percent is not None else "待准备"}%）。\n\n'
        f'已完成轨迹：{value.get("completed_units", 0)}/{value.get("total_units", 0)}；'
        f'当前单元：{value.get("active_unit", "无")}。\n\n'
        '本阶段只验证实现与资源消耗，不计入论文确认样本。未自动启动 A/B/C。\n\n'
        '暂停：运行 `tools/structure-robustness-control.ps1 pause`。'
        '等待状态 paused-safe-checkpoint 或工程完成后再关机。\n\n'
        '恢复：运行同脚本 resume。每10请求原子保存；已保存小段核验后复用。'
        '突然断电最多重算当前未提交小段，不删除已保存文件。\n'
    ).encode('utf-8'))


def prepare(out, cfg, context):
    manifest = load_study_design_manifest(ROOT / cfg['historical_parameter_source'])
    ns = cfg['seed_namespace']; rows = {}; parents = []; logical = []
    for n in cfg['node_counts']:
        cell = manifest.size_cell(n)
        ensemble = matched_synthetic_parent_graphs(node_count=n, attachment_count=cell.attachment_count,
            block_count=cell.block_count, sbm_within_edge_count=cell.sbm_within_edge_count,
            base_seed=seed(ns, 'parents', n), replicate_index=0, max_attempts=1000)
        for draw in ensemble.draws:
            if (out / 'PAUSE').exists():
                update(out, 'paused-safe-checkpoint'); return None
            key = f'n{n}-{draw.model.value}-000'; path = out / 'parents' / (key + '.json.gz')
            if path.exists():
                parent, parent_hash = load(path)
                assert parent['binding'] == context and parent['parent_id'] == key
            else:
                graph = draw.graph
                training = [requests_for(manifest, cell, regime, ns, key, cfg['training_demand_horizon'])
                            for regime in manifest.regimes if regime.role.value == 'training']
                assert len(training) == 4
                sources = {f'fhs{k}': fixed_hyperedge_size(graph, k) for k in [3, 5]}
                candidates = {family: candidate_topologies(graph, top, ns, [key, family], training)
                              for family, top in sources.items()}
                all_tops = {family: [top] for family, top in sources.items()}
                for family, sets in candidates.items():
                    all_tops.update({f'{family}-{name}': tops for name, tops in sets.items()})
                arm_states = {name: [uniform(list(graph.nodes), topology_payload(t), cfg['per_node_capital'])
                                    for t in tops] for name, tops in all_tops.items()}
                all_states = [s for states in arm_states.values() for s in states]
                max_degree = max(max(Counter(node for _, balances in s for node, _ in balances).values()) for s in all_states)
                traces = {rid: {'requests': requests_for(manifest, cell, manifest.regime(rid), ns, key, cfg['horizon']),
                               'routing_root_seed': seed(ns, key, 'routing', rid)} for rid in cfg['regime_ids']}
                parent = {'binding': context, 'parent_id': key, 'nodes': list(graph.nodes),
                    'parent_edges': [list(e.endpoints) for e in graph.edges],
                    'draw_root_seed': draw.root_seed, 'accepted_attempt': draw.accepted_attempt,
                    'arm_states': arm_states, 'training_requests': training, 'traces': traces,
                    'maximum_incidence_degree': max_degree, 'budget60_feasible_on_pilot_only': max_degree <= 60,
                    'not_a_Bstar_selection': True}
                parent_hash = store(path, parent)
            parents.append({'parent_id': key, 'sha256': parent_hash})
            for rid, trace in sorted(parent['traces'].items()):
                for arm in cfg['arms']:
                    for side, state in enumerate(parent['arm_states'][arm]):
                        s = spec(parent['nodes'], state, trace['requests'], trace['routing_root_seed'])
                        uid = sha(encode(s)); payload = {'spec': s, 'engineering_only': True}
                        up = out / 'inputs' / (uid + '.json.gz')
                        if up.exists():
                            prior, h = load(up); assert prior == payload
                        else:
                            h = store(up, payload)
                        rows[uid] = {'unit_id': uid, 'path': f'inputs/{uid}.json.gz',
                                     'payload_sha256': h, 'horizon': cfg['horizon']}
                        logical.append({'parent_id': key, 'regime': rid, 'arm': arm, 'side': side, 'unit_id': uid})
            update(out, 'preparing-inputs', prepared_parents=len(parents))
    catalog = {'binding': context, 'parents': parents, 'units': list(rows.values()), 'logical_arms': logical,
               'total_requests': sum(r['horizon'] for r in rows.values())}
    cp = out / 'catalogue.json'
    if cp.exists():
        assert json.loads(cp.read_bytes()) == catalog
    else:
        save(cp, catalog)
    return catalog


def check_arithmetic(simulation):
    """Independent balance arithmetic and residual reachability, not R0 optimality."""
    state = {e: dict(balances) for e, balances in simulation[0]}
    for _, request, route, *_ in simulation[1]:
        payer, payee, amount = request
        if route is None:
            seen = {payer}; pending = [payer]
            while pending:
                node = pending.pop()
                for balances in state.values():
                    if balances.get(node, -1) >= amount:
                        for other in balances:
                            if other not in seen:
                                seen.add(other); pending.append(other)
            assert payee not in seen, 'Rejected request has a feasible path'
        else:
            cursor = payer; used_edges = set(); visited = {payer}
            for edge, source, destination in route:
                assert source == cursor and source != destination
                assert edge not in used_edges and destination not in visited
                used_edges.add(edge); visited.add(destination)
                before = sum(state[edge].values())
                assert source in state[edge] and destination in state[edge] and state[edge][source] >= amount
                state[edge][source] -= amount; state[edge][destination] += amount
                assert sum(state[edge].values()) == before
                cursor = destination
            assert cursor == payee
    expected = [[e, [[n, state[e][n]] for n in sorted(state[e])]] for e in sorted(state)]
    assert expected == simulation[2]


def execute_unit(out, row, context, max_chunks=None, callback=None):
    uid = row['unit_id']; unit, h = load(out / row['path'])
    assert h == row['payload_sha256']
    s = unit['spec']; assert sha(encode(s)) == uid
    H = len(s['requests']); assert H == row['horizon']
    state = s['initial_state']; prefix = None; previous = None; offset = 0; new = 0
    while offset < H:
        end = min(offset + context['chunk_requests'], H)
        path = out / 'runs' / uid / 'chunks' / f'{offset:06d}.json.gz'
        if path.exists():
            chunk, chash = load(path)
            assert chunk['context'] == context and chunk['unit_id'] == uid
            assert (chunk['start'], chunk['end'], chunk['previous_sha256']) == (offset, end, previous)
            sim = chunk['simulation']
            assert sim[0] == state and [o[1] for o in sim[1]] == s['requests'][offset:end]
            assert [o[0] for o in sim[1]] == list(range(1, end-offset+1))
            check_arithmetic(sim)
            expected = merge(prefix, sim, offset, s['nodes']); assert expected == chunk['prefix']
        else:
            if (out / 'PAUSE').exists() or (max_chunks is not None and new >= max_chunks):
                return {'state': 'paused-safe-checkpoint', 'completed_requests': offset}
            begin = time.monotonic()
            sim = simulate(s['nodes'], state, s['requests'][offset:end], s['routing_root_seed'], offset)
            check_arithmetic(sim)
            expected = merge(prefix, sim, offset, s['nodes'])
            chunk = {'context': context, 'unit_id': uid, 'start': offset, 'end': end,
                     'previous_sha256': previous, 'simulation': sim, 'prefix': expected,
                     'seconds': time.monotonic()-begin, 'checks': 'core R0 validation + separate conservation/reachability'}
            chash = store(path, chunk); new += 1
        state = sim[2]; prefix = expected; previous = chash; offset = end
        save(out / 'unit-progress' / (uid+'.json'), {'completed_requests': offset, 'horizon': H,
             'last_chunk_sha256': previous, 'updated_utc': now()})
        if callback:
            callback(uid, offset)
    result = {'context': context, 'unit_id': uid, 'final_state': state,
              'prefix': prefix, 'last_chunk_sha256': previous, 'scientific_confirmation': False}
    rp = out / 'runs' / uid / 'result.json.gz'
    if rp.exists():
        old, _ = load(rp); assert old == result
    else:
        store(rp, result)
    return {'state': 'computed-engineering-only', 'completed_requests': H}


def run(out, cfg, resume=False):
    with exclusive(out):
        context = binding(cfg); check_binding(out, context)
        if resume and (out/'PAUSE').exists():
            request = json.loads((out/'PAUSE').read_bytes())
            if request.get('kind') != 'user-pause':
                raise RuntimeError('Error pause requires diagnosis, not automatic resume')
            archive = out/'control-history'/f'pause-{time.time_ns()}.json'
            archive.parent.mkdir(parents=True, exist_ok=True)
            os.replace(out/'PAUSE', archive)
        if (out/'PAUSE').exists():
            update(out, 'paused-safe-checkpoint'); return
        save(out/'owner.json', {'pid': os.getpid(), 'started_utc': now(), 'argv': sys.argv})
        try:
            catalog = prepare(out, cfg, context)
            if catalog is None:
                return
            offsets = {}; done = set(); start = time.monotonic()
            for row in catalog['units']:
                uid = row['unit_id']; pp = out/'unit-progress'/(uid+'.json')
                offsets[uid] = json.loads(pp.read_bytes())['completed_requests'] if pp.exists() else 0
            initial = sum(offsets.values())
            def progress(uid, offset):
                offsets[uid] = offset
                update(out, 'pausing' if (out/'PAUSE').exists() else 'running', active_unit=uid,
                       total_units=len(catalog['units']), total_requests=catalog['total_requests'],
                       checkpointed_requests=sum(offsets.values()), completed_units=len(done),
                       new_requests_this_invocation=sum(offsets.values())-initial,
                       seconds_this_invocation=round(time.monotonic()-start, 3))
            for row in catalog['units']:
                if (out/'PAUSE').exists():
                    update(out, 'paused-safe-checkpoint', active_unit=None); return
                progress(row['unit_id'], offsets[row['unit_id']])
                result = execute_unit(out, row, context, callback=progress)
                if result['state'] == 'paused-safe-checkpoint':
                    update(out, 'paused-safe-checkpoint', active_unit=None); return
                done.add(row['unit_id']); progress(row['unit_id'], row['horizon'])
            timings = []
            for row in catalog['units']:
                for p in sorted((out/'runs'/row['unit_id']/'chunks').glob('*.json.gz')):
                    chunk, _ = load(p)
                    timings.append({'unit_id': row['unit_id'], 'start': chunk['start'],
                                    'requests': chunk['end']-chunk['start'], 'seconds': chunk['seconds']})
            save(out/'engineering-receipt.json', {'status':'completed-engineering-only', 'binding':context,
                 'catalogue_sha256':sha((out/'catalogue.json').read_bytes()), 'units':len(done),
                 'requests':sum(offsets.values()), 'chunk_timings':timings,
                 'pending':['full A input feasibility','precision planning','A selection/executor audit','A scientific freeze'],
                 'no_automatic_scientific_launch':True})
            update(out, 'engineering-complete-awaiting-A-freeze', active_unit=None)
        except BaseException as exc:
            save(out/'PAUSE', {'kind':'error', 'error':repr(exc), 'at':now()})
            update(out, 'stopped-on-error', error=repr(exc)); raise


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['run','resume','pause','status'])
    args = p.parse_args()
    cfg = json.loads(CONFIG.read_bytes()); out = ROOT/cfg['output_root']
    if not __debug__:
        raise RuntimeError('Python optimization disables validation; do not use -O')
    if args.command == 'pause':
        # Never overwrite an error gate with an ordinary user pause.
        if not (out/'PAUSE').exists():
            save(out/'PAUSE', {'kind':'user-pause', 'at':now()})
        print('Pause requested. Wait for paused-safe-checkpoint before shutdown.'); return
    if args.command == 'status':
        status = json.loads((out/'progress.json').read_bytes()) if (out/'progress.json').exists() else {'state':'not-started'}
        try:
            with exclusive(out):
                status['runner_lock_live'] = False
        except OSError:
            status['runner_lock_live'] = True
        if not status['runner_lock_live'] and status['state'] in ['running','pausing','preparing-inputs']:
            status['live_status'] = 'not-running-resume-required; saved progress may be stale'
        print(json.dumps(status,ensure_ascii=False,indent=2)); return
    run(out, cfg, args.command == 'resume')


if __name__ == '__main__':
    main()
