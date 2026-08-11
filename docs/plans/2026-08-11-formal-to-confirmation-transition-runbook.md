# Formal-to-confirmation result-blind transition runbook

Status: executable checklist; confirmation remains unauthorized until every
gate below is satisfied.

This runbook fixes the operational order after the formal scheduler reaches
240/240. It does not authorize reading, displaying or interpreting a formal
endpoint, contrast, interval, gate or direction before confirmation completes.

## Frozen identities

- scientific execution revision:
  `425710a418b1b28e6c5cd813dff18aeeaa6303c3`;
- streaming analysis revision:
  `9ecaadec84f8bebe799fb507969de8e0a0947b66`;
- readiness implementation revision:
  `04356260731e2ac330d59a777490813a41322c94`;
- descriptive projection revision:
  `a85c952afa120f86a9ace96a031819c0d131d2b4`;
- frozen CPython executable:
  `C:\Users\jiate\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`.

Set the command variable explicitly before invoking any tool:

```powershell
$frozenPython = 'C:\Users\jiate\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
```

The confirmation orchestration/authorization revision is intentionally not
filled in yet. It must be the later clean commit that contains the audited
bidirectional formal runner scanner and the exact readiness witness.

## 1. Close formal execution

Do not proceed merely because 240 JSON files exist. Require all of the
following:

1. the formal scheduler exits normally and publishes
   `results/diagnostics/formal-bounded-scheduler/formal-20260811-memory-v1/completion.json`;
2. the completion record strictly replays the complete batch history and the
   exact canonical 240-file byte registry;
3. no formal or confirmation runner remains live;
4. `outputs/formal/synthetic-formal-v1/blocks/.locks` is empty and there is no
   atomic temporary, foreign, redirected or extra block entry; and
5. the global `active-session.json` lease has been released normally.

Never delete a lock, temporary file, artifact or lease to make this gate pass.
Any recovery requires its separately witnessed fail-closed path.

## 2. Freeze the cross-phase orchestration revision

Only after step 1, change `tools/formal_bounded_scheduler.py` so every formal
lease acquisition and stale-recovery entry uses the same bidirectional formal
and confirmation process scanner as `tools/confirmation_bounded_scheduler.py`.
Add the two directional stale-lease tests, run both scheduler suites and the
full repository suite, obtain an independent result-blind audit, then commit
and push. This changes orchestration only; it must not modify
`secondaryexploration/**`, either frozen manifest, any seed ledger or any of
the 240 formal artifacts.

## 3. Stream the formal summary

Run with the frozen CPython executable and the committed analysis revision:

```powershell
& $frozenPython tools/formal_inference.py finalize `
  configs/formal/synthetic-formal-v1.json `
  configs/pilot/synthetic-calibration-v1.json `
  results/pilot/synthetic-calibration-v1/evidence.json `
  results/planning/formal-precision-v1.json `
  --analysis-revision 9ecaadec84f8bebe799fb507969de8e0a0947b66 `
  --workspace-root E:\second `
  --witness results/diagnostics/formal-streaming-finalization/formal-finalization-witness.json
```

The only scientific output created by this command is the canonical
`outputs/formal/synthetic-formal-v1/run-summary.json`. The endpoint-free
finalization witness must bind all 240 raw block hashes. Use the streaming
path only; the frozen runner's legacy `--finalize-only` path remains
prohibited.

## 4. Build formal phase evidence without interpretation

```powershell
& $frozenPython tools/formal_inference.py phase `
  configs/formal/synthetic-formal-v1.json `
  outputs/formal/synthetic-formal-v1/run-summary.json `
  configs/pilot/synthetic-calibration-v1.json `
  results/pilot/synthetic-calibration-v1/evidence.json `
  results/planning/formal-precision-v1.json `
  --analysis-revision 9ecaadec84f8bebe799fb507969de8e0a0947b66 `
  --workspace-root E:\second `
  --output results/inference/formal-phase-evidence.json
