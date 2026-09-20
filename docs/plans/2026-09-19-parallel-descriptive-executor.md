# Parallel descriptive executor contract

The frozen descriptive projection at revision `a85c952afa120f86a9ace96a031819c0d131d2b4` is a single-process, strict replay. The parallel executor changes execution topology only: each worker performs the frozen block loader and projector for a disjoint block; the parent restores canonical order, rebuilds the run summary, rehashes every source block, and invokes the frozen evidence validator.

It is bounded to four workers on the 15.8 GiB local machine. This keeps the combined resident set below a conservative memory budget while using otherwise idle CPU capacity. Each completed block is atomically written as a checkpoint together with its source-file hash, reconstructed summary record, and projected rows. A separate progress record exposes the completed-block count. Restarting the same context validates and reuses only these checkpoints; an interrupted or malformed checkpoint is never treated as complete.

The initial serial Formal run was intentionally stopped before it produced a completion artifact, so exact serial/parallel equivalence cannot be claimed for this transition. The parallel executor instead preserves the frozen per-block loader/projector, rebuilds the canonical summary, rehashes every source block, and invokes the frozen full-evidence validator. Its own execution receipt records revisions, hashes, fingerprints, and worker count. A separate independent scientific replay audit is still required before interpreting or reporting scientific endpoints.

The executor verifies both its own committed source revision and the frozen projection revision. Any source drift, raw-block change, summary mismatch, or reference mismatch stops execution without overwriting existing evidence.
