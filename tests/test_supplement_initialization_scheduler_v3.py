import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from tools import schedule_supplement_initialization_v3 as overlay
from tools import run_supplement_initialization as worker
from tools.supplement_initialization_common import encode,load,sha,store,save

class DiagnosticOverlayTests(unittest.TestCase):
    def test_transient_denial_retries_same_temp_and_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'progress.json'; real=os.replace; seen=[]
            def replace(src,dst):
                seen.append((src,dst,Path(src).read_bytes()))
                if len(seen)<3: raise PermissionError('transient')
                real(src,dst)
            with patch.object(overlay.os,'replace',side_effect=replace): overlay.diagnostic_save(path,{'n':100})
            self.assertEqual(len(seen),3); self.assertEqual(seen[0],seen[1]); self.assertEqual(seen[1],seen[2])
            self.assertEqual(path.read_bytes(),encode({'n':100})); self.assertEqual(list(Path(d).glob('*.tmp')),[])

    def test_persistent_denial_preserves_old_and_temp(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'progress.json'; save(path,{'n':0})
            with patch.object(overlay.os,'replace',side_effect=PermissionError('persistent')):
                with self.assertRaises(PermissionError): overlay.diagnostic_save(path,{'n':100},timeout=0)
            self.assertEqual(json.loads(path.read_bytes()),{'n':0})
            self.assertEqual(next(Path(d).glob('*.tmp')).read_bytes(),encode({'n':100}))

    def test_unrelated_io_not_retried(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(overlay.os,'replace',side_effect=OSError('disk')) as rename:
                with self.assertRaises(OSError): overlay.diagnostic_save(Path(d)/'p.json',{})
                self.assertEqual(rename.call_count,1)

    def test_scientific_save_not_intercepted_and_restored_on_error(self):
        original=worker.save
        def fake(row,ctx,maximum,out): worker.save(Path(out)/'science.json',{})
        with patch.object(worker,'execute_record',side_effect=fake) as execute:
            with patch.object(worker,'save',side_effect=PermissionError('scientific')) as direct:
                with patch.object(overlay,'diagnostic_save') as diagnostic:
                    with self.assertRaises(PermissionError): overlay.execute_record({'unit_id':'id'},{},1)
                    self.assertEqual(execute.call_count,1); self.assertEqual(direct.call_count,1)
                    diagnostic.assert_not_called(); self.assertIs(worker.save,direct)
        self.assertIs(worker.save,original)

    def test_scope_cannot_intercept_other_unit(self):
        def fake(row,ctx,maximum,out): worker.save(Path(out)/'run-progress'/'other.json',{})
        with patch.object(worker,'execute_record',side_effect=fake):
            with patch.object(worker,'save') as direct,patch.object(overlay,'diagnostic_save') as diagnostic:
                overlay.execute_record({'unit_id':'id'},{},1); direct.assert_called_once(); diagnostic.assert_not_called()

    def test_real_two_writers(self):
        with tempfile.TemporaryDirectory() as d:
            def writer(index):
                path=Path(d)/f'{index}.json'
                for n in range(500): overlay.diagnostic_save(path,{'n':n})
                return json.loads(path.read_bytes())
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(list(pool.map(writer,range(2))),[{'n':499},{'n':499}])

    def test_real_science_identical_pause_resume_no_resimulation(self):
        with tempfile.TemporaryDirectory() as d:
            roots=[Path(d)/'original',Path(d)/'overlay']; context={'chunk_requests':100}
            spec={'nodes':['a','b'],'initial_state':[['e', [['a',120],['b',120]]]],
                  'requests':[['a','b',1],['b','a',1]]*60,'routing_root_seed':123}
            uid=sha(encode(spec)); unit={'spec':spec,'reuse_optimized_family':None}; rows=[]
            for root in roots:
                h=store(root/'inputs'/f'{uid}.json.gz',unit)
                rows.append({'unit_id':uid,'path':f'inputs/{uid}.json.gz','payload_sha256':h,'horizon':120})
            worker.execute_record(rows[0],context,1,roots[0]); worker.execute_record(rows[0],context,None,roots[0])
            overlay.execute_record(rows[1],context,1,roots[1])
            first=roots[1]/'runs'/uid/'chunks'/'000000.json.gz'; before=first.read_bytes()
            real=worker.simulate; offsets=[]
            def simulate(nodes,state,requests,seed,offset): offsets.append(offset); return real(nodes,state,requests,seed,offset)
            with patch.object(worker,'simulate',side_effect=simulate): overlay.execute_record(rows[1],context,None,roots[1])
            self.assertEqual(offsets,[100]); self.assertEqual(first.read_bytes(),before)
            for file in ['chunks/000000.json.gz','chunks/000100.json.gz','result.json.gz']:
                a,_=load(roots[0]/'runs'/uid/file); b,_=load(roots[1]/'runs'/uid/file)
                for item in [a,b]: item.pop('generation_seconds',None); item.pop('generated_seconds_this_invocation',None); item.pop('previous_sha256',None); item.pop('last_chunk_sha256',None)
                self.assertEqual(a,b)

if __name__=='__main__': unittest.main()
