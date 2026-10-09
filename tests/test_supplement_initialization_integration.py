"""Read-only reporting checks independent of the assembler's selection loops."""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'manuscript/joconline-integrated-v1'

def load(name):
    return json.loads((OUT / 'source-data' / name).read_bytes())

class IntegrationTests(unittest.TestCase):
    def test_all_source_values_and_scope_recombinations(self):
        s1 = load('S1_S2-results.json')['comparisons']
        self.assertEqual(len(s1), 16)
        s2 = load('S1_S2-s2-descriptive.json')['comparisons']
        self.assertEqual(len(s2), 144)
        for x in s1:
            self.assertLessEqual(Fraction(*x['exact']['adjusted_lower']), 0)
            self.assertGreaterEqual(Fraction(*x['exact']['adjusted_upper']), 0)
            same = next(c for c in s2 if c['group']=='same_distribution' and all(c[k]==x[k] for k in ['phase','node_count','metric']))
            shift = next(c for c in s2 if c['group']=='distribution_shift' and all(c[k]==x[k] for k in ['phase','node_count','metric']))
            self.assertEqual((4*Fraction(*same['estimate'])+3*Fraction(*shift['estimate']))/7, Fraction(*x['exact']['estimate']))

    def test_cost_ratios_and_numeric_anchors(self):
        s3 = load('S3-results.json')
        self.assertEqual(len(s3['arms']), 64)
        self.assertEqual(len(s3['contrasts']), 200)
        main = (OUT / 'main.tex').read_text('utf-8')
        for arm in s3['arms']:
            self.assertEqual(arm['zero_service_parents'], 0)
            self.assertEqual(arm['zero_service_trace_panels'], 0)
            for ratio in arm['cost_per_accepted_request']:
                if ratio['exact_estimate'] is not None:
                    expected = Fraction(*arm['parent_mean_totals'][ratio['cost']]) / Fraction(*arm['parent_mean_totals']['accepted_request_count'])
                    self.assertEqual(expected, Fraction(*ratio['exact_estimate']))
                self.assertEqual(ratio['undefined_bootstrap_draws'], 0)
            if arm['phase']=='confirmation' and arm['node_count']==240 and arm['family']=='demand-aware':
                self.assertIn(f"{arm['mean_per_attempt']['accepted_request_count']:.6f}", main)
                for r in arm['cost_per_accepted_request']:
                    if r['cost'] in ['traversed_hyperedge_count','signaled_participant_slots','quadratic_coordination_exposure']:
                        self.assertIn(f"{r['estimate']:.6f}", main)

    def test_window_counts_and_direct_change(self):
        s4 = load('S4-results.json')
        cells = [x for x in s4['contrasts'] if x['scope']=='combined' and 'matched-binary' in x['comparison']]
        self.assertEqual(len(cells), 128)
        self.assertEqual(sum(Fraction(*c['exact']['estimate'])>0 for c in cells if c['metric']=='normalized_restricted_tau_nopath'), 64)
        self.assertEqual(sum(Fraction(*c['exact']['estimate'])<0 for c in cells if c['metric']=='failure_risk'), 64)
        direct = [x for x in s4['contrasts'] if x['scope']=='combined' and x['comparison']=='DA-minus-FHS5' and x['window']=='half' and x['metric']=='normalized_restricted_tau_nopath']
        self.assertEqual(len(direct), 8)
        self.assertEqual(sum(x['exact']['estimate'][0]==0 for x in direct), 7)
        for change in s4['window_changes']:
            rows = {x['window']: x for x in s4['contrasts'] if all(x[k]==change[k] for k in ['phase','node_count','metric','comparison','scope'])}
            self.assertEqual(Fraction(*change['exact']['estimate']), Fraction(*rows['half']['exact']['estimate'])-Fraction(*rows['full']['exact']['estimate']))
        binary_changes = [x for x in s4['window_changes'] if x['scope']=='combined' and 'matched-binary' in x['comparison']]
        self.assertEqual(sum(Fraction(*x['exact']['estimate'])<0 for x in binary_changes if x['metric']=='normalized_restricted_tau_nopath'), 32)
        self.assertEqual(sum(Fraction(*x['exact']['estimate'])>0 for x in binary_changes if x['metric']=='failure_risk'), 32)

    def test_no_old_corrections_or_references_lost(self):
        main = (OUT / 'main.tex').read_text('utf-8')
        for c in json.loads((ROOT / 'manuscript/joconline-latex/accuracy-corrections.json').read_bytes())['replacements']:
            self.assertIn(c['new'], main)
        self.assertEqual(main.count('\\bibitem'), 15)
        self.assertEqual(main.count('\\begin{equation}'), 18)
        self.assertEqual(main.count('\\begin{figure*}'), 3)
        self.assertNotIn('\\ref{fig:s5-initialization}', main)
        self.assertIn('完整拓扑差与交互见补充图S7', main)
        self.assertNotIn('完整拓扑差与交互见补充图S2', main)
        self.assertEqual((OUT/'supplement.tex').read_text('utf-8').count('\\captionof{figure}'), 8)
        old = ROOT/'manuscript/joconline-latex/main.tex'
        self.assertEqual(hashlib.sha256(old.read_bytes()).hexdigest(),'5940108b1f3d1c9cd3cc047fa06f828e9af270e9436a1356655713cb440f3282')

if __name__ == '__main__':
    unittest.main()
