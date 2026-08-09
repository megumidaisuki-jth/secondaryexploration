# Lightning structural sampling diagnostic v1

This directory records a replayable **diagnostic-only** grid from the four
accepted Lightning cross-sections. The three anchor replicates are not the
formal experimental sample size and cannot be relabelled as independent
network observations.

## Frozen grid

- Source years: 2020, 2022, 2023, and 2026
- Structural anchor strata: core, bridge, and peripheral
- Nested sizes: 30, 60, 120, and 240 nodes
- Diagnostic anchors per year/stratum: 3
- Base seed: `2026080702`
- Registry fingerprint:
  `b51af2a7689fbd79c0b1354815d037e9fa3c31d000da12758f1c45dd77eaf211`

The machine-readable artifact is
`lightning-sampling-registry-v1.json`. It binds each source, parent graph,
largest connected component, canonical strata record, anchor, discovery-order
fingerprint, induced-subgraph fingerprint, and sample fingerprint.

## Source and strata checks

| Year | Parent nodes | Parent edges | LCC nodes | LCC edges | Core pool | Bridge pool | Peripheral pool |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2020 | 6,553 | 29,087 | 6,529 | 29,075 | 1,306 | 97 | 1,306 |
| 2022 | 11,268 | 61,966 | 11,209 | 61,933 | 2,242 | 406 | 2,242 |
| 2023 | 15,100 | 64,212 | 15,071 | 64,196 | 3,015 | 345 | 3,015 |
| 2026 | 6,277 | 31,789 | 6,225 | 31,751 | 1,245 | 231 | 1,245 |

All 144 requested samples replayed as exact-size connected induced graphs. No
pair of diagnostic anchors within the same year, stratum, and size produced an
identical node set. The largest observed pairwise Jaccard overlap was
`69/411 = 0.1679` (2026 peripheral, size 240). These overlap checks are
descriptive and do not create independent parent-graph replicates.

The rank boundary is materially tied, especially in the periphery. For
example, all 1,306 selected 2020 peripheral candidates lie in a
`(core number=1, degree=1)` boundary class containing 2,844 nodes; the 2023
class contains 6,592 nodes for 3,015 selected candidates. The formal Lightning
analysis must therefore report a boundary-tie sensitivity based on a
source-bound hash ordering in addition to the frozen node-id ordering.

The registry now performs that candidate-pool sensitivity without changing the
frozen primary samples. Candidate-set Jaccard overlap between node-ID and
source-bound SHA-256 tie breaking is:

| Year | Core | Bridge | Peripheral |
|---:|---:|---:|---:|
| 2020 | 1,297/1,315 (0.986) | 95/97 (0.979) | 603/2,009 (0.300) |
| 2022 | 2,241/2,243 (0.999) | 406/406 (1.000) | 1,222/3,262 (0.375) |
| 2023 | 2,947/3,083 (0.956) | 345/345 (1.000) | 1,365/4,665 (0.293) |
| 2026 | 1,244/1,246 (0.998) | 231/231 (1.000) | 590/1,900 (0.311) |

Thus core and bridge membership is stable, whereas peripheral membership is
tie-break-sensitive. Formal peripheral conclusions must be repeated under the
alternative source-bound ordering; the primary node-ID result alone is not a
robustness claim.

## Rebuild

From the repository root, with the hash-attested source files available under
the local ignored `tmp` tree:

```powershell
python -m secondaryexploration.analysis.lightning_registry `
  --historical-manifest configs\lightning\dataverse-2020-2023.json `
  --historical-archive tmp\lightning-sources\snapshots.geo.zip `
  --prior-topology tmp\upstream-hpn\LN_data_2022.zip `
  --prior-trace tmp\upstream-hpn\Lightning_2022_10k_transactions.csv `
  --rgs-manifest configs\lightning\rgs-2026-08-07.json `
  --rgs-snapshot tmp\lightning-sources\rgs-v2-snapshot-0.lngossip `
  --output results\diagnostics\lightning-sampling-registry-v1.json `
  --base-seed 2026080702 --replicate-count 3 --sizes 30 60 120 240
```

The CLI revalidates every source hash and fully rebuilds the registry before
writing it atomically.
