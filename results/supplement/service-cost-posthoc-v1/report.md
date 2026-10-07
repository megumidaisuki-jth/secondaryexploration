# S3 服务量—成本联合分析

本分析复用480个已存档父图区块，按保存路线重算服务与暴露成本。未新增支付模拟。结果为后验探索性描述，区间为点对点未校正95%区间，不能按某个区间是否跨零作同时优越性或新的确认性结论。

## 统计量及作用

- 成功率 S/H 描述支付服务完成程度；成功支付总额 V/H 以实验金额单位报告，不能直接换算货币收益。
- 首次无可用路径是首个失败事件，并不意味着之后所有请求均停止；S和C统计整个固定时域H内的保存请求。这一补充回答累计服务与成本问题，与S1的首次事件时间问题互补。
- 总暴露 C/H 描述每次尝试的平均路线暴露；它同时受成功数与路线结构影响。
- 单位成功服务成本定义为 E[C]/E[S]。七条轨迹先在父图内等权汇总，三模型各20父图等权。它不是 E[C/S]，也不是单位成功金额成本。
- 配对效率差为 E[C_A]/E[S_A]−E[C_B]/E[S_B]，每次bootstrap同时抽取同一父图的服务与成本，随后重新求两组比值和差。不是 E[(C_A−C_B)/(S_A−S_B)]。
- 二元参照在对应资源面板内先等权平均；一个父图的多个二元臂不增加独立样本量。
- 成本依次为超边遍历次数、Σ|e|参与者信令槽、逐成功路线的去重参与者数之和、Σ|e|²协调暴露，以及Σ|e|log₂|e|敏感性暴露。单位均为模型计数/暴露代理，不能声称测量了真实字节、延迟或密码学费用。

设 a 为方案，g 为父图模型层，b 为该层父图，r 为留出轨迹。则 $\bar S_a=\frac{1}{3}\sum_{g=1}^{3}\frac{1}{20}\sum_{b=1}^{20}\frac{1}{7}\sum_{r=1}^{7}S_{a,g,b,r}$，$\bar C_a$ 按相同权重定义；单位成功成本 $R_a=\bar C_a/\bar S_a$。如果 a 是资源匹配二元参照，还需在每条轨迹上先对注册二元臂等权平均。

每次bootstrap在每个模型层内有放回抽取20个父图，得到共同索引后的 $\bar C_a^*$ 与 $\bar S_a^*$，再计算 $R_a^*=\bar C_a^*/\bar S_a^*$。配对差复制值为 $D_{a,b}^*=R_a^*-R_b^*$。这保持服务量与成本的相关性；不能把二者分别抽样后拼接比值区间。

## 成功服务和单位成功成本

