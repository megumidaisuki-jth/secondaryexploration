# S4：6n与12n窗口敏感性

入口：[中文分析报告](report.md)。数据是保存事件重分析，不是新模拟。图表使用未校正点态区间，仅供探索性解释。

- window-contrasts.csv：480个窗口效应（combined 160带区间；另320描述性）。
- paired-window-changes.csv：240个配对变化（combined 80带区间；另160描述性）。
- parent-window-contrasts.csv：28,800条父图级精确有理数效应。
- saved-event-observations.csv：每变体/轨迹原事件与两个窗口事件标记，含原区块SHA与配对清单指纹。
- absolute-window-means.csv：384条宽表，每条含时间/风险两个均值，共768个终点均值；面板事件数可为分数，不是把二元臂当独立重复。
- event-timing-summary.csv：窗口前/恰在边界/窗口后至原H/行政删失的精确分数计数，辅助解释短窗口的事件信息量。
- DA-FHS5-paired-information.csv：420对测量中共同无事件、任一方有事件及时间/风险差非零的计数；不当作独立样本量。
- parents/：480个可校验事件信封；bootstrap/：320组500次精确整数复制值及哈希收据。
- verification.json及verification-checkpoints/：单独实现算术核验；不是盲审或新增确认许可。
- resume-demonstration.json：4区块暂停/恢复实例；progress.json和verification-progress.json可读进度。
- 两组S4图表：SVG、PDF、600dpi TIFF、300dpi PNG；figure-contract.md与figure-qa.md记录口径与检查。

复现（本机冻结运行时）：运行 tools/supplement_short_window.py，再运行 tools/verify_supplement_short_window.py、tools/report_supplement_short_window.py；检查最终PNG并记录figure-qa.md，然后运行 tools/qa_supplement_short_window.py、tools/seal_supplement_short_window.py。PYTHONPATH需包含E:\second-doc-runtime及E:\second，源码/配置必须与binding.json一致。

安全暂停：在本目录创建空PAUSE文件，等待progress或verification-progress为paused-safe-checkpoint且运行锁消失。恢复需先确认进程已退出，再移除PAUSE；不要删除活跃锁或编辑已绑定文件。提取与bootstrap断点可复用，校验bootstrap每阶段/规模一个校验收据，最多重检一个规模的20,000个复制值。

S5仍需新增模拟，本轮未启动。
