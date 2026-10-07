"""S4 CSV/Chinese report and Python-only editable scientific figure bundle."""
import csv
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/supplement/short-window-posthoc-v1'
CFG=ROOT/'configs/supplement/short-window-posthoc-v1.json'
matplotlib.rcParams.update({'font.family':'Arial','font.size':6.5,'axes.titlesize':7.5,'axes.labelsize':6.5,
    'xtick.labelsize':6.5,'ytick.labelsize':6.5,'legend.fontsize':6.5,'svg.fonttype':'none','pdf.fonttype':42,
    'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':0.6,'lines.linewidth':0.8})

def write_csv(path,rows):
    buf=io.StringIO(newline=''); w=csv.DictWriter(buf,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    path.write_text(buf.getvalue(),encoding='utf-8',newline='')

def flatten(r):
    p={k:r[k] for k in ['phase','node_count','window','scope','comparison','metric','independent_parents']}
    p['horizon']=r.get('horizon',''); p['interval_type']='pointwise-unadjusted-95-percent' if 'lower' in r['exact'] else 'descriptive-only'
    for name in ['estimate','lower','upper']:
        f=r['exact'].get(name)
        p[name]=repr(r['display'][name]) if f else ''; p[name+'_numerator']=f[0] if f else ''; p[name+'_denominator']=f[1] if f else ''
    return p

def source_tables(result,cfg):
    write_csv(OUT/'window-contrasts.csv',[flatten(r) for r in result['contrasts']])
    write_csv(OUT/'paired-window-changes.csv',[flatten(r) for r in result['window_changes']])
    parent_rows=[]; events=[]; absolute={}; timing={}; paired_info={}
    for path in sorted((OUT/'parents').glob('*.json')):
        p=json.loads(path.read_bytes())['payload']; n=p['node_count']; H=12*n
        totals=np.asarray(p['integer_sums'],dtype=np.int64)
        for w,window in enumerate(cfg['windows']):
            h=cfg['requests_per_node'][window]*n
            for si,(scope,count) in enumerate(zip(cfg['scopes'],cfg['traces_per_scope'])):
                for c,comp in enumerate(cfg['comparisons']):
                    for m,metric in enumerate(cfg['metrics']):
                        value=Fraction(int(totals[w,si,c,m]),2*count*(h if m==0 else 1))
                        parent_rows.append({'phase':p['phase'],'parent_graph_id':p['parent_graph_id'],'node_count':n,'parent_model':p['parent_model'],
                            'parent_replicate':p['parent_replicate'],'window':window,'scope':scope,'comparison':comp,'metric':metric,
                            'numerator':value.numerator,'denominator':value.denominator,'value':repr(float(value))})
        for tr in p['events']:
            ev={v['variant_id']:(v['observed'],v['request_index']) for v in tr['variants']}
            for window in cfg['windows']:
                h=cfg['requests_per_node'][window]*n; da,fh=ev['demand-aware'],ev['fhs5']
                da_f=int(da[0] and da[1]<=h); fh_f=int(fh[0] and fh[1]<=h)
                z=paired_info.setdefault((p['phase'],n,window),[0,0,0,0,0])
                for j,value in enumerate([1,int(not da_f and not fh_f),int(bool(da_f or fh_f)),int(min(da[1],h)!=min(fh[1],h)),int(da_f!=fh_f)]): z[j]+=value
            for v in tr['variants']:
                flag,t=v['observed'],v['request_index']
                events.append({'phase':p['phase'],'parent_graph_id':p['parent_graph_id'],'node_count':n,'parent_model':p['parent_model'],
                    'parent_replicate':p['parent_replicate'],'regime_id':tr['regime_id'],'scope':tr['scope'],'paired_manifest_fingerprint':tr['paired_manifest_fingerprint'],
                    'variant_id':v['variant_id'],'family':v['family'],'original_horizon':H,'saved_observed':int(flag),'saved_request_index':t,
                    'half_horizon':6*n,'half_restricted_time':min(t,6*n),'half_observed':int(flag and t<=6*n),
                    'full_restricted_time':t,'full_observed':int(flag),'raw_sha256':p['raw_sha256']})
            for family in cfg['families']:
                for role,ids in [('source',[family]),('binary_panel',p['panels'][family])]:
                    for vid in ids:
                        flag,t=ev[vid]
                        category='original-administrative-censor' if not flag else ('before-half' if t<6*n else 'at-half' if t==6*n else 'after-half-through-full')
                        key=p['phase'],n,family,role,category
                        timing[key]=timing.get(key,Fraction(0))+Fraction(1,len(ids))
            for window in cfg['windows']:
                h=cfg['requests_per_node'][window]*n
                for scope,count in [('combined',7),(tr['scope'],4 if tr['scope']=='same_distribution' else 3)]:
                    for family in cfg['families']:
                        for role,ids in [('source',[family]),('binary_panel',p['panels'][family])]:
                            key=p['phase'],n,window,scope,family,role
                            avg_t=sum(Fraction(min(ev[v][1],h),h) for v in ids)/len(ids)
                            avg_r=sum(Fraction(int(ev[v][0] and ev[v][1]<=h)) for v in ids)/len(ids)
                            # Equal trace count and 60 balanced parents; fractional counts for two-arm panels.
                            z=absolute.setdefault(key,[Fraction(0),Fraction(0),Fraction(0)])
                            z[0]+=avg_t/(60*count); z[1]+=avg_r/(60*count); z[2]+=avg_r
    write_csv(OUT/'parent-window-contrasts.csv',parent_rows)
    write_csv(OUT/'saved-event-observations.csv',events)
    abs_rows=[]
    for key,z in sorted(absolute.items()):
        r=dict(zip(['phase','node_count','window','scope','family','role'],key))
        for label,f in zip(['normalized_restricted_time','failure_risk','panel_weighted_event_count'],z):
            r[label]=repr(float(f)); r[label+'_numerator']=f.numerator; r[label+'_denominator']=f.denominator
        r['interval_type']='descriptive-only'; abs_rows.append(r)
    write_csv(OUT/'absolute-window-means.csv',abs_rows)
    timing_rows=[]
    for phase in ['formal','confirmation']:
        for n in [30,60,120,240]:
            for family in cfg['families']:
                for role in ['source','binary_panel']:
                    total=Fraction(0)
                    for cat in ['before-half','at-half','after-half-through-full','original-administrative-censor']:
                        value=timing.get((phase,n,family,role,cat),Fraction(0)); total+=value
                        timing_rows.append({'phase':phase,'node_count':n,'family':family,'role':role,'category':cat,
                            'weighted_trace_count_numerator':value.numerator,'weighted_trace_count_denominator':value.denominator,
                            'weighted_trace_count':repr(float(value)),'weighted_trace_fraction':repr(float(value/420))})
                    assert total==420
    write_csv(OUT/'event-timing-summary.csv',timing_rows)
    info_rows=[]
    for key,val in sorted(paired_info.items()):
        assert val[0]==420 and val[1]+val[2]==420
        r=dict(zip(['phase','node_count','window'],key)); r.update(zip(['trace_pairs','both_no_event_within_window','at_least_one_observed_event','nonzero_time_difference_pairs','nonzero_risk_difference_pairs'],val))
        info_rows.append(r)
    write_csv(OUT/'DA-FHS5-paired-information.csv',info_rows)
    assert len(parent_rows)==28800
    return abs_rows,len(events)

def plot_data(path):
    with path.open(encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f))
    for r in rows:
        for name in ['estimate','lower','upper']:
            if r[name]: assert float(r[name])==float(Fraction(int(r[name+'_numerator']),int(r[name+'_denominator'])))
    return {(r['phase'],int(r['node_count']),r['window'],r['comparison'],r['metric']):r for r in rows if r['scope']=='combined'}

