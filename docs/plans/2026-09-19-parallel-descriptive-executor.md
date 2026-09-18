# Parallel descriptive executor contract

The frozen descriptive projection at revision `a85c952afa120f86a9ace96a031819c0d131d2b4` is a single-process, strict replay. The parallel executor changes execution topology only: each worker performs the frozen block loader and projector for a disjoint block; the parent restores canonical order, rebuilds the run summary, rehashes every source block, and invokes the frozen evidence validator.

It is bounded to four workers on the 15.8 GiB local machine. This keeps the combined resident set below a conservative memory budget while using otherwise idle CPU capacity.

Before applying the executor to Confirmation, it must exactly match the completed sequential Formal descriptive projection. The equivalence receipt records only revisions, hashes, fingerprints and worker count. It does not replace the independent scientific replay audit required before interpreting or reporting scientific endpoints.

The executor verifies both its own committed source revision and the frozen projection revision. Any source drift, raw-block change, summary mismatch, or reference mismatch stops execution without overwriting existing evidence.
