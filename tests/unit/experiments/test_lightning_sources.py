"""Contract tests for hash-attested Lightning RGS topology snapshots."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from secondaryexploration.experiments import (
    BITCOIN_MAINNET_CHAIN_HASH_WIRE,
    LightningSourceError,
    load_manifested_rapid_gossip_snapshot,
    load_rapid_gossip_snapshot,
    load_rapid_gossip_source_manifest,
)


def _u16(value: int) -> bytes:
    return value.to_bytes(2, "big")


def _u32(value: int) -> bytes:
    return value.to_bytes(4, "big")


def _collection(payload: bytes) -> bytes:
    return _u16(len(payload)) + payload


def _bigsize(value: int) -> bytes:
    if value < 0xFD:
        return bytes((value,))
    if value <= 0xFFFF:
        return b"\xfd" + value.to_bytes(2, "big")
    if value <= 0xFFFFFFFF:
        return b"\xfe" + value.to_bytes(4, "big")
    return b"\xff" + value.to_bytes(8, "big")


def _node(byte: int) -> bytes:
    return bytes((2 + byte % 2,)) + bytes((byte,)) * 32


def _snapshot(version: int) -> bytes:
    first = _node(1)
    second = _node(2)
    prefix = b"LDK" + bytes((version,)) + bytes.fromhex(
        BITCOIN_MAINNET_CHAIN_HASH_WIRE
    ) + _u32(1_786_060_800)
    if version == 1:
        nodes = _u32(2) + first + second
        announcement = _collection(b"") + _bigsize(42) + _bigsize(0) + _bigsize(1)
    else:
        prefix += b"\x01" + _collection(b"\x01")
        # Mark address details on the first node and encode one IPv4-sized opaque
        # address record. The parser need not interpret address semantics.
        first_flagged = bytes((first[0] | 0b100,)) + first[1:]
        nodes = _u32(2) + first_flagged + b"\x01\x03abc" + second
        capacity_payload = _bigsize(1_500_000)
        announcement = (
            _collection(b"")
            + _bigsize(42)
            + _bigsize(0)
            + _bigsize((1 << 63) | 1)
            + _collection(capacity_payload)
        )
    # The loader only interprets the announcement prefix but requires an update
    # count field to prove the prefix is not truncated.
    return prefix + nodes + _u32(1) + announcement + _u32(0)


class RapidGossipSourceTests(unittest.TestCase):
    def _load(self, payload: bytes):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.lngossip"
            path.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            return load_rapid_gossip_snapshot(path, digest)

    def test_v1_recovers_announcement_topology_without_capacities(self) -> None:
        snapshot = self._load(_snapshot(1))

        self.assertEqual(snapshot.version, 1)
        self.assertEqual(snapshot.latest_seen_timestamp, 1_786_060_800)
        self.assertEqual(snapshot.announced_node_count, 2)
        self.assertEqual(snapshot.channel_count, 1)
        self.assertEqual(snapshot.parent.edge_count, 1)
        self.assertIsNone(snapshot.channels[0].capacity_sats)
        self.assertIsNone(snapshot.simple_edge_capacities)

    def test_v2_recovers_capacity_and_clears_node_detail_bits(self) -> None:
        snapshot = self._load(_snapshot(2))

        channel = snapshot.channels[0]
        self.assertEqual(snapshot.version, 2)
        self.assertEqual(channel.capacity_sats, 1_500_000)
        self.assertEqual(snapshot.simple_edge_capacities[0][1], 1_500_000)
        self.assertTrue(all(node_id[:2] in {"02", "03"} for node_id in snapshot.node_ids))

    def test_parallel_channels_are_aggregated_for_the_simple_parent(self) -> None:
        payload = _snapshot(2)
        marker = payload.rfind(_u32(0))
        first_announcement_end = marker
        second_announcement = (
            _collection(b"")
            + _bigsize(1)
            + _bigsize(0)
            + _bigsize((1 << 63) | 1)
            + _collection(_bigsize(500_000))
        )
        announcement_count_offset = (
            40 + 1 + len(_collection(b"\x01")) + 4 + 33 + 5 + 33
        )
        payload = (
            payload[:announcement_count_offset]
            + _u32(2)
            + payload[announcement_count_offset + 4:first_announcement_end]
            + second_announcement
            + _u32(0)
        )

        snapshot = self._load(payload)

        self.assertEqual(snapshot.channel_count, 2)
        self.assertEqual(snapshot.parent.edge_count, 1)
        self.assertEqual(snapshot.simple_edge_capacities[0][1], 2_000_000)

    def test_hash_mismatch_blocks_loading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.lngossip"
            path.write_bytes(_snapshot(1))

            with self.assertRaisesRegex(LightningSourceError, "SHA-256 mismatch"):
                load_rapid_gossip_snapshot(path, "0" * 64)

    def test_truncated_announcement_prefix_is_rejected(self) -> None:
        with self.assertRaisesRegex(LightningSourceError, "truncated"):
            self._load(_snapshot(2)[:-5])

    def test_strict_manifest_binds_size_hash_version_chain_and_timestamp(self) -> None:
        payload = _snapshot(2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot_path = root / "snapshot.lngossip"
            manifest_path = root / "manifest.json"
            snapshot_path.write_bytes(payload)
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source_id": "fixture-rgs-v2",
                        "panel_year": 2026,
                        "download_url": "https://example.test/snapshot/v2/0",
                        "rgs_version": 2,
                        "expected_chain_hash_wire": BITCOIN_MAINNET_CHAIN_HASH_WIRE,
                        "latest_seen_timestamp": 1_786_060_800,
                        "retrieved_at_utc": "2026-08-07T01:56:58Z",
                        "http_last_modified": "Fri, 07 Aug 2026 00:55:06 GMT",
                        "http_etag": "fixture",
                        "content_length": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "trust_model": "single-observer-semi-trusted-gossip-view",
                    }
                ),
                encoding="utf-8",
            )

            manifest = load_rapid_gossip_source_manifest(manifest_path)
            snapshot = load_manifested_rapid_gossip_snapshot(manifest, snapshot_path)

        self.assertEqual(snapshot.channel_count, 1)

    def test_manifest_rejects_duplicate_and_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
            with self.assertRaisesRegex(LightningSourceError, "duplicate JSON key"):
                load_rapid_gossip_source_manifest(path)

            path.write_text('{"unknown":1}', encoding="utf-8")
            with self.assertRaisesRegex(LightningSourceError, "unknown=\\['unknown'\\]"):
                load_rapid_gossip_source_manifest(path)


if __name__ == "__main__":
    unittest.main()
