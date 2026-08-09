"""Tests for the non-writing synthetic block profiler."""

from unittest.mock import patch
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


if __name__ == "__main__":
    unittest.main()
