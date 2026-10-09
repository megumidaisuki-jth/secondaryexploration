"""Author-readable complete combined-scope S5 tables; verified inference only."""
from fractions import Fraction
import json
from tools.supplement_initialization_common import ROOT,sha,atomic,save
from tools.seal_supplement_initialization_analysis import OUT,validate

LABELS={'DA-U-minus-FHS5-U':'ΔU：DA-U − FHS5-U','DA-O-minus-FHS5-O':'ΔO：DA-O − FHS5-O',
        'interaction-O-minus-U':'交互：ΔO − ΔU','DA-O-minus-DA-U':'DA：O − U','FHS5-O-minus-FHS5-U':'FHS5：O − U'}

def number(pair,risk=False):
    value=Fraction(*pair)*(100 if risk else 1)
    return format(float(value),'+.3f' if risk else '+.6f')

def main():
    proof=validate()
    result_path=OUT/'results.json'; raw=result_path.read_bytes(); data=json.loads(raw)
    comparisons=data['comparisons']; means=data['arm_means']
    assert len(comparisons)==240 and len(means)==192
    within=[r for r in comparisons if r['scope']=='combined' and r['metric']=='normalized_restricted_tau_nopath'
            and r['comparison'] in ['DA-O-minus-DA-U','FHS5-O-minus-FHS5-U']]
    assert len(within)==16
    negative=sum(Fraction(*r['exact']['estimate'])<0 for r in within)
    positive=sum(Fraction(*r['exact']['estimate'])>0 for r in within)
    body=['# S5 四臂配对统计：已核验结果与解释边界','',
          '状态：完整模拟、公共票据重放、四臂重抽样和单独算术核验均通过。该报告不等于新增盲科学审查。','',
          '## 首先需要注意的实测现象','',
          f'16个分阶段/规模/拓扑条件的O−U归一化时间差点估计中，{negative}个为负，{positive}个为正。即本数据中原优化初态并不普遍优于均匀初态；必须同时报告这些方向，不能只呈现原优化拓扑差ΔO。16个条件对比不是16个新增独立样本，此方向计数也不是统计检验。','',
          '上述观察不能外推为所有拓扑或所有需求下优化均有害，也不能仅凭点态区间做全家族结论。动态首次无路径时间与原优化训练目标是否一致，应在后续讨论中据原目标定义解释，不以本结果凭空推断机制。','',
          '## 研究问题与设计','',
          'DA-U、FHS5-U分别使用各自冻结拓扑及均匀初态；DA-O、FHS5-O复用原优化初态及原受审计终点。四臂在同一父图、同一请求轨迹、同一请求级路由票据下配对。两阶段各240父图；每阶段/规模60父图，三模型各20，7条轨迹先在父图内汇总。执行去重后的4228单元不是独立样本量。','',
          '每个节点总资金固定为120；均匀分配按节点关联度及规范超边编号分配整除余数。超边总资金可能随分配改变，因此不能宣称固定超边资金的纯拓扑因果效应。没有新增训练、测试种子或优化臂模拟。','',
          '## 终点、方向与推导关系','',
          '- Y = min(首次无可用路径请求索引, H) / H，H = 12n；更大表示首次无路径更晚或未在窗口内观测到，不等于无界期望寿命。',
          '- F = 1{窗口内出现首次无路径}；更小表示窗口内失败风险较低。事件恰好发生于H与窗口内无事件的Y相同，但F不同。首次耗竭及首次拒绝不能代替本终点。',
          '- ΔU = DA-U − FHS5-U；ΔO = DA-O − FHS5-O；交互 = ΔO − ΔU = (DA-O − DA-U) − (FHS5-O − FHS5-U)。',
          '- 对Y，正拓扑差有利于DA；对F，负拓扑差有利于DA。交互描述拓扑对比随初始化变化的幅度，不用“一个显著另一个不显著”判断交互。','',
          '## 统计口径（可用于后续方法撰写）','',
          'Python 3.12.14。每阶段/规模对三个模型分别进行20000次整父图有放回重抽样；每模型抽20图，四臂及两终点完全共用索引。轨迹等权、模型均值等权。以固定种子2026100705及SHA-256派生副本/模型种子保存整数四臂总和；所有点估计与区间端点保留精确有理数。','',
          '80个combined比较区间采用逆经验分布第500与19500顺序统计量，点态95%、未作多重比较校正。不报告p值或全家族覆盖；160个同分布/偏移范围估计仅作描述，不给区间。退化经验区间不能证明总体等效。两阶段标签沿用原数据，本补充属事后分析，不宣称新增预注册盲确认。','',
          '## 完整combined四臂均值','',
          'Y无量纲；F为概率（0—1）。所有同分布/偏移均值及精确分数保存在results.json。','',
          '| 阶段 | 节点数 | 终点 | DA-U | FHS5-U | DA-O | FHS5-O |',
          '|---|---:|---|---:|---:|---:|---:|']
    for phase in ['formal','confirmation']:
        for n in [30,60,120,240]:
            for metric in ['normalized_restricted_tau_nopath','failure_risk']:
                values=[]
                for arm in ['DA-U','FHS5-U','DA-O','FHS5-O']:
                    row=next(r for r in means if (r['phase'],r['node_count'],r['scope'],r['metric'],r['arm'])==(phase,n,'combined',metric,arm))
                    values.append(format(float(Fraction(*row['estimate'])),'.6f'))
                body.append(f"| {phase} | {n} | {'Y' if metric.startswith('normalized') else 'F'} | "+' | '.join(values)+' |')
    for metric,title,risk in [('normalized_restricted_tau_nopath','Y对比（归一化时间差）',False),('failure_risk','F对比（百分点差）',True)]:
        body.extend(['',f'## {title}','',
                     '以下为全部40个combined比较；区间均为点态、未校正。风险数值乘100换算成百分点，不是相对风险百分比。' if risk else '以下为全部40个combined比较；区间均为点态、未校正。',
                     '', '| 阶段 | 节点数 | 对比 | 点估计 | 95%区间下界 | 上界 |', '|---|---:|---|---:|---:|---:|'])
        for row in comparisons:
            if row['scope']!='combined' or row['metric']!=metric: continue
            exact=row['exact']; body.append(f"| {row['phase']} | {row['node_count']} | {LABELS[row['comparison']]} | "+' | '.join(number(exact[k],risk) for k in ['estimate','lower','upper'])+' |')
    body.extend(['','## 保存内容与复核','',
                 '- parents.json.gz：480父图的四臂整数汇总；traces.json.gz：3360轨迹的四臂事件、公共票据来源映射及直接对比。',
                 '- checkpoints/：320个500副本断点，保留全部160000次共享索引重抽样四臂整数总和；arithmetic-checkpoints/：逐段单独算术核验收据。',
                 '- results.json：240对比行、192四臂均值；80完整combined区间、160范围描述估计及精确有理数。',
                 '- verification.json：源事件重建、全部副本/区间检查；16个原S1优化拓扑点估计逐项精确复现。',
                 '- 原模拟数据、请求/路径/状态见证仍在initialization-ablation-v1，无需为论文作图重新生成长模拟。','',
                 f"统计结果文件SHA-256：{sha(raw)}。核验副本：{proof['bootstrap_replicates_verified']}。",'',
                 '后续步骤：据已核验源表作图、逐图注明设计及作用，再更新正文与补充材料。此报告没有自动改写原论文结论。',''])
    atomic(OUT/'report.md','\n'.join(body).encode('utf8'))
    save(OUT/'report-binding.json',{'results_sha256':sha(raw),'verification_sha256':sha((OUT/'verification.json').read_bytes()),
         'reporter_sha256':sha((ROOT/'tools/report_supplement_initialization_analysis.py').read_bytes()),'report_sha256':sha((OUT/'report.md').read_bytes()),
         'full_combined_contrasts':80,'full_combined_arm_means':64,'subscope_estimates_preserved_in_source':160})
    print('Verified author report saved; no simulation or manuscript modification.')

if __name__=='__main__': main()
