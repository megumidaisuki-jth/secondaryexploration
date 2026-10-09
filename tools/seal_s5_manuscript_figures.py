"""Seal visually reviewed S5 artifacts, package source and verify Git bytes."""
from pathlib import Path
import argparse
import json
import re
import subprocess
import sys
import zipfile
import unittest
from pypdf import PdfReader
from tools import build_s5_manuscript_figures as builder

ROOT=builder.ROOT; OUT=builder.OUT; PAPER=builder.PAPER
DIAG=ROOT/'results/diagnostics/S5-manuscript-figures-v1'
SCRIPT=Path(__file__)

def record(p): return {'bytes':p.stat().st_size,'sha256':builder.sha(p)}

def paths():
    output=[p for p in OUT.iterdir() if p.is_file()]
    output += [p for p in PAPER.rglob('*') if p.is_file() and p.suffix not in ['.aux','.out','.log']]
    output += [ROOT/'.gitattributes',ROOT/'tools/build_s5_manuscript_figures.py',SCRIPT,ROOT/'tests/test_s5_manuscript_figures.py']
    return sorted(set(output))

def seal():
    builder.load_verified()
    data=json.loads((OUT/'source-data.json').read_bytes())
    assert builder.sha(OUT/'source-data.json')==builder.SOURCE_SHA
    ledger=json.loads((OUT/'display-ledger.json').read_bytes()); builder.verify_ledger(data,ledger)
    assert builder.sha(ROOT/'manuscript/joconline-latex/main.tex')==builder.TEX_SHA
    tests=unittest.defaultTestLoader.loadTestsFromName('tests.test_s5_manuscript_figures')
    result=unittest.TextTestRunner(verbosity=2).run(tests)
    assert result.wasSuccessful()
    counts={name:len(PdfReader(PAPER/f'{name}.pdf').pages) for name in ['main','supplement']}
    assert counts=={'main':11,'supplement':3}
    for name in counts:
        log=(PAPER/f'{name}.log').read_text(encoding='utf-8',errors='replace')
        assert not re.search(r'Overfull|Underfull|undefined|Missing character|LaTeX Font Warning',log)
    text=''.join(p.extract_text() for p in PdfReader(PAPER/'supplement.pdf').pages)
    assert all('图 '+name in text for name in ['S1','S2','S3'])
    tex=(PAPER/'main.tex').read_text(encoding='utf-8')
    assert len(re.findall(r'\\begin\{equation\}',tex))==17
    assert len(re.findall(r'\\begin\{figure\*?\}',tex))==4
    assert len(re.findall(r'\\bibitem\{',tex))==15
    # Explicit files only. Old manifests and compiled PDFs are not copied into source package.
    members=[p for p in PAPER.rglob('*') if p.is_file() and p.suffix in ['.tex','.md','.json']]
    members += list((PAPER/'figures').glob('*.pdf'))
    members=[p for p in members if p.name not in ['manifest.json']]
    archive=PAPER/'source-package.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
        for p in sorted(members): bundle.write(p,p.relative_to(PAPER).as_posix())
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        for p in members: assert bundle.read(p.relative_to(PAPER).as_posix())==p.read_bytes()
    files={p.relative_to(ROOT).as_posix():record(p) for p in paths() if p!=OUT/'manifest.json'}
    builder.save_json(OUT/'manifest.json',{'schema':'S5-figures-and-manuscript-v1','status':'display-and-author-artifacts-verified',
        'source_results_sha256':builder.SOURCE_SHA,'arithmetic_proof_sha256':builder.PROOF_SHA,
        'original_tex_sha256':builder.TEX_SHA,'pages':counts,'marks_verified':144,'tests_passed':result.testsRun,
        'new_simulations':0,'new_bootstrap_replicates':0,'independent_blinded_scientific_review':False,
        'visual_review':'3 figure PNGs, 11 main pages, 3 supplementary pages inspected by main analyst',
        'files':files})
    print(json.dumps({'status':'sealed','files':len(files)+1,'pages':counts,'marks':144}))

def check_git(rev):
    manifest=json.loads((OUT/'manifest.json').read_bytes())
    assert manifest['status']=='display-and-author-artifacts-verified'
    members=dict(manifest['files'])
    members[(OUT/'manifest.json').relative_to(ROOT).as_posix()]=record(OUT/'manifest.json')
    for rel,expected in members.items():
        assert record(ROOT/rel)==expected, f'Local file changed: {rel}'
        blob=subprocess.run(['git','show',f'{rev}:{rel}'],cwd=ROOT,capture_output=True,check=True).stdout
        import hashlib
        assert {'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()}==expected, f'Git bytes differ: {rel}'
    return len(members)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--check-git'); parser.add_argument('--record-upload',action='store_true')
    args=parser.parse_args()
    if args.check_git:
        count=check_git(args.check_git); print(f'Git bytes verified: {count} files at {args.check_git}')
    elif args.record_upload:
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/codex/research-contract'],cwd=ROOT,text=True).split()[0]
        assert remote==commit
        count=check_git('HEAD'); DIAG.mkdir(exist_ok=True)
        builder.save_json(DIAG/'s5-figures-upload.json',{'status':'uploaded-byte-verified','commit':commit,'remote_commit':remote,
            'files_checked':count,'manifest_sha256':builder.sha(OUT/'manifest.json')})
        print(json.dumps({'upload':'verified','commit':commit,'files':count}))
    else: seal()

if __name__=='__main__': main()
