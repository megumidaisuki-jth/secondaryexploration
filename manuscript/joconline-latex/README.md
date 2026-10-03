# 中文双栏 LaTeX 作者稿

题目：资源匹配下超图支付网络的服务可靠性。

本版将中文扩展母稿整理为 A4 双栏正文，含通栏中英文题名、摘要及关键词。
2026-10-03 本机实际编译为 **10 页**，并逐页检查渲染结果。
这是《通信学报》风格的作者稿，**不是出版社提供或认证的官方模板**；
正式投稿前仍需按当期投稿要求复核。作者、单位、邮箱和基金均按要求保留待填。

## 文件与编译

- `main.pdf`：本机核验后的阅读版。
- `main.tex`：完整正文、公式、算法、表格与参考文献；可直接编辑。
- `figures/`：三幅原有矢量 PDF 图，与已核验母稿逐字节一致。
- `source-package.zip`：可上传 Overleaf 或在其他电脑编译的源码包。
- `compression-map.json`：18 段重复说明的删减记录，原文全部保留在映射内。
- `supplement-recommendations.md`：后续内容与实验建议，尚未执行。
- `metric-definitions.md`：13 项描述指标的公式、聚合口径和解释边界。
- `accuracy-corrections.json`、`revision-notes.md`：准确性修正映射及逐项处理记录。
- `qa.md`、`manifest.json`：检查范围、输入与交付文件的字节数及 SHA-256。

将源码包完整解压，工作目录切到含 `main.tex` 的文件夹，执行：

```sh
xelatex -interaction=nonstopmode -halt-on-error main.tex
xelatex -interaction=nonstopmode -halt-on-error main.tex
```

也可使用已配置的 Tectonic：`tectonic main.tex`。
Overleaf 选择 **XeLaTeX**，主文档选择 `main.tex`，不能只上传单个 tex 文件。
需要 ctex、fontspec、amsmath、booktabs 等常用 TeX 包；参考文献已内嵌，无需 BibTeX。
本机使用宋体/黑体；若无这些字体，源码自动回退到 Fandol 字体。
字体或 TeX 版本变化可能改变换行和页数，10 页结论对应随包交付的本机 PDF。

应用内 LaTeX 编辑器已请求打开该源文件，但内置编译器发生环境初始化错误
`Unable to find standard directories for platform`。本版 PDF 来自已有的
Tectonic 0.17.0 编译器，不是内置编译成功的结果；没有新安装 TeX 或插件。
文档包含外部图文件，单文件编译服务还需要支持这些依赖。

## 可追溯构建

仓库根目录运行 `python tools/build_joconline_latex.py` 可从
`manuscript/joconline-expanded/manuscript-zh.md` 重新生成正文及图文件。
构建器校验母稿、两张数据输入 JSON 和图文件的冻结哈希，并应用
`accuracy-corrections.json` 中的修正；锚点不唯一时立即失败。不运行模拟或统计推断。
表 1 复用已有显示值；表 2 对已有有理数均值按三位小数显示；表 3 复用已有计数。

注意：构建器是从母稿到 LaTeX 的单向转换，**重新运行会覆盖对 main.tex 的直接修改**。
直接修改 LaTeX 后应保留编辑版本，不要无意重建；重新编译、渲染、核验后才更新交付清单。
仓库根目录执行 `python -m tools.package_joconline_latex`（需要 pypdf）
会验证固定交付结构和来源、打包源码并更新清单，
但它不能替代编译和人工逐页检查，也不能证明未来修改后的 PDF 与源码一致。

原短版、15 页扩展 Word 母稿及全部科学结果均未覆盖。旧母稿保留审查前表述，
不应继续作为已修正版本引用；本目录的 main.tex 是当前修订稿。