def export(fig,name):
    fig.savefig(OUT/f'{name}.svg')
    fig.savefig(OUT/f'{name}.pdf')
    fig.savefig(OUT/f'{name}.tiff',dpi=600,pil_kwargs={'compression':'tiff_lzw'})
    fig.savefig(OUT/f'{name}.png',dpi=300)
    plt.close(fig)

COLORS={'half':'#D55E00','full':'#0072B2'}
def points(ax,lookup,comp,metric,changes=False):
    handles=[]
    windows=['half-minus-full'] if changes else ['half','full']
    for wi,w in enumerate(windows):
        for pi,phase in enumerate(['formal','confirmation']):
            offset=(pi-0.5)*0.12 if changes else (2*wi+pi-1.5)*0.10
            records=[lookup[phase,n,w,comp,metric] for n in [30,60,120,240]]
            y=np.asarray([float(r['estimate'])*100 for r in records]); lo=np.asarray([float(r['lower'])*100 for r in records]); hi=np.asarray([float(r['upper'])*100 for r in records])
            assert np.all(lo<=y) and np.all(y<=hi)
            ax.errorbar(np.arange(4)+offset,y,yerr=np.vstack([y-lo,hi-y]),fmt='o' if pi==0 else '^',
                color='#333333' if changes else COLORS[w],markersize=3.0,capsize=1.7,linestyle='none',elinewidth=0.7,
                markerfacecolor='white' if pi else ('#333333' if changes else COLORS[w]),markeredgewidth=0.7)
            handles.append(Line2D([],[],color='#333333' if changes else COLORS[w],marker='o' if pi==0 else '^',linestyle='none',
                markersize=3.5,markerfacecolor='white' if pi else ('#333333' if changes else COLORS[w]),label=f'{phase.title()}, '+('half - full' if changes else ('6n' if wi==0 else '12n'))))
    ax.axhline(0,color='#777777',linewidth=0.5,zorder=0); ax.set_xticks(range(4),['30','60','120','240']); ax.set_xlim(-0.4,3.4)
    ax.set_xlabel('Nodes n'); ax.grid(axis='y',alpha=0.15,linewidth=0.4)
    return handles

