# Manuscript workspace

## Draft status

The current paper type is **algorithmic**, and result-free working drafts now
cover **Introduction**, **Related Work** and **Methods**. The source workflow is
**Chinese-to-English**, and the target style is the generic journal route
calibrated toward IEEE Transactions on Network and Service Management. Result
and effect-direction language remains gated on complete formal and confirmation
evidence.

## One-sentence argument

In hypergraph payment networks, we evaluate how topology, traffic and
balance-aware routing jointly shape service reliability using resource-matched
topologies, train-once held-out evaluation, paired request traces and
parent-stratified inference, with conclusions bounded to the registered
synthetic and structural-panel conditions.

## Section outline

1. Study overview and phase separation.
2. Hypergraph state, atomic payments and balance-aware routing.
3. Parent-graph strata, topology construction and resource matching.
4. Training demand, demand-aware topology search and common capacity allocation.
5. Paired execution, service endpoints and censoring.
6. Parent-level estimands, stratified bootstrap and independent confirmation.
7. Reproducibility controls and claim boundaries.

## Chinese drafting notes

- Methods 按“输入—构造—训练—留出评估—父图聚合—独立确认”的执行顺序组织，避免把设计动机、算法细节和结果主张混写在同一段。
- 校准结果已经改变主推断路由：正式主终点是归一化受限 `tau_nopath` 与固定时域失败风险；`q=0.10` 下分位数只报告可识别性，不把删失时域冒充失败时间。
- 当前稿件只陈述已冻结且可重放的合同。任何 *improves*、*outperforms* 或“普遍更优”表述必须等待完整 formal 与 confirmation 证据。
- 术语统一以 [terminology.md](terminology.md) 为准，尤其不能混同 `tau_dep`、`tau_nopath` 与 `tau_rej`。

## Why this structure

- It separates what the system is, why each module is required and how it is
  evaluated.
- It introduces the independent experimental unit before the bootstrap, which
  prevents nested traffic traces from being mistaken for independent samples.
- It presents censoring and phase separation before inferential decisions, so
  the claim boundary is visible rather than deferred to the Discussion.

## Prepared artifacts

- [Methods working draft](methods.md)
- [Terminology ledger](terminology.md)
- [Introduction and Related Work outline](introduction-outline.md)
- [Introduction and Related Work working draft](introduction.md)
- [Methods citation claims](citations/method-claims.md) and
  [EndNote export](citations/method-references.enw)
- [Introduction and Related Work citation claims](citations/intro-related-work-claims.md)
  and [EndNote export](citations/intro-related-work-references.enw)
- [Data Availability working draft](data-availability.md)
- [IEEE TNSM submission and page-budget contract](tnsm-submission-contract.md)

## Next manuscript inputs

- Complete formal and confirmation evidence before drafting Results.
- Compress the verified result-free opening and Methods only after the complete
  evidence determines which implementation and sensitivity details must remain
  in the 10-page main article.
- Keep the unresolved 2026 Lightning snapshot preservation gate explicit; the
  corresponding structural panel remains diagnostic-only unless that gate is
  resolved.
- Obtain the exact LaTeX package through the frozen IEEE TNSM selector route at
  the start of typesetting and record its download date and SHA-256.
