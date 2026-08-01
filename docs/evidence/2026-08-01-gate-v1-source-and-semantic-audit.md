# Gate V1 Source and Semantic Reproduction Evidence

**Date:** 2026-08-01
**Status:** Passed after independent numerical and adversarial contract audit
**Machine-readable summary:**
`results/gate-v1-prior-paper/summary.json`

## Outcome

The accessible 2022 input has been identified exactly, and the central
topology/path directions of the uploaded HPN paper have been recovered on its
full 10,000-request trace. Exact success-rate identity is not claimed because
the paper does not publish its HPN simulator and its narrative semantics differ
from the accessible traffic-simulator dependency.

The full common-trace result is:

| Topology | Success rate | Mean successful hops | Paper path length |
|---|---:|---:|---:|
| LN | 79.93% | 2.647 | 2.60 |
| NCH, source-order cover | 82.69% | 1.567 | 1.54 |
| FHS-5 | 82.86% | 2.450 | 2.42 |
| FHS-50 | 83.14% | 2.011 | 1.97 |

Thus all registered directional checks pass:

- the three tested hypergraph constructions do not have lower fixed-horizon
  success than LN on the shared trace;
- NCH shortens paths sharply relative to LN;
- increasing FHS arity from 5 to 50 shortens paths further;
- all four path-length values differ from the uploaded paper by at most 0.05
  hops. This descriptive tolerance was made explicit during the Gate audit,
  not preregistered before observing the reproduction.

## Source identity and exact input anchor

The 14-page uploaded paper is *Addressing Scalability Issues of Blockchains
with Hypergraph Payment Networks*. Its SHA-256 is
`bfc209a86de41064e7e963910ea6e004888e5254cfe25819468d7fd777b4be3d`.

The paper links public repository commit
`2c4ffc92d704fa1b043fac395c1e5f662990d497`. The two used blobs are:

- `LN_data_2022.zip`:
  `20998f859721383a8bbb23abd512043a53f6f98e5c658f12e369620cf3093499`;
- `Lightning_2022_10k_transactions.csv`:
  `705e619032964cb038044c3e54f2cae035759b43e75469f8b82094982d1e6cc9`.

Retaining a channel when at least one directional policy is present and not
disabled gives 65,883 active channel records; collapsing parallel channels
yields exactly 11,268 nodes and 61,966 simple edges. This recovers two linked
paper-table quantities derived from the same edge count:

- `2E/N = 10.99858`, close to the paper's displayed/truncated `10.99` (ordinary
  two-decimal rounding would be `11.00`);
- two L1 operations per binary channel at `w_c=3` give
  `2 * (2E) * 3 = 743,592`, exactly the Table IV construction cost.

The trace contains 10,000 fixed 60,000 SAT requests. There are 349 requests
whose source or target is outside the active graph. They remain explicit
failures in the denominator, matching the accessible dependency behavior.

## Locked semantic reproduction

- Channel capacity is split equally between the two endpoints. Exact doubled
  units avoid rounding odd SAT capacities; the 60,000 SAT payment is therefore
  executed as 120,000 exact half-SAT units. The recorded amount multiplier is
  then applied to those exact units.
- Transformed topologies preserve every node's resulting total capital and
  allocate it as evenly as integer units permit among incidences.
- NCH uses the source-compatible NetworkX insertion order but corrects the
  paper's literal open-neighborhood pseudocode to `{c} union N(c)`.
- FHS uses maximum residual degree, bounded BFS including the seed, and removes
  residual edges induced by the selected set.
- Routing chooses uniformly among every currently feasible minimum-hop path.
  One hyperedge traversal is one hop, irrespective of arity.
- All topology variants reuse the same requests and request-indexed route-choice
  tickets from root seed `20260801`.

## Discrepancy ledger

### 1. Anchor-matching filter versus public dependency preprocessing

The Gate filter is a declared interpretation chosen because it reproduces the
paper's 11,268-node, 61,966-edge input anchor. It is not identical to the
accessible dependency's `ln_utils.preprocess_json_file` pipeline. Requiring
both directional policies while retaining a channel if at least one is enabled
gives 61,542 simple edges and 11,135 nodes. Applying the dependency's 60,000 SAT
minimum-capacity filter as well gives 59,849 edges and 10,511 nodes.

This difference can affect reachability, path length, and success probability.
Accordingly, Gate V1 claims a transparent semantic reproduction of the paper
table under an anchor-matching filter; it does not claim an unchanged rerun of
the public traffic dependency.

### 2. LN success level

The reproduced LN success rate is 79.93%, while the paper reports 67.21%.
The path length matches closely, and the graph/cost anchors match exactly, so
this is not explained by the wrong topology input.

The accessible dependency differs from the paper narrative in two consequential
ways: it initializes directional balances with a random split, and its path
search minimizes accumulated fee rather than hop count. Its printed success
proxy is also derived from intermediate-router fee records, which warrants a
separate audit for direct-payment classification. These mechanisms can lower
success without materially changing the structural path-length anchor. Because
the actual HPN simulator is absent, the exact 67.21% is not presently
reproducible from public code.

### 3. NCH largest hyperedge

The reported average NCH arity `27` is bracketed by two declared orderings:
canonical order gives `25.60`, and source-compatible NetworkX insertion order
gives `28.76`. Mean incidence degrees are likewise close to the reported
`9.61`. Both versions, however, contain a maximum arity of 2,502 rather than the
paper's stated 350. The public input contains the corresponding high-degree hub;
the unpublished implementation may have used directed neighborhoods, another
filter, or another manuscript input revision. The discrepancy is unresolved
and remains visible.

### 4. Large-arity FHS tails

FHS-3 and FHS-5 closely recover the reported resource direction. Under the
literal Algorithm 3 rule of deleting only selected-set internal residual edges,
FHS-500 and FHS-5000 retain many small residual tail hyperedges, unlike the
near-partition behavior implied by the paper table. This indicates an
unpublished node-removal or tail-merge convention. Paper-2 primary experiments
will keep the literal, fully declared rule and will not tune it to the table.

## Gate decision

The independent reviewer reproduced all source hashes, all nine structural
rows, all four 10,000-request trajectories, and their final balance hashes. It
also cross-checked the accelerated router against independent exhaustive
residual-graph enumeration. The first audit nevertheless kept the Gate
provisional until the public-preprocessing difference was added above and the
comparison result gained structurally framed input fingerprints plus complete
re-execution validation. The remediation audit rejected the original
serialization collision and 186 additional boundary re-partition attacks, then
independently reproduced all four v2 input and final-balance hash sets. Gate V1
therefore passes within the claim boundary stated above.
