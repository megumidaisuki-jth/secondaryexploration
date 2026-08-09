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

The accepted post-optimization diagnostic grid uses replicate 0 under the
formal manifest.  ER-GNM runs generation plus the exact replay at sizes 120
and 240.  Barabasi-Albert and fixed-count SBM run generation at both sizes.
The ER runs measure the replay multiplier at each large size, while the six
generation measurements cover every large-size parent-model stratum.  No
generation-only record is mislabelled as a complete runner block.

The grid is launched concurrently at profiler revision
`80f529e0f12e196974f5c684cdd6e1cf794ba55a` as a six-worker throughput smoke
test.  Each stdout is redirected to a unique `tmp/profiling/*.stdout.json`
file and each stderr to a corresponding zero-length `*.stderr.txt` file.  The
profiler records its own Windows peak working set.  The six profiler processes
never invoke the formal artifact writer.

An earlier optimized size-240 ER generation-only process completed between
145 and 152 minutes of observed wall time, but its stdout pipe became
unavailable after a tool-context compaction.  It is not an accepted profiling
record and supplies no claimed result fingerprint.  Its conservative
152-minute upper bound is retained solely as the independently observed solo
throughput reference for the concurrent smoke test.

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

## Frozen launch gate

Formal execution remains paused until all six current records pass the rules
above.  Six formal workers are permitted only when all of the following hold:

1. every record has the current formal-manifest fingerprint, replicate 0,
   correct model and size, a positive generation time and peak working set,
   and `wrote_formal_artifacts=false`;
2. both ER records have positive validation time, while the four explicitly
   generation-only records have `validation_ns=null`;
3. all six stderr files are empty and all result fingerprints are valid,
   lowercase SHA-256 values;
4. six times the largest recorded peak working set is no more than 50% of the
   machine's physical memory;
5. concurrent size-240 ER generation takes no more than 190 minutes, the
   prespecified rounded ceiling of 1.25 times the conservative 152-minute solo
   reference;
6. the existing 15 formal artifacts still strict-load, the lock directory is
   empty, and no partial run summary exists.

Passing this gate authorizes exactly six resumable whole-block shards.  It
does not authorize eight workers, change the frozen simulation inputs, or
convert nested traffic traces into independent units.
