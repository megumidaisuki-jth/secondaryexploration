from fractions import Fraction
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from tools import analyze_supplement_initialization as a
from tools import verify_supplement_initialization_analysis as v

class FourArmTests(unittest.TestCase):
    def test_horizon_event_and_censoring_differ_in_risk_not_time(self):
        events={arm:{'observed':False,'request_index':360} for arm in a.ARMS}
        events['DA-U']['observed']=True
        vector=a.event_vector(events,360)
        self.assertEqual(a.contrast(vector)[:5],[0]*5)
        self.assertEqual(a.contrast(vector)[5],1)

    def test_direct_interaction_and_within_topology_identity(self):
        vector=[50,20,100,40,1,0,0,1]; values=a.contrast(vector)
        self.assertEqual(values,[30,60,30,50,20,1,-1,-2,-1,1])
        self.assertEqual(values[2],values[3]-values[4])
        self.assertEqual(values[7],values[8]-values[9])
        self.assertEqual(v.differences(vector),values)

    def test_checker_has_own_gate_and_no_generator_import(self):
        with tempfile.TemporaryDirectory() as d,patch.object(v,'SOURCE',Path(d)),patch.object(v,'load',side_effect=AssertionError('must not read science')):
            (Path(d)/'VERIFYING.lock').write_text('active')
            with self.assertRaises(RuntimeError): v.require_complete()
        self.assertNotIn('analyze_supplement_initialization',Path(v.__file__).read_text().split('from tools.supplement_initialization_common')[0])

    def test_separate_scalar_checker_matches_240_generated_shapes(self):
        cfg={'scopes':['combined','same_distribution','distribution_shift'],'traces_per_scope':[7,4,3],
            'metrics':['Y','F'],'comparisons':['U','O','interaction','DA','FHS'],'models':['one','two','three']}
        parents=[{'arm_totals':{'combined':[7,0,14,0,0,7,0,7],'same_distribution':[4,0,8,0,0,4,0,4],'distribution_shift':[3,0,6,0,0,3,0,3]}} for _ in range(60)]
        draws=[[i,0,2*i,0,0,0,0,0] for i in range(20000)]
        generated,generated_arms=a.summaries(cfg,'formal',30,parents,draws)
        rows={(r['phase'],r['node_count'],r['scope'],r['metric'],r['comparison']):r for r in generated}
        arms={(r['phase'],r['node_count'],r['scope'],r['metric'],r['arm']):r for r in generated_arms}
        self.assertEqual(v.check_summary(cfg,rows,arms,'formal',30,parents,draws),30)
        row=next(r for r in generated if r['scope']=='combined'); row['exact']['upper']=[999,1]
        with self.assertRaises(AssertionError): v.check_summary(cfg,rows,arms,'formal',30,parents,draws)

    def test_shared_sampling_arms_and_contrasts_commute(self):
        cfg={'bootstrap_seed':1,'models':['one','two','three']}
        strata={m:[[i+1,2*i+1,3*i+1,4*i+1,i%2,1-i%2,i%2,1-i%2] for i in range(20)] for m in cfg['models']}
        draws=a.bootstrap(cfg,'formal',30,strata,0,10)
        for rep,draw in enumerate(draws):
            direct=[0]*10
            for model in cfg['models']:
                for i in a.indices(cfg,'formal',30,rep,model):
                    direct=[x+y for x,y in zip(direct,a.contrast(strata[model][i]))]
            self.assertEqual(a.contrast(draw),direct)

    def test_bootstrap_checkpoint_resume_preserves_bytes(self):
        cfg={'bootstrap_seed':1,'models':['one','two','three']}
        strata={m:[[i]*8 for i in range(20)] for m in cfg['models']}; binding={'source':'synthetic-only'}
        with tempfile.TemporaryDirectory() as d:
            out=Path(d); values,created=a.checkpoint(cfg,'formal',30,strata,0,binding,out)
            self.assertTrue(created); path=out/'checkpoints/formal-n0030-00000.json.gz'; before=path.read_bytes()
            with patch.object(a,'bootstrap',side_effect=AssertionError('must reuse completed chunk')):
                resumed,created=a.checkpoint(cfg,'formal',30,strata,0,binding,out)
                self.assertFalse(created); self.assertEqual(values,resumed); self.assertEqual(before,path.read_bytes())
            with self.assertRaises(AssertionError): a.checkpoint(cfg,'formal',30,strata,0,{'source':'changed'},out)

    def test_actual_inverse_ecdf_ranks_and_no_subscope_intervals(self):
        cfg={'scopes':['combined','same_distribution','distribution_shift'],'traces_per_scope':[7,4,3],
             'metrics':['Y','F'],'comparisons':['U','O','interaction','DA','FHS'],'models':['one','two','three']}
        parents=[{'arm_totals':{'combined':[7,0,14,0,0,7,0,7],'same_distribution':[4,0,8,0,0,4,0,4],'distribution_shift':[3,0,6,0,0,3,0,3]}} for _ in range(60)]
        draws=[[i,0,2*i,0,0,0,0,0] for i in range(20000)]
        rows,arms=a.summaries(cfg,'formal',30,parents,draws)
        self.assertEqual(len(rows),30); self.assertEqual(len(arms),24)
        row=next(r for r in rows if r['scope']=='combined' and r['metric']=='Y' and r['comparison']=='U')
        self.assertEqual(Fraction(*row['exact']['lower']),Fraction(499,420*360))
        self.assertEqual(Fraction(*row['exact']['upper']),Fraction(19499,420*360))
        self.assertTrue(all(set(r['exact'])=={'estimate'} for r in rows if r['scope']!='combined'))
        for comp in cfg['comparisons']:
            points={r['scope']:Fraction(*r['exact']['estimate']) for r in rows if r['comparison']==comp and r['metric']=='Y'}
            self.assertEqual(points['combined'],Fraction(4,7)*points['same_distribution']+Fraction(3,7)*points['distribution_shift'])

    def test_active_generation_gate_never_opens_endpoints(self):
        with tempfile.TemporaryDirectory() as d,patch.object(a,'load',side_effect=AssertionError('must not read science')):
            path=Path(d); (path/'RUNNING.lock').write_text('active')
            with self.assertRaisesRegex(RuntimeError,'active or paused'): a.ensure_ready(path)

    def test_incomplete_verification_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,'witness is missing'): a.ensure_ready(Path(d))

    def test_invalid_censoring_and_zero_nopath_refused(self):
        events={arm:{'observed':False,'request_index':360} for arm in a.ARMS}
        events['DA-U']['request_index']=359
        with self.assertRaises(AssertionError): a.event_vector(events,360)
        events['DA-U']={'observed':True,'request_index':0}
        with self.assertRaises(AssertionError): a.event_vector(events,360)

if __name__=='__main__': unittest.main()