def figures():
    contrast=plot_data(OUT/'window-contrasts.csv'); change=plot_data(OUT/'paired-window-changes.csv')
    metrics=['normalized_restricted_tau_nopath','failure_risk']; names=['DA','FHS3','FHS5','NCH']
    fig_width_mm=170
    fig,axes=plt.subplots(4,2,figsize=(fig_width_mm/25.4,190/25.4))
    fig.subplots_adjust(left=.11,right=.975,bottom=.08,top=.92,hspace=.72,wspace=.40)
    for row,family in enumerate(['demand-aware','fhs3','fhs5','nch']):
        for col,metric in enumerate(metrics):
            ax=axes[row,col]; handles=points(ax,contrast,f'{family}-minus-matched-binary',metric)
            ax.set_title(f'{names[row]} - own binary panel',loc='left')
            ax.set_ylabel('Restricted-time effect (% of window)' if col==0 else 'Failure-risk effect (percentage points)')
            ax.text(-.22,1.10,chr(97+row*2+col),transform=ax.transAxes,fontweight='bold',fontsize=8)
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.54,.995),ncol=2,frameon=False)
    fig.text(.5,.012,'Means; pointwise unadjusted 95% bootstrap intervals. n = 60 parents per phase and size.',ha='center',fontsize=6.5)
    export(fig,'S4-matched-binary-window-effects')
    fig,axes=plt.subplots(2,2,figsize=(fig_width_mm/25.4,115/25.4))
    fig.subplots_adjust(left=.12,right=.975,bottom=.12,top=.85,hspace=.66,wspace=.42)
    for row in range(2):
        for col,metric in enumerate(metrics):
            ax=axes[row,col]; handles=points(ax,change if row else contrast,'DA-minus-FHS5',metric,changes=bool(row))
            ax.set_title('Paired half - full change' if row else 'DA - FHS5 effect',loc='left')
            ax.set_ylabel('Time effect / change (%)' if col==0 else 'Risk effect / change (pp)')
            ax.text(-.23,1.12,chr(97+row*2+col),transform=ax.transAxes,fontweight='bold',fontsize=8)
            if row==0: legend=handles
    fig.legend(handles=legend,loc='upper center',bbox_to_anchor=(.55,.995),ncol=2,frameon=False)
    fig.text(.5,.018,'Same resampled parents for both windows; zero differences and intervals retained.',ha='center',fontsize=6.5)
    export(fig,'S4-DA-FHS5-window-effects-and-changes')

