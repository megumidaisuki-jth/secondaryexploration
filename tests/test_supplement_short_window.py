import json
import unittest
from fractions import Fraction
import numpy as np
from tools import supplement_short_window as s
from tools import verify_supplement_short_window as v


class ShortWindowTests(unittest.TestCase):
    def test_administrative_censor_stays_unobserved(self):
        self.assertEqual(s.observation(False, 120, 120, 60), (60, 0))

    def test_survival_area_separate_checker(self):
        for flag,t in [(True,0),(True,59),(True,60),(True,61),(True,120),(False,120)]:
            for h in [60,120]:
                time,risk=s.observation(flag,t,120,h)
                self.assertEqual(v.endpoint((flag,t),h,120),(Fraction(time,h),Fraction(risk)))

    def test_event_at_boundary_is_observed(self):
        self.assertEqual(s.observation(True, 60, 120, 60), (60, 1))
        self.assertEqual(s.observation(True, 61, 120, 60), (60, 0))
        self.assertEqual(s.observation(True, 0, 120, 60), (0, 1))

    def test_invalid_censor_or_extended_horizon_rejected(self):
        for args in [(False, 100, 120, 60), (True, 130, 120, 60), (True, 100, 120, 121)]:
            with self.assertRaises(AssertionError): s.observation(*args)

    def test_clip_individual_times_not_contrast(self):
        ev={'a':(True,8),'b':(True,6)}
        self.assertEqual(s.trace_difference(ev,'a',['b'],10,10),[4,0])
        self.assertEqual(s.trace_difference(ev,'a',['b'],5,10),[0,0])

    def test_bracket_averaged_after_clipping(self):
        ev={'a':(True,4),'b':(True,2),'c':(True,9)}
        self.assertEqual(s.trace_difference(ev,'a',['b','c'],5,10),[1,1])

    def test_shared_stratified_indices(self):
        cfg={'bootstrap_seed':2026100704,'models':['a','b','c']}
        ids=s.samples(cfg,'formal',30,23)
        self.assertEqual([sum(g*20<=i<(g+1)*20 for i in ids) for g in range(3)],[20]*3)
        self.assertEqual(ids,s.samples(cfg,'formal',30,23))
        self.assertNotEqual(ids,s.samples(cfg,'confirmation',30,23))
        arr=np.arange(60,dtype=np.int64)[:,None,None,None,None]*np.ones((60,2,3,5,2),dtype=np.int64)
        draw=s.bootstrap(cfg,'formal',30,arr,0)
        for rep in (0,1,499):
            np.testing.assert_array_equal(draw[rep],arr[s.samples(cfg,'formal',30,rep)].sum(axis=0))
        np.testing.assert_array_equal(draw[:,0],draw[:,1])

    def test_change_normalization_and_exact_quantiles(self):
        cfg=json.loads(s.CONFIG.read_bytes())
        arr=np.zeros((60,2,3,5,2),dtype=np.int64)
        arr[:,0,0,0,:]=[2,1]; arr[:,1,0,0,:]=[3,2]
        draws=np.repeat(arr.sum(axis=0)[None],20000,axis=0)
        rows,changes=s.summarize(cfg,'formal',30,arr,draws)
        def get(records,metric):
            return next(r for r in records if r['scope']=='combined' and r['comparison']==cfg['comparisons'][0] and r['metric']==metric)
        self.assertEqual(get(changes,cfg['metrics'][0])['exact']['estimate'],s.frac(Fraction(1,2*7*360)))
        self.assertEqual(get(changes,cfg['metrics'][1])['exact']['estimate'],s.frac(Fraction(-1,14)))
        r=s.result_item('formal',30,'half','combined','x','risk',0,1,np.arange(20000))
        self.assertEqual(r['exact']['lower'],[499,1]); self.assertEqual(r['exact']['upper'],[19499,1])
        self.assertEqual(len(rows),60); self.assertEqual(len(changes),30)

if __name__=='__main__': unittest.main()
