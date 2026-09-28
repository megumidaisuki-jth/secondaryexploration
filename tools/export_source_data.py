"""Build the complete, result-blind-contract Source Data export.

The exporter consumes only fixed evidence paths after independent replay.  It
does not derive, filter, round, rank, or interpret any scientific endpoint.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "results" / "diagnostics" / "independent-replay" / "20260922-v1"
OUTPUT = ROOT / "results" / "source-data" / "synthetic-hypergraph-payment-v1" / "source-data.json"

PHASES = ("formal", "confirmation")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, object]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            value = json.load(handle, object_pairs_hook=_unique_object, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot load {path}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object at {path}")
    return value


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_new_or_identical(path: Path, value: dict[str, object]) -> None:
    if path.exists():
        if load_json(path) != value:
            raise RuntimeError(f"existing Source Data differs: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def flatten_intervals(phase: str, evidence: dict[str, object]) -> list[dict[str, object]]:
    rows = []
    hierarchies = evidence.get("hierarchies")
    if not isinstance(hierarchies, list) or len(hierarchies) != 8:
        raise RuntimeError(f"{phase} hierarchy registry differs")
    for hierarchy in hierarchies:
        if not isinstance(hierarchy, dict) or not isinstance(hierarchy.get("intervals"), list):
            raise RuntimeError(f"{phase} hierarchy is malformed")
        for interval in hierarchy["intervals"]:
            if not isinstance(interval, dict):
                raise RuntimeError(f"{phase} interval is malformed")
            rows.append(
                {
                    "phase": phase,
                    "family_id": hierarchy["family_id"],
                    "phase_family_scope": hierarchy["phase_family_scope"],
                    "adjusted_tail_probability": hierarchy["adjusted_tail_probability"],
                    "resamples": hierarchy["resamples"],
                    **interval,
                }
            )
    rows.sort(key=lambda row: row["contrast_id"])
    if len(rows) != 40 or len({row["contrast_id"] for row in rows}) != 40:
        raise RuntimeError(f"{phase} interval registry differs")
    return rows


def audited_input(stage: str, path: Path) -> dict[str, object]:
    receipt = load_json(AUDIT / f"{stage}.success.json")
    if receipt.get("exit_code") != 0 or receipt.get("output_sha256") != digest(path):
        raise RuntimeError(f"independent replay receipt does not bind {stage}")
    return receipt


def phase_paths(phase: str) -> dict[str, Path]:
    return {
        "phase_evidence": ROOT / f"results/inference/{phase}-phase-evidence.json",
        "descriptive_evidence": ROOT / f"results/inference/{phase}-descriptive-mechanism-v1.json",
        "run_summary": ROOT / f"outputs/{phase}/synthetic-{phase}-v1/run-summary.json",
    }


def build() -> dict[str, object]:
    phase_data: dict[str, object] = {}
    source_files: dict[str, str] = {}
    audit_receipts: dict[str, object] = {}
    for phase in PHASES:
        paths = phase_paths(phase)
        phase_evidence = load_json(paths["phase_evidence"])
        descriptive_evidence = load_json(paths["descriptive_evidence"])
        summary = load_json(paths["run_summary"])
        if phase_evidence.get("status") != "complete-strict-replay":
            raise RuntimeError(f"{phase} phase evidence is not complete")
        if descriptive_evidence.get("status") != "complete-exploratory-no-inference":
            raise RuntimeError(f"{phase} descriptive evidence is not complete")
        if summary.get("status") != "complete" or summary.get("completed_block_count") != 240:
            raise RuntimeError(f"{phase} run summary is incomplete")
        phase_data[phase] = {
            "registered_intervals": flatten_intervals(phase, phase_evidence),
            "parent_model_values": phase_evidence["parent_contrasts"],
            "event_coverage_q0_10": phase_evidence["event_coverage"],
            "activity_sensitivity": phase_evidence["activity_sensitivity"],
            "descriptive_parent_values": descriptive_evidence["parent_contrasts"],
            "descriptive_summaries": descriptive_evidence["summaries"],
            "runtime_and_environment": summary,
            "phase_source_fingerprints": phase_evidence["source_fingerprints"],
            "descriptive_source_fingerprints": descriptive_evidence["source_fingerprints"],
        }
        for label, path in paths.items():
            source_files[f"{phase}/{label}"] = digest(path)
        audit_receipts[f"{phase}-phase"] = audited_input(f"{phase}-phase", paths["phase_evidence"])
        audit_receipts[f"{phase}-descriptive"] = audited_input(f"{phase}-descriptive", paths["descriptive_evidence"])

    replication_path = ROOT / "results/inference/formal-confirmation-replication-evidence.json"
    replication = load_json(replication_path)
    rows = replication.get("contrast_results")
    if replication.get("status") != "complete-strict-replay" or not isinstance(rows, list) or len(rows) != 40:
        raise RuntimeError("cross-phase replication evidence is incomplete")
    source_files["cross-phase/replication_evidence"] = digest(replication_path)
    audit_receipts["replication"] = audited_input("replication", replication_path)

    body: dict[str, object] = {
        "schema_version": "synthetic-hypergraph-payment-source-data.v1",
        "reporting_contract": "docs/plans/2026-08-11-results-reporting-contract.md",
        "phase_data": phase_data,
        "cross_phase_replication_records": sorted(rows, key=lambda row: row["contrast_id"]),
        "source_file_sha256": source_files,
        "independent_replay_receipts": audit_receipts,
    }
    return {**body, "content_fingerprint": canonical_digest(body)}


def main() -> int:
    value = build()
    write_new_or_identical(OUTPUT, value)
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
