"""Create a portable inventory after numerical and visual checks."""
import csv
import hashlib
import json
from pathlib import Path
import platform
import matplotlib
from tools import supplement_da_fhs5 as s

OUT = s.DEFAULT_OUT
results = json.loads((OUT/'results.json').read_bytes())
verification = json.loads((OUT/'verification.json').read_bytes())
assert verification['status'] == 'passed'
assert verification['results_sha256'] == s.sha((OUT/'results.json').read_bytes())
assert verification['verifier_sha256'] == s.sha((s.ROOT/'tools/verify_supplement_da_fhs5.py').read_bytes())
assert len(list((OUT/'checkpoints').glob('*.json'))) == 320
assert not list(OUT.rglob('*.tmp')) and not list(OUT.rglob('*.lock'))
with (OUT/'figure-s1-source.csv').open(encoding='utf-8-sig', newline='') as f:
    csv_rows = list(csv.DictReader(f))
assert len(csv_rows) == 16
for row, result in zip(csv_rows, results['comparisons']):
    assert row['phase'] == result['phase'] and int(row['nodes']) == result['node_count'] and row['metric'] == result['metric']
    for name in ('estimate', 'adjusted_lower', 'adjusted_upper'):
        assert float(row[name]) == result['display'][name]
assert '<text' in (OUT/'figure-s1-da-fhs5.svg').read_text(encoding='utf-8')
inputs = [s.DEFAULT_CONFIG, s.ROOT/'tools/supplement_da_fhs5.py', s.ROOT/'tools/verify_supplement_da_fhs5.py',
          s.ROOT/'tools/summarize_supplement_scopes.py', s.ROOT/'tools/plot_supplement_da_fhs5.py',
          Path(__file__), s.ROOT/'tests/test_supplement_da_fhs5.py']
files = inputs + sorted(p for p in OUT.rglob('*') if p.is_file() and p.name != 'delivery-manifest.json')
manifest = {'date': '2026-10-07', 'completed': ['S1 exact paired ablation', 'S2 descriptive scopes and all regimes'],
            'not_executed': ['S3 cost-service absolute summaries', 'S4 shorter-window sensitivity', 'S5 new initialization simulations'],
            'python': platform.python_version(), 'matplotlib': matplotlib.__version__,
            'unit_tests_passed': 9, 'figure_preflight': {'pass': 13, 'warn': 1, 'fail': 0, 'warning': '170 mm existing-manuscript width; not generic Nature 89/183 mm'},
            'numerical_crosscheck': 'all 160000 paired bootstrap replicates; not new blinded scientific replay',
            'figure_source_rows_checked': 16, 'figure_visual_review': 'PNG all panels reviewed; all zero differences retained',
            'files': [{'path': p.relative_to(s.ROOT).as_posix(), 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
s.save(OUT/'delivery-manifest.json', manifest)
print(f'Sealed {len(files)} files; all exact results, source data and checkpoints retained.')
