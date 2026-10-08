import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,MagicMock
from tools import task_entry_supplement_initialization as entry

class TaskEntryTests(unittest.TestCase):
    def test_unresolved_controls_refuse_dispatch(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'PAUSE').touch()
            with patch.object(entry.subprocess,'Popen') as dispatch:
                with self.assertRaises(AssertionError): entry.launch(root/'diag',root)
                dispatch.assert_not_called()

    def test_single_failure_recorded_without_retry(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); source=root/'supervisor.py'; source.touch()
            child=MagicMock(); child.pid=123; child.wait.return_value=7
            with patch.object(entry,'job_membership',return_value=False),patch.object(entry.subprocess,'Popen',return_value=child) as dispatch:
                self.assertEqual(entry.launch(root/'diag',root,source),7)
                dispatch.assert_called_once()
                kwargs=dispatch.call_args.kwargs
                self.assertEqual(kwargs['env']['PYTHONIOENCODING'],'utf-8')
            receipt=json.loads(next((root/'diag').glob('*-receipt.json')).read_bytes())
            self.assertEqual(receipt['exit_code'],7); self.assertEqual(receipt['state'],'stopped-on-error')
            self.assertFalse((root/'diag'/'ENTRY.lock').exists())

    def test_success_records_exit_and_cleans_only_entry_lock(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); source=root/'supervisor.py'; source.touch()
            child=MagicMock(); child.pid=123; child.wait.return_value=0
            with patch.object(entry,'job_membership',return_value=False),patch.object(entry.subprocess,'Popen',return_value=child):
                self.assertEqual(entry.launch(root/'diag',root,source),0)
            receipt=json.loads(next((root/'diag').glob('*-receipt.json')).read_bytes())
            self.assertEqual(receipt['state'],'finished'); self.assertEqual(receipt['restarts'],0)

if __name__=='__main__': unittest.main()
