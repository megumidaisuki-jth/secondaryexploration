"""S3 tables and scientific figures from verified saved results only."""
import csv
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/supplement/service-cost-posthoc-v1'
FAMILIES=['demand-aware','fhs3','fhs5','nch']
LABELS=['DA','FHS3','FHS5','NCH']
COLORS=['#3A6EA5','#B07D3C','#7C669B','#5C8D78']
MARKERS={'demand-aware':'^','fhs3':'o','fhs5':'s','nch':'D'}
mpl.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],
                     'font.size':6,'axes.labelsize':6,'xtick.labelsize':5.5,'ytick.labelsize':5.5,
                     'legend.fontsize':5.5,'svg.fonttype':'none','pdf.fonttype':42,
                     'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.6,'legend.frameon':False})

def save_csv(name,rows):
    f=io.StringIO(newline=''); w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    (OUT/name).write_text(f.getvalue(),encoding='utf-8',newline='')

def export(fig,name):
    fig.savefig(OUT/f'{name}.svg')
    fig.savefig(OUT/f'{name}.pdf')
    fig.savefig(OUT/f'{name}.tiff',dpi=600,pil_kwargs={'compression':'tiff_lzw'})
    fig.savefig(OUT/f'{name}.png',dpi=300)
    plt.close(fig)

def fmt(v): return 'undefined' if v is None else f'{v:.6f}'

