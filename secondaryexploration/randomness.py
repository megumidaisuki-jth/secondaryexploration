"""Versioned deterministic seed derivation for replayable experiments."""

from __future__ import annotations

import hashlib
import random


_SEED_DOMAIN_V1 = b"secondaryexploration.seed.v1\x00"
_MAX_UNSIGNED_64 = 2**64 - 1
_MAX_UNSIGNED_32 = 2**32 - 1


class SeedError(ValueError):
    """Raised when a deterministic seed request is not representable."""


def derive_seed(base_seed: int, namespace: str, index: int) -> int:
    """Derive a stable unsigned 64-bit seed from a semantic seed tuple."""

    _validate_unsigned_64(base_seed, "base_seed")
    _validate_namespace(namespace)
    _validate_unsigned_64(index, "index")

    encoded_namespace = namespace.encode("utf-8")
    if len(encoded_namespace) > _MAX_UNSIGNED_32:
        raise SeedError("namespace UTF-8 encoding is too long")

    framed_request = b"".join(
        (
            _SEED_DOMAIN_V1,
            base_seed.to_bytes(8, byteorder="big", signed=False),
            len(encoded_namespace).to_bytes(4, byteorder="big", signed=False),
            encoded_namespace,
            index.to_bytes(8, byteorder="big", signed=False),
        )
    )
    digest = hashlib.sha256(framed_request).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def rng_for(base_seed: int, namespace: str, index: int) -> random.Random:
    """Create an independent standard-library generator for a seed tuple."""

    return random.Random(derive_seed(base_seed, namespace, index))


def _validate_unsigned_64(value: object, field: str) -> None:
    if type(value) is not int or not 0 <= value <= _MAX_UNSIGNED_64:
        raise SeedError(f"{field} must be an integer in [0, 2**64 - 1]")


def _validate_namespace(value: object) -> None:
    if not isinstance(value, str):
        raise SeedError("namespace must be a string")
    if not value or value != value.strip():
        raise SeedError("namespace must be non-empty and have no outer whitespace")
    if "\x00" in value:
        raise SeedError("namespace must not contain NUL")


__all__ = ["SeedError", "derive_seed", "rng_for"]
