import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from tools import seal_supplement_initialization_analysis as seal
from tools.supplement_initialization_common import save

class SealGateTests(unittest.TestCase):
    def test_active_statistics_cannot_be_sealed(self):
        with tempfile.TemporaryDirectory() as d,patch.object(seal,'ensure_ready'):
            root=Path(d); (root/'RUNNING.lock').touch()
            with patch.object(seal,'OUT',root):
                with self.assertRaises(AssertionError): seal.validate()

    def test_failed_arithmetic_receipt_cannot_be_sealed(self):
        with tempfile.TemporaryDirectory() as d,patch.object(seal,'ensure_ready'):
            root=Path(d); save(root/'verification.json',{'status':'failed'})
            with patch.object(seal,'OUT',root):
                with self.assertRaises(AssertionError): seal.validate()

    def test_incomplete_sample_counts_cannot_be_sealed(self):
        with tempfile.TemporaryDirectory() as d,patch.object(seal,'ensure_ready'):
            root=Path(d); save(root/'verification.json',{'status':'passed','parents_verified':479})
            with patch.object(seal,'OUT',root):
                with self.assertRaises(AssertionError): seal.validate()

    def test_validation_failure_never_reaches_git(self):
        with patch.object(seal,'validate',side_effect=AssertionError('unverified')),patch.object(seal,'git') as git:
            with self.assertRaises(AssertionError): seal.main()
            git.assert_not_called()

if __name__=='__main__': unittest.main()