```

The command must finish its complete raw replay and create-or-identical write.
Do not open, display or summarize the evidence. Keep it human-embargoed until
confirmation is complete.

Do not generate, open or publish the formal descriptive projection at this
transition. It is not a confirmation launch input. Deferring it until after
confirmation completes gives the strongest operational guarantee that its 13
exploratory metrics cannot influence whether confirmation starts.

## 5. Publish the non-result readiness witness

```powershell
& $frozenPython tools/confirmation_launch_readiness.py `
  --formal-manifest configs/formal/synthetic-formal-v1.json `
  --formal-summary outputs/formal/synthetic-formal-v1/run-summary.json `
  --formal-evidence results/inference/formal-phase-evidence.json `
  --finalization-witness results/diagnostics/formal-streaming-finalization/formal-finalization-witness.json `
  --calibration-manifest configs/pilot/synthetic-calibration-v1.json `
  --calibration-evidence results/pilot/synthetic-calibration-v1/evidence.json `
  --precision results/planning/formal-precision-v1.json `
  --analysis-revision 9ecaadec84f8bebe799fb507969de8e0a0947b66 `
  --readiness-revision 04356260731e2ac330d59a777490813a41322c94 `
  --workspace-root E:\second `
  --output results/diagnostics/confirmation-launch-readiness/formal-ready.json
```

This builder may parse formal evidence only inside its strict build path. The
confirmation scheduler must use the result-blind readiness loader, which does
not parse the phase-evidence JSON and instead rehashes the pinned readiness
record, its seven direct sources and all 240 formal block bytes.

## 6. Commit and independently authorize confirmation

The audited scanner change has already been committed and pushed under step 2.
For the later authorization commit, stage only the endpoint-free finalization
witness, the endpoint-free readiness witness and result-blind audit record.
Before confirmation completes, **do not stage or push** the formal
`run-summary.json`, phase-evidence JSON or any descriptive projection: those
files contain scientific values and remain under the human embargo. Preserve
the complete formal scheduler session locally for strict launch-gate replay,
but never stage its active/runtime directory by a directory-wide glob. Record
its completion fingerprint in a separate result-blind audit document instead.
Commit and push the allowed files, then use that full commit SHA as both:

- `--orchestration-revision`; and
- `--readiness-authorization-revision`.

Use an empty-index, exact-path whitelist. The canonical result-blind audit
record for this transition is
`docs/evidence/formal-completion-readiness-v1.md`:

```powershell
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
  throw 'index must be empty before the authorization staging step'
}
$authorizationFiles = @(
  'results/diagnostics/formal-streaming-finalization/formal-finalization-witness.json',
  'results/diagnostics/confirmation-launch-readiness/formal-ready.json',
  'docs/evidence/formal-completion-readiness-v1.md'
)
git add -- $authorizationFiles
if ($LASTEXITCODE -ne 0) { throw 'authorization staging failed' }
$staged = @(git diff --cached --name-only)
$expected = @($authorizationFiles | Sort-Object)
$observed = @($staged | Sort-Object)
if (Compare-Object $expected $observed) {
  throw 'staged authorization paths differ from the exact whitelist'
}
if ($staged | Where-Object {
    $_ -like 'results/diagnostics/formal-bounded-scheduler/*' -or
    $_ -eq 'outputs/formal/synthetic-formal-v1/run-summary.json' -or
    $_ -eq 'results/inference/formal-phase-evidence.json' -or
    $_ -like 'results/inference/*descriptive-mechanism*.json'
  }) {
  throw 'result-bearing or runtime path entered the authorization index'
}
```

Do not use `git add -A`, `git add results` or another directory-wide staging
command for this commit.

An independent result-blind audit must confirm the Git-pinned readiness raw
bytes, the complete transitive 240-block chain, the bidirectional process
scanner, empty confirmation output and frozen environment before launch.

## 7. Launch confirmation automatically

After the authorization audit passes, launch exactly once:

```powershell
$utcDate = (Get-Date).ToUniversalTime().ToString('yyyyMMdd')
$sessionId = "confirmation-$utcDate-memory-v1"
$authorizationRevision = (git rev-parse HEAD).Trim()
if ($sessionId -notmatch '^[a-z0-9][a-z0-9._-]{7,79}$') {
  throw 'confirmation session ID is invalid'
}
if ($authorizationRevision -notmatch '^[0-9a-f]{40}$') {
  throw 'authorization revision is not a full Git SHA'
}
& $frozenPython tools/confirmation_bounded_scheduler.py `
  --session-id $sessionId `
  --orchestration-revision $authorizationRevision `
  --readiness-authorization-revision $authorizationRevision `
  --python-executable $frozenPython
```

