"""Hash-attested readers for public Lightning structural cross-sections."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import zipfile

from secondaryexploration.topology import GraphEdge, ParentGraph


BITCOIN_MAINNET_CHAIN_HASH_WIRE = (
    "6fe28c0ab6f1b372c1a6a246ae63f74f931e8365e15a089c68d6190000000000"
)
_RGS_PREFIX = b"LDK"
RGS_SOURCE_MANIFEST_SCHEMA_VERSION = 1
HISTORICAL_GML_MANIFEST_SCHEMA_VERSION = 1


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
class HistoricalGmlMemberManifest:
    """Identity and declared semantics of one selected Dataverse GML member."""

    panel_year: int
    member_name: str
    content_length: int
    sha256: str
    capital_semantics: str

    def __post_init__(self) -> None:
        if type(self.panel_year) is not int or self.panel_year < 2018:
            raise LightningSourceError("historical panel year is invalid")
        if self.member_name != f"{self.panel_year}1230.gml.geo" and not (
            self.panel_year == 2023 and self.member_name == "20230716.gml.geo"
        ):
            raise LightningSourceError("historical member violates the frozen date rule")
        if type(self.content_length) is not int or self.content_length <= 0:
            raise LightningSourceError("historical member length must be positive")
        _validate_digest(self.sha256)
        if self.capital_semantics != "unavailable-equal-node-capital-only":
            raise LightningSourceError("unsupported historical capital semantics")


@dataclass(frozen=True, slots=True)
class HistoricalGmlSourceManifest:
    """Immutable archive and member identity for the 2020/2023 source."""

    schema_version: int
    source_id: str
    dataset_doi: str
    dataset_version: str
    release_time_utc: str
    archive_url: str
    dataverse_file_id: int
    archive_content_length: int
    archive_member_count: int
    archive_md5: str
    archive_sha256: str
    selection_rule: str
    members: tuple[HistoricalGmlMemberManifest, ...]

    def __post_init__(self) -> None:
        if self.schema_version != HISTORICAL_GML_MANIFEST_SCHEMA_VERSION:
            raise LightningSourceError("unsupported historical GML manifest schema")
        if type(self.source_id) is not str or not self.source_id:
            raise LightningSourceError("historical source_id must be nonempty")
        if self.dataset_doi != "10.7910/DVN/2OAVO6":
            raise LightningSourceError("unexpected historical dataset DOI")
        if self.dataset_version != "1.1":
            raise LightningSourceError("unexpected historical dataset version")
        if type(self.release_time_utc) is not str or not self.release_time_utc.endswith("Z"):
            raise LightningSourceError("historical release time must be UTC")
        if type(self.archive_url) is not str or not self.archive_url.startswith("https://"):
            raise LightningSourceError("historical archive URL must use HTTPS")
        if self.dataverse_file_id != 12510549:
            raise LightningSourceError("unexpected Dataverse file id")
        if type(self.archive_content_length) is not int or self.archive_content_length <= 0:
            raise LightningSourceError("historical archive length must be positive")
        if type(self.archive_member_count) is not int or self.archive_member_count <= 0:
            raise LightningSourceError("historical archive member count must be positive")
        _validate_hex(self.archive_md5, 32, "MD5")
        _validate_digest(self.archive_sha256)
        if self.selection_rule != "latest-quality-controlled-snapshot-within-calendar-year":
            raise LightningSourceError("unsupported historical snapshot selection rule")
        if type(self.members) is not tuple or tuple(
            member.panel_year for member in self.members
        ) != (2020, 2023):
            raise LightningSourceError("historical members must be canonical 2020/2023 entries")

    def member_for_year(self, panel_year: int) -> HistoricalGmlMemberManifest:
        for member in self.members:
            if member.panel_year == panel_year:
                return member
        raise LightningSourceError(f"historical panel year is not declared: {panel_year}")


@dataclass(frozen=True, slots=True)
class HistoricalGmlEdge:
    """One simple public edge retained by the dataset's cleaning pipeline."""

    scid_direction: str
    node1: str
    node2: str
    htlc_maximum_msat: int

    def __post_init__(self) -> None:
        if type(self.scid_direction) is not str or not self.scid_direction:
            raise LightningSourceError("historical edge SCID must be nonempty")
        if self.node1 == self.node2:
            raise LightningSourceError("historical self edges are unsupported")
        if type(self.htlc_maximum_msat) is not int or self.htlc_maximum_msat <= 0:
            raise LightningSourceError("historical edge must have a positive HTLC maximum")


