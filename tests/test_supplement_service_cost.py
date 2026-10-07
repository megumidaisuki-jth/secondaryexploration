import unittest
import numpy as np
from tools import supplement_service_cost as s

class ServiceCostTests(unittest.TestCase):
    def test_saved_route_costs_and_rejection(self):
        edges=[['a',['u','v','w']],['b',['v','w']]]
        simulation=[[],[[1,['u','w',7],[['a','u','v'],['b','v','w']],0,[],0,[]],
                         [2,['u','w',4],None,0,[],0,[]]],[],[],[],[]]
        count,value,cost=s.summary_from_routes(edges,simulation)
        self.assertEqual((count,value),(1,7))
        self.assertEqual(cost,{'traversed_hyperedge_count':2,'signaled_participant_slots':5,
                              'quadratic_coordination_exposure':13,'unique_signaled_participants':3,
                              'route_arity_histogram':[[2,1],[3,1]]})

    def test_zero_success_is_not_zero_efficiency(self):
        self.assertIsNone(s.interval(np.full(20000,np.nan)))
        vals=np.ones(20000); vals[0]=np.nan
        self.assertIsNone(s.interval(vals))

    def test_ratio_of_means_differs_from_mean_of_ratios(self):
        service=np.array([1,9]); cost=np.array([2,9])
        self.assertEqual(cost.sum()/service.sum(),1.1)
        self.assertEqual(np.mean(cost/service),1.5)

    def test_percentile_nearest_rank(self):
        self.assertEqual(s.interval(np.arange(20000)),[499,19499])

    def test_bracket_arms_averaged_before_ratio(self):
        families=['demand-aware','fhs3','fhs5','nch']
        arms=[{'variant_id':f,'values':[10,20,30,40,50,60],'arity_log2_exposure':100.0} for f in families]
        arms.extend([{'variant_id':'b1','values':[1,2,3,4,5,6],'arity_log2_exposure':10.0},
                     {'variant_id':'b2','values':[9,18,9,18,27,36],'arity_log2_exposure':30.0}])
        parent={'panels':{f:['b1','b2'] for f in families},'traces':[{'arms':arms}]*7}
        result=s.parent_values(parent,families)
        self.assertEqual(result[1,2]/result[1,0],1.2)
        self.assertNotEqual(result[1,2]/result[1,0],(3/1+9/9)/2)

    def test_bootstrap_chunk_split_invariance(self):
        cfg={'bootstrap_seed':2026100703,'models':['a','b','c']}
        parents=np.arange(60*8*7,dtype=float).reshape(60,8,7)
        whole=s.bootstrap(cfg,'formal',30,parents,0,8)
        split=np.concatenate([s.bootstrap(cfg,'formal',30,parents,0,3),s.bootstrap(cfg,'formal',30,parents,3,8)])
        np.testing.assert_array_equal(whole,split)
        self.assertNotEqual(s.sample_indices(cfg,'formal',30,0),s.sample_indices(cfg,'confirmation',30,0))

if __name__=='__main__': unittest.main()
