"""Verify this bounded audit and preservation of the sealed source package."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from collect_metadata import ROOT

BASE = Path(__file__).resolve().parent
PAYLOAD = [".gitattributes", "collect_metadata.py", "inspect_submission.py", "verify_delivery.py", "review.md", "retrieval-v2/metadata.json", "submission-checks.json"]


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def verify():
    metadata = json.loads((BASE / "retrieval-v2/metadata.json").read_text(encoding="utf-8"))
    checks = json.loads((BASE / "submission-checks.json").read_text(encoding="utf-8"))
    refs = metadata["references"]
    assert len(refs) == 15
    identifiers = [ref["doi"] for ref in refs if ref["doi"]]
    assert len(identifiers) == 12 and len(set(doi.lower() for doi in identifiers)) == 12
    assert refs[0]["doi"] == "10.1109/ACCESS.2020.3046020"
    assert refs[-2]["doi"] is None and refs[-1]["doi"] is None
    for ref in refs:
        if "crossref_metadata" in ref:
            assert ref["crossref_metadata"]["DOI"].lower() == ref["doi"].lower()
    assert checks["all_references_cited"] and checks["reference_order_correct"]
    assert checks["title_characters"] == 17
    assert checks["abstract_characters_including_punctuation"] == 216
    assert checks["main_figure_widths_mm"] == ["170"] * 3
    assert metadata["source_sha256"] == checks["source_sha256"] == fingerprint(Path(checks["source_path"]))["sha256"]
    for name, doi in [("datacite-r6", refs[5]["doi"]), ("datacite-r13", refs[12]["doi"])]:
        assert checks["sources"][name]["metadata"]["doi"].lower() == doi.lower()
    assert checks["sources"]["crossref-r1-retry"]["ok"]
    assert checks["sources"]["starfish-published-doi"]["metadata"]["DOI"].lower() == "10.1016/j.hcc.2026.100443"
    original = ROOT / "manuscript/joconline-integrated-v1/manifest.json"
    manifest = json.loads(original.read_text(encoding="utf-8"))
    for item in manifest["files"]:
        actual = fingerprint(ROOT / item["path"])
        assert actual["bytes"] == item["bytes"] and actual["sha256"] == item["sha256"], item["path"]
    assert not re.search(r"^\s*(?:import|from)\s+(?:secondaryexploration|numpy|scipy)", (BASE / "collect_metadata.py").read_text(encoding="utf-8"), re.M)
    return {"status": "bounded-audit-record-checks-pass", "source_package_files_unchanged": len(manifest["files"]),
            "source_manifest": str(original), "source_manifest_fingerprint": fingerprint(original),
            "source_git_revision_before_audit": "97159973be2e75e6b805cad05832932e73ab6430",
            "new_simulations": 0, "new_bootstrap_replicates": 0,
            "independent_scientific_review": False, "submission_ready": False,
            "checks": ["15 references and 12 unique parsed DOIs", "registry identity checks on successful lookups", "reference first-citation order", "static abstract/title/width measurements", "old sealed package unchanged"],
            "files": [{"path": str((BASE / name).relative_to(ROOT)).replace("\\", "/"), **fingerprint(BASE / name)} for name in PAYLOAD]}


def main():
    result = verify()
    path = BASE / "verification.json"
    if path.exists():
        assert json.loads(path.read_text(encoding="utf-8")) == result, "Record changed; create a new audit version"
    else:
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in result.items() if key != "files"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
