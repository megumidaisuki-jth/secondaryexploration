"""Validated, content-addressed experiment configuration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Any


_EXPECTED_FIELDS = (
    "schema_version",
    "experiment_id",
    "base_seed",
    "replicate_count",
    "output_root",
)
_EXPECTED_FIELD_SET = frozenset(_EXPECTED_FIELDS)
_EXPERIMENT_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_NON_PORTABLE_PATH_CHARACTER = re.compile(r'[<>:"|?*\x00-\x1f]')
_MAX_UNSIGNED_64 = 2**64 - 1
_MAX_REPLICATES = 1_000_000


class ConfigError(ValueError):
    """Raised when an experiment configuration is missing or ambiguous."""


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    """The minimal immutable identity and execution envelope for an experiment."""

    schema_version: int
    experiment_id: str
    base_seed: int
    replicate_count: int
    output_root: str

    def __post_init__(self) -> None:
        _validate_schema_version(self.schema_version)
        _validate_experiment_id(self.experiment_id)
        _validate_base_seed(self.base_seed)
        _validate_replicate_count(self.replicate_count)
        _validate_output_root(self.output_root)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "ExperimentConfig":
        """Build a configuration while rejecting missing and unknown fields."""

        if not isinstance(raw, Mapping):
            raise ConfigError("configuration must be a mapping")

        missing = [field for field in _EXPECTED_FIELDS if field not in raw]
        unknown = [key for key in raw if key not in _EXPECTED_FIELD_SET]
        problems: list[str] = []
        if missing:
            problems.append("missing keys: " + ", ".join(missing))
        if unknown:
            rendered = ", ".join(sorted(repr(key) for key in unknown))
            problems.append("unknown keys: " + rendered)
        if problems:
            raise ConfigError("; ".join(problems))

        return cls(
            schema_version=raw["schema_version"],  # type: ignore[arg-type]
            experiment_id=raw["experiment_id"],  # type: ignore[arg-type]
            base_seed=raw["base_seed"],  # type: ignore[arg-type]
            replicate_count=raw["replicate_count"],  # type: ignore[arg-type]
            output_root=raw["output_root"],  # type: ignore[arg-type]
        )

    def to_canonical_mapping(self) -> dict[str, object]:
        """Return fields in the documented human-facing order."""

        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "base_seed": self.base_seed,
            "replicate_count": self.replicate_count,
            "output_root": self.output_root,
        }

    def fingerprint(self) -> str:
        """Return the SHA-256 identity of canonical JSON configuration bytes."""

        canonical_json = json.dumps(
            self.to_canonical_mapping(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(canonical_json.encode("ascii")).hexdigest()


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    """Load a strict UTF-8 JSON object and validate its experiment contract."""

    source = Path(path)
    try:
        with source.open("r", encoding="utf-8") as stream:
            raw = json.load(
                stream,
                object_pairs_hook=_mapping_without_duplicate_keys,
                parse_constant=_reject_non_json_constant,
            )
    except ConfigError as exc:
        raise ConfigError(f"invalid configuration {source}: {exc}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"could not load configuration {source}: {exc}") from exc

    try:
        return ExperimentConfig.from_mapping(raw)
    except ConfigError as exc:
        raise ConfigError(f"invalid configuration {source}: {exc}") from exc


def _validate_schema_version(value: object) -> None:
    if type(value) is not int or value != 1:
        raise ConfigError("schema_version must be integer 1")


def _validate_experiment_id(value: object) -> None:
    if not isinstance(value, str):
        raise ConfigError("experiment_id must be a string")
    if value != value.strip() or _EXPERIMENT_ID_PATTERN.fullmatch(value) is None:
        raise ConfigError(
            "experiment_id must contain 1-64 portable characters and begin with "
            "an ASCII letter or digit"
        )


def _validate_base_seed(value: object) -> None:
    if type(value) is not int or not 0 <= value <= _MAX_UNSIGNED_64:
        raise ConfigError("base_seed must be an integer in [0, 2**64 - 1]")


def _validate_replicate_count(value: object) -> None:
    if type(value) is not int or not 1 <= value <= _MAX_REPLICATES:
        raise ConfigError("replicate_count must be an integer in [1, 1_000_000]")


def _validate_output_root(value: object) -> None:
    if not isinstance(value, str):
        raise ConfigError("output_root must be a string")
    if not value or value != value.strip():
        raise ConfigError("output_root must be a non-empty unpadded relative path")
    if "\\" in value:
        raise ConfigError("output_root must use portable forward slashes")
    if _NON_PORTABLE_PATH_CHARACTER.search(value) is not None:
        raise ConfigError("output_root contains a non-portable path character")

    windows_path = PureWindowsPath(value)
    if PurePosixPath(value).is_absolute() or windows_path.is_absolute() or windows_path.drive:
        raise ConfigError("output_root must be relative and must not specify a drive")

    segments = value.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ConfigError("output_root must not contain empty, '.' or '..' segments")


def _mapping_without_duplicate_keys(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_json_constant(value: str) -> object:
    raise ConfigError(f"non-JSON numeric constant: {value}")


__all__ = ["ConfigError", "ExperimentConfig", "load_experiment_config"]
