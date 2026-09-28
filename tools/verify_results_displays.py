"""Verify derived display files, exact source pointers and editable exports.

Uses pypdf for text/size inspection, not for rendering or image manipulation.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from PIL import Image
from pypdf import PdfReader

from tools import build_results_displays as report
from tools import export_source_data as source


def main():
    out = report.OUT
    manifest = source.load_json(out / "manifest.json")
    report.require(source.digest(source.OUTPUT) == report.SOURCE_SHA == manifest["source_sha256"], "source hash differs")
    report.require(source.digest(report.ROOT / "tools/build_results_displays.py") == manifest["generator_sha256"], "generator hash differs")
    for filename, witness in manifest["files"].items():
        path = out / filename
        report.require(path.stat().st_size == witness["bytes"] and source.digest(path) == witness["sha256"], f"output hash differs: {filename}")
    data = source.load_json(source.OUTPUT)
    registry = source.load_json(out / "numerical-registry.json")
    report.require(len(registry["phase_intervals"]) == 80 and len(registry["cross_phase_replication"]) == 40, "row count differs")
    def resolve(pointer):
        value = data
        for part in pointer.split("/")[1:]:
            value = value[int(part)] if isinstance(value, list) else value[part]
        return value
    for row in registry["phase_intervals"]:
        original = resolve(row["source_pointer"])
        expected = {k: v for k, v in original.items() if k != "bootstrap_values"}
        observed = {k: v for k, v in row.items() if k not in {"source_pointer", "display", "interval_direction"}}
        report.require(observed == expected, "interval no longer matches source pointer")
        report.require(row["display"] == {k: report.decimal(original[k]) for k in ("estimate", "lower", "upper")}, "display rounding differs")
        report.require(row["interval_direction"] == report.interval_direction(original), "derived direction differs")
    for row in registry["cross_phase_replication"]:
        report.require({k:v for k,v in row.items() if k != "source_pointer"} == resolve(row["source_pointer"]), "replication source pointer differs")
    table = json.loads((out / "table-1.json").read_text(encoding="utf-8"))
    expected_ids = [cid for cid in report.IDS if cid.endswith(".global")]
    report.require([row["contrast_id"] for row in table] == expected_ids, "table selection differs")
    indexed = {(r["phase"], r["contrast_id"]): r for r in registry["phase_intervals"]}
    for row in table:
        for phase in source.PHASES:
            report.require(row[phase] == indexed[phase,row["contrast_id"]], "table/source mismatch")
    exports = []
    for basename, height in (("figure-1-design",77), ("figure-2-global-contrasts",82), ("figure-3-replication-matrix",115)):
        svg = ET.parse(out / f"{basename}.svg").getroot()
        report.require(abs(float(svg.attrib["width"].removesuffix("pt"))*25.4/72 - 183) < .01, "SVG width differs")
        text_nodes = svg.findall(".//{http://www.w3.org/2000/svg}text")
        report.require(len(text_nodes) >= 10, "SVG editable text missing")
        pdf = PdfReader(out / f"{basename}.pdf")
        report.require(len(pdf.pages) == 1, "PDF page count differs")
        page = pdf.pages[0]
        report.require(abs(float(page.mediabox.width)*25.4/72 - 183) < .01, "PDF width differs")
        report.require(abs(float(page.mediabox.height)*25.4/72 - height) < .01, "PDF height differs")
        text = page.extract_text()
        report.require(len(text) > 100, "PDF selectable text missing")
        with Image.open(out / f"{basename}.png") as im:
            report.require(abs(im.width-183/25.4*300) < 1 and abs(im.height-height/25.4*300) < 1, "PNG size differs")
        if basename == "figure-3-replication-matrix":
            for phase, prefix in (("formal","F"),("confirmation","C")):
                for direction, glyph in report.SHORT.items():
                    expected = sum(r[f"{phase}_interval_direction"] == direction for r in registry["cross_phase_replication"])
                    report.require(text.count(f"{prefix}:{glyph}") == expected, "matrix glyph counts differ from registry")
        exports.append({"figure": basename, "width_mm":183, "height_mm":height, "editable_svg_text_nodes":len(text_nodes), "selectable_pdf_characters":len(text)})
    print(json.dumps({"status":"pass", "manifest_files_checked":len(manifest["files"]),
        "interval_source_pointers":80, "replication_source_pointers":40,
        "global_table_rows":8, "exports":exports}, indent=2))


if __name__ == "__main__":
    main()