def run():
    raw=(OUT/'results.json').read_bytes(); verification=json.loads((OUT/'verification.json').read_bytes())
    assert verification['status']=='passed' and verification['results_sha256']==hashlib.sha256(raw).hexdigest()
    result=json.loads(raw); arms=result['arms']; contrasts=result['contrasts']
    validator=Path('C:/Users/jiate/.codex/skills/nature-figure/scripts/validate_figure.py')
    checked=subprocess.run([sys.executable,str(validator),str(Path(__file__)), '--json'],capture_output=True,text=True,check=True)
    preflight=json.loads(checked.stdout); assert preflight['summary']['counts']['FAIL']==0
    (OUT/'figure-preflight.json').write_text(json.dumps(preflight,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
    flat=[]
    for r in arms:
        row={k:r[k] for k in ('phase','node_count','family','role','independent_parents','zero_service_trace_panels','trace_panels','zero_service_parents')}
        for name,val in r['mean_per_attempt'].items(): row[name+'_per_attempt']=val
        for cost in r['cost_per_accepted_request']:
            prefix=cost['cost']; row[prefix+'_per_success']=cost['estimate']
            ci=cost['pointwise_95_interval']; row[prefix+'_lower']=None if ci is None else ci[0]; row[prefix+'_upper']=None if ci is None else ci[1]
            row[prefix+'_exact']=None if cost['exact_estimate'] is None else str(Fraction(*cost['exact_estimate']))
        flat.append(row)
    save_csv('figure-s3-arms.csv',flat)
    crows=[]
    for r in contrasts:
        ci=r['pointwise_95_interval']
        crows.append({k:r[k] for k in ('phase','node_count','comparison','cost','estimate','undefined_bootstrap_draws')}|
                     {'lower':None if ci is None else ci[0],'upper':None if ci is None else ci[1],
                      'exact_estimate':None if r['exact_estimate'] is None else str(Fraction(*r['exact_estimate']))})
    save_csv('figure-s3-contrasts.csv',crows)
    parents=[]
    for file in sorted((OUT/'parents').glob('*.json')):
        p=json.loads(file.read_bytes())
        for family in FAMILIES:
            for role in ('source','binary_panel'):
                ids=[family] if role=='source' else p['panels'][family]
                totals=[Fraction(0) for _ in range(6)]; logtotal=0.0; zeros=0
                for t in p['traces']:
                    data={a['variant_id']:a for a in t['arms']}
                    success=Fraction(0)
                    for vid in ids:
                        for col,value in enumerate(data[vid]['values']): totals[col]+=Fraction(value,len(ids))
                        success+=Fraction(data[vid]['values'][0],len(ids)); logtotal+=data[vid]['arity_log2_exposure']/len(ids)
                    zeros+=success==0
                parents.append({'phase':p['phase'],'node_count':p['node_count'],'parent_model':p['parent_model'],'parent_replicate':p['parent_replicate'],
                                'parent_graph_id':p['parent_graph_id'],'family':family,'role':role,'zero_trace_panels':zeros,
                                'mean_accepted_requests':str(totals[0]/7),'mean_accepted_value':str(totals[1]/7),
                                'mean_traversals':str(totals[2]/7),'mean_participant_slots':str(totals[3]/7),
                                'mean_unique_participants':str(totals[4]/7),'mean_quadratic_exposure':str(totals[5]/7),
                                'mean_arity_log2_exposure':logtotal/7,'raw_sha256':p['raw_sha256']})
    save_csv('parent-source-data.csv',parents)
    lookup={(r['phase'],r['node_count'],r['family'],r['role']):r for r in arms}
    width_mm=170; fig,axes=plt.subplots(2,4,figsize=(width_mm/25.4,112/25.4),squeeze=False)
    global_min=min(r['mean_per_attempt']['accepted_request_count']*100 for r in arms)
    xmin=max(0,global_min-2); xmax=100.7
    for row,phase in enumerate(('formal','confirmation')):
        for col,n in enumerate((30,60,120,240)):
            ax=axes[row,col]
            for family,label,color in zip(FAMILIES,LABELS,COLORS):
                data=[lookup[phase,n,family,role] for role in ('source','binary_panel')]
                xy=[]
                for role,r in zip(('source','binary_panel'),data):
                    y=next(c for c in r['cost_per_accepted_request'] if c['cost']=='signaled_participant_slots')
                    x=r['mean_per_attempt']['accepted_request_count']*100; xy.append((x,y['estimate']))
                    ci=y['pointwise_95_interval']; error=None if ci is None else np.array([[y['estimate']-ci[0]],[ci[1]-y['estimate']]])
                    # A percentile interval can exclude its point estimate; draw endpoints directly.
                    if ci is not None: ax.vlines(x,ci[0],ci[1],color=color,linewidth=.6,alpha=.65)
                    ax.plot(x,y['estimate'],MARKERS[family],ms=5.2 if family=='demand-aware' else 3.4,
                            mfc=color if role=='source' else 'white',mec=color,mew=.7,
                            label=label+(' source' if role=='source' else ' binary') if row==0 and col==0 else None)
                ax.plot([v[0] for v in xy],[v[1] for v in xy],color=color,lw=.5,alpha=.5,zorder=0)
            ax.set_xlim(xmin,xmax); ax.set_title(f'{phase.capitalize()}, n={n}',fontsize=6.5)
            ax.set_xlabel('Successful attempts (%)'); ax.set_ylabel('Participant slots / success' if col==0 else '')
            ax.text(-.13,1.1,'abcdefgh'[row*4+col],transform=ax.transAxes,weight='bold',fontsize=8)
            ax.grid(axis='y',color='#E6E6E6',lw=.4)
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',ncol=4,bbox_to_anchor=(.5,.01),columnspacing=1)
    fig.subplots_adjust(left=.085,right=.985,top=.9,bottom=.2,wspace=.35,hspace=.65)
    export(fig,'figure-s3-service-cost')

    fig,axes=plt.subplots(1,3,figsize=(width_mm/25.4,120/25.4),sharey=True)
    costs=['traversed_hyperedge_count','signaled_participant_slots','quadratic_coordination_exposure']
    titles=['Traversals / success','Participant slots / success','Quadratic exposure / success']
    labels=[f'n={n}  {label}' for n in (30,60,120,240) for label in LABELS]
    for col,(ax,cost,title) in enumerate(zip(axes,costs,titles)):
        ax.axvline(0,color='#777777',ls='--',lw=.6)
        for k,(n,family) in enumerate((n,f) for n in (30,60,120,240) for f in FAMILIES):
            for phase,offset,marker in (('formal',-.14,'o'),('confirmation',.14,'s')):
                r=next(r for r in contrasts if r['phase']==phase and r['node_count']==n and r['cost']==cost and r['comparison']==f'{family}-minus-matched-binary')
                y=15-k+offset; ci=r['pointwise_95_interval']; color=COLORS[k%4]
                if ci is not None: ax.hlines(y,*ci,color=color,lw=.9)
                ax.plot(r['estimate'],y,marker,ms=3,mfc=color if phase=='formal' else 'white',mec=color,mew=.6)
        ax.set_title(title,fontsize=6.5); ax.set_xlabel('Source minus matched binary'); ax.set_ylim(-.6,15.6)
        ax.set_yticks(range(16),list(reversed(labels))); ax.tick_params(axis='y',length=0)
        ax.text(-.06,1.08,'abc'[col],transform=ax.transAxes,weight='bold',fontsize=8)
    fig.text(.55,.025,'Filled circles: Formal   Open squares: Confirmation\nPointwise 95% intervals; no simultaneous superiority decision',ha='center',fontsize=6)
    fig.subplots_adjust(left=.2,right=.98,top=.91,bottom=.16,wspace=.2)
    export(fig,'figure-s3-paired-cost')

    md=['# S3 服务量—成本联合分析','',
        '本分析复用480个已存档父图区块，按保存路线重算服务与暴露成本。未新增支付模拟。结果为后验探索性描述，区间为点对点未校正95%区间，不能按某个区间是否跨零作同时优越性或新的确认性结论。','',
        '## 统计量及作用','',
        '- 成功率 S/H 描述支付服务完成程度；成功支付总额 V/H 以实验金额单位报告，不能直接换算货币收益。',
        '- 首次无可用路径是首个失败事件，并不意味着之后所有请求均停止；S和C统计整个固定时域H内的保存请求。这一补充回答累计服务与成本问题，与S1的首次事件时间问题互补。',
        '- 总暴露 C/H 描述每次尝试的平均路线暴露；它同时受成功数与路线结构影响。',
        '- 单位成功服务成本定义为 E[C]/E[S]。七条轨迹先在父图内等权汇总，三模型各20父图等权。它不是 E[C/S]，也不是单位成功金额成本。',
        '- 配对效率差为 E[C_A]/E[S_A]−E[C_B]/E[S_B]，每次bootstrap同时抽取同一父图的服务与成本，随后重新求两组比值和差。不是 E[(C_A−C_B)/(S_A−S_B)]。',
        '- 二元参照在对应资源面板内先等权平均；一个父图的多个二元臂不增加独立样本量。',
        '- 成本依次为超边遍历次数、Σ|e|参与者信令槽、逐成功路线的去重参与者数之和、Σ|e|²协调暴露，以及Σ|e|log₂|e|敏感性暴露。单位均为模型计数/暴露代理，不能声称测量了真实字节、延迟或密码学费用。','',
        r'设 a 为方案，g 为父图模型层，b 为该层父图，r 为留出轨迹。则 $\bar S_a=\frac{1}{3}\sum_{g=1}^{3}\frac{1}{20}\sum_{b=1}^{20}\frac{1}{7}\sum_{r=1}^{7}S_{a,g,b,r}$，$\bar C_a$ 按相同权重定义；单位成功成本 $R_a=\bar C_a/\bar S_a$。如果 a 是资源匹配二元参照，还需在每条轨迹上先对注册二元臂等权平均。','',
        r'每次bootstrap在每个模型层内有放回抽取20个父图，得到共同索引后的 $\bar C_a^*$ 与 $\bar S_a^*$，再计算 $R_a^*=\bar C_a^*/\bar S_a^*$。配对差复制值为 $D_{a,b}^*=R_a^*-R_b^*$。这保持服务量与成本的相关性；不能把二者分别抽样后拼接比值区间。','',
        '## 成功服务和单位成功成本','',
        '| 相位 | n | 方案 | 角色 | 成功率 | 遍历/成功 | 信令槽/成功 | 去重参与者/成功 | 平方暴露/成功 | log₂暴露/成功 |',
        '|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in arms:
        ratios=[c['estimate'] for c in r['cost_per_accepted_request']]
        md.append(f"| {r['phase']} | {r['node_count']} | {r['family']} | {r['role']} | {r['mean_per_attempt']['accepted_request_count']:.6f} | "+' | '.join(fmt(v) for v in ratios)+' |')
    md+=['','## 全部配对效率差（探索性）','','| 相位 | n | 对比 | 成本 | 点估计 | 点对点95%区间 |','|---|---:|---|---|---:|---|']
    for r in contrasts:
        ci=r['pointwise_95_interval']; text='undefined' if ci is None else f'[{ci[0]:.6f}, {ci[1]:.6f}]'
        md.append(f"| {r['phase']} | {r['node_count']} | {r['comparison']} | {r['cost']} | {fmt(r['estimate'])} | {text} |")
    md+=['','## 图注','',
         '图S3a 服务量与参与者信令成本。八个子图分别对应两个相位和四个规模。横坐标为父图/模型等权成功率；纵坐标为平均信令槽总数除以平均成功请求数。颜色与形状共同对应方案：DA三角、FHS3圆、FHS5方形、NCH菱形；实心为源方案，空心为其自身资源匹配二元参照，连线仅标识配对。DA与FHS5的实际坐标近乎重合，使用不同形状及大小保留可见性，不移动数据点。纵向线为20000次模型分层父图bootstrap的点对点未校正95%百分位区间；横坐标不显示区间，本图不构成联合置信区域。每个点60独立父图，父图内7轨迹为嵌套测量。全部方案、规模及相位保留。',
         '', '图S3b 配对单位成功成本差。三个面板分别显示遍历、参与者信令槽和平方协调暴露。差值为源方案比值减其二元面板比值，负值为较小模型暴露。颜色为方案，实心圆/空心方形分别为正式/确认相位；横线为点对点未校正95%百分位区间，零参考线仅表示比值相等。低暴露不能独立推出可靠性、延迟或真实部署费用优势。全部32个配对点在每个面板保留。','',
         '## 验证、复用与限制','',
         '保留全部480个父图提取断点与320个bootstrap断点，共160000次父图重抽样。整数成本和服务的点估计用精确有理数保存；log₂敏感性暴露以及区间采用float64。抽样索引由固定复制编号及模型层种子决定；所有成本和方案共用索引。区间取第500及19500个有序复制值，无插值。',
         '', 'verification.json记录另一套路线算术和索引求和实现对全部区块、复制和520个比值/配对区间的复核。它是同一分析者的数值交叉检查，不是独立盲审、不验证路由最优性，也不构成新实验。',
         '', '输出目录创建PAUSE文件可在区块/500复制块完成后安全暂停；恢复前明确移除暂停标记。代码、配置、运行时、证据指纹改变会拒绝静默续算。提取断点已经保存绝对服务、成本、arity histogram、配对指纹与原始字节哈希，可复用而无需重新执行长期模拟。',
         '', 'S4较短时域敏感性尚未执行；S5新增初始化模拟仍需单独授权。']
    zero_traces=sum(r['zero_service_trace_panels'] for r in arms)
    zero_parents=sum(r['zero_service_parents'] for r in arms)
    undefined=sum(c['undefined_bootstrap_draws'] for r in arms for c in r['cost_per_accepted_request'])
    md+=['','## 零服务审查','',f'全部64个相位×规模×源方案×角色单元中，零服务轨迹面板计数之和为{zero_traces}，零服务父图面板计数之和为{zero_parents}。这些计数涉及共享二元参照和重复角色，不能视为独立样本数。320个绝对比值的未定义bootstrap计数之和为{undefined}。逐单元计数见results.json，任何未定义情况均不作零成本替代。']
    (OUT/'report.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    print(f'Exported 64 arm rows, 200 paired rows, {len(parents)} parent-arm rows, and 2 figure bundles.')

if __name__=='__main__': run()
