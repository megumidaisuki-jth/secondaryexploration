"""Contract tests for deterministic, namespaced random seeds."""

from __future__ import annotations

import unittest

from secondaryexploration.randomness import SeedError, derive_seed, rng_for


class SeedDerivationTests(unittest.TestCase):
    def test_derivation_is_deterministic_and_unsigned_64_bit(self) -> None:
        first = derive_seed(20260731, "traffic", 3)
        second = derive_seed(20260731, "traffic", 3)

        self.assertEqual(first, second)
        self.assertGreaterEqual(first, 0)
        self.assertLess(first, 2**64)

    def test_each_input_dimension_separates_tested_seed_families(self) -> None:
        reference = derive_seed(20260731, "traffic", 3)

        self.assertNotEqual(reference, derive_seed(20260732, "traffic", 3))
        self.assertNotEqual(reference, derive_seed(20260731, "topology", 3))
        self.assertNotEqual(reference, derive_seed(20260731, "traffic", 4))

    def test_version_one_known_vector(self) -> None:
        self.assertEqual(
            derive_seed(20260731, "traffic", 3),
            10157683160262707388,
        )

    def test_invalid_base_seed_is_rejected(self) -> None:
        for invalid_value in (True, 1.0, -1, 2**64):
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaisesRegex(SeedError, "base_seed"):
                    derive_seed(invalid_value, "traffic", 0)  # type: ignore[arg-type]

    def test_invalid_namespace_is_rejected(self) -> None:
        for invalid_value in (4, "", " ", " traffic", "traffic ", "traf\x00fic"):
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaisesRegex(SeedError, "namespace"):
                    derive_seed(0, invalid_value, 0)  # type: ignore[arg-type]

    def test_invalid_index_is_rejected(self) -> None:
        for invalid_value in (True, 1.0, -1, 2**64):
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaisesRegex(SeedError, "index"):
                    derive_seed(0, "traffic", invalid_value)  # type: ignore[arg-type]

    def test_namespace_is_case_sensitive(self) -> None:
        self.assertNotEqual(
            derive_seed(0, "traffic", 0),
            derive_seed(0, "Traffic", 0),
        )


class RandomReplayTests(unittest.TestCase):
    def test_rng_for_replays_the_same_sequence(self) -> None:
        first = rng_for(20260731, "traffic", 3)
        second = rng_for(20260731, "traffic", 3)

        self.assertEqual(
            [first.random() for _ in range(10)],
            [second.random() for _ in range(10)],
        )

    def test_different_namespace_changes_the_tested_sequence(self) -> None:
        traffic = rng_for(20260731, "traffic", 3)
        topology = rng_for(20260731, "topology", 3)

        self.assertNotEqual(
            [traffic.random() for _ in range(10)],
            [topology.random() for _ in range(10)],
        )


if __name__ == "__main__":
    unittest.main()
