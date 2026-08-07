# Lightning structural-panel source audit

**Date:** 2026-08-07
**Scope:** immutable source identity and admissible claims for the 2020, 2022,
2023, and 2026 Lightning cross-sections

## Locked interpretation

The four years are separate structural cross-sections. They are not a
node-level longitudinal panel: public keys can appear, disappear, or be
observed differently by different gossip collectors. Results may support
claims about robustness under observed public structures, but may not be
reported as real Lightning payment-failure rates, causal year effects, or
remaining network lifetime.

## Accepted 2026 source

The accepted current cross-section is the Lightning Dev Kit public Rapid
Gossip Sync v2 response captured from
`https://rapidsync.lightningdevkit.org/snapshot/v2/0`.

Its immutable contract is
[`configs/lightning/rgs-2026-08-07.json`](../../configs/lightning/rgs-2026-08-07.json):

- latest-seen time: `2026-08-07T00:00:00Z` (`1786060800`);
- retrieval time: `2026-08-07T01:56:58Z`;
- HTTP Last-Modified: `Fri, 07 Aug 2026 00:55:06 GMT`;
- ETag: `"6a752cea-36430b"`;
- content length: `3,556,107` bytes;
- SHA-256:
  `a0d495d951f44e350c35bd7ba9fb11ca59391fa8bc113a8d9efaf07fc0a611a0`.

The source is labeled `single-observer-semi-trusted-gossip-view`, following
LDK's own RGS trust model. It is one collector's approximate public gossip
view; there is no global consensus snapshot of the Lightning graph.

The hash-attested reader recovers the announcement prefix and verifies the
RGS magic, version, Bitcoin-mainnet chain hash, latest-seen timestamp, node
indices, canonical BigSize encodings, funding amounts, content length, and
full-file SHA-256. The captured response contains:

| Quantity | Value |
|---|---:|
| announced node records | 6,434 |
| nodes incident to an announced channel | 6,277 |
| channel announcements | 36,544 |
| distinct unordered endpoint pairs | 31,789 |
| public channel capacity | 605,575,282,718 sat |
| declared directional updates | 73,088 |

The 157 metadata-only node records are excluded from the parent topology
because no captured channel announcement is incident to them. Parallel public
channels are retained in the channel table, collapsed to one edge for the
simple parent graph, and summed for public-capacity-derived node totals.

The reader does not interpret the subsequent routing-policy update payload.
This is deliberate: the structural panels use public adjacency and channel
capacity, while private directional balances remain unavailable. Equal
directional balance is therefore a simulation initialization assumption, not
an observed Lightning fact.

## Rejected 2026 shortcut

The mempool.space `channels-geo` response captured at
`2026-08-07T01:52:52Z` returned exactly 10,000 rows, only 1,268 distinct
nodes, 9,999 distinct endpoint pairs, and one duplicate row. It is suitable
for a visualization service but is visibly capped and cannot represent the
full structural cross-section. It is not an analysis input.

## Historical sources

### 2022

The uploaded paper's public 2022 topology remains the accepted 2022 source.
Its source commit, semantic filter, and hashes are already frozen in
[`docs/evidence/2026-08-01-gate-v1-source-and-semantic-audit.md`](2026-08-01-gate-v1-source-and-semantic-audit.md).
The topology archive SHA-256 is
`20998f859721383a8bbb23abd512043a53f6f98e5c658f12e369620cf3093499`.

### 2020 and 2023

The accepted source is Harvard Dataverse dataset
`doi:10.7910/DVN/2OAVO6`, *Geolocated Lightning Network topology snapshots:
A dataset covering 2019–2023*. Dataset version 1.1 was released at
`2026-02-15T00:02:00Z`. Its strict contract is
[`configs/lightning/dataverse-2020-2023.json`](../../configs/lightning/dataverse-2020-2023.json).

The `snapshots.geo.zip` archive has Dataverse file id `12510549`, size
`562,027,011` bytes, 337 members, repository MD5
`e6edd6fd7acae460abd0f70f71c9dbec`, and independently computed SHA-256
`f380b71796edd86019ddc0b7822938559bfd40a2f650b21ccb66f14ef10e9320`.
The repository MD5 matched, and a full ZIP CRC pass found no damaged member.

The frozen selection rule is the latest quality-controlled snapshot available
within each requested calendar year. It selects:

| Panel | Member | Bytes | SHA-256 | Nodes | Simple edges |
|---|---|---:|---|---:|---:|
| 2020 | `20201230.gml.geo` | 12,283,518 | `351b5ffd35f5b275a22b113275b9016ab721777e273a6d509871040950702cc8` | 6,553 | 29,087 |
| 2023 | `20230716.gml.geo` | 32,928,305 | `ee1b054a6ba2cb0ea3184f9f68f5cca7d8e70d17ff2d9e44e5e8871be8a8b855` | 15,100 | 64,212 |

The archive's published scripts reconstruct gossip at target dates, discard
updates older than two weeks, convert the directed policy view to an
undirected graph, remove retained edges with nonpositive advertised HTLC
maximum, and remove zero-degree nodes. Our standard-library reader preserves
that published cleaned-graph semantics and verifies that node indices are
contiguous, public-key labels are unique, endpoints exist, HTLC maxima are
positive, and the result is a simple graph without isolated records.

These GML files do **not** contain funding-output capacity. Their
`htlc_maximum_msat` field is an advertised directional policy ceiling and must
not be relabeled as channel capacity or liquidity. Consequently, 2020 and
2023 are admissible only for the equal-per-node-capital panel. The
public-capacity-derived sensitivity is limited to the separately attested 2022
and RGS-v2 2026 sources.

## Source references

- LDK Rapid Gossip Sync client and trust model:
  <https://docs.rs/lightning-rapid-gossip-sync/latest/lightning_rapid_gossip_sync/>
- LDK public snapshot endpoint used here:
  <https://rapidsync.lightningdevkit.org/snapshot/v2/0>
- Lightning gossip semantics:
  <https://docs.lightning.engineering/the-lightning-network/the-gossip-network>
- Harvard Dataverse historical dataset:
  <https://doi.org/10.7910/DVN/2OAVO6>
- Dataset methods article:
  <https://doi.org/10.1038/s41597-025-06413-7>

## Next gate

The source-identity and graph-semantics gates are now closed for all four
cross-sections. The next gate is the deterministic core/bridge/periphery
subgraph sampler. It must preserve the ordering
`source identity -> graph semantics -> sampling -> experiments` and must keep
capital-panel availability explicit by year.