| 相位 | n | 方案 | 角色 | 成功率 | 遍历/成功 | 信令槽/成功 | 去重参与者/成功 | 平方暴露/成功 | log₂暴露/成功 |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| formal | 30 | demand-aware | source | 0.999147 | 1.715227 | 8.255112 | 7.395205 | 40.401374 | 18.835359 |
| formal | 30 | demand-aware | binary_panel | 0.966068 | 3.098727 | 6.197454 | 4.098727 | 12.394908 | 6.197454 |
| formal | 30 | fhs3 | source | 0.995132 | 1.948632 | 5.731577 | 4.763525 | 16.966092 | 8.950589 |
| formal | 30 | fhs3 | binary_panel | 0.978581 | 2.561386 | 5.122772 | 3.561386 | 10.245544 | 5.122772 |
| formal | 30 | fhs5 | source | 0.998664 | 1.720957 | 8.277070 | 7.407436 | 40.499205 | 18.880742 |
| formal | 30 | fhs5 | binary_panel | 0.966068 | 3.098727 | 6.197454 | 4.098727 | 12.394908 | 6.197454 |
| formal | 30 | nch | source | 1.000000 | 1.329987 | 10.171171 | 9.533618 | 89.448446 | 30.813236 |
| formal | 30 | nch | binary_panel | 0.987927 | 2.170126 | 4.340252 | 3.170126 | 8.680504 | 4.340252 |
| formal | 60 | demand-aware | source | 0.999778 | 1.958989 | 9.453278 | 8.409013 | 46.338388 | 21.596350 |
| formal | 60 | demand-aware | binary_panel | 0.959641 | 3.511626 | 7.023252 | 4.511626 | 14.046503 | 7.023252 |
| formal | 60 | fhs3 | source | 0.995552 | 2.274933 | 6.683666 | 5.395552 | 19.768730 | 10.428244 |
| formal | 60 | fhs3 | binary_panel | 0.971931 | 3.012432 | 6.024865 | 4.012432 | 12.049729 | 6.024865 |
| formal | 60 | fhs5 | source | 0.999772 | 1.960894 | 9.464388 | 8.417820 | 46.396962 | 21.623511 |
| formal | 60 | fhs5 | binary_panel | 0.959641 | 3.511626 | 7.023252 | 4.511626 | 14.046503 | 7.023252 |
| formal | 60 | nch | source | 0.999997 | 1.538087 | 13.046895 | 12.121965 | 135.171307 | 41.944888 |
| formal | 60 | nch | binary_panel | 0.983856 | 2.571115 | 5.142230 | 3.571115 | 10.284460 | 5.142230 |
| formal | 120 | demand-aware | source | 0.999821 | 2.218544 | 10.741032 | 9.470458 | 52.726327 | 24.571231 |
| formal | 120 | demand-aware | binary_panel | 0.963500 | 3.903468 | 7.806936 | 4.903468 | 15.613872 | 7.806936 |
| formal | 120 | fhs3 | source | 0.995655 | 2.575115 | 7.579514 | 5.997062 | 22.446881 | 11.842635 |
| formal | 120 | fhs3 | binary_panel | 0.972646 | 3.403579 | 6.807158 | 4.403579 | 13.614316 | 6.807158 |
| formal | 120 | fhs5 | source | 0.999821 | 2.217923 | 10.737116 | 9.467264 | 52.703585 | 24.561093 |
| formal | 120 | fhs5 | binary_panel | 0.963500 | 3.903468 | 7.806936 | 4.903468 | 15.613872 | 7.806936 |
| formal | 120 | nch | source | 0.999980 | 1.721780 | 16.221106 | 15.099600 | 209.821220 | 55.698852 |
| formal | 120 | nch | binary_panel | 0.982807 | 2.943042 | 5.886084 | 3.943042 | 11.772167 | 5.886084 |
| formal | 240 | demand-aware | source | 0.999922 | 2.476409 | 12.019947 | 10.511983 | 59.107586 | 27.533181 |
| formal | 240 | demand-aware | binary_panel | 0.962607 | 4.363149 | 8.726298 | 5.363149 | 17.452597 | 8.726298 |
| formal | 240 | fhs3 | source | 0.996314 | 2.879667 | 8.491923 | 6.607971 | 25.181609 | 13.287307 |
| formal | 240 | fhs3 | binary_panel | 0.970088 | 3.844336 | 7.688672 | 4.844336 | 15.377344 | 7.688672 |
| formal | 240 | fhs5 | source | 0.999922 | 2.476433 | 12.020044 | 10.512078 | 59.108042 | 27.533389 |
| formal | 240 | fhs5 | binary_panel | 0.962607 | 4.363149 | 8.726298 | 5.363149 | 17.452597 | 8.726298 |
| formal | 240 | nch | source | 0.999973 | 1.883511 | 19.857743 | 18.579698 | 329.682884 | 73.107821 |
| formal | 240 | nch | binary_panel | 0.980981 | 3.334261 | 6.668522 | 4.334261 | 13.337045 | 6.668522 |
| confirmation | 30 | demand-aware | source | 0.999702 | 1.720472 | 8.260408 | 7.390030 | 40.370123 | 18.825774 |
| confirmation | 30 | demand-aware | binary_panel | 0.960694 | 3.077549 | 6.155098 | 4.077549 | 12.310195 | 6.155098 |
| confirmation | 30 | fhs3 | source | 0.993876 | 1.957211 | 5.748739 | 4.770918 | 17.000426 | 8.967757 |
| confirmation | 30 | fhs3 | binary_panel | 0.973019 | 2.572031 | 5.144062 | 3.572031 | 10.288124 | 5.144062 |
| confirmation | 30 | fhs5 | source | 0.999392 | 1.729452 | 8.295147 | 7.413406 | 40.518431 | 18.896407 |
| confirmation | 30 | fhs5 | binary_panel | 0.960694 | 3.077549 | 6.155098 | 4.077549 | 12.310195 | 6.155098 |
| confirmation | 30 | nch | source | 0.999940 | 1.332361 | 10.129108 | 9.497344 | 87.875866 | 30.550810 |
| confirmation | 30 | nch | binary_panel | 0.986101 | 2.178630 | 4.357260 | 3.178630 | 8.714521 | 4.357260 |
| confirmation | 60 | demand-aware | source | 0.999772 | 1.964268 | 9.465126 | 8.411728 | 46.363585 | 21.609816 |
| confirmation | 60 | demand-aware | binary_panel | 0.962221 | 3.509010 | 7.018020 | 4.509010 | 14.036041 | 7.018020 |
| confirmation | 60 | fhs3 | source | 0.995774 | 2.264936 | 6.659650 | 5.383453 | 19.708633 | 10.397170 |
| confirmation | 60 | fhs3 | binary_panel | 0.972761 | 2.994556 | 5.989111 | 3.994556 | 11.978223 | 5.989111 |
| confirmation | 60 | fhs5 | source | 0.999782 | 1.965998 | 9.473810 | 8.418210 | 46.406693 | 21.629913 |
| confirmation | 60 | fhs5 | binary_panel | 0.962221 | 3.509010 | 7.018020 | 4.509010 | 14.036041 | 7.018020 |
| confirmation | 60 | nch | source | 0.999964 | 1.538016 | 12.980138 | 12.054218 | 133.064916 | 41.618453 |
| confirmation | 60 | nch | binary_panel | 0.983254 | 2.564953 | 5.129907 | 3.564953 | 10.259814 | 5.129907 |
| confirmation | 120 | demand-aware | source | 0.999798 | 2.216312 | 10.730061 | 9.461343 | 52.687616 | 24.549090 |
| confirmation | 120 | demand-aware | binary_panel | 0.963387 | 3.925709 | 7.851418 | 4.925709 | 15.702837 | 7.851418 |
| confirmation | 120 | fhs3 | source | 0.995271 | 2.571866 | 7.576260 | 5.997133 | 22.450105 | 11.845073 |
| confirmation | 120 | fhs3 | binary_panel | 0.971882 | 3.417491 | 6.834981 | 4.417491 | 13.669963 | 6.834981 |
| confirmation | 120 | fhs5 | source | 0.999803 | 2.216688 | 10.732260 | 9.463178 | 52.698537 | 24.554331 |
| confirmation | 120 | fhs5 | binary_panel | 0.963387 | 3.925709 | 7.851418 | 4.925709 | 15.702837 | 7.851418 |
| confirmation | 120 | nch | source | 0.999909 | 1.726093 | 15.948043 | 14.836283 | 193.723015 | 53.952741 |
| confirmation | 120 | nch | binary_panel | 0.982447 | 2.942731 | 5.885461 | 3.942731 | 11.770923 | 5.885461 |
| confirmation | 240 | demand-aware | source | 0.999918 | 2.478775 | 12.025870 | 10.515625 | 59.109145 | 27.538246 |
| confirmation | 240 | demand-aware | binary_panel | 0.962056 | 4.379770 | 8.759540 | 5.379770 | 17.519080 | 8.759540 |
| confirmation | 240 | fhs3 | source | 0.996215 | 2.882923 | 8.504278 | 6.616860 | 25.223850 | 13.309917 |
| confirmation | 240 | fhs3 | binary_panel | 0.970414 | 3.847310 | 7.694621 | 4.847310 | 15.389242 | 7.694621 |
| confirmation | 240 | fhs5 | source | 0.999918 | 2.478779 | 12.025797 | 10.515510 | 59.108481 | 27.537969 |
| confirmation | 240 | fhs5 | binary_panel | 0.962056 | 4.379770 | 8.759540 | 5.379770 | 17.519080 | 8.759540 |
| confirmation | 240 | nch | source | 0.999987 | 1.884407 | 19.781199 | 18.508586 | 319.610669 | 72.392187 |
| confirmation | 240 | nch | binary_panel | 0.982290 | 3.326478 | 6.652956 | 4.326478 | 13.305912 | 6.652956 |

