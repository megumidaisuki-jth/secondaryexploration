"""S2 descriptive scope/regime decomposition; no new hypothesis tests."""
from fractions import Fraction
import json
from tools import supplement_da_fhs5 as s

def run():
    config = json.loads(s.DEFAULT_CONFIG.read_bytes())
    out = s.DEFAULT_OUT
    s1 = json.loads((out/'results.json').read_bytes())['comparisons']
    all_rows = []
    for phase in ('formal', 'confirmation'):
        parents, traces = s.extract(phase, config)
        assert (out/f'{phase}-traces.json').read_bytes() == s.encoded(traces)
        for n in config['node_counts']:
            regimes = sorted({r['regime_id'] for r in traces if r['node_count'] == n})
            for metric in config['metrics']:
                lookup = {}
                for kind, groups in [('scope', ['same_distribution', 'distribution_shift']), ('regime_id', regimes)]:
                    for group in groups:
                        selected = [r for r in traces if r['node_count'] == n and r['metric'] == metric and r[kind] == group]
                        by_parent = {}
                        for r in selected:
                            by_parent.setdefault((r['parent_model'], r['parent_graph_id']), []).append(Fraction(r['integer_delta'], r['horizon'] if metric == config['metrics'][0] else 1))
                        assert len(by_parent) == 60
                        expected = 4 if group == 'same_distribution' else 3 if group == 'distribution_shift' else 1
                        assert all(len(v) == expected for v in by_parent.values())
                        vals = {key: sum(v, Fraction(0))/len(v) for key, v in by_parent.items()}
                        strata = {model: sum((v for (m, _), v in vals.items() if m == model), Fraction(0))/20 for model in config['models']}
                        mean = sum(strata.values(), Fraction(0))/3
                        row = {'phase': phase, 'node_count': n, 'metric': metric, 'group_type': kind, 'group': group,
                               'independent_parents': 60, 'traces_per_parent': expected, 'estimate': [mean.numerator, mean.denominator],
                               'display': float(mean), 'parent_sign_counts': {'negative': sum(v < 0 for v in vals.values()), 'zero': sum(v == 0 for v in vals.values()), 'positive': sum(v > 0 for v in vals.values())}}
                        all_rows.append(row)
                        if kind == 'scope':
                            lookup[group] = mean
                global_row = next(r for r in s1 if r['phase'] == phase and r['node_count'] == n and r['metric'] == metric)
                assert Fraction(4, 7)*lookup['same_distribution'] + Fraction(3, 7)*lookup['distribution_shift'] == Fraction(*global_row['exact']['estimate'])
    assert len(all_rows) == 144
    s.save(out/'s2-descriptive.json', {'scope': 'post-hoc descriptive only; no new CIs or tests; all mechanisms shown', 'comparisons': all_rows,
                                    'validation': '32 scope means + 112 regime means; all 16 weighted scope recombinations equal S1 exactly'})
    report = ['# S2 同分布与偏移分解', '', '仅描述性后验汇总，无新增显著性检验。每项60个独立父图，每层20个；同分布4条轨迹、偏移3条轨迹在父图内先平均。不因符号不同宣称范围间存在显著交互。', '', '|相位|规模|终点|同分布均值|偏移均值|', '|---|---:|---|---:|---:|']
    for phase in ('formal', 'confirmation'):
        for n in config['node_counts']:
            for metric in config['metrics']:
                vals = {r['group']: r['display'] for r in all_rows if r['phase'] == phase and r['node_count'] == n and r['metric'] == metric and r['group_type'] == 'scope'}
                report.append(f'|{phase}|{n}|{"ΔY" if metric == config["metrics"][0] else "ΔF"}|{vals["same_distribution"]:.6f}|{vals["distribution_shift"]:.6f}|')
    report.extend(['', '完整7机制、两相位、4规模、2终点的112项描述性均值保存在s2-descriptive.json，不筛选有利机制。所有16个4:3范围重组均与S1精确点估计一致。', ''])
    s.atomic(out/'s2-report.md', '\n'.join(report).encode('utf-8'))
    print('S2 complete: 144 descriptive summaries; no simulation; no new hypothesis tests.')

if __name__ == '__main__':
    run()