@dataclass(frozen=True, slots=True)
class HistoricalGmlPanel:
    """Hash-attested simple graph from one quality-controlled GML member."""

    panel_year: int
    member_name: str
    member_sha256: str
    node_ids: tuple[str, ...]
    edges: tuple[HistoricalGmlEdge, ...]

    def __post_init__(self) -> None:
        _validate_digest(self.member_sha256)
        if not self.node_ids or len(set(self.node_ids)) != len(self.node_ids):
            raise LightningSourceError("historical node identifiers must be nonempty and unique")
        if any(len(node_id) != 66 or node_id[:2] not in {"02", "03"} for node_id in self.node_ids):
            raise LightningSourceError("historical node label is not a compressed public key")
        if not self.edges:
            raise LightningSourceError("historical panel edge set must be nonempty")
        known = set(self.node_ids)
        canonical_edges = [GraphEdge.from_endpoints(edge.node1, edge.node2) for edge in self.edges]
        if len(set(canonical_edges)) != len(canonical_edges):
            raise LightningSourceError("historical GML must be a simple graph")
        if any(edge.node1 not in known or edge.node2 not in known for edge in self.edges):
            raise LightningSourceError("historical edge endpoint is missing from node records")
        incident = {endpoint for edge in self.edges for endpoint in (edge.node1, edge.node2)}
        if incident != known:
            raise LightningSourceError("historical panel contains isolated node records")

    @property
    def parent(self) -> ParentGraph:
        return ParentGraph.from_edges(
            self.node_ids,
            ((edge.node1, edge.node2) for edge in self.edges),
        )


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


def load_historical_gml_source_manifest(
    source: str | Path,
) -> HistoricalGmlSourceManifest:
    """Load the strict Dataverse archive/member contract."""

    path = Path(source)
    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text, object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LightningSourceError(f"cannot load historical GML manifest: {path}") from exc
    if not isinstance(raw, dict):
        raise LightningSourceError("historical GML manifest must be a JSON object")
    expected = {
        "schema_version",
        "source_id",
        "dataset_doi",
        "dataset_version",
        "release_time_utc",
        "archive_url",
        "dataverse_file_id",
        "archive_content_length",
        "archive_member_count",
        "archive_md5",
        "archive_sha256",
        "selection_rule",
        "members",
    }
    _require_exact_fields(raw, expected, "historical GML manifest")
    raw_members = raw["members"]
    if not isinstance(raw_members, list):
        raise LightningSourceError("historical members must be a JSON array")
    member_fields = {
        "panel_year",
        "member_name",
        "content_length",
        "sha256",
        "capital_semantics",
    }
    members: list[HistoricalGmlMemberManifest] = []
    for raw_member in raw_members:
        if not isinstance(raw_member, dict):
            raise LightningSourceError("historical member must be a JSON object")
        _require_exact_fields(raw_member, member_fields, "historical GML member")
        members.append(HistoricalGmlMemberManifest(**raw_member))
    payload = dict(raw)
    payload["members"] = tuple(members)
    return HistoricalGmlSourceManifest(**payload)


def load_manifested_historical_gml_panel(
    manifest: HistoricalGmlSourceManifest,
    archive_path: str | Path,
    panel_year: int,
) -> HistoricalGmlPanel:
    """Verify the Dataverse archive and parse one declared historical member."""

    if not isinstance(manifest, HistoricalGmlSourceManifest):
        raise LightningSourceError("manifest must be a HistoricalGmlSourceManifest")
    member = manifest.member_for_year(panel_year)
    path = Path(archive_path)
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise LightningSourceError(f"cannot stat historical archive: {path}") from exc
    if size != manifest.archive_content_length:
        raise LightningSourceError(
            "historical archive content length mismatch: "
            f"expected {manifest.archive_content_length}, observed {size}"
        )
    observed_md5, observed_sha256 = _file_digests(path)
    if observed_md5 != manifest.archive_md5:
        raise LightningSourceError("historical archive MD5 mismatch")
    if observed_sha256 != manifest.archive_sha256:
        raise LightningSourceError("historical archive SHA-256 mismatch")
    try:
        with zipfile.ZipFile(path) as archive:
            if len(archive.infolist()) != manifest.archive_member_count:
                raise LightningSourceError("historical archive member count mismatch")
            info = archive.getinfo(member.member_name)
            if info.file_size != member.content_length:
                raise LightningSourceError("historical member content length mismatch")
            payload = archive.read(info)
    except (OSError, KeyError, zipfile.BadZipFile, RuntimeError) as exc:
        raise LightningSourceError("cannot read declared historical GML member") from exc
    observed_member_sha256 = hashlib.sha256(payload).hexdigest()
    if observed_member_sha256 != member.sha256:
        raise LightningSourceError("historical member SHA-256 mismatch")
    return _parse_historical_gml(
        payload,
        member.panel_year,
        member.member_name,
        observed_member_sha256,
    )


