# Formal runtime profiling protocol

## Purpose and non-interference guarantee

The formal and confirmation manifests are frozen at the execution revision
`425710a418b1b28e6c5cd813dff18aeeaa6303c3`.  No formal phase may be launched
until the size-120 and size-240 paths have a measured resource envelope.

`tools/profile_synthetic_block.py` profiles an exact registered
parent-model block in memory.  It uses the frozen manifest, registered parent
seed, topology-search budget, capacity-search budget, traffic traces and
complete result replay, but never calls an artifact writer.  It therefore
cannot create or alter a formal output directory.

The first diagnostic is an ER-GNM parent at size 120, replicate 0, under the
formal manifest.  The full profile includes both generation and the exact
replay that the runner uses before it commits an artifact.  The other two
parent-model strata at each large size will be measured before a parallel
envelope is declared.

## Commands

Use the environment pinned by the formal manifest, not the system Python:

```powershell
$py = 'C:\Users\jiate\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -m cProfile -o tmp/profiling/n120-er-r0-full.pstats `
  tools/profile_synthetic_block.py configs/formal/synthetic-formal-v1.json `
  --node-count 120 --parent-replicate 0 --model er_gnm
```

The script emits one JSON record containing the generation and validation wall
times, the exact result fingerprint and an explicit confirmation that no formal
artifact was written.  Store stdout, stderr, `pstats` top cumulative-time rows,
CPU time, and peak working set in the profiling record.

## Decision rules

1. The profiling record is valid only if stdout contains one successful JSON
   record, stderr is empty, and the profile result has no formal output path.
2. A worker count is allowed only when the recorded peak working set multiplied
   by the worker count leaves a conservative memory reserve, and a concurrent
   smoke test shows no harmful throughput collapse.  The benchmark runs are
   always independent blocks; neither a parent graph nor nested traffic trace
   is split between workers.
3. If routing, simulation construction, or complete replay dominates runtime,
   an optimization may be considered only if it preserves the exact output
   fingerprint for each representative frozen block.  It must then pass all
   regression tests and force a new execution revision plus regenerated formal
   and confirmation manifests.  The current frozen manifests must never be
   silently reused with altered execution code.
4. Reducing the horizon, topology-search budget, capacity-search budget,
   model strata, or exact replay is not a runtime optimization for the formal
   study.  Such a change is a design change and requires a new scientific
   decision and precision freeze.
