# Results drafting and evidence audit

## Draft and argument

The English draft is [results.md](results.md). This is a Results-only working
draft, not a completed paper or a typeset page-budget approval.

One-sentence argument: in the registered synthetic hypergraph payment-network
benchmark, all registered resource-matched service contrasts reproduced in
formal and confirmation, while coverage, activity and coordination records
bound the interpretation and do not identify a mechanism.

The existing terminology ledger, algorithmic-paper framing and IEEE TNSM
target were reused. The primary reader is a network/service-management
researcher evaluating fair comparison and reproducibility. No new novelty
claim or external citation was introduced.

## Section outline and paragraph jobs

| Subsection | Frozen evidence jobs | Paragraph jobs |
|---|---|---|
| A | 1: completion, phase separation, independent unit | Execution evidence; inferential convention |
| B | 2–4: globals, named gates, model strata | Global effect estimates; complete named registry; descriptive model patterns |
| C | 5–6: coverage and activity | Censoring identification; changed/unchanged subgroup boundaries |
| D | 7–8: descriptors, runtime and scope | Full descriptor pattern including coordination costs; measured cost and external-validity boundary |

This preserves all eight frozen jobs in their original order. The global
table supplies every estimate and bound; the main text does not repeat all
bounds. The complete registry is retained rather than selecting favourable
named-family examples. Interpretation beyond these observations belongs in
Discussion, which has not been filled during this step.

## Claim–evidence map

All pointers below refer to the frozen Source Data unless another file is
named. The writing-support JSON retains source pointers for derived summaries.

| Claim | Evidence | Status / boundary |
|---|---|---|
| 240 blocks in each phase; 60 parents per contrast | `/phase_data/{phase}/runtime_and_environment`; all registered interval parent/stratum counts | Supported; seven traces are nested, not extra n |
| Eight global and 32 named-family contrasts independently confirmed | `/cross_phase_replication_records`; Table 1 and full numerical registry | Supported under frozen state rules, not an independent implementation audit |
| All reported global point estimates and adjusted bounds | `/phase_data/{phase}/registered_intervals`; Table 1 | Supported; exact fractions control state, not rounding |
| All 60 risk and 60 time model-stratum means have beneficial signs per phase | `evidence-summary.json`: `phases/{phase}/parent_stratum_summaries` | Descriptive only; not proof every individual parent benefits |
| Two fully identified coverage cells per phase; 34/24 zero-identified cells | `phases/{phase}/event_coverage` in writing support, linked to 96 original cells per phase | Supported; no numerical lower quantile and no pooling of repeated parents |
| Changed topology counts 33/21/5/1 and 34/16/13/1 | `/phase_data/{phase}/activity_sensitivity` | Supported; one count set per size, not doubled across endpoints |
| Changed n=240 subgroup means unavailable | Same activity cells; BA/ER-GNM/SBM counts 1/0/0 and 0/1/0 | Supported; never replace null by zero |
| Unchanged n=240 means −0.922/−0.898 and 0.638/0.647 | Corresponding activity cells' exact equal-model descriptive means | Descriptive; not a trained-versus-seed contrast |
| Signs of all 13 descriptor families and coordination ranges | All 208 descriptor cells per phase, 3 strata per cell; writing support descriptor ranges | Descriptive, source-minus-matched-binary; no p values or mediation claim |
| Generation/validation block-hour totals and execution environment | `/phase_data/{phase}/runtime_and_environment` | Supported; totals reproduced from block durations, not elapsed study time |
| Timer meaning | `secondaryexploration/experiments/runner.py`, generation and validation around `perf_counter_ns` | Elapsed per-block durations, not process CPU time |
| Scope excludes Lightning | Frozen Results reporting contract and current synthetic evidence inputs | No empirical live-network claim |

## Statistical reporting review

Reviewed: new Results prose, existing Table 1 and complete numerical registry,
canonical Source Data, and deterministic writing-support aggregations.
No new statistical test, bootstrap run, exclusion, inferential subgroup
analysis or changed simulation design was performed.

- Independent unit: parent graph within phase, size and model stratum.
- Paired reference: only each source family's registered binary arms; global
  means weight the four source-family contrasts equally.
- Primary endpoints: normalized restricted no-path time and fixed-horizon
  failure risk. Their beneficial directions remain opposite.
- Multiplicity: 40 contrasts per phase, eight local hierarchies, 20,000
  resamples, local confidence parameter 159/160, per-tail probability 1/1600.
  No joint 80-contrast 95% claim or invented p values.
- Descriptive cells: not additional independent replicates. Counts of signs
  are not treated as replication probabilities or a new success metric.
- Activity strata: empty/singleton cases retained; null means stay null;
  no claim that changing topology caused an improvement.
- Cost: reported adverse coordination patterns alongside service differences;
  runtime sums are not used to claim speedup or efficient implementation.
- Analysis provenance: archived replay is distinguished from an independently
  developed implementation or an independent code-review verdict.

## Remaining publication checks

- [P1] Whole-run peak memory and end-to-end elapsed runtime are not provided
  by the canonical summaries. The draft states that boundary rather than
  substituting a worker snapshot or summed parallel duration. If essential
  for a later efficiency claim, first audit existing diagnostics; no such
  efficiency claim is made here.
- [P1] Cross-phase agreement does not provide independent implementation
  verification. An independent code review, if pursued, must be labelled
  separately and must not be inferred from the archived success receipts.
- [P1] Final journal-template integration and the frozen 2.6-page Results
  allocation remain unverified until typesetting. No evidence row may be
  removed to recover space.
- [P2] Confirm final article-wide abbreviation first-use locations and figure
  numbering after joining this section to Introduction and Methods.

No new author decision is needed to use this bounded Results draft. It still
requires author review before submission. All long-running analyses are
unchanged; the new support script performs only exact arithmetic on archived
summary data.

## Verification commands

`python -m unittest tests.test_results_writing_support -v` passed seven tests
covering archived hashes, all source-derived primary estimates, event-count
coverage, activity partitions/null handling, all descriptor cells, numerical
prose and the reported descriptive directions/counts. The pre-existing 13
display checks and export verifier were also rerun. This is a reporting
consistency check, not a new independent statistical audit.

## 中文说明

本稿按“完整性与统计口径—主结果和分层—删失与活动性—描述指标和成本”组织，
保留冻结结构的全部八项任务。特别写明：更好的服务终点不等于协调开销更低；
需求感知拓扑没有变化的样本仍可能优于二元参考，不能据此把收益归因于训练。
240 节点 changed 组只各有一个父图，缺失模型层均值不能补零。累计区块计时
不能当作用户实际等待时间。原 Results scaffold 作为事前设计记录保留不覆盖。

如需调整，请指定具体段落或主张；其余段落及术语保持不变。
