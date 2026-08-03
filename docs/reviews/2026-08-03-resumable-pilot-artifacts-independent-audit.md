# Resumable Pilot Artifact Runner Independent Audit

**Date:** 2026-08-03

**Verdict:** PASS after four rounds of adversarial correction

## Blocking findings resolved

1. The first summary builder accepted caller-supplied expected counts, invented
   block keys, malformed digests, and mixed manifests/ledgers. Legal blocks and
   counts are now derived only from a fully regenerated ledger and the three
   registered parent models; complete summaries require that exact set.
2. The first atomic writer allowed `NaN` and `Infinity`. Serialization and
   fingerprinting now use strict finite canonical JSON and fail before changing
   the target.
3. Early block artifacts validated only shallow structure and an outer hash.
   They now carry the complete result witness, recompute the inner result hash,
   regenerate parent and training inputs, and cross-derive every scientific
   summary and resource field.
4. Held-out family labels initially self-certified from the summary, and the
   runner delayed revision checking until after expensive execution. Family is
   now derived from the trained witness registry; revision syntax and frozen
   formal/confirmation equality are checked at the runner entrance.

## Independent evidence

- Recomputed-fingerprint attacks against result identity, draw metadata,
  training and held-out seeds, family labels, resources, capacity budgets,
  horizons, and plausible as well as impossible service summaries were all
  rejected.
- Accepted counts/values, success rates, three event observations, initial and
  final states, arity histograms, traversed edges, participant slots, quadratic
  exposure, and unique signaled participants were independently re-derived
  from simulation witnesses.
- Coordinated replacement of the inner and outer training-demand hashes failed
  because request traces and amount-weighted demand were regenerated from the
  ledger and manifest.
- Nested unknown/duplicate keys, nonfinite numbers, invalid UTF-8, cross
  revision/environment/manifest/model checkpoints, duplicate blocks, and
  `--no-resume` violations failed closed.
- Atomic replacement failures preserved the old target and left no temporary
  files. One of three valid model blocks produced `in_progress`; all three
  produced sorted `complete` output with exact timing arithmetic.
- An invalid CLI revision exited before creating the output directory. A
  formal revision mismatch likewise failed before execution.
- Real CPython 3.10.16 and 3.12.13 each passed the focused artifact test and the
  full 267-test suite. Both passed `compileall`; `git diff --check` passed.

## Non-blocking residual risks

SHA-256 supplies integrity rather than keyed provenance. The declared Git
revision is not yet compared automatically with repository HEAD. The atomic
writer synchronizes file contents but not the parent directory entry. The run
summary is rebuilt and fingerprinted internally but does not yet expose a
standalone public strict loader; the runner's resume trust boundary is the
individually validated block artifact set.
