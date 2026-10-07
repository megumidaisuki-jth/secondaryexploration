import json
import tempfile
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch
from tools import schedule_supplement_initialization_v2 as s
from tools.supplement_initialization_common import save

class SharedProgressTests(unittest.TestCase):
    def test_real_two_writers_read_only_after_return(self):
        with tempfile.TemporaryDirectory() as d:
            def writer(path):
                for i in range(500): save(path,{'index':i})
                return path
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(writer,Path(d)/f'{i}.json') for i in range(2)]
                for future in futures:
                    self.assertEqual(s.read_progress(future.result()),{'index':499})

    def test_scientific_worker_not_reimplemented(self):
        from tools.run_supplement_initialization import execute_record,execution_context
        self.assertIs(s.execute_record,execute_record)
        self.assertIs(s.execution_context,execution_context)

    def test_transient_access_is_retried_not_skipped(self):
        with patch.object(s,'shared_read',side_effect=[PermissionError('rename'),b'{"index":1}']):
            self.assertEqual(s.read_progress('irrelevant'),{'index':1})

    def test_persistent_access_denial_stops(self):
        with patch.object(s,'shared_read',side_effect=PermissionError('blocked')):
            with self.assertRaises(PermissionError): s.read_progress('irrelevant',timeout=0)

    def test_corrupt_json_is_not_silently_accepted(self):
        with patch.object(s,'shared_read',return_value=b'invalid'):
            with self.assertRaises(json.JSONDecodeError): s.read_progress('irrelevant')

    def test_only_live_display_write_retries_are_bounded(self):
        with patch.object(s,'atomic',side_effect=[PermissionError('viewer'),None]) as write:
            s.publish_progress('display',b'data'); self.assertEqual(write.call_count,2)
        with patch.object(s,'atomic',side_effect=PermissionError('permanent')):
            with self.assertRaises(PermissionError): s.publish_progress('display',b'data',timeout=0)

if __name__=='__main__': unittest.main()
