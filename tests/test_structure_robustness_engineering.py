import json
from itertools import combinations
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import structure_robustness_engineering as e
from secondaryexploration.topology import ParentGraph, fixed_hyperedge_size


class StructureEngineeringTests(unittest.TestCase):
    def fixture(self, out):
        s = e.spec(['a','b','c','d'],
            [['e1',[['a',5],['b',5],['c',5]]],['e2',[['b',5],['c',5],['d',5]]]],
            [['a','d',9],['a','d',3],['d','a',2],['b','c',2],['c','b',4],['a','d',1]], 82)
        uid = e.sha(e.encode(s)); h = e.store(out/'input.json.gz', {'spec':s,'engineering_only':True})
        return s, {'unit_id':uid,'path':'input.json.gz','payload_sha256':h,'horizon':6}

    def test_pause_resume_exact_outcomes_and_prefix(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp); s,row=self.fixture(out); context={'chunk_requests':2}
            first=e.execute_unit(out,row,context,max_chunks=1)
            self.assertEqual(first,{'state':'paused-safe-checkpoint','completed_requests':2})
            cp=out/'runs'/row['unit_id']/'chunks/000000.json.gz'; before=cp.read_bytes()
            second=e.execute_unit(out,row,context)
            self.assertEqual(second['state'],'computed-engineering-only')
            self.assertEqual(before,cp.read_bytes())
            result,_=e.load(out/'runs'/row['unit_id']/'result.json.gz')
            full=e.simulate(s['nodes'],s['initial_state'],s['requests'],s['routing_root_seed'],0)
            self.assertEqual(result['final_state'],full[2])
            self.assertEqual(result['prefix'],e.merge(None,full,0,s['nodes']))
            joined=[]
            for start in [0,2,4]:
                chunk,_=e.load(out/'runs'/row['unit_id']/'chunks'/f'{start:06d}.json.gz')
                for outcome in chunk['simulation'][1]:
                    outcome[0]+=start; joined.append(outcome)
            self.assertEqual(joined,full[1])
            with patch.object(e,'simulate',side_effect=AssertionError('completed input rerun')):
                e.execute_unit(out,row,context)

    def test_pause_prevents_simulation(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp); _,row=self.fixture(out); e.save(out/'PAUSE',{'kind':'user-pause'})
            with patch.object(e,'simulate',side_effect=AssertionError('must pause')):
                self.assertEqual(e.execute_unit(out,row,{'chunk_requests':2})['completed_requests'],0)

    def test_rehashed_corrupt_checkpoint_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp); _,row=self.fixture(out); context={'chunk_requests':2}
            e.execute_unit(out,row,context,max_chunks=1)
            cp=out/'runs'/row['unit_id']/'chunks/000000.json.gz'
            chunk,_=e.load(cp); chunk['prefix']['accepted_value']+=1; e.store(cp,chunk)
            with self.assertRaises(AssertionError): e.execute_unit(out,row,context)

    def test_changed_context_and_raw_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp); _,row=self.fixture(out)
            e.execute_unit(out,row,{'chunk_requests':2},max_chunks=1)
            with self.assertRaises(AssertionError): e.execute_unit(out,row,{'chunk_requests':3})
            cp=out/'runs'/row['unit_id']/'chunks/000000.json.gz'
            raw=bytearray(cp.read_bytes()); raw[-4]^=1
            e.atomic(cp,raw)
            with self.assertRaises(Exception): e.execute_unit(out,row,{'chunk_requests':2})

    def test_binding_refuses_change(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp); e.check_binding(out,{'version':1})
            with self.assertRaises(RuntimeError): e.check_binding(out,{'version':2})

    def test_exclusive_lock_releases_after_exception(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)
            with self.assertRaises(ValueError):
                with e.exclusive(out):
                    with self.assertRaises(OSError):
                        with e.exclusive(out): pass
                    raise ValueError('simulated shutdown')
            with e.exclusive(out): pass

    def test_binary_odd_brackets_nested_connected_and_deterministic(self):
        nodes=tuple('abcdef')
        first=e.ranked_binary(nodes,17,lambda pair:e.seed('test',*pair))
        self.assertEqual(first,e.ranked_binary(nodes,17,lambda pair:e.seed('test',*pair)))
        self.assertEqual([t.resources.incidence_count for t in first],[16,18])
        self.assertTrue(all(t.is_connected for t in first))
        self.assertTrue(set(first[0].hyperedges)<set(first[1].hyperedges))
        for top in first:
            state=e.uniform(nodes,e.topology_payload(top),120)
            totals={n:0 for n in nodes}
            for _,balances in state:
                for n,b in balances: totals[n]+=b; self.assertGreater(b,0)
            self.assertEqual(set(totals.values()),{120})

    def test_eight_candidate_slots_training_only_and_replay(self):
        nodes=tuple('abcdef')
        graph=ParentGraph.from_edges(nodes,combinations(nodes,2))
        source=fixed_hyperedge_size(graph,3)
        training=[[['a','b',6],['b','a',2],['a','c',1]]]
        candidates=e.candidate_topologies(graph,source,'test','parent',training)
        self.assertEqual(len(candidates),8)
        self.assertEqual(candidates,e.candidate_topologies(graph,source,'test','parent',training))
        self.assertEqual(set(candidates),{'b0','random0','random1','random2','random3','random4','volume','reciprocity'})
        for pair in candidates.values():
            self.assertTrue(all(top.is_connected for top in pair))
            self.assertTrue(all(abs(top.resources.incidence_count-source.resources.incidence_count)<=1 for top in pair))

    def test_independent_reachability_catches_false_reject(self):
        s={'nodes':['a','b'],'initial_state':[['e',[['a',3],['b',3]]]],'requests':[['a','b',1]],'routing_root_seed':2}
        sim=e.simulate(s['nodes'],s['initial_state'],s['requests'],s['routing_root_seed'],0)
        e.check_arithmetic(sim)
        sim[1][0][2]=None
        with self.assertRaises(AssertionError): e.check_arithmetic(sim)

    def test_namespace_isolation(self):
        self.assertNotEqual(e.seed('structure-robustness-20261022-v1','parents',60),
                            e.seed('structure-robustness-20261022-v1/engineering-only','parents',60))

    def test_real_six_parent_preparation_replay_and_one_run(self):
        cfg=json.loads(e.CONFIG.read_bytes())
        cfg.update(horizon=2, training_demand_horizon=2)
        cfg['seed_namespace']+='/unit-test-only'
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp); context={'chunk_requests':1,'test_only':True}
            catalog=e.prepare(out,cfg,context)
            self.assertEqual(len(catalog['parents']),6)
            self.assertEqual(len(catalog['logical_arms']),sum(
                len(e.load(out/'parents'/(p['parent_id']+'.json.gz'))[0]['arm_states'][a])
                for p in catalog['parents'] for a in cfg['arms'])*2)
            for p in catalog['parents']:
                parent,_=e.load(out/'parents'/(p['parent_id']+'.json.gz'))
                for arm in ['fhs3','fhs5']:
                    L=sum(len(b) for _,b in parent['arm_states'][arm][0])
                    for kind in ['b0','random0','volume','reciprocity']:
                        states=parent['arm_states'][arm+'-'+kind]
                        incidences=[sum(len(b) for _,b in s) for s in states]
                        self.assertEqual(incidences,[L] if L%2==0 else [L-1,L+1])
            self.assertEqual(catalog,e.prepare(out,cfg,context))
            self.assertEqual(e.execute_unit(out,catalog['units'][0],context)['state'],'computed-engineering-only')


if __name__=='__main__': unittest.main()
