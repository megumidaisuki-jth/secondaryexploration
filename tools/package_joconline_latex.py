"""Validate and package the typeset author manuscript; no simulation/inference.

Compile and visually inspect the PDF before running. This is not a replacement
for those steps and does not establish source/PDF equivalence after future edits.
"""
from pathlib import Path
import hashlib
import json
import re
import zipfile

from pypdf import PdfReader
from tools.build_joconline_latex import tables

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'manuscript/joconline-latex'
SRC = ROOT / 'manuscript/joconline-expanded'


def record(path):
    data = path.read_bytes()
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    source_manifest = json.loads((SRC/'manifest.json').read_text(encoding='utf-8'))
    for rel, expected in source_manifest['files'].items():
        require(record(SRC/rel) == expected, f'Expanded manuscript changed: {rel}')
    inputs = {}
    for rel, key in (
        ('manuscript/generated/synthetic-v1/numerical-registry.json', 'source_registry_sha256'),
        ('manuscript/generated/synthetic-v1/table-1.json', 'source_table_sha256'),
        ('manuscript/generated/results-writing-v1/evidence-summary.json', 'source_descriptive_sha256'),
    ):
        inputs[rel] = record(ROOT/rel)
        require(inputs[rel]['sha256'] == source_manifest[key], f'Input changed: {rel}')
    tex = (OUT/'main.tex').read_text(encoding='utf-8')
    for table in tables().values():
        require(table in tex, 'Generated table not identical to bound input rendering')
    counts = {
        'equations': len(re.findall(r'\\begin\{equation\}', tex)),
        'algorithms': len(re.findall(r'\\algtitle\{算法', tex)),
        'figures': len(re.findall(r'\\begin\{figure\*?\}', tex)),
        'tables': len(re.findall(r'\\begin\{table\*?\}', tex)),
        'references': len(re.findall(r'\\bibitem\{', tex)),
        'pages': len(PdfReader(OUT/'main.pdf').pages),
    }
    require(counts == dict(equations=16, algorithms=2, figures=3, tables=3,
                          references=15, pages=10), f'Unexpected counts: {counts}')
    require(set(re.findall(r'\\label\{eq:(\d+)\}', tex)) ==
            {str(i) for i in range(1, 17)}, 'Equation label mismatch')
    log = (OUT/'main.log').read_text(encoding='utf-8', errors='replace')
    require(not re.search(r'Overfull|Underfull|undefined|Missing character|LaTeX Font Warning', log),
            'Inspect compilation log before delivery')
    compression = json.loads((OUT/'compression-map.json').read_text(encoding='utf-8'))
    require(len(compression['omitted_repeated_paragraphs']) == 18 and
            compression['omitted_han_characters'] == 2486, 'Compression map changed')
    figure_paths = sorted((OUT/'figures').glob('*.pdf'))
    require(len(figure_paths) == 3, 'Unexpected figure inventory')
    for fig in figure_paths:
        require(record(fig) == record(SRC/'figures'/fig.name), f'Figure changed: {fig.name}')
    members = [OUT/name for name in ('main.tex', 'README.md', 'qa.md',
               'supplement-recommendations.md', 'compression-map.json')] + figure_paths
    archive = OUT/'source-package.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in members:
            bundle.write(path, path.relative_to(OUT).as_posix())
    with zipfile.ZipFile(archive) as bundle:
        require(bundle.testzip() is None, 'ZIP CRC failure')
        for path in members:
            require(bundle.read(path.relative_to(OUT).as_posix()) == path.read_bytes(),
                    f'ZIP member mismatch: {path.name}')
    manifest = {
        'schema': 'joconline-latex-author-manuscript.v1',
        'checked_date': '2026-10-03',
        'official_publisher_template': False,
        'scientific_computation_performed': False,
        'compiler': 'existing Tectonic 0.17.0',
        'native_compiler': 'environment initialization failed; not used for delivered PDF',
        'counts': counts,
        'input_files': inputs,
        'source_manuscript': record(SRC/'manuscript-zh.md'),
        'source_manifest': record(SRC/'manifest.json'),
        'builder': record(ROOT/'tools/build_joconline_latex.py'),
        'packager': record(Path(__file__)),
        'compile_log': record(OUT/'main.log'),
        'files': {p.relative_to(OUT).as_posix(): record(p)
                  for p in members + [OUT/'main.pdf', archive]},
    }
    (OUT/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n',
                                     encoding='utf-8')
    print(json.dumps({'validation': 'passed', 'counts': counts,
                      'zip': record(archive)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
