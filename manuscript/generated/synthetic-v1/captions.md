# Figure captions

## Figure 1 | Registered design and evidence flow

Result-free schematic of the synthetic benchmark. Independent parent graphs feed paired held-out traffic and resource-matched comparisons. Formal and confirmation evidence are analysed separately before the complete cross-phase registry is displayed. Traces and binary arms are not independent graph replicates.

## Figure 2 | Global resource-matched service contrasts

a Failure-risk difference. b Normalized restricted no-path-time difference. Blue circles show formal estimates and orange squares confirmation estimates; horizontal lines show adjusted bounds. The dashed line is zero. All four registered sizes appear in each panel.

Each contrast uses n=60 independent parent graphs per phase: 20 BA, 20 ER-GNM, and 20 fixed-count SBM graphs. Seven held-out traffic traces are nested within each parent and do not increase n. Contrasts are source minus the equal mean of its registered resource-matched binary arms; global contrasts equally average the four source-family contrasts. Failure-risk differences are probability differences (negative is beneficial); restricted no-path time is divided by H=12 times node count (positive is beneficial). Bounds are multiplicity-adjusted percentile interval bounds from 20,000 parent-stratified bootstrap resamples, with adjusted empirical probability 1/1600 in each tail and local confidence parameter 159/160. The studywise 95% family covers 40 contrasts separately within each phase, not 80 jointly; phases are not pooled. Exact fractions, all 40 contrasts per phase, and JSON source pointers are in numerical-registry.json and the linked Source Data. No p values are inferred from bounds.

## Figure 3 | Complete cross-phase replication registry

Every row is one endpoint and node-count hierarchy, with its five contrasts. Cell fill denotes replication state only. F and C identify phases; B, H and I denote beneficial, harmful and inconclusive adjusted intervals. A hatched phase half-cell denotes a closed secondary gate; an unhatched secondary cell is open. Global gates are not applicable. Independently confirmed requires beneficial intervals and applicable open gates in both phases; other states do not imply equivalence.

Each contrast uses n=60 independent parent graphs per phase: 20 BA, 20 ER-GNM, and 20 fixed-count SBM graphs. Seven held-out traffic traces are nested within each parent and do not increase n. Contrasts are source minus the equal mean of its registered resource-matched binary arms; global contrasts equally average the four source-family contrasts. Failure-risk differences are probability differences (negative is beneficial); restricted no-path time is divided by H=12 times node count (positive is beneficial). Bounds are multiplicity-adjusted percentile interval bounds from 20,000 parent-stratified bootstrap resamples, with adjusted empirical probability 1/1600 in each tail and local confidence parameter 159/160. The studywise 95% family covers 40 contrasts separately within each phase, not 80 jointly; phases are not pooled. Exact fractions, all 40 contrasts per phase, and JSON source pointers are in numerical-registry.json and the linked Source Data. No p values are inferred from bounds.
