# 补充说明：13 项描述指标的精确定义

本说明对应修正后的中文双栏稿第 4.4 节与第 5.4 节，记录既有冻结实现，
不引入新指标、重算、显著性检验或新实验。正式与确认相位仍分开报告。

## 记号与共同口径

沿用正文：节点数为 $n$，参与关系数为 $L$，超边成员数为 $|e|$，
超边资金为 $C_e>0$，观测时域为 $H$，请求接受指示为 $A_t$。
节点对覆盖重数为 $m_{uv}$。记
$U=\{\{u,v\}:u<v,m_{uv}>0\}$，选中路径长度为 $\ell_t$，
$N_t$ 为同时满足最短路和最优瓶颈条件的路径数量；无路径时二者取 0。
瓶颈评分 $b_t=b(P_t,q_t)$ 按正文式（6）定义，无路径时在累计量中贡献 0。
当前核心协议中，有可行选中路径即接受请求。

这里的“每次尝试”一律以 $H$ 为分母，包括失败请求；首次事件后仍执行到 $H$。
信令人数在**每次请求内部**取成员并集，再跨请求累加，不是整个实验的去重人数。
“独立参与者”仅表示去重成员，不表示统计独立样本。

## 定义与源数据字段

| 序号 | 名称／源数据字段 | 精确定义 |
|---|---|---|
| 1 | 节点对覆盖比例 `topology_pair_coverage_fraction` | $\lvert U\rvert/\binom n2$ |
| 2 | 已覆盖节点对的平均重数 `topology_mean_pair_multiplicity_covered` | $\sum_{\{u,v\}\in U}m_{uv}/\lvert U\rvert$ |
| 3 | 初始坐标失衡 `initial_coordinate_imbalance` | $B(x(0))$ |
| 4 | 终态坐标失衡 `final_coordinate_imbalance` | $B(x(H))$ |
| 5 | 终态零坐标比例 `final_zero_coordinate_fraction` | $L^{-1}\sum_{e\in\mathcal E}\sum_{v\in e}\mathbf1\{x_{e,v}(H)=0\}$ |
| 6 | 最优路径重数累计量／尝试 `optimal_route_multiplicity_mass_per_attempt` | $H^{-1}\sum_{t=1}^H N_t$ |
| 7 | 多最优路径请求比例／尝试 `multiple_optimal_route_fraction_per_attempt` | $H^{-1}\sum_{t=1}^H\mathbf1\{N_t>1\}$ |
| 8 | 瓶颈余额累计量／尝试 `route_bottleneck_mass_per_attempt` | $H^{-1}\sum_{t:A_t=1} b_t$ |
| 9 | 跳数累计量／尝试 `route_hop_mass_per_attempt` | $H^{-1}\sum_{t:A_t=1}\ell_t$ |
| 10 | 经过超边数／尝试 `traversed_hyperedge_count_per_attempt` | $H^{-1}\sum_{t:A_t=1}\lvert\{e:e\in P_t\}\rvert$；当前简单路径下等于第 9 项 |
| 11 | 信令参与槽位／尝试 `signaled_participant_slots_per_attempt` | $H^{-1}\sum_{t:A_t=1}\sum_{e\in P_t}\lvert e\rvert$ |
| 12 | 二次协调暴露量／尝试 `quadratic_coordination_exposure_per_attempt` | $Q=H^{-1}\sum_{t:A_t=1}\sum_{e\in P_t}\lvert e\rvert^2$ |
| 13 | 去重信令参与人数／尝试 `unique_signaled_participants_per_attempt` | $H^{-1}\sum_{t:A_t=1}\lvert\bigcup_{e\in P_t}e\rvert$ |

其中

$$B(x)=\frac1L\sum_{e\in\mathcal E}\sum_{v\in e}\left|\frac{x_{e,v}}{C_e}-\frac1{|e|}\right|.$$

静态指标 1—3 每父图变体只取一次，不按 7 条轨迹增加独立样本量；
动态指标按 4 条同分布与 3 条分布偏移轨迹形成 4:3 父图汇总。
源构造分别减去其二元参照均值，随后按父图模型等权汇总。
所有 13 项均为描述性投影，没有新增置信区间或 p 值。

## 必须保留的解释边界

1. $B$ 同时依赖余额和超边规模。单个 $k$ 元超边的资金全部集中于一名成员时，
   $B=2(k-1)/k^2$；例如 $k=2$ 时为 0.5，$k=5$ 时为 0.32。
   因此跨规模的较小值不能单独证明更均衡，不应解释为已识别的性能机制。
2. $Q$ 采用 $|e|^2$，不是训练目标 $O$ 中的 $\binom{|e|}{2}$；两者不可互换。
3. 跳数和经过超边数在当前路径定义下重复记录同一量，不能当作两项独立支持证据。
4. 较低瓶颈累计量可能与接受比例或选中路径的余额有关，不必然表示流动性更好或成本更低。
5. 信令量是协议暴露计数，不是实测消息数、签名数、通信时延、手续费或货币成本；
   按尝试归一也不等于按成功支付归一。

## 实现定位

- `tools/formal_descriptive_projection.py`：`_metric_registry`、`_state_metrics`、
  `_simulation_metrics`、`_project_block`。
- `secondaryexploration/metrics/cost.py`：`RunCostMetrics`。
- 目标函数归一化分母见正文第 3.2 节及 `secondaryexploration/optimization/demand.py`。

这些实现文件没有在本次文稿修正中改动。原始扩展 Word/Markdown 是历史母稿，
尚未同步本次修正，后续写作应以本目录的 `main.tex` 及本说明为准。
