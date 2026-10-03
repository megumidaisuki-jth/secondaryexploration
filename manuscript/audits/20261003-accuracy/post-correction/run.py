"""Recheck the corrected manuscript, preserving the pre-correction receipt.

Run from any directory with the existing artifact Python and repository imports.
No simulation, bootstrap resampling or raw-block replay.
"""
from pathlib import Path
import importlib.util
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))


def main():
    subprocess.run([
        sys.executable, '-m', 'unittest',
        'tests.unit.model.test_entities',
        'tests.unit.model.test_transition',
        'tests.unit.routing.test_search',
        'tests.unit.metrics.test_stratified_inference',
        'tests.unit.optimization.test_demand', '-q',
    ], cwd=ROOT, check=True)
    spec = importlib.util.spec_from_file_location('accuracy_check', HERE.parent/'check.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = HERE
    module.CHECK_DATE = '2026-10-04'
    module.main()


if __name__ == '__main__':
    main()
