"""Tests for the non-writing synthetic block profiler."""

from unittest.mock import patch
from types import SimpleNamespace
import unittest

from tools import profile_synthetic_block as target


class ProfileSyntheticBlockTests(unittest.TestCase):
    def test_windows_peak_working_set_is_positive(self) -> None:
        observed = target._peak_working_set_bytes()
        self.assertIsInstance(observed, int)
        self.assertGreater(observed, 0)

    def test_non_windows_peak_working_set_is_unavailable(self) -> None:
        with patch.object(target.sys, "platform", "linux"):
            self.assertIsNone(target._peak_working_set_bytes())

    def test_batch_and_profile_identity_are_exact(self) -> None:
        args = SimpleNamespace(
            batch_id="a" * 64,
            profile_id="n120-er-r0-full",
            node_count=120,
            parent_replicate=0,
            model="er_gnm",
            skip_replay=False,
        )
        target._validate_batch_identity(args)
        args.profile_id = "n120-er-r0-generation"
        with self.assertRaises(SystemExit):
            target._validate_batch_identity(args)


if __name__ == "__main__":
    unittest.main()
