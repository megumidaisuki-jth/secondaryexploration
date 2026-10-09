# 全部补充证据整合稿

在原11页四臂稿基础上，加入S1搜索增量、S2负载分解、S3每成功请求成本及S4窗口敏感性，保留S5、不利结果及原准确性修正。旧10页与S5版不覆盖。

`main.tex/main.pdf`为双栏正文，`supplement.tex/supplement.pdf`统一S1–S5分析与图S1–S8编号。作者、单位、邮箱、基金信息仍待填；本稿不是出版社官方类。

`claim-evidence-map.md`给出中心论点、技术贡献、证据及排除范围。
`integration-sections.tex`是新增正文的编辑源；`source-data/`保存各补充完整JSON及算术核验收据。
`source-validation.json`记录原归档清单的逐字节核验；`manifest.json`绑定本版文件，`source-package.zip`保存可复用作者包。
原仓库的父图数据、请求、bootstrap检查点、图表全部格式与代码仍保留；包不复制这些大型完整目录，核验清单明确指向它们。

运行仓库根的 `python -m tools.integrate_supplement_initialization_manuscript` 构建，默认要求原固定输入哈希，输入改变会拒绝。编译用现有Tectonic或XeLaTeX（在本目录分别编译main.tex和supplement.tex）；不安装新TeX。构建和编译不产生模拟、训练、重抽样或统计检验。

S1区间与S3–S5点态区间使用不同的多重比较口径。补充分析不是原确认家族的一部分，独立算术实现检查不等于新的盲科学审查。详见补充首段、各图注及论证映射。