Do not add `--resume`, `--recover-interrupted` or `--recover-global-lease` to a
fresh launch. Once readiness is valid, formal results may not be used to
cancel, select or delay confirmation. The scheduler alone owns the canonical
240 singleton schedule, maximum six-process concurrency, global lease and
pre-batch memory gate.

## 8. Post-confirmation route

Do not proceed merely because 240 confirmation JSON files exist. First require
the strict confirmation completion witness, complete batch-history and exact
canonical 240-file byte-registry replay, normal scheduler exit, no live formal
or confirmation runner, empty locks/temporaries and normal global-lease
release.

Stream the confirmation summary:

```powershell
& $frozenPython tools/formal_inference.py finalize `
  configs/confirmation/synthetic-confirmation-v1.json `
  configs/pilot/synthetic-calibration-v1.json `
  results/pilot/synthetic-calibration-v1/evidence.json `
  results/planning/formal-precision-v1.json `
  --analysis-revision 9ecaadec84f8bebe799fb507969de8e0a0947b66 `
  --workspace-root E:\second `
  --witness results/diagnostics/formal-streaming-finalization/confirmation-finalization-witness.json
```

This produces the fixed summary
`outputs/confirmation/synthetic-confirmation-v1/run-summary.json`. Build the
confirmation phase evidence:

```powershell
& $frozenPython tools/formal_inference.py phase `
  configs/confirmation/synthetic-confirmation-v1.json `
  outputs/confirmation/synthetic-confirmation-v1/run-summary.json `
  configs/pilot/synthetic-calibration-v1.json `
  results/pilot/synthetic-calibration-v1/evidence.json `
  results/planning/formal-precision-v1.json `
  --analysis-revision 9ecaadec84f8bebe799fb507969de8e0a0947b66 `
  --workspace-root E:\second `
  --output results/inference/confirmation-phase-evidence.json
```

Generate both complete exploratory descriptive projections only now:

```powershell
& $frozenPython tools/formal_descriptive_projection.py `
  configs/formal/synthetic-formal-v1.json `
  outputs/formal/synthetic-formal-v1/run-summary.json `
  configs/pilot/synthetic-calibration-v1.json `
  results/pilot/synthetic-calibration-v1/evidence.json `
  results/planning/formal-precision-v1.json `
  --projection-revision a85c952afa120f86a9ace96a031819c0d131d2b4 `
  --workspace-root E:\second `
  --output results/inference/formal-descriptive-mechanism-v1.json

& $frozenPython tools/formal_descriptive_projection.py `
  configs/confirmation/synthetic-confirmation-v1.json `
  outputs/confirmation/synthetic-confirmation-v1/run-summary.json `
  configs/pilot/synthetic-calibration-v1.json `
  results/pilot/synthetic-calibration-v1/evidence.json `
  results/planning/formal-precision-v1.json `
  --projection-revision a85c952afa120f86a9ace96a031819c0d131d2b4 `
  --workspace-root E:\second `
  --output results/inference/confirmation-descriptive-mechanism-v1.json
```

Finally build the exact cross-phase record:

```powershell
& $frozenPython tools/formal_inference.py replication `
  --formal-manifest configs/formal/synthetic-formal-v1.json `
  --formal-summary outputs/formal/synthetic-formal-v1/run-summary.json `
  --formal-evidence results/inference/formal-phase-evidence.json `
  --confirmation-manifest configs/confirmation/synthetic-confirmation-v1.json `
  --confirmation-summary outputs/confirmation/synthetic-confirmation-v1/run-summary.json `
  --confirmation-evidence results/inference/confirmation-phase-evidence.json `
  --calibration-manifest configs/pilot/synthetic-calibration-v1.json `
  --calibration-evidence results/pilot/synthetic-calibration-v1/evidence.json `
  --precision results/planning/formal-precision-v1.json `
  --analysis-revision 9ecaadec84f8bebe799fb507969de8e0a0947b66 `
  --workspace-root E:\second `
  --output results/inference/formal-confirmation-replication-evidence.json
```

Independently strict-replay both summaries, both phase-evidence artifacts,
both descriptive projections and the replication evidence before any
interpretation or manuscript population. Results reporting must consume these
fixed paths through the registered reporting contract; manually copied values
and selective rows remain prohibited.