## 全部配对效率差（探索性）

| 相位 | n | 对比 | 成本 | 点估计 | 点对点95%区间 |
|---|---:|---|---|---:|---|
| formal | 30 | demand-aware-minus-matched-binary | traversed_hyperedge_count | -1.383500 | [-1.424048, -1.342744] |
| formal | 30 | demand-aware-minus-matched-binary | signaled_participant_slots | 2.057658 | [1.975839, 2.139884] |
| formal | 30 | demand-aware-minus-matched-binary | unique_signaled_participants | 3.296478 | [3.250794, 3.342965] |
| formal | 30 | demand-aware-minus-matched-binary | quadratic_coordination_exposure | 28.006466 | [27.727250, 28.284657] |
| formal | 30 | demand-aware-minus-matched-binary | arity_log2_exposure | 12.637905 | [12.511258, 12.764648] |
| formal | 30 | fhs3-minus-matched-binary | traversed_hyperedge_count | -0.612754 | [-0.632871, -0.593077] |
| formal | 30 | fhs3-minus-matched-binary | signaled_participant_slots | 0.608805 | [0.567476, 0.649046] |
| formal | 30 | fhs3-minus-matched-binary | unique_signaled_participants | 1.202139 | [1.179409, 1.224130] |
| formal | 30 | fhs3-minus-matched-binary | quadratic_coordination_exposure | 6.720548 | [6.617317, 6.821593] |
| formal | 30 | fhs3-minus-matched-binary | arity_log2_exposure | 3.827817 | [3.773932, 3.880797] |
| formal | 30 | fhs5-minus-matched-binary | traversed_hyperedge_count | -1.377770 | [-1.418836, -1.336421] |
| formal | 30 | fhs5-minus-matched-binary | signaled_participant_slots | 2.079616 | [1.997430, 2.162840] |
| formal | 30 | fhs5-minus-matched-binary | unique_signaled_participants | 3.308709 | [3.263560, 3.354975] |
| formal | 30 | fhs5-minus-matched-binary | quadratic_coordination_exposure | 28.104297 | [27.822642, 28.386389] |
| formal | 30 | fhs5-minus-matched-binary | arity_log2_exposure | 12.683288 | [12.556355, 12.810369] |
| formal | 30 | nch-minus-matched-binary | traversed_hyperedge_count | -0.840139 | [-0.854232, -0.826346] |
| formal | 30 | nch-minus-matched-binary | signaled_participant_slots | 5.830918 | [5.705145, 5.964847] |
| formal | 30 | nch-minus-matched-binary | unique_signaled_participants | 6.363492 | [6.237401, 6.496603] |
| formal | 30 | nch-minus-matched-binary | quadratic_coordination_exposure | 80.767941 | [77.152053, 84.880227] |
| formal | 30 | nch-minus-matched-binary | arity_log2_exposure | 26.472984 | [25.792964, 27.208200] |
| formal | 30 | DA-minus-FHS5 | traversed_hyperedge_count | -0.005730 | [-0.007711, -0.003892] |
| formal | 30 | DA-minus-FHS5 | signaled_participant_slots | -0.021958 | [-0.030982, -0.013481] |
| formal | 30 | DA-minus-FHS5 | unique_signaled_participants | -0.012231 | [-0.020003, -0.004970] |
| formal | 30 | DA-minus-FHS5 | quadratic_coordination_exposure | -0.097831 | [-0.147419, -0.050345] |
| formal | 30 | DA-minus-FHS5 | arity_log2_exposure | -0.045383 | [-0.068005, -0.023996] |
| formal | 60 | demand-aware-minus-matched-binary | traversed_hyperedge_count | -1.552637 | [-1.577214, -1.529049] |
| formal | 60 | demand-aware-minus-matched-binary | signaled_participant_slots | 2.430027 | [2.385554, 2.473834] |
| formal | 60 | demand-aware-minus-matched-binary | unique_signaled_participants | 3.897387 | [3.870722, 3.922708] |
| formal | 60 | demand-aware-minus-matched-binary | quadratic_coordination_exposure | 32.291885 | [32.109819, 32.468192] |
| formal | 60 | demand-aware-minus-matched-binary | arity_log2_exposure | 14.573099 | [14.493167, 14.649833] |
| formal | 60 | fhs3-minus-matched-binary | traversed_hyperedge_count | -0.737499 | [-0.753094, -0.722208] |
| formal | 60 | fhs3-minus-matched-binary | signaled_participant_slots | 0.658801 | [0.625868, 0.691645] |
| formal | 60 | fhs3-minus-matched-binary | unique_signaled_participants | 1.383120 | [1.364922, 1.401456] |
| formal | 60 | fhs3-minus-matched-binary | quadratic_coordination_exposure | 7.719001 | [7.637213, 7.801457] |
| formal | 60 | fhs3-minus-matched-binary | arity_log2_exposure | 4.403379 | [4.360680, 4.446524] |
| formal | 60 | fhs5-minus-matched-binary | traversed_hyperedge_count | -1.550732 | [-1.575862, -1.526525] |
| formal | 60 | fhs5-minus-matched-binary | signaled_participant_slots | 2.441137 | [2.393861, 2.487488] |
| formal | 60 | fhs5-minus-matched-binary | unique_signaled_participants | 3.906194 | [3.877971, 3.933409] |
| formal | 60 | fhs5-minus-matched-binary | quadratic_coordination_exposure | 32.350459 | [32.162875, 32.531287] |
| formal | 60 | fhs5-minus-matched-binary | arity_log2_exposure | 14.600259 | [14.516733, 14.681114] |
| formal | 60 | nch-minus-matched-binary | traversed_hyperedge_count | -1.033028 | [-1.046475, -1.020201] |
| formal | 60 | nch-minus-matched-binary | signaled_participant_slots | 7.904665 | [7.762239, 8.054694] |
| formal | 60 | nch-minus-matched-binary | unique_signaled_participants | 8.550850 | [8.411366, 8.699774] |
| formal | 60 | nch-minus-matched-binary | quadratic_coordination_exposure | 124.886847 | [119.479485, 131.095634] |
| formal | 60 | nch-minus-matched-binary | arity_log2_exposure | 36.802658 | [35.997193, 37.672174] |
| formal | 60 | DA-minus-FHS5 | traversed_hyperedge_count | -0.001905 | [-0.003647, -0.000589] |
| formal | 60 | DA-minus-FHS5 | signaled_participant_slots | -0.011110 | [-0.024265, -0.000688] |
| formal | 60 | DA-minus-FHS5 | unique_signaled_participants | -0.008808 | [-0.019470, -0.000341] |
| formal | 60 | DA-minus-FHS5 | quadratic_coordination_exposure | -0.058574 | [-0.135808, 0.005761] |
| formal | 60 | DA-minus-FHS5 | arity_log2_exposure | -0.027161 | [-0.062526, 0.001986] |
| formal | 120 | demand-aware-minus-matched-binary | traversed_hyperedge_count | -1.684924 | [-1.703623, -1.667297] |
| formal | 120 | demand-aware-minus-matched-binary | signaled_participant_slots | 2.934096 | [2.892761, 2.974002] |
| formal | 120 | demand-aware-minus-matched-binary | unique_signaled_participants | 4.566990 | [4.541501, 4.592559] |
| formal | 120 | demand-aware-minus-matched-binary | quadratic_coordination_exposure | 37.112454 | [36.953396, 37.275837] |
| formal | 120 | demand-aware-minus-matched-binary | arity_log2_exposure | 16.764294 | [16.692431, 16.837787] |
| formal | 120 | fhs3-minus-matched-binary | traversed_hyperedge_count | -0.828464 | [-0.838665, -0.818438] |
| formal | 120 | fhs3-minus-matched-binary | signaled_participant_slots | 0.772356 | [0.749173, 0.794857] |
| formal | 120 | fhs3-minus-matched-binary | unique_signaled_participants | 1.593483 | [1.579287, 1.607601] |
| formal | 120 | fhs3-minus-matched-binary | quadratic_coordination_exposure | 8.832564 | [8.768279, 8.897312] |
| formal | 120 | fhs3-minus-matched-binary | arity_log2_exposure | 5.035476 | [5.001456, 5.069803] |
| formal | 120 | fhs5-minus-matched-binary | traversed_hyperedge_count | -1.685546 | [-1.704295, -1.667905] |
| formal | 120 | fhs5-minus-matched-binary | signaled_participant_slots | 2.930180 | [2.889385, 2.969675] |
| formal | 120 | fhs5-minus-matched-binary | unique_signaled_participants | 4.563796 | [4.539346, 4.588560] |
| formal | 120 | fhs5-minus-matched-binary | quadratic_coordination_exposure | 37.089712 | [36.936820, 37.246458] |
| formal | 120 | fhs5-minus-matched-binary | arity_log2_exposure | 16.754157 | [16.685188, 16.825095] |
| formal | 120 | nch-minus-matched-binary | traversed_hyperedge_count | -1.221262 | [-1.229440, -1.212910] |
| formal | 120 | nch-minus-matched-binary | signaled_participant_slots | 10.335022 | [10.028553, 10.651398] |
| formal | 120 | nch-minus-matched-binary | unique_signaled_participants | 11.156558 | [10.859405, 11.464526] |
| formal | 120 | nch-minus-matched-binary | quadratic_coordination_exposure | 198.049053 | [182.091569, 215.527310] |
| formal | 120 | nch-minus-matched-binary | arity_log2_exposure | 49.812769 | [47.939475, 51.774643] |
| formal | 120 | DA-minus-FHS5 | traversed_hyperedge_count | 0.000622 | [-0.000605, 0.002206] |
| formal | 120 | DA-minus-FHS5 | signaled_participant_slots | 0.003916 | [-0.004415, 0.013991] |
| formal | 120 | DA-minus-FHS5 | unique_signaled_participants | 0.003193 | [-0.003934, 0.011579] |
| formal | 120 | DA-minus-FHS5 | quadratic_coordination_exposure | 0.022742 | [-0.026177, 0.078661] |
| formal | 120 | DA-minus-FHS5 | arity_log2_exposure | 0.010138 | [-0.012332, 0.035903] |
| formal | 240 | demand-aware-minus-matched-binary | traversed_hyperedge_count | -1.886741 | [-1.901121, -1.873193] |
| formal | 240 | demand-aware-minus-matched-binary | signaled_participant_slots | 3.293649 | [3.261676, 3.324356] |
| formal | 240 | demand-aware-minus-matched-binary | unique_signaled_participants | 5.148833 | [5.128489, 5.168825] |
| formal | 240 | demand-aware-minus-matched-binary | quadratic_coordination_exposure | 41.654989 | [41.530253, 41.779716] |
| formal | 240 | demand-aware-minus-matched-binary | arity_log2_exposure | 18.806883 | [18.750470, 18.863310] |
| formal | 240 | fhs3-minus-matched-binary | traversed_hyperedge_count | -0.964669 | [-0.975733, -0.953389] |
| formal | 240 | fhs3-minus-matched-binary | signaled_participant_slots | 0.803250 | [0.778785, 0.828869] |
| formal | 240 | fhs3-minus-matched-binary | unique_signaled_participants | 1.763635 | [1.749739, 1.778424] |
| formal | 240 | fhs3-minus-matched-binary | quadratic_coordination_exposure | 9.804265 | [9.743576, 9.869098] |
| formal | 240 | fhs3-minus-matched-binary | arity_log2_exposure | 5.598635 | [5.567274, 5.632436] |
| formal | 240 | fhs5-minus-matched-binary | traversed_hyperedge_count | -1.886717 | [-1.901108, -1.873176] |
| formal | 240 | fhs5-minus-matched-binary | signaled_participant_slots | 3.293745 | [3.261716, 3.324468] |
| formal | 240 | fhs5-minus-matched-binary | unique_signaled_participants | 5.148928 | [5.128560, 5.168967] |
| formal | 240 | fhs5-minus-matched-binary | quadratic_coordination_exposure | 41.655445 | [41.530355, 41.780299] |
| formal | 240 | fhs5-minus-matched-binary | arity_log2_exposure | 18.807091 | [18.750571, 18.863661] |
| formal | 240 | nch-minus-matched-binary | traversed_hyperedge_count | -1.450750 | [-1.459835, -1.441643] |
| formal | 240 | nch-minus-matched-binary | signaled_participant_slots | 13.189221 | [12.924677, 13.479662] |
| formal | 240 | nch-minus-matched-binary | unique_signaled_participants | 14.245437 | [13.992318, 14.521840] |
| formal | 240 | nch-minus-matched-binary | quadratic_coordination_exposure | 316.345839 | [298.962294, 335.934574] |
| formal | 240 | nch-minus-matched-binary | arity_log2_exposure | 66.439299 | [64.763446, 68.295097] |
| formal | 240 | DA-minus-FHS5 | traversed_hyperedge_count | -0.000024 | [-0.000072, 0.000000] |
| formal | 240 | DA-minus-FHS5 | signaled_participant_slots | -0.000097 | [-0.000290, 0.000000] |
| formal | 240 | DA-minus-FHS5 | unique_signaled_participants | -0.000095 | [-0.000285, 0.000000] |
| formal | 240 | DA-minus-FHS5 | quadratic_coordination_exposure | -0.000456 | [-0.001367, 0.000000] |
| formal | 240 | DA-minus-FHS5 | arity_log2_exposure | -0.000208 | [-0.000625, 0.000000] |
| confirmation | 30 | demand-aware-minus-matched-binary | traversed_hyperedge_count | -1.357076 | [-1.414165, -1.303069] |
| confirmation | 30 | demand-aware-minus-matched-binary | signaled_participant_slots | 2.105311 | [1.983332, 2.220160] |
| confirmation | 30 | demand-aware-minus-matched-binary | unique_signaled_participants | 3.312481 | [3.249143, 3.371479] |
| confirmation | 30 | demand-aware-minus-matched-binary | quadratic_coordination_exposure | 28.059928 | [27.692766, 28.415766] |
| confirmation | 30 | demand-aware-minus-matched-binary | arity_log2_exposure | 12.670676 | [12.498923, 12.836937] |
| confirmation | 30 | fhs3-minus-matched-binary | traversed_hyperedge_count | -0.614820 | [-0.637224, -0.592540] |
| confirmation | 30 | fhs3-minus-matched-binary | signaled_participant_slots | 0.604677 | [0.557974, 0.652488] |
| confirmation | 30 | fhs3-minus-matched-binary | unique_signaled_participants | 1.198887 | [1.173412, 1.225560] |
| confirmation | 30 | fhs3-minus-matched-binary | quadratic_coordination_exposure | 6.712302 | [6.601776, 6.829318] |
| confirmation | 30 | fhs3-minus-matched-binary | arity_log2_exposure | 3.823695 | [3.766203, 3.884420] |
| confirmation | 30 | fhs5-minus-matched-binary | traversed_hyperedge_count | -1.348097 | [-1.405901, -1.293931] |
| confirmation | 30 | fhs5-minus-matched-binary | signaled_participant_slots | 2.140049 | [2.015053, 2.257486] |
| confirmation | 30 | fhs5-minus-matched-binary | unique_signaled_participants | 3.335858 | [3.270222, 3.396561] |
| confirmation | 30 | fhs5-minus-matched-binary | quadratic_coordination_exposure | 28.208235 | [27.822526, 28.574436] |
| confirmation | 30 | fhs5-minus-matched-binary | arity_log2_exposure | 12.741310 | [12.560894, 12.912698] |
| confirmation | 30 | nch-minus-matched-binary | traversed_hyperedge_count | -0.846269 | [-0.862161, -0.830675] |
| confirmation | 30 | nch-minus-matched-binary | signaled_participant_slots | 5.771848 | [5.638657, 5.917015] |
| confirmation | 30 | nch-minus-matched-binary | unique_signaled_participants | 6.318714 | [6.180540, 6.469963] |
| confirmation | 30 | nch-minus-matched-binary | quadratic_coordination_exposure | 79.161345 | [75.143296, 84.131013] |
| confirmation | 30 | nch-minus-matched-binary | arity_log2_exposure | 26.193549 | [25.451084, 27.030611] |
| confirmation | 30 | DA-minus-FHS5 | traversed_hyperedge_count | -0.008979 | [-0.012943, -0.005295] |
| confirmation | 30 | DA-minus-FHS5 | signaled_participant_slots | -0.034738 | [-0.052907, -0.017430] |
| confirmation | 30 | DA-minus-FHS5 | unique_signaled_participants | -0.023376 | [-0.038127, -0.009166] |
| confirmation | 30 | DA-minus-FHS5 | quadratic_coordination_exposure | -0.148307 | [-0.237168, -0.062596] |
| confirmation | 30 | DA-minus-FHS5 | arity_log2_exposure | -0.070634 | [-0.112225, -0.030462] |
| confirmation | 60 | demand-aware-minus-matched-binary | traversed_hyperedge_count | -1.544743 | [-1.570761, -1.519685] |
| confirmation | 60 | demand-aware-minus-matched-binary | signaled_participant_slots | 2.447106 | [2.392119, 2.501919] |
| confirmation | 60 | demand-aware-minus-matched-binary | unique_signaled_participants | 3.902717 | [3.868101, 3.936562] |
| confirmation | 60 | demand-aware-minus-matched-binary | quadratic_coordination_exposure | 32.327544 | [32.099753, 32.556770] |
| confirmation | 60 | demand-aware-minus-matched-binary | arity_log2_exposure | 14.591796 | [14.488610, 14.695447] |
| confirmation | 60 | fhs3-minus-matched-binary | traversed_hyperedge_count | -0.729620 | [-0.745733, -0.715030] |
| confirmation | 60 | fhs3-minus-matched-binary | signaled_participant_slots | 0.670538 | [0.639918, 0.698630] |
| confirmation | 60 | fhs3-minus-matched-binary | unique_signaled_participants | 1.388897 | [1.372887, 1.403890] |
| confirmation | 60 | fhs3-minus-matched-binary | quadratic_coordination_exposure | 7.730410 | [7.661976, 7.796048] |
| confirmation | 60 | fhs3-minus-matched-binary | arity_log2_exposure | 4.408059 | [4.372714, 4.442322] |
| confirmation | 60 | fhs5-minus-matched-binary | traversed_hyperedge_count | -1.543012 | [-1.569051, -1.517810] |
| confirmation | 60 | fhs5-minus-matched-binary | signaled_participant_slots | 2.455790 | [2.400058, 2.511650] |
| confirmation | 60 | fhs5-minus-matched-binary | unique_signaled_participants | 3.909199 | [3.874534, 3.943302] |
| confirmation | 60 | fhs5-minus-matched-binary | quadratic_coordination_exposure | 32.370652 | [32.142293, 32.603824] |
| confirmation | 60 | fhs5-minus-matched-binary | arity_log2_exposure | 14.611893 | [14.508759, 14.717257] |
| confirmation | 60 | nch-minus-matched-binary | traversed_hyperedge_count | -1.026938 | [-1.038351, -1.015759] |
| confirmation | 60 | nch-minus-matched-binary | signaled_participant_slots | 7.850231 | [7.720633, 7.983042] |
| confirmation | 60 | nch-minus-matched-binary | unique_signaled_participants | 8.489265 | [8.365657, 8.617167] |
| confirmation | 60 | nch-minus-matched-binary | quadratic_coordination_exposure | 122.805103 | [118.040051, 128.051155] |
| confirmation | 60 | nch-minus-matched-binary | arity_log2_exposure | 36.488546 | [35.767295, 37.245238] |
| confirmation | 60 | DA-minus-FHS5 | traversed_hyperedge_count | -0.001730 | [-0.002899, -0.000675] |
| confirmation | 60 | DA-minus-FHS5 | signaled_participant_slots | -0.008684 | [-0.017083, -0.001509] |
| confirmation | 60 | DA-minus-FHS5 | unique_signaled_participants | -0.006482 | [-0.013299, -0.000699] |
| confirmation | 60 | DA-minus-FHS5 | quadratic_coordination_exposure | -0.043108 | [-0.094409, 0.000658] |
| confirmation | 60 | DA-minus-FHS5 | arity_log2_exposure | -0.020097 | [-0.043245, -0.000246] |
| confirmation | 120 | demand-aware-minus-matched-binary | traversed_hyperedge_count | -1.709397 | [-1.730996, -1.687832] |
| confirmation | 120 | demand-aware-minus-matched-binary | signaled_participant_slots | 2.878643 | [2.832581, 2.924356] |
| confirmation | 120 | demand-aware-minus-matched-binary | unique_signaled_participants | 4.535634 | [4.508718, 4.562812] |
| confirmation | 120 | demand-aware-minus-matched-binary | quadratic_coordination_exposure | 36.984779 | [36.832672, 37.140556] |
| confirmation | 120 | demand-aware-minus-matched-binary | arity_log2_exposure | 16.697672 | [16.628126, 16.769111] |
| confirmation | 120 | fhs3-minus-matched-binary | traversed_hyperedge_count | -0.845625 | [-0.857651, -0.833952] |
| confirmation | 120 | fhs3-minus-matched-binary | signaled_participant_slots | 0.741279 | [0.715785, 0.767278] |
| confirmation | 120 | fhs3-minus-matched-binary | unique_signaled_participants | 1.579642 | [1.565101, 1.594715] |
| confirmation | 120 | fhs3-minus-matched-binary | quadratic_coordination_exposure | 8.780142 | [8.715553, 8.847656] |
| confirmation | 120 | fhs3-minus-matched-binary | arity_log2_exposure | 5.010092 | [4.976185, 5.045532] |
| confirmation | 120 | fhs5-minus-matched-binary | traversed_hyperedge_count | -1.709021 | [-1.730592, -1.687455] |
| confirmation | 120 | fhs5-minus-matched-binary | signaled_participant_slots | 2.880842 | [2.834665, 2.926447] |
| confirmation | 120 | fhs5-minus-matched-binary | unique_signaled_participants | 4.537469 | [4.510762, 4.564503] |
| confirmation | 120 | fhs5-minus-matched-binary | quadratic_coordination_exposure | 36.995700 | [36.844256, 37.150965] |
| confirmation | 120 | fhs5-minus-matched-binary | arity_log2_exposure | 16.702913 | [16.633833, 16.774314] |
| confirmation | 120 | nch-minus-matched-binary | traversed_hyperedge_count | -1.216638 | [-1.225145, -1.208181] |
| confirmation | 120 | nch-minus-matched-binary | signaled_participant_slots | 10.062581 | [9.864617, 10.268580] |
| confirmation | 120 | nch-minus-matched-binary | unique_signaled_participants | 10.893552 | [10.702104, 11.094287] |
| confirmation | 120 | nch-minus-matched-binary | quadratic_coordination_exposure | 181.952093 | [172.855843, 191.491268] |
| confirmation | 120 | nch-minus-matched-binary | arity_log2_exposure | 48.067280 | [46.896018, 49.291703] |
| confirmation | 120 | DA-minus-FHS5 | traversed_hyperedge_count | -0.000376 | [-0.001244, 0.000315] |
| confirmation | 120 | DA-minus-FHS5 | signaled_participant_slots | -0.002199 | [-0.008001, 0.002805] |
| confirmation | 120 | DA-minus-FHS5 | unique_signaled_participants | -0.001835 | [-0.006670, 0.002480] |
| confirmation | 120 | DA-minus-FHS5 | quadratic_coordination_exposure | -0.010921 | [-0.042749, 0.017938] |
| confirmation | 120 | DA-minus-FHS5 | arity_log2_exposure | -0.005241 | [-0.019989, 0.007918] |
| confirmation | 240 | demand-aware-minus-matched-binary | traversed_hyperedge_count | -1.900995 | [-1.916210, -1.886383] |
| confirmation | 240 | demand-aware-minus-matched-binary | signaled_participant_slots | 3.266330 | [3.232110, 3.299238] |
| confirmation | 240 | demand-aware-minus-matched-binary | unique_signaled_participants | 5.135855 | [5.114579, 5.156732] |
| confirmation | 240 | demand-aware-minus-matched-binary | quadratic_coordination_exposure | 41.590065 | [41.464109, 41.717827] |
| confirmation | 240 | demand-aware-minus-matched-binary | arity_log2_exposure | 18.778706 | [18.721044, 18.837198] |
| confirmation | 240 | fhs3-minus-matched-binary | traversed_hyperedge_count | -0.964387 | [-0.978807, -0.951603] |
| confirmation | 240 | fhs3-minus-matched-binary | signaled_participant_slots | 0.809657 | [0.779547, 0.836767] |
| confirmation | 240 | fhs3-minus-matched-binary | unique_signaled_participants | 1.769550 | [1.753239, 1.784694] |
| confirmation | 240 | fhs3-minus-matched-binary | quadratic_coordination_exposure | 9.834608 | [9.765352, 9.899821] |
| confirmation | 240 | fhs3-minus-matched-binary | arity_log2_exposure | 5.615296 | [5.579548, 5.649164] |
| confirmation | 240 | fhs5-minus-matched-binary | traversed_hyperedge_count | -1.900991 | [-1.916205, -1.886383] |
| confirmation | 240 | fhs5-minus-matched-binary | signaled_participant_slots | 3.266257 | [3.232001, 3.299200] |
| confirmation | 240 | fhs5-minus-matched-binary | unique_signaled_participants | 5.135740 | [5.114459, 5.156638] |
| confirmation | 240 | fhs5-minus-matched-binary | quadratic_coordination_exposure | 41.589401 | [41.463624, 41.717411] |
| confirmation | 240 | fhs5-minus-matched-binary | arity_log2_exposure | 18.778429 | [18.720709, 18.837049] |
| confirmation | 240 | nch-minus-matched-binary | traversed_hyperedge_count | -1.442071 | [-1.451667, -1.433281] |
| confirmation | 240 | nch-minus-matched-binary | signaled_participant_slots | 13.128243 | [12.864604, 13.417570] |
| confirmation | 240 | nch-minus-matched-binary | unique_signaled_participants | 14.182108 | [13.925285, 14.463547] |
| confirmation | 240 | nch-minus-matched-binary | quadratic_coordination_exposure | 306.304758 | [288.952907, 325.631092] |
| confirmation | 240 | nch-minus-matched-binary | arity_log2_exposure | 65.739231 | [64.047978, 67.596375] |
| confirmation | 240 | DA-minus-FHS5 | traversed_hyperedge_count | -0.000004 | [-0.000012, 0.000000] |
| confirmation | 240 | DA-minus-FHS5 | signaled_participant_slots | 0.000074 | [0.000000, 0.000221] |
| confirmation | 240 | DA-minus-FHS5 | unique_signaled_participants | 0.000115 | [0.000000, 0.000345] |
| confirmation | 240 | DA-minus-FHS5 | quadratic_coordination_exposure | 0.000664 | [0.000000, 0.001992] |
| confirmation | 240 | DA-minus-FHS5 | arity_log2_exposure | 0.000277 | [0.000000, 0.000830] |

