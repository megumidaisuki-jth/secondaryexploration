"""Seal author artifacts without changing any scientific input or Git state."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'manuscript/joconline-submission-v1'

def record(path):
    return dict(path=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())

if __name__=='__main__':
    destination=OUT/'source-package.zip'
    manifest_path=OUT/'manifest.json'
    assert not destination.exists() and not manifest_path.exists(), 'Existing seal must be preserved.'
    files=sorted(p for p in OUT.rglob('*') if p.is_file() and p.suffix not in ('.aux','.out','.log','.gz'))
    manifest=dict(schema='joconline-editorial-submission-v1',date='2026-10-10',
        status='editorial-export-QA-complete-not-submission-ready',
        baseline_manifest_sha256=hashlib.sha256((ROOT/'manuscript/joconline-integrated-v1/manifest.json').read_bytes()).hexdigest(),
        pdf_pages=dict(main=11,supplement=10),word_preview_pages=dict(main=17,supplement=9),
        new_simulations=0,new_bootstrap_replicates=0,independent_blinded_review=False,
        reporting_tests_passed=9,original_numbered_equations_preserved=18,
        original_unnumbered_displays_preserved=2,original_accuracy_corrections_preserved=14,
        pending=['monochrome-figure-and-font-adaptation','author-metadata','English-abstract-limit-clarification','official-template-check'],
        files=[record(p) for p in files],
        tooling=[record(ROOT/p) for p in ['tools/build_joconline_submission_revision.py','tools/seal_joconline_submission_revision.py','tests/test_joconline_submission_revision.py']])
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    with zipfile.ZipFile(destination,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in files+[manifest_path]: archive.write(path,path.relative_to(OUT).as_posix())
        for item in manifest['tooling']:
            path=ROOT/item['path'];archive.write(path,'reproduction/'+path.name)
    print(json.dumps(dict(files=len(files),zip=record(destination)),ensure_ascii=False))
