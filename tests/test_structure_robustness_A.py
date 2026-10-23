from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import structure_robustness_A as a


class StructureATests(unittest.TestCase):
    def test_windows_transient_replace_denial_retries_without_deleting_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'progress.json'; a.save(path,{'old':True})
            real=a.os.replace; calls=[]
            def replace(source,target):
                calls.append(1)
                if len(calls)==1:
                    self.assertEqual(json.loads(path.read_bytes()),{'old':True})
                    raise PermissionError('transient reader handle')
                return real(source,target)
            with patch.object(a.os,'replace',side_effect=replace): a.save(path,{'new':True})
            self.assertEqual(len(calls),2); self.assertEqual(json.loads(path.read_bytes()),{'new':True})

    def fixture(self,out):
        cfg=a.config(); cfg.update(horizon=6,workers=2,minimum_free_disk_bytes=0)
        requests=[['a','c',20],['a','c',2],['c','a',1],['b','c',2],['c','b',1],['a','b',2]]
        source=[['s',[['a',5],['b',5],['c',5]]]]
        binary=[['x',[['a',3],['b',3]]],['y',[['b',3],['c',3]]],['z',[['a',3],['c',3]]]]
        context={'chunk_requests':2,'horizon':6,'test':True}
        parent={'parent_id':'toy','nodes':['a','b','c'],
                'training':{rid:{'requests':requests,'routing_root_seed':j+1} for j,rid in enumerate(cfg['training_regimes'])},
                'test':{rid:{'requests':requests,'routing_root_seed':j+101} for j,rid in enumerate(cfg['test_regimes'])},
                'families':{family:{'source':[source],**{c:[binary] for c in a.CANDIDATES}} for family in cfg['families']}}
        h=a.store(out/'parents/toy.json.gz',{'binding_sha256':a.sha(a.encode(context)),'parent':parent})
        pr={'parent_id':'toy','path':'parents/toy.json.gz','payload_sha256':h}
        index={'parents':[pr]}; a.save(out/'input-freeze.json',{'test':True})
        return cfg,context,index

    def test_training_selection_lexicographic_and_tie(self):
        base=(Fraction(1,2),Fraction(-1),Fraction(1,2))
        metrics={c:[[base] for _ in range(4)] for c in a.CANDIDATES}; fingerprints={c:c for c in a.CANDIDATES}
        metrics['volume']=[[(Fraction(3,4),-1,0)] for _ in range(4)]
        winner,scores=a.score_candidates(metrics,fingerprints); self.assertEqual(winner,'volume')
        metrics['random1']=metrics['volume']; fingerprints['random1']='000'
        self.assertEqual(a.score_candidates(metrics,fingerprints)[0],'random1')
        metrics['reciprocity']=[[(Fraction(3,4),0,0)] for _ in range(4)]
        self.assertEqual(a.score_candidates(metrics,fingerprints)[0],'reciprocity')

    def test_brackets_averaged_not_best_side(self):
        metrics={c:[[(Fraction(3,4),0,1)] for _ in range(4)] for c in a.CANDIDATES}
        metrics['volume']=[[(1,0,1),(0,-1,0)] for _ in range(4)]
        winner,scores=a.score_candidates(metrics,{c:c for c in a.CANDIDATES})
        self.assertNotEqual(winner,'volume'); self.assertEqual(scores['volume'],(Fraction(1,2),Fraction(-1,2),Fraction(1,2)))

    def test_chunk_resume_cache_and_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d); cfg,ctx,index=self.fixture(out)
            catalog=a.make_catalog(out,index,cfg,'training'); row=catalog['units'][0]
            first=a.unit_execute(str(out),row,ctx,0,max_new_chunks=1); self.assertFalse(first['complete'])
            cp=out/'runs'/row['unit_id']/'chunks/000000.json.gz'; raw=cp.read_bytes()
            self.assertTrue(a.unit_execute(str(out),row,ctx,0)['complete']); self.assertEqual(raw,cp.read_bytes())
            parent=a.read_parent(out,row['parent']); s=a.make_spec(parent,row['split'],row['regime'],row['family'],row['arm'],row['side'])
            full=a.simulate(s['nodes'],s['initial_state'],s['requests'],s['routing_root_seed'],0)
            saved,_=a.load_result(out,row['unit_id'],a.sha(a.encode(ctx)))
            self.assertEqual(saved['prefix'],a.merge(None,full,0,s['nodes'])); self.assertEqual(saved['final_state'],full[2])
            with patch.object(a,'simulate',side_effect=AssertionError('do not rerun')):
                self.assertTrue(a.unit_execute(str(out),row,ctx,0)['reused'])
            a.atomic(cp,raw+b'changed')
            with self.assertRaises(AssertionError): a.unit_execute(str(out),row,ctx,0)

    def test_pause_and_disk_guard_do_not_simulate(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d); cfg,ctx,index=self.fixture(out); row=a.make_catalog(out,index,cfg,'training')['units'][0]
            with patch.object(a,'simulate',side_effect=AssertionError('must not simulate')):
                with self.assertRaises(RuntimeError): a.unit_execute(str(out),row,ctx,2**80)
                a.save(out/'PAUSE',{'kind':'user-pause'})
                self.assertFalse(a.unit_execute(str(out),row,ctx,0)['complete'])

    def test_two_worker_training_selection_test_pipeline(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d); cfg,ctx,index=self.fixture(out)
            training=a.make_catalog(out,index,cfg,'training')
            # Two families x eight candidates share exact scientific specs: four unique runs.
            self.assertEqual(len(training['units']),4); self.assertEqual(len(training['logical']),64)
            with patch.object(a,'context_for',return_value=ctx):
                self.assertTrue(a.run_stage(out,training,cfg,ctx))
            selected=a.select_all(out,index,training,cfg,ctx)
            self.assertEqual(set(selected['toy']),{'fhs3','fhs5'})
            self.assertEqual(selected,a.select_all(out,index,training,cfg,ctx))
            test=a.make_catalog(out,index,cfg,'test',selected)
            self.assertEqual(len(test['units']),14)
            with patch.object(a,'context_for',return_value=ctx):
                self.assertTrue(a.run_stage(out,test,cfg,ctx))
            for row in test['units']:
                value,_=a.load_result(out,row['unit_id'],a.sha(a.encode(ctx)))
                self.assertEqual(value['split'],'test')
            self.assertFalse(json.loads((out/'selection-freeze.json').read_bytes())['test_results_used'])

    def test_missing_training_result_blocks_selection(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d); cfg,ctx,index=self.fixture(out); training=a.make_catalog(out,index,cfg,'training')
            with self.assertRaises(FileNotFoundError): a.select_all(out,index,training,cfg,ctx)
            self.assertFalse((out/'selection-freeze.json').exists())

    def test_real_parent_feasibility_and_seed_reproduction(self):
        cfg=a.config(); cfg.update(horizon=3); cfg['seed_namespace']+='/tests-only'
        parent=a.generate_parent(cfg,60,0,'er_gnm')
        self.assertEqual(parent,a.generate_parent(cfg,60,0,'er_gnm'))
        self.assertEqual(len(parent['training']),4); self.assertEqual(len(parent['test']),7)
        for family,states in parent['families'].items():
            L=sum(len(b) for _,b in states['source'][0])
            for name in a.CANDIDATES:
                self.assertEqual([sum(len(b) for _,b in s) for s in states[name]],[L] if L%2==0 else [L-1,L+1])
                for state in states[name]:
                    totals={n:0 for n in parent['nodes']}
                    for _,balances in state:
                        for node,value in balances: totals[node]+=value; self.assertGreater(value,0)
                    self.assertEqual(set(totals.values()),{120})

    def test_registry_24_and_80_family_allocation(self):
        registry=a.comparison_registry(a.config())
        self.assertEqual(len(registry),24); self.assertEqual(len({x['id'] for x in registry}),24)
        self.assertTrue(all(x['bonferroni_family_size']==80 for x in registry))


if __name__=='__main__': unittest.main()