## 图注

图S3a 服务量与参与者信令成本。八个子图分别对应两个相位和四个规模。横坐标为父图/模型等权成功率；纵坐标为平均信令槽总数除以平均成功请求数。颜色与形状共同对应方案：DA三角、FHS3圆、FHS5方形、NCH菱形；实心为源方案，空心为其自身资源匹配二元参照，连线仅标识配对。DA与FHS5的实际坐标近乎重合，使用不同形状及大小保留可见性，不移动数据点。纵向线为20000次模型分层父图bootstrap的点对点未校正95%百分位区间；横坐标不显示区间，本图不构成联合置信区域。每个点60独立父图，父图内7轨迹为嵌套测量。全部方案、规模及相位保留。

图S3b 配对单位成功成本差。三个面板分别显示遍历、参与者信令槽和平方协调暴露。差值为源方案比值减其二元面板比值，负值为较小模型暴露。颜色为方案，实心圆/空心方形分别为正式/确认相位；横线为点对点未校正95%百分位区间，零参考线仅表示比值相等。低暴露不能独立推出可靠性、延迟或真实部署费用优势。全部32个配对点在每个面板保留。

## 验证、复用与限制

保留全部480个父图提取断点与320个bootstrap断点，共160000次父图重抽样。整数成本和服务的点估计用精确有理数保存；log₂敏感性暴露以及区间采用float64。抽样索引由固定复制编号及模型层种子决定；所有成本和方案共用索引。区间取第500及19500个有序复制值，无插值。

verification.json记录另一套路线算术和索引求和实现对全部区块、复制和520个比值/配对区间的复核。它是同一分析者的数值交叉检查，不是独立盲审、不验证路由最优性，也不构成新实验。

输出目录创建PAUSE文件可在区块/500复制块完成后安全暂停；恢复前明确移除暂停标记。代码、配置、运行时、证据指纹改变会拒绝静默续算。提取断点已经保存绝对服务、成本、arity histogram、配对指纹与原始字节哈希，可复用而无需重新执行长期模拟。

S4较短时域敏感性尚未执行；S5新增初始化模拟仍需单独授权。

## 零服务审查

全部64个相位×规模×源方案×角色单元中，零服务轨迹面板计数之和为0，零服务父图面板计数之和为0。这些计数涉及共享二元参照和重复角色，不能视为独立样本数。320个绝对比值的未定义bootstrap计数之和为0。逐单元计数见results.json，任何未定义情况均不作零成本替代。
