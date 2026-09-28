"""Verify manuscript reporting summaries against archived evidence, not raw runs."""
from fractions import Fraction
import unittest

from tools import export_source_data as source
from tools import build_results_displays as display
from tools import build_results_writing_support as support


class WritingSupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = source.load_json(source.OUTPUT)
        cls.result = support.build(cls.data)

    def test_source_and_saved_output(self):
        self.assertEqual(source.digest(source.OUTPUT), display.SOURCE_SHA)
        self.assertEqual(self.result, source.load_json(support.OUT / 'evidence-summary.json'))
        manifest=source.load_json(support.OUT / 'manifest.json')
        self.assertEqual(manifest['generator_sha256'], source.digest(source.ROOT/'tools/build_results_writing_support.py'))
        for name,sha in manifest['files'].items():
            self.assertEqual(source.digest(support.OUT/name),sha)

    def test_parent_summary_reconstructs_every_primary_estimate(self):
        for phase,p in self.result['phases'].items():
            self.assertEqual(len(p['parent_stratum_summaries']),120)
            for interval in self.data['phase_data'][phase]['registered_intervals']:
                rows=[r for r in p['parent_stratum_summaries'] if
                    f"{r['metric']}.n{r['node_count']:04d}.{r['source_family']}"==interval['contrast_id']]
                self.assertEqual(len(rows),3)
                self.assertEqual(sum((display.frac(r['mean']) for r in rows),Fraction())/3,display.frac(interval['estimate']))

    def test_coverage_counts_recomputed_from_events(self):
        for phase,p in self.result['phases'].items():
            self.assertEqual(len(p['event_coverage']),96)
            for row,original in zip(p['event_coverage'],self.data['phase_data'][phase]['event_coverage_q0_10']):
                count=0
                for parent in original['parents']:
                    source_ok=Fraction(parent['source_event_count'],parent['trace_count'])>=Fraction(1,10)
                    arms_ok=all(Fraction(a['event_count'],a['trace_count'])>=Fraction(1,10) for a in parent['binary_arms'])
                    count+=source_ok and arms_ok
                self.assertEqual(row['identified_parent_count'],count)
                self.assertIsNone(row['quantile_estimate'])

    def test_activity_groups_partition_parents_without_filling_null(self):
        for phase,p in self.result['phases'].items():
            self.assertEqual(len(p['activity_sensitivity']),16)
            for size in display.SIZES:
                for metric in display.METRICS:
                    groups=[r for r in p['activity_sensitivity'] if r['node_count']==size and r['metric']==metric]
                    for model in support.MODELS:
                        self.assertEqual(sum(s['parent_count'] for g in groups for s in g['strata'] if s['parent_model']==model),20)
                    for g in groups:
                        if any(s['parent_count']==0 for s in g['strata']):
                            self.assertIsNone(g['equal_model_descriptive_mean'])
                        for s in g['strata']:
                            self.assertIsNone(s['interval'])

    def test_all_descriptor_cells_and_strata_retained(self):
        for phase,p in self.result['phases'].items():
            self.assertEqual(len(p['descriptive_summaries']),208)
            self.assertEqual(len(p['descriptor_cell_ranges']),13)
            self.assertEqual(sum(len(r['strata']) for r in p['descriptive_summaries']),624)
            for row in p['descriptor_cell_ranges'].values():
                self.assertEqual(row['count'],16)
                self.assertEqual(row['negative']+row['zero']+row['positive'],16)

    def test_main_text_global_estimates_and_runtime_match(self):
        prose=(source.ROOT/'manuscript/results.md').read_text(encoding='utf-8').replace('−','-')
        for phase,p in self.result['phases'].items():
            for row in self.data['phase_data'][phase]['registered_intervals']:
                if row['tier']=='global':
                    self.assertIn(display.decimal(row['estimate']),prose)
            for key in ['generation_block_hours','exact_validation_block_hours']:
                self.assertIn(display.decimal(p['runtime'][key]),prose)
        for boundary in ['not jointly','not tests of one hypergraph family','No\nnumerical q=0.10','neither end-to-end wall-clock times','did\nnot identify a causal mechanism']:
            self.assertIn(boundary,prose)

    def test_main_text_counts_and_descriptor_directions(self):
        expected_changes={'formal':[33,21,5,1],'confirmation':[34,16,13,1]}
        negative_metrics={'initial_coordinate_imbalance','final_coordinate_imbalance',
            'final_zero_coordinate_fraction','route_hop_mass_per_attempt',
            'traversed_hyperedge_count_per_attempt','route_bottleneck_mass_per_attempt'}
        positive_metrics={'topology_pair_coverage_fraction','topology_mean_pair_multiplicity_covered',
            'signaled_participant_slots_per_attempt','unique_signaled_participants_per_attempt',
            'quadratic_coordination_exposure_per_attempt'}
        for phase,p in self.result['phases'].items():
            self.assertEqual(sum(r['identified_parent_count']==20 for r in p['event_coverage']),2)
            self.assertEqual(sum(r['identified_parent_count']==0 for r in p['event_coverage']),34 if phase=='formal' else 24)
            changed=[r for r in p['activity_sensitivity'] if r['metric']=='failure_risk' and r['topology_activity']=='changed']
            self.assertEqual([sum(s['parent_count'] for s in r['strata']) for r in changed],expected_changes[phase])
            for row in p['parent_stratum_summaries']:
                self.assertTrue(display.frac(row['mean'])<0 if row['metric']=='failure_risk' else display.frac(row['mean'])>0)
            for metric,r in p['descriptor_cell_ranges'].items():
                if metric in negative_metrics:
                    self.assertEqual(r['negative'],16)
                elif metric in positive_metrics:
                    self.assertEqual(r['positive'],16)
                else:
                    self.assertGreater(r['negative'],0)
                    self.assertGreater(r['positive'],0)


if __name__=='__main__':
    unittest.main()