def _parse_historical_gml(
    payload: bytes,
    panel_year: int,
    member_name: str,
    member_sha256: str,
) -> HistoricalGmlPanel:
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise LightningSourceError("historical GML is not UTF-8") from exc
    depth = 0
    current_kind: str | None = None
    current: dict[str, object] = {}
    node_by_index: dict[int, str] = {}
    edge_records: list[tuple[int, int, str, int]] = []
    saw_graph = False
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.endswith("["):
            key = stripped[:-1].strip()
            if depth == 0:
                if key != "graph" or saw_graph:
                    raise LightningSourceError("historical GML root must be one graph")
                saw_graph = True
            elif depth == 1:
                if key not in {"node", "edge"} or current_kind is not None:
                    raise LightningSourceError(
                        f"unsupported historical GML block at line {line_number}"
                    )
                current_kind = key
                current = {}
            depth += 1
            continue
        if stripped == "]":
            if depth <= 0:
                raise LightningSourceError("historical GML has an unmatched closing bracket")
            if depth == 2 and current_kind is not None:
                if current_kind == "node":
                    _finish_historical_node(current, node_by_index)
                else:
                    edge_records.append(_finish_historical_edge(current))
                current_kind = None
                current = {}
            depth -= 1
            continue
        if depth == 2 and current_kind is not None:
            key, separator, value = stripped.partition(" ")
            if not separator:
                raise LightningSourceError(
                    f"malformed historical GML scalar at line {line_number}"
                )
            wanted = (
                {"id", "label"}
                if current_kind == "node"
                else {"source", "target", "scid", "htlc_maximum_msat"}
            )
            if key in wanted:
                if key in current:
                    raise LightningSourceError(f"duplicate historical GML field: {key}")
                current[key] = _parse_gml_scalar(key, value)
    if not saw_graph or depth != 0 or current_kind is not None:
        raise LightningSourceError("historical GML bracket structure is incomplete")
    if not node_by_index or not edge_records:
        raise LightningSourceError("historical GML contains no structural graph")
    ordered_indices = sorted(node_by_index)
    if ordered_indices != list(range(len(ordered_indices))):
        raise LightningSourceError("historical GML node indices must be contiguous from zero")
    node_ids = tuple(node_by_index[index] for index in ordered_indices)
    edges: list[HistoricalGmlEdge] = []
    for source, target, scid, htlc_maximum_msat in edge_records:
        if source not in node_by_index or target not in node_by_index:
            raise LightningSourceError("historical edge index is out of bounds")
        edges.append(
            HistoricalGmlEdge(
                scid,
                node_by_index[source],
                node_by_index[target],
                htlc_maximum_msat,
            )
        )
    return HistoricalGmlPanel(
        panel_year,
        member_name,
        member_sha256,
        node_ids,
        tuple(edges),
    )


def _finish_historical_node(
    record: dict[str, object],
    node_by_index: dict[int, str],
) -> None:
    if set(record) != {"id", "label"}:
        raise LightningSourceError("historical GML node is missing id or label")
    index = record["id"]
    label = record["label"]
    if type(index) is not int or index < 0 or type(label) is not str:
        raise LightningSourceError("historical GML node id or label is malformed")
    if index in node_by_index:
        raise LightningSourceError("historical GML node id is duplicated")
    if label in node_by_index.values():
        raise LightningSourceError("historical GML node label is duplicated")
    node_by_index[index] = label


def _finish_historical_edge(record: dict[str, object]) -> tuple[int, int, str, int]:
    expected = {"source", "target", "scid", "htlc_maximum_msat"}
    if set(record) != expected:
        raise LightningSourceError("historical GML edge is missing a required field")
    source = record["source"]
    target = record["target"]
    scid = record["scid"]
    htlc_maximum_msat = record["htlc_maximum_msat"]
    if (
        type(source) is not int
        or type(target) is not int
        or type(scid) is not str
        or type(htlc_maximum_msat) is not int
    ):
        raise LightningSourceError("historical GML edge fields are malformed")
    return source, target, scid, htlc_maximum_msat


def _parse_gml_scalar(key: str, value: str) -> int | str:
    if key in {"label", "scid"}:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise LightningSourceError(f"historical GML string is malformed: {key}") from exc
        if type(parsed) is not str:
            raise LightningSourceError(f"historical GML field must be a string: {key}")
        return parsed
    try:
        return int(value)
    except ValueError as exc:
        try:
            parsed = json.loads(value)
            if type(parsed) is str and parsed and parsed.isdecimal():
                return int(parsed)
        except json.JSONDecodeError:
            pass
        raise LightningSourceError(f"historical GML integer is malformed: {key}") from exc


def _validate_digest(value: str) -> None:
    _validate_hex(value, 64, "SHA-256")


def _validate_hex(value: str, length: int, label: str) -> None:
    if (
        type(value) is not str
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise LightningSourceError(
            f"{label} digest must be {length} lowercase hexadecimal characters"
        )


def _file_digests(path: Path) -> tuple[str, str]:
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while True:
                block = stream.read(1024 * 1024)
                if not block:
                    break
                md5.update(block)
                sha256.update(block)
    except OSError as exc:
        raise LightningSourceError(f"cannot hash historical archive: {path}") from exc
    return md5.hexdigest(), sha256.hexdigest()


def _require_exact_fields(
    raw: dict[str, object],
    expected: set[str],
    label: str,
) -> None:
    observed = set(raw)
    if observed != expected:
        missing = sorted(expected - observed)
        unknown = sorted(observed - expected)
        raise LightningSourceError(
            f"{label} fields differ: missing={missing}, unknown={unknown}"
        )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise LightningSourceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result
