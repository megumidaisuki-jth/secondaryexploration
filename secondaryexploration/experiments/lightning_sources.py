"""Hash-attested readers for public Lightning structural cross-sections."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from secondaryexploration.topology import GraphEdge, ParentGraph


BITCOIN_MAINNET_CHAIN_HASH_WIRE = (
    "6fe28c0ab6f1b372c1a6a246ae63f74f931e8365e15a089c68d6190000000000"
)
_RGS_PREFIX = b"LDK"
RGS_SOURCE_MANIFEST_SCHEMA_VERSION = 1


class LightningSourceError(ValueError):
    """Raised when an external Lightning source violates its declared contract."""


@dataclass(frozen=True, slots=True)
class RapidGossipSourceManifest:
    """Immutable identity and HTTP provenance for one captured RGS response."""

    schema_version: int
    source_id: str
    panel_year: int
    download_url: str
    rgs_version: int
    expected_chain_hash_wire: str
    latest_seen_timestamp: int
    retrieved_at_utc: str
    http_last_modified: str
    http_etag: str
    content_length: int
    sha256: str
    trust_model: str

    def __post_init__(self) -> None:
        if self.schema_version != RGS_SOURCE_MANIFEST_SCHEMA_VERSION:
            raise LightningSourceError("unsupported RGS source manifest schema")
        if type(self.source_id) is not str or not self.source_id:
            raise LightningSourceError("source_id must be nonempty")
        if type(self.panel_year) is not int or self.panel_year < 2018:
            raise LightningSourceError("panel_year is invalid")
        if type(self.download_url) is not str or not self.download_url.startswith("https://"):
            raise LightningSourceError("RGS download URL must use HTTPS")
        if self.rgs_version not in (1, 2):
            raise LightningSourceError("unsupported RGS version")
        if self.expected_chain_hash_wire != BITCOIN_MAINNET_CHAIN_HASH_WIRE:
            raise LightningSourceError("source manifest must declare Bitcoin mainnet")
        if type(self.latest_seen_timestamp) is not int or self.latest_seen_timestamp <= 0:
            raise LightningSourceError("latest_seen_timestamp must be positive")
        if type(self.retrieved_at_utc) is not str or not self.retrieved_at_utc.endswith("Z"):
            raise LightningSourceError("retrieved_at_utc must be a UTC timestamp")
        if type(self.http_last_modified) is not str or not self.http_last_modified:
            raise LightningSourceError("HTTP Last-Modified must be recorded")
        if type(self.http_etag) is not str or not self.http_etag:
            raise LightningSourceError("HTTP ETag must be recorded")
        if type(self.content_length) is not int or self.content_length <= 0:
            raise LightningSourceError("content_length must be positive")
        _validate_digest(self.sha256)
        if self.trust_model != "single-observer-semi-trusted-gossip-view":
            raise LightningSourceError("unsupported RGS trust model")


@dataclass(frozen=True, slots=True)
class RapidGossipChannel:
    """One public channel announcement recovered from an RGS snapshot."""

    short_channel_id: int
    node1: str
    node2: str
    capacity_sats: int | None

    def __post_init__(self) -> None:
        if type(self.short_channel_id) is not int or self.short_channel_id < 0:
            raise LightningSourceError("short_channel_id must be a nonnegative integer")
        if self.node1 == self.node2:
            raise LightningSourceError("self-channel announcements are unsupported")
        if self.capacity_sats is not None and (
            type(self.capacity_sats) is not int or self.capacity_sats <= 0
        ):
            raise LightningSourceError("channel capacity must be a positive integer")


@dataclass(frozen=True, slots=True)
class RapidGossipSnapshot:
    """Announcement topology from one immutable Rapid Gossip Sync response."""

    source_sha256: str
    version: int
    chain_hash_wire: str
    latest_seen_timestamp: int
    node_ids: tuple[str, ...]
    channels: tuple[RapidGossipChannel, ...]
    declared_update_count: int

    def __post_init__(self) -> None:
        _validate_digest(self.source_sha256)
        if self.version not in (1, 2):
            raise LightningSourceError("unsupported RGS version")
        if self.chain_hash_wire != BITCOIN_MAINNET_CHAIN_HASH_WIRE:
            raise LightningSourceError("RGS snapshot is not for Bitcoin mainnet")
        if type(self.latest_seen_timestamp) is not int or self.latest_seen_timestamp <= 0:
            raise LightningSourceError("latest_seen_timestamp must be positive")
        if len(set(self.node_ids)) != len(self.node_ids):
            raise LightningSourceError("RGS node identifiers must be unique")
        if any(len(node_id) != 66 or node_id[:2] not in {"02", "03"} for node_id in self.node_ids):
            raise LightningSourceError("RGS node identifiers must be compressed public keys")
        if len({channel.short_channel_id for channel in self.channels}) != len(self.channels):
            raise LightningSourceError("RGS short channel identifiers must be unique")
        if not self.channels:
            raise LightningSourceError("RGS announcement topology must be nonempty")
        known = set(self.node_ids)
        if any(
            channel.node1 not in known or channel.node2 not in known
            for channel in self.channels
        ):
            raise LightningSourceError("channel endpoint is missing from the node table")
        if self.version == 1 and any(
            channel.capacity_sats is not None for channel in self.channels
        ):
            raise LightningSourceError("RGS v1 must not contain capacities")
        if self.version == 2 and any(
            channel.capacity_sats is None for channel in self.channels
        ):
            raise LightningSourceError("RGS v2 channel capacity is missing")
        if type(self.declared_update_count) is not int or self.declared_update_count < 0:
            raise LightningSourceError("declared update count must be nonnegative")

    @property
    def announced_node_count(self) -> int:
        return len(self.node_ids)

    @property
    def channel_count(self) -> int:
        return len(self.channels)

    @property
    def channel_node_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    endpoint
                    for channel in self.channels
                    for endpoint in (channel.node1, channel.node2)
                }
            )
        )

    @property
    def parent(self) -> ParentGraph:
        simple_edges = sorted(
            {
                GraphEdge.from_endpoints(channel.node1, channel.node2)
                for channel in self.channels
            }
        )
        return ParentGraph.from_edges(
            self.channel_node_ids,
            (edge.endpoints for edge in simple_edges),
        )

    @property
    def simple_edge_capacities(self) -> tuple[tuple[GraphEdge, int], ...] | None:
        if self.version == 1:
            return None
        capacities: dict[GraphEdge, int] = {}
        for channel in self.channels:
            if channel.capacity_sats is None:  # guarded by the snapshot contract
                raise LightningSourceError("RGS v2 channel capacity is missing")
            edge = GraphEdge.from_endpoints(channel.node1, channel.node2)
            capacities[edge] = capacities.get(edge, 0) + channel.capacity_sats
        return tuple((edge, capacities[edge]) for edge in sorted(capacities))


class _Reader:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.position = 0

    def take(self, length: int) -> bytes:
        if type(length) is not int or length < 0:
            raise LightningSourceError("invalid RGS field length")
        end = self.position + length
        if end > len(self.payload):
            raise LightningSourceError("RGS snapshot is truncated")
        value = self.payload[self.position:end]
        self.position = end
        return value

    def uint(self, length: int) -> int:
        return int.from_bytes(self.take(length), "big")

    def collection_length(self) -> int:
        prefix = self.uint(2)
        if prefix < 0xFFFF:
            return prefix
        extension = self.uint(8)
        return 0xFFFF + extension

    def vector(self) -> bytes:
        return self.take(self.collection_length())

    def bigsize(self) -> int:
        prefix = self.uint(1)
        if prefix < 0xFD:
            return prefix
        if prefix == 0xFD:
            value = self.uint(2)
            if value < 0xFD:
                raise LightningSourceError("non-canonical BigSize value")
            return value
        if prefix == 0xFE:
            value = self.uint(4)
            if value < 0x10000:
                raise LightningSourceError("non-canonical BigSize value")
            return value
        value = self.uint(8)
        if value < 0x100000000:
            raise LightningSourceError("non-canonical BigSize value")
        return value


def load_rapid_gossip_snapshot(
    source: str | Path,
    expected_sha256: str,
) -> RapidGossipSnapshot:
    """Verify and parse the topology/capacity announcement prefix of RGS v1/v2."""

    _validate_digest(expected_sha256)
    path = Path(source)
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise LightningSourceError(f"cannot read RGS snapshot: {path}") from exc
    observed_sha256 = hashlib.sha256(payload).hexdigest()
    if observed_sha256 != expected_sha256:
        raise LightningSourceError(
            f"RGS SHA-256 mismatch: expected {expected_sha256}, observed {observed_sha256}"
        )

    reader = _Reader(payload)
    if reader.take(3) != _RGS_PREFIX:
        raise LightningSourceError("unknown RGS prefix")
    version = reader.uint(1)
    if version not in (1, 2):
        raise LightningSourceError("unsupported RGS version")
    chain_hash_wire = reader.take(32).hex()
    latest_seen_timestamp = reader.uint(4)

    default_feature_count = 0
    if version == 2:
        default_feature_count = reader.uint(1)
        for _ in range(default_feature_count):
            reader.vector()

    node_count = reader.uint(4)
    if node_count > 500_000:
        raise LightningSourceError("RGS node count exceeds the reader safety bound")
    node_ids: list[str] = []
    for _ in range(node_count):
        raw_node_id = bytearray(reader.take(33))
        detail_flags = raw_node_id[0]
        if version == 2:
            raw_node_id[0] = detail_flags & 0b11
            if detail_flags & (1 << 2):
                address_count = reader.uint(1)
                for _ in range(address_count):
                    reader.take(reader.uint(1))
            feature_marker = (detail_flags >> 3) & 0b111
            if feature_marker == 0b111:
                reader.vector()
            elif feature_marker > default_feature_count:
                raise LightningSourceError("RGS node feature-default index is out of bounds")
            if detail_flags & (1 << 7):
                reader.vector()
        node_ids.append(bytes(raw_node_id).hex())

    announcement_count = reader.uint(4)
    if announcement_count > 2_000_000:
        raise LightningSourceError("RGS channel count exceeds the reader safety bound")
    previous_short_channel_id = 0
    channels: list[RapidGossipChannel] = []
    for _ in range(announcement_count):
        reader.vector()  # channel feature bits are not needed for structural panels
        short_channel_id = previous_short_channel_id + reader.bigsize()
        if short_channel_id > (1 << 64) - 1:
            raise LightningSourceError("short channel identifier overflow")
        previous_short_channel_id = short_channel_id
        node1_index = reader.bigsize()
        node2_index = reader.bigsize()
        has_additional_data = version == 2 and bool(node2_index & (1 << 63))
        if version == 2:
            node2_index &= ~(1 << 63)
        if max(node1_index, node2_index) >= node_count:
            raise LightningSourceError("RGS channel endpoint index is out of bounds")
        capacity_sats: int | None = None
        if version == 2:
            if not has_additional_data:
                raise LightningSourceError("RGS v2 channel is missing funding data")
            additional_data = _Reader(reader.vector())
            capacity_sats = additional_data.bigsize()
            if additional_data.position != len(additional_data.payload):
                raise LightningSourceError("unsupported RGS channel additional data")
        channels.append(
            RapidGossipChannel(
                short_channel_id,
                node_ids[node1_index],
                node_ids[node2_index],
                capacity_sats,
            )
        )

    declared_update_count = reader.uint(4)
    return RapidGossipSnapshot(
        observed_sha256,
        version,
        chain_hash_wire,
        latest_seen_timestamp,
        tuple(node_ids),
        tuple(channels),
        declared_update_count,
    )


def load_rapid_gossip_source_manifest(
    source: str | Path,
) -> RapidGossipSourceManifest:
    """Load a strict JSON source manifest, rejecting duplicate and unknown keys."""

    path = Path(source)
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text, object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LightningSourceError(f"cannot load RGS source manifest: {path}") from exc
    if not isinstance(raw, dict):
        raise LightningSourceError("RGS source manifest must be a JSON object")
    expected = {
        "schema_version",
        "source_id",
        "panel_year",
        "download_url",
        "rgs_version",
        "expected_chain_hash_wire",
        "latest_seen_timestamp",
        "retrieved_at_utc",
        "http_last_modified",
        "http_etag",
        "content_length",
        "sha256",
        "trust_model",
    }
    observed = set(raw)
    if observed != expected:
        missing = sorted(expected - observed)
        unknown = sorted(observed - expected)
        raise LightningSourceError(
            f"RGS source manifest fields differ: missing={missing}, unknown={unknown}"
        )
    return RapidGossipSourceManifest(**raw)


def load_manifested_rapid_gossip_snapshot(
    manifest: RapidGossipSourceManifest,
    snapshot_path: str | Path,
) -> RapidGossipSnapshot:
    """Load an RGS snapshot and bind its identity to all manifest assertions."""

    if not isinstance(manifest, RapidGossipSourceManifest):
        raise LightningSourceError("manifest must be a RapidGossipSourceManifest")
    path = Path(snapshot_path)
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise LightningSourceError(f"cannot stat RGS snapshot: {path}") from exc
    if size != manifest.content_length:
        raise LightningSourceError(
            f"RGS content length mismatch: expected {manifest.content_length}, observed {size}"
        )
    snapshot = load_rapid_gossip_snapshot(path, manifest.sha256)
    if snapshot.version != manifest.rgs_version:
        raise LightningSourceError("RGS version does not match source manifest")
    if snapshot.chain_hash_wire != manifest.expected_chain_hash_wire:
        raise LightningSourceError("RGS chain hash does not match source manifest")
    if snapshot.latest_seen_timestamp != manifest.latest_seen_timestamp:
        raise LightningSourceError("RGS latest-seen timestamp does not match source manifest")
    return snapshot


def _validate_digest(value: str) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise LightningSourceError("SHA-256 digest must be 64 lowercase hexadecimal characters")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise LightningSourceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result
