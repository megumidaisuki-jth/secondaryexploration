"""Read-only scientific-input checks; writes only this audit's receipts.

No raw-block access, simulation or bootstrap resampling. Stored bootstrap
order statistics and source-data parent means are checked independently.
"""
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict
import hashlib
import json
import math
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).parent
CHECK_DATE = '2026-10-03'


def read(rel):
    return json.loads((ROOT/rel).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def rounded(x):
    q = round(x * 1000)
    return ('-' if q < 0 else '') + f'{abs(q)//1000}.{abs(q)%1000:03d}'


def main():
    data = read('results/source-data/synthetic-hypergraph-payment-v1/source-data.json')
    registry = read('manuscript/generated/synthetic-v1/numerical-registry.json')
    desc = read('manuscript/generated/results-writing-v1/evidence-summary.json')
    tex = (ROOT/'manuscript/joconline-latex/main.tex').read_text(encoding='utf-8')
    from tools.build_results_writing_support import build
    require(build(data) == desc, 'Descriptive summary no longer reproduces source data')
    checks = defaultdict(int)
    phase_notes = {}
    for phase, p in data['phase_data'].items():
        groups = defaultdict(list)
        family_by_parent = defaultdict(dict)
        for row in p['parent_model_values']:
            z = F(*row['combined_parent_value'])
            require(z == F(4,7)*F(*row['same_distribution_mean']) +
                    F(3,7)*F(*row['distribution_shift_mean']), 'Equation 15 mismatch')
            require(row['horizon'] == 12*row['node_count'], 'Horizon mismatch')
            groups[(row['metric'],row['node_count'],row['source_family'])].append(row)
            family_by_parent[(row['metric'],row['node_count'],row['parent_graph_id'])][row['source_family']] = z
            checks['parent_aggregations'] += 1
        for values in family_by_parent.values():
            require(values['global'] == sum((values[f] for f in ('demand-aware','fhs3','fhs5','nch')),F())/4,
                    'Equation 13 equal-family global mismatch')
            checks['global_parent_aggregations'] += 1
        for row in p['registered_intervals']:
            key = (row['metric'],row['node_count'],row['contrast_id'].split('.')[-1])
            parents = groups[key]
            strata = defaultdict(list)
            for item in parents:
                strata[item['parent_model']].append(F(*item['combined_parent_value']))
            require(len(strata) == 3 and all(len(s)==20 for s in strata.values()), 'Parent n differs')
            exact_mean = sum((sum(s,F())/20 for s in strata.values()),F())/3
            require(exact_mean == F(*row['estimate']), 'Equation 16 estimate mismatch')
            values = sorted(F(*v) for v in row['bootstrap_values'])
            require(len(values)==20000, 'Bootstrap array length differs')
            lower = values[math.ceil(len(values)*F(1,1600))-1]
            upper = values[math.ceil(len(values)*F(1599,1600))-1]
            require(lower==F(*row['lower']) and upper==F(*row['upper']), 'Stored percentile endpoint differs')
            reg = next(r for r in registry['phase_intervals'] if r['phase']==phase and r['contrast_id']==row['contrast_id'])
            for name, value in [('estimate',exact_mean),('lower',lower),('upper',upper)]:
                require(reg[name]==row[name] and reg['display'][name]==rounded(value), 'Registry/rounding differs')
            require(upper<0 if row['metric']=='failure_risk' else lower>0, 'Claim of favorable direction differs')
            checks['intervals'] += 1
        summary = desc['phases'][phase]
        coverage = summary['event_coverage']
        phase_notes[phase] = {
            'coverage_cells':len(coverage),
            'complete_coverage':sum(r['identified_parent_count']==20 for r in coverage),
            'no_covered_parents':sum(r['identified_parent_count']==0 for r in coverage),
            'fully_covered_cells':[{k:r[k] for k in ('node_count','parent_model','source_family','scope')}
                                   for r in coverage if r['identified_parent_count']==20],
            'activity_changed':{}, 'activity_unchanged_means_n240':{},
            'descriptor_signs':{m:[r['negative'],r['zero'],r['positive']]
                                for m,r in summary['descriptor_cell_ranges'].items()},
            'coordination_range':[rounded(F(*summary['descriptor_cell_ranges']['quadratic_coordination_exposure_per_attempt'][k]))
                                   for k in ('minimum','maximum')],
            'block_hours':{k:rounded(F(*summary['runtime'][k])) for k in ('generation_block_hours','exact_validation_block_hours')},
        }
        for r in summary['activity_sensitivity']:
            if r['metric']=='failure_risk' and r['topology_activity']=='changed':
                phase_notes[phase]['activity_changed'][r['node_count']]=sum(s['parent_count'] for s in r['strata'])
            if r['node_count']==240 and r['topology_activity']=='unchanged':
                phase_notes[phase]['activity_unchanged_means_n240'][r['metric']]=rounded(F(*r['equal_model_descriptive_mean']))
        print(f'{phase}: exact parent means and stored-bootstrap endpoints passed', flush=True)
    # Independent TeX table reconstruction, not the manuscript conversion code.
    table1 = tex.split('\\label{tab:1}',1)[1].split('\\end{table*}',1)[0]
    for row in registry['phase_intervals']:
        if row['tier']=='global':
            values = [rounded(F(*row[k])) for k in ('estimate','lower','upper')]
            cell = '$'+values[0]+r'\;['+values[1]+', '+values[2]+']$'
            require(cell in table1, 'Table 1 numerical cell missing')
            checks['table1_estimate_interval_cells'] += 1
    table2 = tex.split('\\label{tab:2}',1)[1].split('\\end{table}',1)[0]
    for n in (30,60,120,240):
        for model,label in [('barabasi_albert','BA'),('er_gnm','ER-GNM'),('sbm_fixed_count','SBM')]:
            values=[]
            for phase in ('formal','confirmation'):
                row=next(r for r in desc['phases'][phase]['parent_stratum_summaries']
                         if (r['node_count'],r['metric'],r['source_family'],r['parent_model'])==(n,'failure_risk','global',model))
                values.append('$'+rounded(F(*row['mean']))+'$')
                checks['table2_cells'] += 1
            require(' & '.join([str(n),label]+values)+r'\\' in table2,'Table 2 row mismatch')
    table3 = tex.split('\\label{tab:3}',1)[1].split('\\end{table}',1)[0]
    for n in (30,60,120,240):
        vals=[str(n)]
        for phase in ('formal','confirmation'):
            changed=phase_notes[phase]['activity_changed'][n]
            vals.extend([str(changed),str(60-changed)])
        require(' & '.join(vals)+r'\\' in table3,'Table 3 row mismatch')
        checks['table3_cells'] += 4
    # Pointwise check of the restricted-time survival identity, including censoring.
    for H in range(1,20):
        for tau in list(range(1,H+2))+[math.inf]:
            require(min(tau,H)==sum(tau>t for t in range(H)), 'Equation 14 off-by-one error')
            checks['survival_identity_cases'] += 1
    # The text allows this node-simple path; the frozen Route type rejects it.
    from secondaryexploration.model import Route, TransferStep, ModelError
    try:
        Route((TransferStep('e','A','B'), TransferStep('e','B','C')))
    except ModelError as error:
        repeated_edge_rejection=str(error)
    else:
        raise AssertionError('Expected repeated-hyperedge validation absent')
    from tools.build_results_displays import check_registry
    check_registry(data)
    figures = {}
    for fig in (ROOT/'manuscript/joconline-latex/figures').glob('*.pdf'):
        require(sha(fig)==sha(ROOT/'manuscript/joconline/figures'/fig.name), 'Figure differs from approved original')
        figures[fig.name]=sha(fig)
    from tools import build_results_displays
    require(sha(ROOT/'results/source-data/synthetic-hypergraph-payment-v1/source-data.json')==build_results_displays.SOURCE_SHA,'Source bytes differ')
    output={
        'date':CHECK_DATE, 'scope':'manuscript/source-data consistency; not raw-block independent replay',
        'input_commit':'af92520d91979b15d66e4526968b0775e46e319e',
        'counts':dict(checks), 'phase_notes':phase_notes, 'figures':figures,
        'replication_records':len(data['cross_phase_replication_records']),
        'all_recorded_replications_confirmed':all(r['replication_state']=='independently_confirmed' for r in data['cross_phase_replication_records']),
        'repeated_hyperedge_counterexample':repeated_edge_rejection,
        'confidence_levels':{'phase_family':'19/20','local_five_contrast_family':'159/160',
                             'single_interval':'799/800','per_tail':'1/1600'},
        'unit_tests':{'passed':60,'command':'python -m unittest tests.unit.model.test_entities tests.unit.model.test_transition tests.unit.routing.test_search tests.unit.metrics.test_stratified_inference tests.unit.optimization.test_demand -q'},
        'manuscript_sha256':sha(ROOT/'manuscript/joconline-latex/main.tex'),
    }
    (OUT/'checks.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'passed','counts':dict(checks),'phase_notes':phase_notes},ensure_ascii=False))


if __name__=='__main__':
    main()
