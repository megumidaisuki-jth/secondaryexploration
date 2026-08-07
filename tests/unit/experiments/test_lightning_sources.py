"""Contract tests for hash-attested Lightning RGS topology snapshots."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from secondaryexploration.experiments import (
    BITCOIN_MAINNET_CHAIN_HASH_WIRE,
    HistoricalGmlSourceManifest,
    LightningSourceError,
    load_historical_gml_source_manifest,
    load_manifested_historical_gml_panel,
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


def _historical_gml() -> bytes:
    first, second, third = (_node(index).hex() for index in (1, 2, 3))
    return f'''graph [
  node [
    id 0
    label "{first}"
    geojson [
      country "US"
    ]
  ]
  node [
    id 1
    label "{second}"
  ]
  node [
    id 2
    label "{third}"
  ]
  edge [
    source 0
    target 1
    scid "42x1x0/0"
    htlc_maximum_msat 1000
  ]
  edge [
    source 1
    target 2
    scid "43x1x0/1"
    htlc_maximum_msat "2000"
  ]
]
'''.encode("utf-8")


def _historical_fixture(root: Path) -> tuple[Path, Path]:
    archive_path = root / "snapshots.geo.zip"
    payloads = {
        "20201230.gml.geo": _historical_gml(),
        "20230716.gml.geo": _historical_gml(),
    }
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in payloads.items():
            archive.writestr(name, payload)
    archive_bytes = archive_path.read_bytes()
    manifest_path = root / "historical.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_id": "fixture-historical",
                "dataset_doi": "10.7910/DVN/2OAVO6",
                "dataset_version": "1.1",
                "release_time_utc": "2026-02-15T00:02:00Z",
                "archive_url": "https://example.test/snapshots.geo.zip",
                "dataverse_file_id": 12510549,
                "archive_content_length": len(archive_bytes),
                "archive_member_count": 2,
                "archive_md5": hashlib.md5(archive_bytes).hexdigest(),
                "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
                "selection_rule": "latest-quality-controlled-snapshot-within-calendar-year",
                "members": [
                    {
                        "panel_year": year,
                        "member_name": name,
                        "content_length": len(payloads[name]),
                        "sha256": hashlib.sha256(payloads[name]).hexdigest(),
                        "capital_semantics": "unavailable-equal-node-capital-only",
                    }
                    for year, name in (
                        (2020, "20201230.gml.geo"),
                        (2023, "20230716.gml.geo"),
                    )
                ],
            }
        ),
        encoding="utf-8",
    )
    return archive_path, manifest_path


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


class HistoricalGmlSourceTests(unittest.TestCase):
    def test_manifested_archive_recovers_simple_parent_and_policy_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive_path, manifest_path = _historical_fixture(Path(directory))
            manifest = load_historical_gml_source_manifest(manifest_path)
            panel = load_manifested_historical_gml_panel(manifest, archive_path, 2020)

        self.assertIsInstance(manifest, HistoricalGmlSourceManifest)
        self.assertEqual(panel.panel_year, 2020)
        self.assertEqual(len(panel.node_ids), 3)
        self.assertEqual(panel.parent.edge_count, 2)
        self.assertEqual(tuple(edge.htlc_maximum_msat for edge in panel.edges), (1000, 2000))

    def test_manifest_rejects_nested_unknown_member_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, manifest_path = _historical_fixture(Path(directory))
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["members"][0]["unknown"] = True
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(LightningSourceError, "unknown=\\['unknown'\\]"):
                load_historical_gml_source_manifest(manifest_path)

    def test_archive_hash_mismatch_blocks_member_loading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive_path, manifest_path = _historical_fixture(Path(directory))
            manifest = load_historical_gml_source_manifest(manifest_path)
            bad_manifest = HistoricalGmlSourceManifest(
                manifest.schema_version,
                manifest.source_id,
                manifest.dataset_doi,
                manifest.dataset_version,
                manifest.release_time_utc,
                manifest.archive_url,
                manifest.dataverse_file_id,
                manifest.archive_content_length,
                manifest.archive_member_count,
                manifest.archive_md5,
                "0" * 64,
                manifest.selection_rule,
                manifest.members,
            )

            with self.assertRaisesRegex(LightningSourceError, "archive SHA-256 mismatch"):
                load_manifested_historical_gml_panel(bad_manifest, archive_path, 2023)


if __name__ == "__main__":
    unittest.main()
