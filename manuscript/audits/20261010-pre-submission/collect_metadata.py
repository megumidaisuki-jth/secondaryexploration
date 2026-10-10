"""Read-only public metadata audit; never reads experiment blocks or edits the manuscript.

Generated files are metadata snapshots, not independent scientific audit receipts.
Network reruns require a fresh --output directory (no silent overwrites).
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
SKILL = Path(r"C:\Users\jiate\.codex\skills\nature-academic-search")


def fetch(url):
    stamp = datetime.now(timezone.utc).isoformat()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "SecondaryExploration-ReferenceAudit/1.0", "Accept": "application/json, application/atom+xml, text/html"})
        with urllib.request.urlopen(request, timeout=25) as response:
            body = response.read()
            return {"url": url, "retrieved_utc": stamp, "ok": True,
                    "status": response.status, "resolved_url": response.url,
                    "response_sha256": hashlib.sha256(body).hexdigest(), "response_bytes": len(body)}, body
    except Exception as error:
        return {"url": url, "retrieved_utc": stamp, "ok": False, "error": str(error)}, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Output exists; use a new directory to preserve the retrieval record")
    args.output.mkdir(parents=True)
    source = ROOT / "manuscript/joconline-integrated-v1/main.tex"
    text = source.read_text(encoding="utf-8")
    references = []
    for match in re.finditer(r"\\bibitem\{(r\d+)\}(.*?)(?=\\bibitem|\\end\{thebibliography\})", text, re.S):
        entry = match[2].strip()
        doi_match = re.search(r"DOI:\s*(10\.\d{4,}/[^\s{}]+)", entry)
        references.append({"key": match[1], "manuscript": entry,
                           "doi": doi_match[1].rstrip(".") if doi_match else None})
    if len(references) != 15:
        raise SystemExit(f"Expected 15 references, got {len(references)}")
    def resolve(ref):
        if not ref["doi"]:
            return ref
        receipt, body = fetch("https://api.crossref.org/works/" + urllib.parse.quote(ref["doi"], safe=""))
        ref["crossref_receipt"] = receipt
        if body:
            work = json.loads(body)["message"]
            fields = ["DOI", "title", "author", "container-title", "publisher", "type", "volume", "issue", "page", "article-number", "published", "published-print", "published-online", "issued", "event", "URL", "link"]
            ref["crossref_metadata"] = {field: work[field] for field in fields if field in work}
        return ref
    with ThreadPoolExecutor(max_workers=3) as pool:
        references = list(pool.map(resolve, references))
    # Import the provided fallback engine, but do not fabricate a user contact.
    spec = importlib.util.spec_from_file_location("academic_fallback", SKILL / "scripts/academic_search.py")
    fallback = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fallback)
    fallback.MAILTO = ""
    queries = ["hypergraph payment networks", "multi-party payment channel liquidity reliability", "payment channel resource matching topology"]
    discovery = []
    for query in queries:
        try:
            discovery.append({"source": "OpenAlex discovery only", "query": query,
                              "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                              "year_from": 2024, "limit": 15, "ok": True,
                              "results": fallback.search(query, limit=15, year_from=2024)})
        except Exception as error:
            discovery.append({"source": "OpenAlex discovery only", "query": query, "ok": False, "error": str(error)})
    urls = {
        "arxiv-two-identifiers": "https://export.arxiv.org/api/query?id_list=2601.04835,2504.20536v2&max_results=2",
        "crossref-star-fish-title": "https://api.crossref.org/works?query.title=Starfish%20Rebalancing%20Multi-Party%20Off-Chain%20Payment%20Channels&rows=5",
    }
    extra = {}
    for name, url in urls.items():
        receipt, body = fetch(url)
        extra[name] = receipt
        if body:
            if name.startswith("arxiv"):
                extra[name]["atom"] = body.decode("utf-8")
            else:
                records = json.loads(body)["message"]["items"]
                extra[name]["metadata"] = [{field: row[field] for field in ["DOI", "title", "author", "container-title", "published", "volume", "issue", "page", "article-number"] if field in row} for row in records]
    result = {"source_path": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "created_utc": datetime.now(timezone.utc).isoformat(), "references": references,
              "discovery": discovery, "extra": extra,
              "limits": ["Metadata verification does not establish claim support or priority", "OpenAlex is discovery, not an independent publisher witness", "No scientific endpoint data accessed"]}
    target = args.output / "metadata.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    for ref in references:
        work = ref.get("crossref_metadata")
        if work:
            print(ref["key"], json.dumps({k: work[k] for k in ["title", "volume", "issue", "page", "article-number", "published", "published-online", "published-print"] if k in work}, ensure_ascii=False), [(a.get("given"), a.get("family")) for a in work.get("author", [])])
        else:
            print(ref["key"], ref.get("crossref_receipt", "non-DOI: primary-source required"))
    print("discovery", [(item["query"], len(item.get("results", [])), item.get("error")) for item in discovery])
    print("saved", target)


if __name__ == "__main__":
    main()
