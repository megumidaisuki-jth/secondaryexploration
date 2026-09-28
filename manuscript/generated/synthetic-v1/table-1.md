# Table 1 | Global resource-matched contrasts

Each contrast uses n=60 independent parent graphs per phase: 20 BA, 20 ER-GNM, and 20 fixed-count SBM graphs. Seven held-out traffic traces are nested within each parent and do not increase n. Contrasts are source minus the equal mean of its registered resource-matched binary arms; global contrasts equally average the four source-family contrasts. Failure-risk differences are probability differences (negative is beneficial); restricted no-path time is divided by H=12 times node count (positive is beneficial). Bounds are multiplicity-adjusted percentile interval bounds from 20,000 parent-stratified bootstrap resamples, with adjusted empirical probability 1/1600 in each tail and local confidence parameter 159/160. The studywise 95% family covers 40 contrasts separately within each phase, not 80 jointly; phases are not pooled. Exact fractions, all 40 contrasts per phase, and JSON source pointers are in numerical-registry.json and the linked Source Data. No p values are inferred from bounds.

| Endpoint | Nodes | Formal estimate [lower, upper] | Formal direction | Confirmation estimate [lower, upper] | Confirmation direction | n per phase (BA+ER+SBM) | Replication state |
|---|---:|---|---|---|---|---|---|
| Failure risk | 30 | -0.425 [-0.478, -0.371] | beneficial | -0.449 [-0.506, -0.393] | beneficial | 60 (20+20+20) | independently confirmed |
| Failure risk | 60 | -0.559 [-0.612, -0.507] | beneficial | -0.575 [-0.628, -0.519] | beneficial | 60 (20+20+20) | independently confirmed |
| Failure risk | 120 | -0.701 [-0.754, -0.645] | beneficial | -0.693 [-0.745, -0.646] | beneficial | 60 (20+20+20) | independently confirmed |
| Failure risk | 240 | -0.805 [-0.842, -0.765] | beneficial | -0.787 [-0.829, -0.742] | beneficial | 60 (20+20+20) | independently confirmed |
| Restricted no-path time / H | 30 | 0.192 [0.158, 0.230] | beneficial | 0.216 [0.183, 0.249] | beneficial | 60 (20+20+20) | independently confirmed |
| Restricted no-path time / H | 60 | 0.307 [0.266, 0.346] | beneficial | 0.305 [0.266, 0.344] | beneficial | 60 (20+20+20) | independently confirmed |
| Restricted no-path time / H | 120 | 0.437 [0.401, 0.474] | beneficial | 0.441 [0.398, 0.485] | beneficial | 60 (20+20+20) | independently confirmed |
| Restricted no-path time / H | 240 | 0.566 [0.531, 0.600] | beneficial | 0.562 [0.530, 0.594] | beneficial | 60 (20+20+20) | independently confirmed |
