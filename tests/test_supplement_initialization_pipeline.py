import tempfile
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from tools import pipeline_supplement_initialization as p

class PipelineTests(unittest.TestCase):
    def test_active_lock_refuses_mutation(self):
        with tempfile.TemporaryDirectory() as d,patch.object(p,'OUT',Path(d)):
            (Path(d)/'RUNNING.lock').write_bytes(b'preserve')
            with self.assertRaises(AssertionError): p.ensure_idle()
            self.assertEqual((Path(d)/'RUNNING.lock').read_bytes(),b'preserve')

    def test_git_blob_bytes_and_size_checked(self):
        data=b'bound\n'; rows=[{'path':'example.json','bytes':len(data),'sha256':p.sha(data)}]
        with patch.object(p,'git',return_value=b'abc blob 6\n'+data+b'\n'): p.check_git_bytes(rows,'HEAD')
        with patch.object(p,'git',return_value=b'abc blob 6\nwrong\n\n'):
            with self.assertRaises(AssertionError): p.check_git_bytes(rows,'HEAD')

    def test_snapshot_excludes_active_controls(self):
        with tempfile.TemporaryDirectory() as d,patch.object(p,'ROOT',Path(d)),patch.object(p,'OUT',Path(d)/'results'),patch.object(p,'SOURCES',[]):
            root=Path(d)/'results'; root.mkdir()
            for name in ['PAUSE','PIPELINE.lock','progress.json','pipeline-status.json','orphan.tmp','input.json']: (root/name).write_bytes(b'keep')
            self.assertEqual([x.name for x in p.source_paths()],['input.json'])

    def test_paused_supervisor_never_dispatches(self):
        with tempfile.TemporaryDirectory() as d,patch.object(p,'OUT',Path(d)),patch.object(p,'DIAG',Path(d)/'logs'),patch.object(p,'invoke') as invoke:
            root=Path(d)
            (root/'preflight.json').write_text(json.dumps({'status':'passed'}))
            (root/'snapshot-preflight.json').write_text(json.dumps({'files':[]}))
            (root/'PAUSE').write_text('user requested')
            p.run_pipeline(); invoke.assert_not_called()
            self.assertFalse((root/'PIPELINE.lock').exists())
            self.assertEqual(json.loads((root/'pipeline-status.json').read_bytes())['state'],'paused-safe-checkpoint')

    def test_child_failure_stops_without_retry_or_upload(self):
        with tempfile.TemporaryDirectory() as d,patch.object(p,'OUT',Path(d)),patch.object(p,'DIAG',Path(d)/'logs'),patch.object(p,'invoke',side_effect=AssertionError('failure')) as invoke,patch.object(p,'seal_upload') as upload:
            root=Path(d)
            (root/'preflight.json').write_text(json.dumps({'status':'passed'}))
            (root/'snapshot-preflight.json').write_text(json.dumps({'files':[]}))
            with self.assertRaises(AssertionError): p.run_pipeline()
            self.assertEqual(invoke.call_count,1); upload.assert_not_called()
            self.assertFalse((root/'PIPELINE.lock').exists())
            self.assertEqual(json.loads((root/'pipeline-status.json').read_bytes())['state'],'stopped-on-error')

    def test_resume_binds_inputs_but_not_mutable_invocation_receipts(self):
        with tempfile.TemporaryDirectory() as d,patch.object(p,'ROOT',Path(d)):
            root=Path(d); paths=['inputs/x.json','run-progress/x.json','execution-receipts/x.json']
            rows=[]
            for name in paths:
                path=root/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(b'original')
                rows.append({'path':name,'bytes':8,'sha256':p.sha(b'original')})
            (root/paths[1]).write_bytes(b'new PID'); (root/paths[2]).write_bytes(b'new duration')
            p.validate_preflight_snapshot({'files':rows})
            (root/paths[0]).write_bytes(b'changed scientific input')
            with self.assertRaises(AssertionError): p.validate_preflight_snapshot({'files':rows})

if __name__=='__main__': unittest.main()
