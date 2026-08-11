"""Publish and result-blindly verify the formal-to-confirmation readiness witness.

The build path performs the complete streaming formal source/evidence replay.
The result-blind load path never parses the phase-evidence JSON; it validates a
small, exact-schema witness and recomputes every referenced raw file hash.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from typing import Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from secondaryexploration.experiments import (
    StudyManifestError,
    build_study_seed_ledger,
    load_study_design_manifest,
)
from secondaryexploration.experiments.runner import runtime_environment_fingerprint
from tools.formal_inference import (
    _load_strict_json,
    _mapping_fingerprint,
    load_phase_evidence,
    load_phase_sources,
)


SCHEMA_VERSION = "confirmation-launch-readiness.v1"
STATUS = "formal-complete-strict-replay-result-blind-ready"
EXECUTION_REVISION = "425710a418b1b28e6c5cd813dff18aeeaa6303c3"
FORMAL_MANIFEST_FINGERPRINT = (
    "ac7152fc11b79c61b1ec14dc24b26d0ee60d159b00ddaa396e166651212191a6"
)
ENVIRONMENT_FINGERPRINT = (
    "0a499b6a1334446fa6bf02a02b25e80934a22689168d6282a2ccb067ac6216c3"
)
FORMAL_PHASE = "formal"
BLOCK_COUNT = 240
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
_FIELDS = {
    "schema_version",
    "status",
    "created_at_utc",
    "readiness_revision",
    "analysis_revision",
    "execution_revision",
    "environment_fingerprint",
    "formal_manifest_fingerprint",
    "formal_summary_fingerprint",
    "formal_phase_evidence_fingerprint",
    "formal_block_registry_fingerprint",
    "source_records",
    "limitations",
    "readiness_fingerprint",
}
_SOURCE_FIELDS = {"role", "path", "sha256"}
_SOURCE_ROLES = (
    "formal_manifest",
    "formal_summary",
    "formal_phase_evidence",
    "formal_finalization_witness",
    "calibration_manifest",
    "calibration_evidence",
    "precision_evidence",
)
_CANONICAL_SOURCE_PATHS = {
    "formal_manifest": "configs/formal/synthetic-formal-v1.json",
    "formal_summary": "outputs/formal/synthetic-formal-v1/run-summary.json",
    "formal_phase_evidence": "results/inference/formal-phase-evidence.json",
    "formal_finalization_witness": (
        "results/diagnostics/formal-streaming-finalization/"
        "formal-finalization-witness.json"
    ),
    "calibration_manifest": "configs/pilot/synthetic-calibration-v1.json",
    "calibration_evidence": "results/pilot/synthetic-calibration-v1/evidence.json",
    "precision_evidence": "results/planning/formal-precision-v1.json",
}
_CANONICAL_OUTPUT = (
    "results/diagnostics/confirmation-launch-readiness/formal-ready.json"
)
_LIMITATIONS = [
    "contains-no-interval-bound-gate-estimate-direction-or-claim-field",
    "confirmation-scheduler-must-not-load-formal-phase-evidence-json",
    "readiness-does-not-authorize-selective-confirmation-launch",
    "formal-and-confirmation-scientific-evidence-remain-separate",
]
_FINALIZATION_FIELDS = {
    "schema_version",
    "status",
    "phase",
    "analysis_revision",
    "execution_revision",
    "manifest_fingerprint",
    "summary_fingerprint",
    "block_count",
    "block_byte_registry",
    "limitations",
    "witness_fingerprint",
}
_FINALIZATION_LIMITATIONS = [
    "summary-code-revision-is-scientific-execution-revision",
    "witness-analysis-revision-identifies-streaming-tooling",
    "no-scientific-endpoint-or-contrast-is-emitted-by-finalization",
]


def _digest(value: object, label: str, *, length: int = 64) -> str:
    pattern = _REVISION if length == 40 else _DIGEST
    if type(value) is not str or not pattern.fullmatch(value):
        raise StudyManifestError(f"{label} must be lowercase hexadecimal")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(root: Path, value: str | Path, *, must_exist: bool = True) -> Path:
    raw = Path(value)
    candidate = raw if raw.is_absolute() else root / raw
    lexical = Path(os.path.abspath(str(candidate)))
    try:
        lexical.relative_to(root)
    except ValueError as exc:
        raise StudyManifestError("readiness path escapes workspace") from exc
    current = root
    parts = lexical.relative_to(root).parts
    for part in (None, *parts):
        if part is not None:
            current = current / part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            continue
        attributes = getattr(metadata, "st_file_attributes", 0)
        if stat.S_ISLNK(metadata.st_mode) or (
            attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        ):
            raise StudyManifestError("readiness path contains a redirected component")
    path = lexical.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise StudyManifestError("readiness resolved path escapes workspace") from exc
    if must_exist and (not path.is_file() or path.is_symlink()):
        raise StudyManifestError(f"readiness input is missing or redirected: {path}")
    return path


def _relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise StudyManifestError("readiness source escapes workspace") from exc


def _source_records(root: Path, paths: Mapping[str, Path]) -> list[dict[str, str]]:
    if tuple(paths) != _SOURCE_ROLES:
        raise StudyManifestError("readiness source roles are not canonical")
    return [
        {"role": role, "path": _relative(root, paths[role]), "sha256": _sha256_file(paths[role])}
        for role in _SOURCE_ROLES
    ]


def canonical_source_paths(root: Path) -> dict[str, Path]:
    return {
        role: _inside(root, _CANONICAL_SOURCE_PATHS[role])
        for role in _SOURCE_ROLES
    }


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ("git", "-C", str(root), *arguments),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise StudyManifestError("Git is required for readiness attestation") from exc


def _git_blob_sha256(root: Path, revision: str, relative_path: str) -> str:
    try:
        completed = subprocess.run(
            ("git", "-C", str(root), "cat-file", "blob", f"{revision}:{relative_path}"),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise StudyManifestError("Git is required for raw readiness attestation") from exc
    if completed.returncode:
        raise StudyManifestError("cannot read readiness witness Git blob")
    return hashlib.sha256(completed.stdout).hexdigest()


def verify_source_snapshots(
    root: Path, *, readiness_revision: str, analysis_revision: str
) -> None:
    _digest(readiness_revision, "readiness_revision", length=40)
    _digest(analysis_revision, "analysis_revision", length=40)
    for revision in (readiness_revision, analysis_revision, EXECUTION_REVISION):
        if _git(root, "rev-parse", "--verify", f"{revision}^{{commit}}").returncode:
            raise StudyManifestError("declared readiness source revision does not exist")
    required = {
        readiness_revision: (
            "tools/confirmation_launch_readiness.py",
            "docs/plans/2026-08-11-confirmation-memory-operational-amendment.md",
        ),
        analysis_revision: ("tools/formal_inference.py",),
    }
    for revision, paths in required.items():
        for path in paths:
            if _git(root, "cat-file", "-e", f"{revision}:{path}").returncode:
                raise StudyManifestError("declared revision lacks readiness source")
        if _git(root, "diff", "--quiet", revision, "--", *paths).returncode:
            raise StudyManifestError("readiness source differs from declared revision")
    if _git(root, "diff", "--quiet", EXECUTION_REVISION, "--", "secondaryexploration").returncode:
        raise StudyManifestError("execution package differs from frozen revision")
    untracked = _git(
        root, "ls-files", "--others", "--exclude-standard", "--", "secondaryexploration"
    )
    if untracked.returncode or untracked.stdout.strip():
        raise StudyManifestError("untracked execution source prevents readiness")


def _validate_finalization_witness(
    witness: Mapping[str, object],
    *,
    root: Path,
    summary: Mapping[str, object],
    manifest,
    analysis_revision: str,
) -> list[dict[str, str]]:
    if set(witness) != _FINALIZATION_FIELDS:
        raise StudyManifestError("finalization witness fields differ")
    supplied = witness["witness_fingerprint"]
    content = dict(witness)
    content.pop("witness_fingerprint")
    if supplied != _mapping_fingerprint(content):
        raise StudyManifestError("finalization witness fingerprint mismatch")
    expected_scalars = {
        "schema_version": "formal-streaming-finalization-witness.v1",
        "status": "complete-memory-bounded-strict-replay",
        "phase": FORMAL_PHASE,
        "analysis_revision": analysis_revision,
        "execution_revision": EXECUTION_REVISION,
        "manifest_fingerprint": FORMAL_MANIFEST_FINGERPRINT,
        "summary_fingerprint": summary["summary_fingerprint"],
        "block_count": BLOCK_COUNT,
        "limitations": _FINALIZATION_LIMITATIONS,
    }
    for key, value in expected_scalars.items():
        if witness[key] != value:
            raise StudyManifestError(f"finalization witness {key} differs")
    registry = witness["block_byte_registry"]
    if type(registry) is not list or len(registry) != BLOCK_COUNT:
        raise StudyManifestError("finalization block registry differs")
    output_root = (root / manifest.output_root).resolve()
    rebuilt: list[dict[str, str]] = []
    for summary_row, row in zip(summary["blocks"], registry):
        if not isinstance(row, Mapping) or set(row) != {"block_key", "file_sha256"}:
            raise StudyManifestError("finalization block row fields differ")
        key = summary_row["block_key"]
        path = output_root / "blocks" / f"{key}.json"
        expected = {"block_key": key, "file_sha256": _sha256_file(path)}
        if dict(row) != expected:
            raise StudyManifestError("finalization block byte registry differs")
        rebuilt.append(expected)
    return rebuilt


def _registry_fingerprint(registry: list[dict[str, str]]) -> str:
    return _mapping_fingerprint({"blocks": registry})


def _canonical_formal_block_keys(root: Path) -> tuple[str, ...]:
    manifest = load_study_design_manifest(
        _inside(root, _CANONICAL_SOURCE_PATHS["formal_manifest"])
    )
    if manifest.fingerprint != FORMAL_MANIFEST_FINGERPRINT:
        raise StudyManifestError("result-blind formal manifest differs")
    ledger = build_study_seed_ledger(manifest)
    models = ("barabasi_albert", "er_gnm", "sbm_fixed_count")
    return tuple(
        sorted(
            f"n{seed.node_count:04d}-r{seed.parent_replicate:04d}-{model}"
            for seed in ledger.parent_seeds
            for model in models
        )
    )


def _result_blind_block_registry(
    root: Path,
    *,
    expected_keys: tuple[str, ...],
) -> list[dict[str, str]]:
    block_root = (root / "outputs/formal/synthetic-formal-v1/blocks").resolve()
    try:
        block_root.relative_to(root)
    except ValueError as exc:
        raise StudyManifestError("formal block root escapes workspace") from exc
    if block_root.is_symlink() or not block_root.is_dir():
        raise StudyManifestError("formal block root is missing or redirected")
    lock_root = block_root / ".locks"
    if lock_root.is_symlink() or not lock_root.is_dir() or any(lock_root.iterdir()):
        raise StudyManifestError("formal block locks must be empty for readiness")
    expected = set(expected_keys)
    observed: dict[str, Path] = {}
    for entry in block_root.iterdir():
        if entry.name == ".locks":
            continue
        if entry.is_symlink() or not entry.is_file() or entry.suffix != ".json":
            raise StudyManifestError("unknown formal block entry during readiness")
        if entry.stem not in expected:
            raise StudyManifestError("foreign formal block during readiness")
        observed[entry.stem] = entry
    if set(observed) != expected:
        raise StudyManifestError("formal block registry is incomplete for readiness")
    return [
        {"block_key": key, "file_sha256": _sha256_file(observed[key])}
        for key in expected_keys
    ]


def _validate_finalization_result_blind(
    witness: Mapping[str, object],
    *,
    record: Mapping[str, object],
    root: Path,
) -> list[dict[str, str]]:
    """Replay the endpoint-free finalization byte registry only."""

    if set(witness) != _FINALIZATION_FIELDS:
        raise StudyManifestError("result-blind finalization witness fields differ")
    content = dict(witness)
    supplied = content.pop("witness_fingerprint")
    if supplied != _mapping_fingerprint(content):
        raise StudyManifestError("result-blind finalization fingerprint mismatch")
    expected_scalars = {
        "schema_version": "formal-streaming-finalization-witness.v1",
        "status": "complete-memory-bounded-strict-replay",
        "phase": FORMAL_PHASE,
        "analysis_revision": record["analysis_revision"],
        "execution_revision": EXECUTION_REVISION,
        "manifest_fingerprint": FORMAL_MANIFEST_FINGERPRINT,
        "summary_fingerprint": record["formal_summary_fingerprint"],
        "block_count": BLOCK_COUNT,
        "limitations": _FINALIZATION_LIMITATIONS,
    }
    for key, value in expected_scalars.items():
        if witness[key] != value:
            raise StudyManifestError(f"result-blind finalization {key} differs")
    expected_keys = _canonical_formal_block_keys(root)
    if len(expected_keys) != BLOCK_COUNT:
        raise StudyManifestError("canonical formal block count differs")
    registered = witness["block_byte_registry"]
    if type(registered) is not list or len(registered) != BLOCK_COUNT:
        raise StudyManifestError("result-blind finalization registry differs")
    for key, row in zip(expected_keys, registered):
        if (
            not isinstance(row, Mapping)
            or set(row) != {"block_key", "file_sha256"}
            or row["block_key"] != key
        ):
            raise StudyManifestError("result-blind finalization row differs")
        _digest(row["file_sha256"], "formal block hash")
    first = _result_blind_block_registry(root, expected_keys=expected_keys)
    if first != registered:
        raise StudyManifestError("formal block bytes differ from finalization witness")
    second = _result_blind_block_registry(root, expected_keys=expected_keys)
    if second != first:
        raise StudyManifestError("formal blocks changed during result-blind replay")
    if _registry_fingerprint(second) != record["formal_block_registry_fingerprint"]:
        raise StudyManifestError("formal block registry fingerprint differs")
    return second


def validate_readiness_record(
    record: Mapping[str, object],
    *,
    root: Path,
    expected_paths: Mapping[str, Path] | None = None,
    verify_hashes: bool = True,
) -> None:
    """Validate a readiness record without parsing formal phase evidence."""

    if set(record) != _FIELDS:
        raise StudyManifestError("readiness witness fields differ")
    if record["schema_version"] != SCHEMA_VERSION or record["status"] != STATUS:
        raise StudyManifestError("readiness witness status differs")
    if type(record["created_at_utc"]) is not str or not _UTC.fullmatch(record["created_at_utc"]):
        raise StudyManifestError("readiness completion time is not canonical UTC")
    _digest(record["readiness_revision"], "readiness_revision", length=40)
    _digest(record["analysis_revision"], "analysis_revision", length=40)
    for key in (
        "execution_revision",
        "environment_fingerprint",
        "formal_manifest_fingerprint",
        "formal_summary_fingerprint",
        "formal_phase_evidence_fingerprint",
        "formal_block_registry_fingerprint",
        "readiness_fingerprint",
    ):
        _digest(record[key], key, length=40 if key == "execution_revision" else 64)
    if record["execution_revision"] != EXECUTION_REVISION:
        raise StudyManifestError("readiness execution revision differs")
    if record["environment_fingerprint"] != ENVIRONMENT_FINGERPRINT:
        raise StudyManifestError("readiness environment differs")
    if record["formal_manifest_fingerprint"] != FORMAL_MANIFEST_FINGERPRINT:
        raise StudyManifestError("readiness formal manifest differs")
    if record["limitations"] != _LIMITATIONS:
        raise StudyManifestError("readiness limitations differ")
    sources = record["source_records"]
    if type(sources) is not list or len(sources) != len(_SOURCE_ROLES):
        raise StudyManifestError("readiness sources differ")
    observed_roles = []
    for source in sources:
        if not isinstance(source, Mapping) or set(source) != _SOURCE_FIELDS:
            raise StudyManifestError("readiness source fields differ")
        role = source["role"]
        if role not in _SOURCE_ROLES:
            raise StudyManifestError("readiness source role differs")
        observed_roles.append(role)
        _digest(source["sha256"], "readiness source hash")
        path = _inside(root, source["path"])
        if expected_paths is not None and path != expected_paths[role]:
            raise StudyManifestError("readiness source path differs")
        if verify_hashes and _sha256_file(path) != source["sha256"]:
            raise StudyManifestError("readiness source bytes changed")
    if tuple(observed_roles) != _SOURCE_ROLES:
        raise StudyManifestError("readiness source order differs")
    content = dict(record)
    supplied = content.pop("readiness_fingerprint")
    if supplied != _mapping_fingerprint(content):
        raise StudyManifestError("readiness fingerprint mismatch")


def load_readiness_result_blind(
    path: Path,
    *,
    root: Path,
    authorization_revision: str,
    readiness_revision: str,
    analysis_revision: str,
) -> dict[str, object]:
    """Load the Git-pinned witness without parsing its phase-evidence source."""

    root = root.resolve()
    _digest(authorization_revision, "authorization_revision", length=40)
    expected = _inside(root, _CANONICAL_OUTPUT)
    if path.resolve() != expected:
        raise StudyManifestError("readiness witness path is not canonical")
    if _git(root, "rev-parse", "--verify", f"{authorization_revision}^{{commit}}").returncode:
        raise StudyManifestError("readiness authorization revision does not exist")
    relative = _relative(root, expected)
    if _git(root, "cat-file", "-e", f"{authorization_revision}:{relative}").returncode:
        raise StudyManifestError("authorization revision lacks readiness witness")
    if _git(root, "diff", "--quiet", authorization_revision, "--", relative).returncode:
        raise StudyManifestError("readiness witness differs from authorization revision")
    if _git_blob_sha256(root, authorization_revision, relative) != _sha256_file(expected):
        raise StudyManifestError("readiness witness raw bytes differ from Git authorization")
    verify_source_snapshots(
        root,
        readiness_revision=readiness_revision,
        analysis_revision=analysis_revision,
    )
    record = _load_strict_json(expected, "confirmation readiness witness")
    if (
        record.get("readiness_revision") != readiness_revision
        or record.get("analysis_revision") != analysis_revision
    ):
        raise StudyManifestError("readiness source revision binding differs")
    validate_readiness_record(
        record,
        root=root,
        expected_paths=canonical_source_paths(root),
        verify_hashes=True,
    )
    finalization_path = _inside(
        root, _CANONICAL_SOURCE_PATHS["formal_finalization_witness"]
    )
    finalization = _load_strict_json(
        finalization_path, "result-blind formal finalization witness"
    )
    first_registry = _validate_finalization_result_blind(
        finalization, record=record, root=root
    )
    # Close the direct-source and block-registry snapshot around one another.
    validate_readiness_record(
        record,
        root=root,
        expected_paths=canonical_source_paths(root),
        verify_hashes=True,
    )
    second_finalization = _load_strict_json(
        finalization_path, "result-blind formal finalization witness"
    )
    second_registry = _validate_finalization_result_blind(
        second_finalization, record=record, root=root
    )
    if second_finalization != finalization or second_registry != first_registry:
        raise StudyManifestError("readiness raw chain changed during result-blind load")
    return record


def _atomic_create(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(raw_temp)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp, path)
        except FileExistsError as exc:
            raise StudyManifestError("readiness witness already exists") from exc
    finally:
        temp.unlink(missing_ok=True)


def build_readiness(args) -> Path:
    root = Path(args.workspace_root).resolve()
    roles = {
        "formal_manifest": _inside(root, args.formal_manifest),
        "formal_summary": _inside(root, args.formal_summary),
        "formal_phase_evidence": _inside(root, args.formal_evidence),
        "formal_finalization_witness": _inside(root, args.finalization_witness),
        "calibration_manifest": _inside(root, args.calibration_manifest),
        "calibration_evidence": _inside(root, args.calibration_evidence),
        "precision_evidence": _inside(root, args.precision),
    }
    canonical = canonical_source_paths(root)
    if roles != canonical:
        raise StudyManifestError("readiness inputs differ from canonical source paths")
    initial_source_records = _source_records(root, roles)
    verify_source_snapshots(
        root,
        readiness_revision=args.readiness_revision,
        analysis_revision=args.analysis_revision,
    )
    sources = load_phase_sources(
        roles["formal_manifest"],
        roles["formal_summary"],
        roles["calibration_manifest"],
        roles["calibration_evidence"],
        roles["precision_evidence"],
    )
    manifest, _ledger, summary, _projection, _calibration, _precision = sources
    if manifest.phase.value != FORMAL_PHASE or manifest.fingerprint != FORMAL_MANIFEST_FINGERPRINT:
        raise StudyManifestError("readiness requires the frozen formal manifest")
    evidence = load_phase_evidence(
        roles["formal_phase_evidence"],
        sources=sources,
        analysis_revision=args.analysis_revision,
    )
    if (
        evidence["phase"] != FORMAL_PHASE
        or type(evidence["block_registry"]) is not list
        or len(evidence["block_registry"]) != BLOCK_COUNT
    ):
        raise StudyManifestError("readiness requires complete formal phase evidence")
    finalization = _load_strict_json(
        roles["formal_finalization_witness"], "formal finalization witness"
    )
    registry = _validate_finalization_witness(
        finalization,
        root=root,
        summary=summary,
        manifest=manifest,
        analysis_revision=args.analysis_revision,
    )
    created_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    target = _inside(root, args.output, must_exist=False)
    canonical_target = _inside(root, _CANONICAL_OUTPUT, must_exist=False)
    if target != canonical_target:
        raise StudyManifestError("readiness output differs from its canonical path")
    if target.exists():
        existing = _load_strict_json(target, "confirmation readiness witness")
        validate_readiness_record(existing, root=root, expected_paths=roles)
        created_at = existing["created_at_utc"]
    final_source_records = _source_records(root, roles)
    if final_source_records != initial_source_records:
        raise StudyManifestError("readiness source changed during strict replay")
    final_registry = _validate_finalization_witness(
        finalization,
        root=root,
        summary=summary,
        manifest=manifest,
        analysis_revision=args.analysis_revision,
    )
    if final_registry != registry:
        raise StudyManifestError("formal block registry changed during readiness")
    terminal_source_records = _source_records(root, roles)
    if terminal_source_records != final_source_records:
        raise StudyManifestError("readiness source changed after final block replay")
    terminal_finalization = _load_strict_json(
        roles["formal_finalization_witness"], "formal finalization witness"
    )
    if terminal_finalization != finalization:
        raise StudyManifestError("finalization witness changed during readiness")
    verify_source_snapshots(
        root,
        readiness_revision=args.readiness_revision,
        analysis_revision=args.analysis_revision,
    )
    record = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "created_at_utc": created_at,
        "readiness_revision": args.readiness_revision,
        "analysis_revision": args.analysis_revision,
        "execution_revision": EXECUTION_REVISION,
        "environment_fingerprint": runtime_environment_fingerprint(summary["environment"]),
        "formal_manifest_fingerprint": manifest.fingerprint,
        "formal_summary_fingerprint": summary["summary_fingerprint"],
        "formal_phase_evidence_fingerprint": evidence["evidence_fingerprint"],
        "formal_block_registry_fingerprint": _registry_fingerprint(registry),
        "source_records": terminal_source_records,
        "limitations": list(_LIMITATIONS),
    }
    record["readiness_fingerprint"] = _mapping_fingerprint(record)
    validate_readiness_record(record, root=root, expected_paths=roles)
    if target.exists():
        if _load_strict_json(target, "confirmation readiness witness") != record:
            raise StudyManifestError("existing readiness witness differs")
    else:
        _atomic_create(target, record)
    del evidence, sources
    return target


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-manifest", required=True)
    parser.add_argument("--formal-summary", required=True)
    parser.add_argument("--formal-evidence", required=True)
    parser.add_argument("--finalization-witness", required=True)
    parser.add_argument("--calibration-manifest", required=True)
    parser.add_argument("--calibration-evidence", required=True)
    parser.add_argument("--precision", required=True)
    parser.add_argument("--analysis-revision", required=True)
    parser.add_argument("--readiness-revision", required=True)
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    target = build_readiness(_parser().parse_args(argv))
    print(target, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
