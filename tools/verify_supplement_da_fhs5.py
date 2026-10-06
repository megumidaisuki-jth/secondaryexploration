"""Separate arithmetic implementation; does not import the S1 generator.

Checks all bootstrap copies and all archived parent contrasts. This is an
automated numerical cross-check, not a new blinded scientific or routing audit.
"""
from collections import Counter
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import random
import math

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/supplement/da-fhs5-posthoc-v1'

def load(path):
    return json.loads(path.read_bytes())

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def packed(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()

def write(path, obj):
    tmp = path.with_suffix('.verify.tmp')
    with tmp.open('xb') as stream:
        stream.write(packed(obj)); stream.flush(); os.fsync(stream.fileno())
    os.replace(tmp, path)

def verify():
    config_path = ROOT / 'configs/supplement/da-fhs5-posthoc-v1.json'
    config = load(config_path)
    binding = load(OUT / 'binding.json')
    assert binding['config_sha256'] == digest(config_path)
    assert binding['analysis_script_sha256'] == digest(ROOT / 'tools/supplement_da_fhs5.py')
    results = load(OUT / 'results.json')
    assert results['binding'] == binding and len(results['comparisons']) == 16
    rows = {(r['phase'], r['node_count'], r['metric']): r for r in results['comparisons']}
    assert len(rows) == 16
    checked_parents = checked_draws = checked_chunks = 0
    for phase in ('formal', 'confirmation'):
        evidence_path = ROOT / f'results/inference/{phase}-phase-evidence.json'
        assert digest(evidence_path) == config['source_sha256'][phase]
        evidence = load(evidence_path)
        source = {(r['node_count'], r['parent_model'], r['parent_replicate'], r['metric'], r['source_family']): r for r in evidence['parent_contrasts']}
        exported = {(p['node_count'], p['parent_model'], p['parent_replicate']): p for p in load(OUT / f'{phase}-parents.json')}
        for n in (30, 60, 120, 240):
            vectors = {}
            for model in config['models']:
                vectors[model] = []
                for rep in range(20):
                    vec = []
                    for metric in config['metrics']:
                        a = source[n, model, rep, metric, 'demand-aware']
                        b = source[n, model, rep, metric, 'fhs5']
                        # Independent aggregation from archived scope means.
                        value = sum(Fraction(weight, 7) * (Fraction(*a[key]) - Fraction(*b[key]))
                                    for weight, key in [(4, 'same_distribution_mean'), (3, 'distribution_shift_mean')])
                        denominator = 7 * (12 * n if metric == config['metrics'][0] else 1)
                        assert value == Fraction(exported[n, model, rep]['integer_totals'][len(vec)], denominator)
                        vec.append(value)
                        checked_parents += 1
                    vectors[model].append(vec)
            numerators = []
            for start in range(0, 20000, 500):
                checkpoint = load(OUT / 'checkpoints' / f'{phase}-n{n:04d}-{start:05d}.json')
                assert checkpoint['values_sha256'] == hashlib.sha256(packed(checkpoint['values'])).hexdigest()
                assert checkpoint['meta'] == {'binding_sha256': hashlib.sha256(packed(binding)).hexdigest(), 'phase': phase, 'node_count': n, 'start': start, 'stop': start + 500}
                assert len(checkpoint['values']) == 500
                for offset, nums in enumerate(checkpoint['values']):
                    sums = [Fraction(0), Fraction(0)]
                    for model in config['models']:
                        key = f'{config["bootstrap_seed"]}|{phase}|{n}|{start+offset}|{model}'
                        generator = random.Random(int(hashlib.sha256(key.encode()).hexdigest(), 16))
                        counts = Counter(generator.randrange(20) for _ in range(20))
                        for idx, multiplicity in counts.items():
                            for col in (0, 1):
                                sums[col] += multiplicity * vectors[model][idx][col] / 60
                    assert sums == [Fraction(nums[0], 420 * 12 * n), Fraction(nums[1], 420)]
                    checked_draws += 1
                numerators.extend(checkpoint['values'])
                checked_chunks += 1
            for col, metric in enumerate(config['metrics']):
                result = rows[phase, n, metric]
                estimate = sum((v[col] for group in vectors.values() for v in group), Fraction(0)) / 60
                assert Fraction(*result['exact']['estimate']) == estimate
                order = sorted(Fraction(v[col], 420 * (12 * n if col == 0 else 1)) for v in numerators)
                for name, probability in [('adjusted_lower', Fraction(1, 640)), ('adjusted_upper', Fraction(639, 640)), ('unadjusted_lower', Fraction(1, 40)), ('unadjusted_upper', Fraction(39, 40))]:
                    expected = order[math.ceil(probability * 20000) - 1]
                    assert Fraction(*result['exact'][name]) == expected
                vals = [v[col] for group in vectors.values() for v in group]
                assert result['parent_delta_sign_counts'] == {'negative': sum(v < 0 for v in vals), 'zero': sum(v == 0 for v in vals), 'positive': sum(v > 0 for v in vals)}
            print(f'Verified {phase} n={n}: all 20000 bootstrap replicates', flush=True)
    first = OUT / 'checkpoints/formal-n0030-00000.json'
    assert digest(first) == 'fdf4ff2fa2867f493e9b03da626147bdbd2e8501d108fb4c59a7bb6efae6574c'
    verification = {'status': 'passed', 'scope': 'separate exact-arithmetic implementation using archived scope means; all bootstrap copies checked; not new blinded scientific replay',
                    'verified_parent_metric_values': checked_parents, 'verified_bootstrap_replicates': checked_draws, 'verified_chunks': checked_chunks,
                    'results_sha256': digest(OUT / 'results.json'), 'verifier_sha256': digest(Path(__file__)),
                    'first_checkpoint_unchanged_after_pause_resume': True,
                    'new_simulations': 0, 'raw_blocks_read': 0}
    write(OUT / 'verification.json', verification)
    progress = load(OUT / 'progress.json')
    progress.update(state='complete-arithmetic-verified', verification='verification.json')
    write(OUT / 'progress.json', progress)
    print(json.dumps(verification, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    verify()
