import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import supplement_initialization_common as c
from tools import run_supplement_initialization as x
from tools import verify_supplement_initialization as v

class InitializationTests(unittest.TestCase):
    def fixture(self):
        nodes=['a','b','c','d']; state=[['e1',[['a',5],['b',5],['c',5]]],['e2',[['b',5],['c',5],['d',5]]]]
        requests=[['a','d',9],['a','d',3],['d','a',2],['b','c',2],['c','b',4],['a','d',1]]
        return c.spec(nodes,state,requests,2026100705)

    def test_uniform_per_node_budget_and_canonical_remainder(self):
        nodes=['a','b','c']; edges=[['e2',['b','c']],['e1',['a','b']]]
        state=c.uniform(nodes,edges,121)
        self.assertEqual(state,[['e1',[['a',121],['b',61]]],['e2',[['b',60],['c',121]]]])
        self.assertEqual(c.uniform(nodes,list(reversed(edges)),121),state)
        self.assertEqual(v.manual_uniform(nodes,edges,121),state)

    def test_chunk_vs_whole_common_tickets_exact(self):
        s=self.fixture(); full=x.simulate(s['nodes'],s['initial_state'],s['requests'],s['routing_root_seed'],0)
        merged=[]; initial=s['initial_state']; prefix=None
        for start in range(0,len(s['requests']),2):
            chunk=x.simulate(s['nodes'],initial,s['requests'][start:start+2],s['routing_root_seed'],start)
            prefix=x.merge(prefix,chunk,start,s['nodes']); initial=chunk[2]
            for outcome in chunk[1]:
                outcome[0]+=start; merged.append(outcome)
        self.assertEqual(merged,full[1]); self.assertEqual(initial,full[2])
        whole=x.merge(None,full,0,s['nodes']); self.assertEqual(prefix,whole)
        self.assertIsNone(full[1][0][2]); self.assertIsNotNone(full[1][1][2])
        self.assertEqual(whole['completed_requests'],6)

    def test_pause_resume_retains_committed_chunk_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp); s=self.fixture(); uid=c.sha(c.encode(s)); unit={'spec':s,'reuse_optimized_family':None,'reference':{}}
            path=out/'inputs'/(uid+'.json.gz'); h=c.store(path,unit)
            row={'unit_id':uid,'path':path.relative_to(out).as_posix(),'payload_sha256':h,'horizon':len(s['requests'])}
            context={'chunk_requests':2,'version':'test'}
            first=x.execute_record(row,context,1,out); self.assertEqual(first['state'],'paused-safe-checkpoint')
            checkpoint=out/'runs'/uid/'chunks'/'000000.json.gz'; before=checkpoint.read_bytes()
            second=x.execute_record(row,context,None,out); self.assertEqual(second['state'],'computed'); self.assertEqual(before,checkpoint.read_bytes())
            result,_=c.load(out/'runs'/uid/'result.json.gz')
            full=x.simulate(s['nodes'],s['initial_state'],s['requests'],s['routing_root_seed'],0)
            self.assertEqual(result['final_state'],full[2]); self.assertEqual(result['summary']['tau_nopath'],{'observed':True,'request_index':1})
            self.assertEqual(result['summary']['accepted_request_count'],x.merge(None,full,0,s['nodes'])['accepted_request_count'])
            with patch.object(v,'OUT',out):
                checked=v.replay_unit(row,context)
            self.assertEqual(checked['status'],'passed-separate-common-ticket-replay')
            self.assertEqual(checked['chunks'],3)

    def test_pause_control_blocks_new_work(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp); s=self.fixture(); uid=c.sha(c.encode(s)); h=c.store(out/'input.json.gz',{'spec':s,'reuse_optimized_family':None,'reference':{}})
            c.save(out/'PAUSE',{'reason':'test'})
            with patch.object(x,'simulate',side_effect=AssertionError('must not execute')):
                result=x.execute_record({'unit_id':uid,'path':'input.json.gz','payload_sha256':h,'horizon':6},{'chunk_requests':2},None,out)
            self.assertEqual(result['state'],'paused-safe-checkpoint'); self.assertFalse((out/'runs').exists())

    def test_exact_optimized_reuse_does_not_simulate(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp); s=self.fixture(); uid=c.sha(c.encode(s)); ref={'phase':'formal','parent_graph_id':'test','regime_id':'r','raw_sha256':'bound'}
            unit={'spec':s,'reuse_optimized_family':'fhs5','reference':ref}; h=c.store(out/'input.json.gz',unit)
            optimized={'initial_state':s['initial_state'],'simulation_witness_sha256':'checked','summary':{'horizon':6},'audited_S3_cost':{'values':[5,10]}}
            c.store(out/'parents/formal-test.json.gz',{'parent':{'traces':[{'regime_id':'r','optimized':{'fhs5':optimized}}]}})
            with patch.object(x,'simulate',side_effect=AssertionError('must reuse')):
                result=x.execute_record({'unit_id':uid,'path':'input.json.gz','payload_sha256':h,'horizon':6},{'chunk_requests':2},None,out)
            self.assertEqual(result['state'],'computed'); self.assertEqual(result['new_chunks'],0)

    def test_corrupt_prefix_refused_on_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp); s=self.fixture(); uid=c.sha(c.encode(s)); h=c.store(out/'input.json.gz',{'spec':s,'reuse_optimized_family':None,'reference':{}})
            row={'unit_id':uid,'path':'input.json.gz','payload_sha256':h,'horizon':6}; context={'chunk_requests':2}
            x.execute_record(row,context,1,out); path=out/'runs'/uid/'chunks/000000.json.gz'; chunk,_=c.load(path)
            chunk['prefix']['accepted_request_count']+=1; c.store(path,chunk)
            with self.assertRaises(AssertionError): x.execute_record(row,context,None,out)

if __name__=='__main__': unittest.main()
