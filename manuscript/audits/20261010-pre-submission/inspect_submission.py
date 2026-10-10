"""Static submission checks and bounded supplemental metadata retrieval.

No simulations, no analysis endpoints, no changes to sealed manuscript versions.
"""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from collect_metadata import ROOT, fetch

BASE = Path(__file__).resolve().parent


def main():
    destination = BASE / "submission-checks.json"
    if destination.exists():
        raise SystemExit("Checks already exist; preserve the audit record")
    source = ROOT / "manuscript/joconline-integrated-v1/main.tex"
    text = source.read_text(encoding="utf-8")
    before_refs = text.split(r"\begin{thebibliography}")[0]
    keys = re.findall(r"\\bibitem\{([^}]+)\}", text)
    citations = []
    for group in re.findall(r"\\upcite\{([^}]+)\}", before_refs):
        for key in group.split(","):
            if key not in citations:
                citations.append(key)
    abstract = re.search(r"摘要：(.*?)\\par", text, re.S)[1]
    abstract = abstract.replace("$-$", "-")
    title = re.search(r"\\zihao\{2\}\\bfseries\s+([^\\]+)", text)[1].strip()
    en_abstract = re.search(r"Abstract: (.*?)\\par", text, re.S)[1]
    en_abstract = en_abstract.replace("$-$", "-")
    urls = {
        "crossref-r1-retry": "https://api.crossref.org/works/10.1109/ACCESS.2020.3046020",
        "datacite-r6": "https://api.datacite.org/dois/10.4230/LIPIcs.ISAAC.2018.16",
        "datacite-r13": "https://api.datacite.org/dois/10.4230/LIPIcs.DISC.2025.23",
        "starfish-published-doi": "https://api.crossref.org/works/10.1016/j.hcc.2026.100443",
        "journal-format": "https://www.joconline.com.cn/zh/info/15279/",
        "journal-ethics": "https://www.joconline.com.cn/zh/info/15282/",
        "arxiv-new-neighbors": "https://export.arxiv.org/api/query?id_list=2512.11775v2,2609.03600v1&max_results=2",
        "arxiv-query-hypergraph": "https://export.arxiv.org/api/query?search_query=all:hypergraph%20AND%20all:payment&start=0&max_results=20&sortBy=submittedDate&sortOrder=descending",
        "starfish-publisher-redirect": "https://doi.org/10.1016/j.hcc.2026.100443",
    }
    sources = {}
    for key, url in urls.items():
        receipt, body = fetch(url)
        sources[key] = receipt
        if body and key.startswith(("crossref", "starfish-published")):
            work = json.loads(body)["message"]
            sources[key]["metadata"] = {field: work[field] for field in ["DOI", "title", "subtitle", "author", "container-title", "volume", "issue", "page", "article-number", "published", "published-print", "published-online", "URL", "link"] if field in work}
        elif body and key.startswith("datacite"):
            work = json.loads(body)["data"]["attributes"]
            sources[key]["metadata"] = {field: work[field] for field in ["doi", "titles", "creators", "publicationYear", "publisher", "container", "url", "types"] if field in work}
        elif body and key.startswith("arxiv"):
            namespace = {"atom": "http://www.w3.org/2005/Atom"}
            entries = []
            for entry in ET.fromstring(body).findall("atom:entry", namespace):
                entries.append({"id": entry.findtext("atom:id", namespaces=namespace),
                                "title": entry.findtext("atom:title", namespaces=namespace),
                                "published": entry.findtext("atom:published", namespaces=namespace),
                                "updated": entry.findtext("atom:updated", namespaces=namespace),
                                "authors": [a.findtext("atom:name", namespaces=namespace) for a in entry.findall("atom:author", namespace)]})
            sources[key]["entries"] = entries
    result = {"source_path": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "title": title, "title_characters": len(title),
              "abstract_characters_including_punctuation": len(abstract),
              "abstract_han_characters": len(re.findall(r"[\u4e00-\u9fff]", abstract)),
              "english_abstract_words": len(en_abstract.split()),
              "english_abstract_characters": len(en_abstract),
              "references": keys, "first_citation_order": citations,
              "all_references_cited": set(keys) == set(citations),
              "reference_order_correct": keys == citations,
              "main_figure_widths_mm": re.findall(r"\\includegraphics\[width=(\d+)mm\]", text),
              "explicit_placeholders": re.findall(r"【[^】]+】", text),
              "sources": sources}
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in result.items() if key != "sources"}, ensure_ascii=False, indent=2))
    for key, value in sources.items():
        work = value.get("metadata", {})
        print(key, value["ok"], value.get("error"), value.get("resolved_url"), {k: work[k] for k in ["title", "volume", "issue", "page", "article-number", "published"] if k in work})


if __name__ == "__main__":
    main()
