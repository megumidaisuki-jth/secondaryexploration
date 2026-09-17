"""Run the frozen post-confirmation commands with endpoint-free execution receipts.

This supervisor does not replace the independent scientific replay audit.
It never parses phase evidence or raw block contents; those are read only by
the frozen analysis tools. Run with --check to verify inputs without launching.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import formal_inference as analysis
from tools import formal_descriptive_projection as projection
from secondaryexploration.experiments import load_study_design_manifest, build_study_seed_ledger
from secondaryexploration.experiments.artifacts import load_study_run_summary, atomic_write_json
from secondaryexploration.experiments.runner import runtime_environment, runtime_environment_fingerprint

ANALYSIS = '9ecaadec84f8bebe799fb507969de8e0a0947b66'
PROJECTION = 'a85c952afa120f86a9ace96a031819c0d131d2b4'
EXECUTION = '425710a418b1b28e6c5cd813dff18aeeaa6303c3'
DIAG = ROOT / 'results/diagnostics/post-confirmation/20260917-v1'
COMMON = ['configs/pilot/synthetic-calibration-v1.json',
          'results/pilot/synthetic-calibration-v1/evidence.json',
          'results/planning/formal-precision-v1.json']


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def manifest(phase):
    return f'configs/{phase}/synthetic-{phase}-v1.json'


def summary(phase):
    return f'outputs/{phase}/synthetic-{phase}-v1/run-summary.json'


def plan():
    phases = []
    output = 'results/inference/confirmation-phase-evidence.json'
    phases.append(('confirmation-phase', ['tools/formal_inference.py', 'phase',
        manifest('confirmation'), summary('confirmation'), *COMMON,
        '--analysis-revision', ANALYSIS, '--workspace-root', str(ROOT), '--output', output], output))
    for phase in ('formal', 'confirmation'):
        output = f'results/inference/{phase}-descriptive-mechanism-v1.json'
        phases.append((f'{phase}-descriptive', ['tools/formal_descriptive_projection.py',
            manifest(phase), summary(phase), *COMMON, '--projection-revision', PROJECTION,
            '--workspace-root', str(ROOT), '--output', output], output))
    output = 'results/inference/formal-confirmation-replication-evidence.json'
    phases.append(('replication', ['tools/formal_inference.py', 'replication',
        '--formal-manifest', manifest('formal'), '--formal-summary', summary('formal'),
        '--formal-evidence', 'results/inference/formal-phase-evidence.json',
        '--confirmation-manifest', manifest('confirmation'), '--confirmation-summary', summary('confirmation'),
        '--confirmation-evidence', 'results/inference/confirmation-phase-evidence.json',
        '--calibration-manifest', COMMON[0], '--calibration-evidence', COMMON[1],
        '--precision', COMMON[2], '--analysis-revision', ANALYSIS,
        '--workspace-root', str(ROOT), '--output', output], output))
    return phases


def preflight():
    analysis._verify_analysis_snapshot(ROOT, ANALYSIS, EXECUTION)
    projection._verify_projection_snapshot(ROOT, PROJECTION)
    env = runtime_environment_fingerprint(runtime_environment())
    if env != '0a499b6a1334446fa6bf02a02b25e80934a22689168d6282a2ccb067ac6216c3':
        raise RuntimeError('Frozen environment mismatch')
    if (ROOT / 'results/diagnostics/formal-bounded-scheduler/active-session.json').exists():
        raise RuntimeError('Active simulation lease; refusing analysis')
    bindings = {p: digest(ROOT / p) for p in [*COMMON, 'results/inference/formal-phase-evidence.json']}
    reports = {}
    for phase in ('formal', 'confirmation'):
        design = load_study_design_manifest(ROOT / manifest(phase))
        ledger = build_study_seed_ledger(design)
        loaded_summary = load_study_run_summary(ROOT / summary(phase), manifest=design, ledger=ledger)
        witpath = ROOT / f'results/diagnostics/formal-streaming-finalization/{phase}-finalization-witness.json'
        witness = analysis._load_strict_json(witpath, 'finalization witness')
        content = dict(witness)
        supplied = content.pop('witness_fingerprint')
        if analysis._mapping_fingerprint(content) != supplied:
            raise RuntimeError('Witness fingerprint mismatch')
        required = {'phase': phase, 'block_count': 240, 'analysis_revision': ANALYSIS,
                    'execution_revision': EXECUTION, 'manifest_fingerprint': design.fingerprint,
                    'summary_fingerprint': loaded_summary['summary_fingerprint'],
                    'status': 'complete-memory-bounded-strict-replay'}
        if any(witness.get(k) != v for k, v in required.items()):
            raise RuntimeError('Witness/summary binding mismatch')
        output_root = ROOT / design.output_root
        for path in (output_root / 'blocks/.locks', output_root / 'temp'):
            if path.exists() and any(path.iterdir()):
                raise RuntimeError('Nonempty locks or temporary directory')
        registry = witness['block_byte_registry']
        expected = {row['block_key'] + '.json' for row in registry}
        actual = {p.name for p in (output_root / 'blocks').iterdir() if p.name != '.locks'}
        if len(registry) != 240 or len(expected) != 240 or actual != expected:
            raise RuntimeError('Block registry not exact')
        for row in registry:
            file = output_root / 'blocks' / (row['block_key'] + '.json')
            if not file.is_file() or file.is_symlink() or digest(file) != row['file_sha256']:
                raise RuntimeError('Raw block hash mismatch')
        reports[phase] = {'blocks': 240, 'witness_sha256': digest(witpath),
                         'summary_sha256': digest(ROOT / summary(phase)),
                         'manifest_sha256': digest(ROOT / manifest(phase))}
    return {'environment_fingerprint': env, 'phases': reports, 'inputs': bindings,
            'supervisor_sha256': digest(__file__)}


def run():
    # Windows releases the byte-range lock even if the supervisor is interrupted.
    import msvcrt
    DIAG.mkdir(parents=True, exist_ok=True)
    with (DIAG / 'supervisor.lock').open('a+b') as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            atomic_write_json(DIAG / 'status.json', {'status': 'preflight', 'pid': os.getpid(), 'at': utc()})
            context = preflight()
            context_hash = analysis._mapping_fingerprint(context)
            atomic_write_json(DIAG / 'preflight.json', {'at': utc(), 'status': 'byte-bindings-verified', **context})
            for name, arguments, output in plan():
                receipt = DIAG / (name + '.success.json')
                if receipt.exists():
                    prior = analysis._load_strict_json(receipt, 'execution receipt')
                    if (prior.get('context_sha256') != context_hash or prior.get('command') != [sys.executable, *arguments]
                            or not (ROOT / output).is_file() or digest(ROOT / output) != prior.get('output_sha256')):
                        raise RuntimeError('Completed stage identity drift; refusing to resume')
                    continue
                attempt = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                started = utc()
                base = DIAG / (name + '.' + attempt)
                with Path(str(base) + '.stdout.log').open('xb') as out, Path(str(base) + '.stderr.log').open('xb') as err:
                    child = subprocess.Popen([sys.executable, *arguments], cwd=ROOT, stdout=out, stderr=err)
                    atomic_write_json(DIAG / 'status.json', {'status': 'running', 'stage': name,
                        'pid': os.getpid(), 'child_pid': child.pid, 'started_at': started, 'command': [sys.executable, *arguments]})
                    code = child.wait()
                record = {'stage': name, 'command': [sys.executable, *arguments], 'started_at': started,
                    'completed_at': utc(), 'exit_code': code, 'context_sha256': context_hash,
                    'stdout_sha256': digest(str(base) + '.stdout.log'),
                    'stderr_sha256': digest(str(base) + '.stderr.log'), 'output': output}
                if code != 0 or not (ROOT / output).is_file():
                    atomic_write_json(Path(str(base) + '.failure.json'), record)
                    raise RuntimeError(f'{name} failed; see recorded logs (exit {code})')
                record['output_sha256'] = digest(ROOT / output)
                record['output_bytes'] = (ROOT / output).stat().st_size
                atomic_write_json(receipt, record)
            atomic_write_json(DIAG / 'status.json', {'status': 'generated-pending-independent-replay', 'at': utc()})
        except Exception as error:
            atomic_write_json(DIAG / 'status.json', {'status': 'stopped-on-error', 'at': utc(), 'error': str(error)})
            raise
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        print(json.dumps(preflight(), ensure_ascii=False, sort_keys=True))
    else:
        run()