def report(result,absolute,event_count):
    combined=[r for r in result['contrasts'] if r['scope']=='combined']
    matched=[r for r in combined if r['comparison']!='DA-minus-FHS5']
    positive=sum(r['display']['estimate']>0 for r in matched if r['metric']=='normalized_restricted_tau_nopath')
    negative=sum(r['display']['estimate']<0 for r in matched if r['metric']=='failure_risk')
    matched_changes=[r for r in result['window_changes'] if r['scope']=='combined' and r['comparison']!='DA-minus-FHS5']
    smaller_time=sum(r['display']['estimate']<0 for r in matched_changes if r['metric']=='normalized_restricted_tau_nopath')
    closer_risk=sum(r['display']['estimate']>0 for r in matched_changes if r['metric']=='failure_risk')
    zero_da=sum(r['display']['estimate']==0 for r in combined if r['window']=='half' and r['comparison']=='DA-minus-FHS5' and r['metric']=='normalized_restricted_tau_nopath')
    lines=['# S4 较短观测窗口敏感性分析','',
      '本轮用保存的绝对事件时间把原观测窗口 H=12n 缩短为 h=6n，回答“相同拓扑与测试轨迹上的首次无可用路径效应，是否依赖观察多久”。这是事后探索性敏感性分析，不是追加独立确认实验。未重跑支付模拟，未改路由、初始化、参数或父图。','',
      '## 推导与统计口径','',
      '设保存事件标记为 δ、保存的限制时间为 T=min(τ,H)。若 δ=0，则 T=H；h≤H 时，T_h=min(T,h)，δ_h=δ·1{T≤h}，Y_h=T_h/h。事件恰好发生在 h 时 δ_h=1、Y_h=1；与 h 内始终无事件的 Y_h=1、δ_h=0 区分。','',
      '离散时间恒等式 E[min(τ,h)]=Σ_{j=0}^{h−1}P(τ>j) 把限制时间均值与限制生存曲线面积相连。这里所有轨迹在共同 H 处行政删失，保存事件足以恢复 h≤H 的限制终点，无须估计未观察到的尾部。它不是未删失寿命，也不是寿命中位数。','',
      '沿用理论—实验路由分层：本轮重分析的终点是实验层首次无可用路径τ_nopath，并未更改理论层首次触0的扩散与停止时间假设。窗口敏感性结果不是上述理论证明在状态依赖路由下成立的证据；两个事件定义不能互换。','',
      '对源方案 A 与其注册二元面板 B，先在同一轨迹上分别截断每个方案，再对 B 的一臂/两臂等权平均：D_Y(h)=Y_A(h)−mean_B Y_B(h)，D_F(h)=δ_A(h)−mean_B δ_B(h)。DA−FHS5 为直接配对差。不能截断原差值：例如 T_A=8、T_B=6、h=5，原时间差为2，而正确新时间差为0。','',
      '每个父图先对7条测试轨迹等权平均；同分布4条和分布漂移3条另给描述性结果。每阶段每规模有60个独立父图，三模型各20个；模型层内与层间等权。两阶段各240图、总480图；不是把3360条轨迹当独立样本，也不把参考臂或两个窗口当新增重复。','',
      '每阶段/规模进行20,000次分层父图bootstrap，每次在各模型内有放回抽20父图。同一抽样索引同时用于两个窗口、全部对照、范围与终点。给出160个全轨迹窗口效应区间、80个配对窗口变化区间。其余320个范围效应和160个范围变化只给均值。区间为未校正点态95%，最近秩为第500与19500个复制值；无p值、无新增确认门槛、无同时置信带。','',
      '窗口变化定义 C_Y=D_Y(6n)−D_Y(12n)，C_F=D_F(6n)−D_F(12n)。若整数账本 N_h 是2倍配对限制时间和，则 C_Y=(2N_half−N_full)/(2×60×轨迹数×12n)；风险变化用 N_half−N_full。时间效应改变了截断位置和归一化分母，不能称为单纯把原效应减半。','',
      '## 结果（完整数值见CSV）','',
      f'在四家族×两阶段×四规模×两个窗口的64个源方案—自身二元面板单元中，限制时间均值差有{positive}/64为正，事件风险均值差有{negative}/64为负。这里按均值符号计数，不是同时显著性判定。','',
      f'逐个配对比较窗口：32个源—二元面板单元中有{smaller_time}/32的短窗口归一化时间效应更小，{closer_risk}/32的风险效应向零收缩；因此应表述为“这两个窗口内均值方向保持，但幅度依赖窗口”，不能声称效应幅度不受窗口影响。','',
      f'DA−FHS5在短窗口的8个阶段/规模时间单元中，有{zero_da}/8个精确均值为零。原全窗口的微小增量不能直接迁移到短窗口；零值需结合下方绝对事件比例解释。','',
      '归一化限制时间差的正值表示该窗口内较晚遇到首次无可用路径；风险差的负值表示该窗口内至少一次出现该事件的比例较低。风险差不是拒付请求比例，首次事件也不表示后续支付全部停止。','',
      '### DA−FHS5：时间与风险窗口效应及配对变化','',
      '下表为均值[点态95%区间]，时间统一乘100按对应窗口百分数表示，风险统一乘100按百分点表示；各表行不是独立窗口重复。','',
      '| 阶段 | n | 终点 | 6n | 12n | 配对半−全变化 |','|---|---:|---|---:|---:|---:|']
    def show(r):
        d=r['display']; return f"{100*d['estimate']:.6f} [{100*d['lower']:.6f}, {100*d['upper']:.6f}]"
    for phase in ['formal','confirmation']:
        for n in [30,60,120,240]:
            for metric in ['normalized_restricted_tau_nopath','failure_risk']:
                rows=[next(r for r in combined if (r['phase'],r['node_count'],r['window'],r['comparison'],r['metric'])==(phase,n,w,'DA-minus-FHS5',metric)) for w in ['half','full']]
                c=next(r for r in result['window_changes'] if (r['phase'],r['node_count'],r['scope'],r['comparison'],r['metric'])==(phase,n,'combined','DA-minus-FHS5',metric))
                lines.append(f"| {phase} | {n} | {'时间' if metric.startswith('normalized') else '风险'} | {show(rows[0])} | {show(rows[1])} | {show(c)} |")
    lines+=['','### 绝对事件比例：DA及其自身二元面板（描述性）','',
      '| 阶段 | n | 角色 | 6n事件比例 | 12n事件比例 |','|---|---:|---|---:|---:|']
    for phase in ['formal','confirmation']:
        for n in [30,60,120,240]:
            for role in ['source','binary_panel']:
                rs=[next(r for r in absolute if (r['phase'],r['node_count'],r['window'],r['scope'],r['family'],r['role'])==(phase,n,w,'combined','demand-aware',role)) for w in ['half','full']]
                lines.append(f"| {phase} | {n} | {role} | {100*float(rs[0]['failure_risk']):.4f}% | {100*float(rs[1]['failure_risk']):.4f}% |")
    lines+=['','## 图表的作用与实验基础','',
      '图1（S4-matched-binary-window-effects）把四家族相对自身注册二元面板的两个终点完整呈现。颜色区分6n/12n，圆形/三角区分formal/confirmation；用于检验效应方向与幅度的窗口依赖，不用于事后选择最好看的窗口。','',
      '图2（S4-DA-FHS5-window-effects-and-changes）分离“超图相对二元图”与“需求感知相对固定五元超图”的问题，并把配对变化放在下排，避免把两个窗口区间相减当作变化区间。窄区间或零区间保留原值；不能据此证明总体等效。','',
      '图2上排颜色对应窗口，下排黑色点表示直接配对半−全变化，仍用实心圆/空心三角区分阶段。不同终点和行各自适配纵轴，不能仅看图形高度跨面板比较效应大小。','',
      '两图共用三个生成模型BA、ER、固定计数SBM及30/60/120/240节点；具体拓扑、初始化、资源匹配、测试需求及其种子均沿用冻结原实验。保存的逐图/逐轨迹面板映射、原事件时间和指纹见parents与事件CSV，可追踪回原始区块。无新增训练/测试分割或超参数选择。','',
      '### 小增量的可辨识性检查','',
      '下面并列DA与FHS5源方案的绝对事件比例。若短窗口中两者都没有观察到首次无可用路径，则二者的限制时间都位于Y=1上界；零差可能来自窗口内事件信息不足，不能据此证明长期寿命相同。event-timing-summary.csv保留窗口前、恰在窗口边界、窗口后至原H、原行政删失的分层计数，避免混淆时间上界与事件标记。','',
      '| 阶段 | n | 源方案 | 6n事件比例 | 12n事件比例 |','|---|---:|---|---:|---:|']
    for phase in ['formal','confirmation']:
        for n in [30,60,120,240]:
            for family in ['demand-aware','fhs5']:
                rs=[next(r for r in absolute if (r['phase'],r['node_count'],r['window'],r['scope'],r['family'],r['role'])==(phase,n,w,'combined',family,'source')) for w in ['half','full']]
                lines.append(f"| {phase} | {n} | {family} | {100*float(rs[0]['failure_risk']):.4f}% | {100*float(rs[1]['failure_risk']):.4f}% |")
    with (OUT/'DA-FHS5-paired-information.csv').open(encoding='utf-8',newline='') as f: info=list(csv.DictReader(f))
    lines+=['','短窗口逐轨迹配对信息如下。每行420对是60父图×7轨迹的测量次数，不是420个独立重复。','',
        '| 阶段 | n | 双方窗口内无事件 | 至少一方有事件 | 时间配对差非零 | 风险配对差非零 |','|---|---:|---:|---:|---:|---:|']
    for r in info:
        if r['window']=='half':
            lines.append('| '+' | '.join(r[k] for k in ['phase','node_count','both_no_event_within_window','at_least_one_observed_event','nonzero_time_difference_pairs','nonzero_risk_difference_pairs'])+' |')
    lines+=['','这里短窗口并非完全没有失败事件：少数共同事件与大量共同删失同时存在。某些DA−FHS5零效应来自逐轨迹窗口终点完全相同，而非宣称两方案从未失败或总体分布等效。', '']
    lines+=['',
      '## 可用于论文的结论边界','',
      '可以报告这两个观察窗口内的限制时间与事件风险效应，并把短窗口作为对原H=12n结果的补充。是否方向保持、幅度变化应逐对照看表，不可把某个区间不跨零概括为所有拓扑和时域上的总体优越性。DA−FHS5小差值应与主结构效应区分，不扩大成需求感知普适优势。','',
      '不能新增宣称：真实网络延迟/费用、更长寿命、尾部分位数、任意窗口稳健性、前缀服务成本稳健性或不等初始余额稳健性。本轮未计算前缀成本，不能将S3全窗口成本按1/2缩放后引用。共同360请求窗口及S5非均匀初始化仍未执行。','',
      '## 复核与断点','',
      f'保存{event_count}条逐变体/轨迹事件观测、28,800条父图窗口效应、480条汇总效应、240条窗口变化和384条绝对窗口均值宽表（每条含时间、风险两个均值，共768个终点均值）。原窗口DA−FHS5精确均值已核对S1，全部源—二元图原窗口轨迹差已核对原phase evidence。','',
      '独立于主程序的另一实现按离散生存面积恒等式重算事件终点，并以直接索引累加重放全部160,000次bootstrap，对整数与有理数逐项一致性检查。它是同一分析者的单独实现算术核验，不是新增科学盲审。','',
      '实际在4个新事件区块后安全暂停，恢复时保留原4个文件的SHA-256与字节数。每父图一个原子事件信封，每500次重抽样一个压缩整数断点；源码/配置/运行时/输入哈希绑定。PAUSE文件只在安全边界生效，恢复前确认无活跃锁，再移除该控制文件并运行同一版本。不得改绑定后静默接续。','',
      '交付清单记录所有数据、检查收据、源码、配置、图表与源数据的字节数和SHA-256。上传Git后再检查Git blob字节与远端提交一致；不能仅以push命令成功当作科学核验。','']
    (OUT/'report.md').write_text('\n'.join(lines),encoding='utf-8')

