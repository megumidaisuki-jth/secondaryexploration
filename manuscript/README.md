# Manuscript workspace

## 中文双栏 LaTeX 稿（2026-10-03）

最新排版交付为 [10 页双栏稿](joconline-latex/main.pdf)，附
[LaTeX 源码](joconline-latex/main.tex)、[源码包](joconline-latex/source-package.zip)
和 [使用说明](joconline-latex/README.md)。这是《通信学报》风格的作者稿，非官方模板。
保留 16 个编号公式、2 个算法、3 幅图、3 张表和 15 条参考文献；
从扩展母稿中删去 18 段重复说明，完整映射保存在 compression-map.json，原稿不变。
未新增实验或推断。下一步建议见 [补强建议](joconline-latex/supplement-recommendations.md)。

## 中文扩展稿（2026-09-30）

当前推荐阅读 [中文扩展稿](joconline-expanded/manuscript-zh.md) 及同目录可编辑 Word。
按用户“理论与方法细节、实验解释并重”的选择，正文汉字数由约6,963增至14,801，
Word预览由9页增至15页，包含16个编号公式、2个算法、3幅图及3张表。
补充状态更新性质与证明、路由和训练算法细节、复杂度边界、分层结果及不利个例解释。
只使用已有证据，未重跑实验或新增推断；原短版保持不变。
见 [扩写说明](joconline-expanded/revision-notes.md) 和 [检查记录](joconline-expanded/qa.md)。
本版为便于审阅与后续取舍的详细母稿，不宣称已满足最终投稿篇幅或出版社模板要求。

## 中文完整稿（2026-09-29）

按用户最新指定的《通信学报》方向，已另建 [中文完整稿](joconline/manuscript-zh.md)，
覆盖摘要至结束语，附可编辑 Word、3 幅中文图及 15 条参考文献。
作者、单位、通信作者和基金信息按用户要求保留待填。
参见 [编写与证据说明](joconline/writing-notes.md) 及 [质量检查记录](joconline/qa.md)。
以下英文工作稿说明保留为原 TNSM 路线的历史记录，不代表中文稿仍缺讨论和结论。

## Draft status

The current paper type is **algorithmic**. Working drafts cover
**Introduction**, **Related Work**, **Methods**, and an evidence-populated
**Results** section with three main figures and Table 1. The original
result-free Results scaffold is retained as a historical design record;
**Discussion/Conclusion** remains a scaffold. The source workflow is
**Chinese-to-English**, and the target style is the generic journal route
calibrated toward IEEE Transactions on Network and Service Management. The
formal and confirmation evidence and descriptive projections are complete;
Results claims are linked to the archived Source Data. Template integration
and final page-budget verification remain pending.

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
- Results 已根据完整 formal 与 confirmation 证据填写，但结论只适用于已注册的合成条件；不能扩展为“普遍更优”、训练的因果收益或现实网络验证。
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
- [Result-gated Discussion and Conclusion scaffold](discussion-conclusion-scaffold.md)
- [Result-gated Results scaffold](results-scaffold.md)
- [Evidence-populated Results draft](results.md)
- [Results claim–evidence map and reporting notes](results-writing-notes.md)
- [Main figures, Table 1 and exact numerical registry](generated/synthetic-v1/README.md)
- [Complete descriptive writing support](generated/results-writing-v1/descriptive-support.md)
- [Methods citation claims](citations/method-claims.md) and
  [EndNote export](citations/method-references.enw)
- [Introduction and Related Work citation claims](citations/intro-related-work-claims.md)
  and [EndNote export](citations/intro-related-work-references.enw)
- [Data Availability working draft](data-availability.md)
- [IEEE TNSM submission and page-budget contract](tnsm-submission-contract.md)

## Next manuscript inputs

- Review the populated Results draft, then fill the Discussion and Conclusion
  using the complete evidence and its limitations. Follow the
  frozen [Results reporting contract](../docs/plans/2026-08-11-results-reporting-contract.md)
  so all registered rows remain visible. The archived scaffolds' missing-input
  lists describe the earlier evidence-gated state, not the current completion status.
- Compress the verified result-free opening and Methods only after the complete
  evidence determines which implementation and sensitivity details must remain
  in the 10-page main article.
- Keep the unresolved 2026 Lightning snapshot preservation gate explicit. The
  panel is excluded even from diagnostic publication until that gate is
  resolved and remains diagnostic-only, never confirmatory, if preserved.
- Obtain the exact LaTeX package through the frozen IEEE TNSM selector route at
  the start of typesetting and record its download date and SHA-256.