def main():
    cfg=json.loads(CFG.read_bytes()); result=json.loads((OUT/'results.json').read_bytes())
    proof=json.loads((OUT/'verification.json').read_bytes())
    assert proof['status']=='passed' and proof['binding']['results_sha256']==hashlib.sha256((OUT/'results.json').read_bytes()).hexdigest()
    assert proof['binding']['config_sha256']==hashlib.sha256(CFG.read_bytes()).hexdigest()
    absolute,event_count=source_tables(result,cfg); assert len(absolute)==384
    figures(); report(result,absolute,event_count)
    validator=Path('C:/Users/jiate/.codex/skills/nature-figure/scripts/validate_figure.py')
    check=subprocess.run([sys.executable,str(validator),str(Path(__file__).resolve()),'--json'],capture_output=True,check=True)
    (OUT/'figure-source-preflight.json').write_bytes(check.stdout)
    tests=subprocess.run([sys.executable,'-m','unittest','tests.test_supplement_short_window','-v'],cwd=ROOT,capture_output=True,check=True)
    (OUT/'unit-tests.txt').write_bytes(tests.stdout+tests.stderr)
    (OUT/'report-runtime.json').write_text(json.dumps({'python':sys.version,'numpy':np.__version__,'matplotlib':matplotlib.__version__,
        'backend':'python-matplotlib-Agg','report_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'results_sha256':hashlib.sha256((OUT/'results.json').read_bytes()).hexdigest(),'new_simulations':0},indent=2)+'\n',encoding='utf-8')
    (OUT/'README.md').write_text('''# S4：6n与12n窗口敏感性

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

复现（本机冻结运行时）：运行 tools/supplement_short_window.py，再运行 tools/verify_supplement_short_window.py、tools/report_supplement_short_window.py；检查最终PNG并记录figure-qa.md，然后运行 tools/qa_supplement_short_window.py、tools/seal_supplement_short_window.py。PYTHONPATH需包含E:\\second-doc-runtime及E:\\second，源码/配置必须与binding.json一致。

安全暂停：在本目录创建空PAUSE文件，等待progress或verification-progress为paused-safe-checkpoint且运行锁消失。恢复需先确认进程已退出，再移除PAUSE；不要删除活跃锁或编辑已绑定文件。提取与bootstrap断点可复用，校验bootstrap每阶段/规模一个校验收据，最多重检一个规模的20,000个复制值。

S5仍需新增模拟，本轮未启动。
''',encoding='utf-8')
    print(json.dumps({'state':'reported-pending-visual-QA','event_observations':event_count,'parent_contrasts':28800,'absolute_rows':384}),flush=True)

if __name__=='__main__': main()
