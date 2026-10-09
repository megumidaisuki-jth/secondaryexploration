"""Verified S5 displays and separate manuscript revision; no simulations/inference."""
from pathlib import Path
from fractions import Fraction
import hashlib
import json
import shutil
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'results/supplement/initialization-ablation-analysis-v1'
OUT = ROOT/'results/supplement/initialization-ablation-figures-v1'
PAPER = ROOT/'manuscript/joconline-s5-revision-v1'
SOURCE_SHA = '9ec1511cb22aa037f4573946d994179f95d9cbc2c7b0c331304934e7b5e737d2'
TEX_SHA = '5940108b1f3d1c9cd3cc047fa06f828e9af270e9436a1356655713cb440f3282'
PROOF_SHA = 'c8e6ae71a2882874361752943aea42146342201b04081f4de6bf11219ab91d9b'
PHASES = ['formal','confirmation']
NODES = [30,60,120,240]
METRICS = ['normalized_restricted_tau_nopath','failure_risk']
ARMS = ['DA-U','FHS5-U','DA-O','FHS5-O']
COMPARISONS = ['DA-U-minus-FHS5-U','DA-O-minus-FHS5-O','interaction-O-minus-U',
               'DA-O-minus-DA-U','FHS5-O-minus-FHS5-U']
COLORS = ['#0072B2','#D55E00','#0072B2','#D55E00']
MARKERS = ['o','s','^','D']

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save_json(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def load_verified():
    assert sha(SOURCE/'results.json') == SOURCE_SHA, 'Unbound inference results'
    assert sha(SOURCE/'verification.json') == PROOF_SHA, 'Arithmetic verification receipt changed'
    proof=json.loads((SOURCE/'verification.json').read_bytes())
    assert proof['status']=='passed' and proof['binding']['results_sha256']==SOURCE_SHA
    assert proof['bootstrap_replicates_verified']==160000 and proof['contrast_rows_verified']==240
    data=json.loads((SOURCE/'results.json').read_bytes())
    assert len(data['comparisons'])==240 and len(data['arm_means'])==192
    expected={(p,n,s,m,c) for p in PHASES for n in NODES
              for s in ['combined','same_distribution','distribution_shift'] for m in METRICS for c in COMPARISONS}
    actual={(r['phase'],r['node_count'],r['scope'],r['metric'],r['comparison']) for r in data['comparisons']}
    assert actual==expected and len(actual)==len(data['comparisons'])
    expected_means={(p,n,s,m,a) for p in PHASES for n in NODES
                    for s in ['combined','same_distribution','distribution_shift'] for m in METRICS for a in ARMS}
    assert {(r['phase'],r['node_count'],r['scope'],r['metric'],r['arm']) for r in data['arm_means']}==expected_means
    for row in data['comparisons']:
        assert row['independent_parents']==60 and set(row['parents_by_model'].values())=={20}
        if row['scope']=='combined':
            assert row['interval_status']=='pointwise-unadjusted-95-percent'
            assert Fraction(*row['exact']['lower'])<=Fraction(*row['exact']['estimate'])<=Fraction(*row['exact']['upper'])
        else:
            assert 'lower' not in row['exact'] and 'upper' not in row['exact']
    return data

def mean(data, phase,n,metric,arm):
    row=next(r for r in data['arm_means'] if (r['phase'],r['node_count'],r['scope'],r['metric'],r['arm'])==(phase,n,'combined',metric,arm))
    return float(Fraction(*row['estimate']))*(100 if metric=='failure_risk' else 1)

def contrast(data,phase,n,metric,comparison):
    return next(r for r in data['comparisons'] if (r['phase'],r['node_count'],r['scope'],r['metric'],r['comparison'])==(phase,n,'combined',metric,comparison))

def configure():
    font_manager.findfont('SimHei',fallback_to_default=False)
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['SimHei','Arial','DejaVu Sans'],
        'font.size':7,'axes.titlesize':8,'axes.labelsize':7,'xtick.labelsize':7,'ytick.labelsize':7,
        'legend.fontsize':7,'legend.frameon':False,'svg.fonttype':'none','pdf.fonttype':42,'axes.unicode_minus':False,
        'axes.spines.right':False,'axes.spines.top':False,'axes.linewidth':0.6,'savefig.dpi':600})

def export(fig,name,height_mm,ledger):
    # Fixed physical width, not tight-cropped: matches existing 170-mm manuscript figures.
    fig.savefig(OUT/f'{name}.svg')
    fig.savefig(OUT/f'{name}.pdf')
    fig.savefig(OUT/f'{name}.png', dpi=600)
    fig.savefig(OUT/f'{name}.tiff', dpi=600, pil_kwargs={'compression':'tiff_lzw'})
    for ax in fig.axes:
        ledger['axes'].append({'figure':name,'xlabel':ax.get_xlabel(),'ylabel':ax.get_ylabel(),
                               'xlim':list(ax.get_xlim()),'ylim':list(ax.get_ylim())})
    ledger['figures'][name]={'width_mm':170,'height_mm':height_mm}
    plt.close(fig)

def means_figure(data,ledger):
    fig,axes=plt.subplots(2,2,figsize=(170/25.4,114/25.4))
    fig.subplots_adjust(left=.105,right=.98,bottom=.15,top=.86,hspace=.55,wspace=.28)
    for mi,metric in enumerate(METRICS):
        for pi,phase in enumerate(PHASES):
            ax=axes[mi,pi]
            for ai,arm in enumerate(ARMS):
                values=[mean(data,phase,n,metric,arm) for n in NODES]
                offset=(ai-1.5)*.10
                ax.scatter([i+offset for i in range(4)],values,s=16,marker=MARKERS[ai],color=COLORS[ai],label=arm)
                for n,v in zip(NODES,values): ledger['marks'].append({'figure':'s5-arm-means','kind':'mean','phase':phase,'node_count':n,'metric':metric,'arm':arm,'plotted':v})
            ax.set_title(f"{'abcd'[mi*2+pi]}  {'正式相位' if pi==0 else '确认相位'}",loc='left',fontweight='bold')
            ax.set_xticks(range(4),NODES); ax.set_xlim(-.5,3.5); ax.set_xlabel('节点数 n（独立规模条件）')
            ax.set_ylabel('Y 均值（放大，非零起点）' if mi==0 else 'F 均值（%）')
            ax.set_ylim((.98,1.001) if mi==0 else (0,6.5)); ax.grid(axis='y',alpha=.18)
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.53,.99),ncol=4)
    fig.text(.53,.025,'描述性均值，无误差线；每相位/规模60父图，轨迹先在父图内平均',ha='center',fontsize=7)
    export(fig,'s5-arm-means',114,ledger)

def limits(data,comparisons):
    output={}
    for metric in METRICS:
        vals=[float(Fraction(*r['exact'][k]))*(100 if metric=='failure_risk' else 1)
              for r in data['comparisons'] if r['scope']=='combined' and r['metric']==metric and r['comparison'] in comparisons for k in ['lower','upper']]
        lo=min(vals+[0]); hi=max(vals+[0]); span=hi-lo
        assert span>0
        output[metric]=(lo-.08*span,hi+.08*span)
    return output

def draw_interval(ax,row,y,color,marker,figure,ledger):
    factor=100 if row['metric']=='failure_risk' else 1
    low,estimate,high=[float(Fraction(*row['exact'][k]))*factor for k in ['lower','estimate','upper']]
    ax.plot([low,high],[y,y],color=color,lw=1)
    ax.plot([low,low],[y-.04,y+.04],color=color,lw=.7)
    ax.plot([high,high],[y-.04,y+.04],color=color,lw=.7)
    ax.scatter([estimate],[y],s=14,color=color,marker=marker,zorder=3)
    ledger['marks'].append({'figure':figure,'kind':'interval',**{k:row[k] for k in ['phase','node_count','metric','comparison']},
                           'scale':factor,'plotted':[low,estimate,high],'exact':row['exact']})

def topology_figure(data,ledger):
    comps=COMPARISONS[:3]; bounds=limits(data,comps)
    fig,axes=plt.subplots(3,2,figsize=(170/25.4,158/25.4))
    fig.subplots_adjust(left=.10,right=.98,bottom=.14,top=.90,hspace=.62,wspace=.34)
    for ci,comp in enumerate(comps):
        for mi,metric in enumerate(METRICS):
            ax=axes[ci,mi]
            for pi,phase in enumerate(PHASES):
                for i,n in enumerate(NODES): draw_interval(ax,contrast(data,phase,n,metric,comp),i+(pi-.5)*.23,COLORS[pi],['o','s'][pi],'s5-topology-interaction',ledger)
            ax.set_title(f"{'abcdef'[ci*2+mi]}  {['ΔU：均匀初态拓扑差','ΔO：原优化初态拓扑差','Γ：ΔO - ΔU'][ci]}",loc='left',fontweight='bold')
            ax.set_yticks(range(4),NODES); ax.set_ylim(3.5,-.5); ax.set_ylabel('节点数 n')
            ax.set_xlim(bounds[metric]); ax.axvline(0,color='#666666',ls=':',lw=.7)
            ax.set_xlabel('Y 差（无量纲）' if mi==0 else 'F 差（百分点）'); ax.grid(axis='x',alpha=.18)
    from matplotlib.lines import Line2D
    fig.legend([Line2D([],[],color=COLORS[i],marker=['o','s'][i],lw=1) for i in range(2)],['正式相位','确认相位'],loc='upper center',ncol=2)
    fig.text(.54,.045,'ΔU、ΔO：Y 正值 / F 负值有利于 DA；Γ 是直接交互，不是优劣排名',ha='center',fontsize=7)
    fig.text(.54,.02,'点态95% percentile区间，未校正；事后补充分析，不是新增盲确认',ha='center',fontsize=7)
    export(fig,'s5-topology-interaction',158,ledger)

def initialization_figure(data,ledger):
    comps=COMPARISONS[3:]; bounds=limits(data,comps)
    fig,axes=plt.subplots(2,2,figsize=(170/25.4,114/25.4))
    fig.subplots_adjust(left=.10,right=.98,bottom=.17,top=.86,hspace=.55,wspace=.34)
    for mi,metric in enumerate(METRICS):
        for pi,phase in enumerate(PHASES):
            ax=axes[mi,pi]
            for ci,comp in enumerate(comps):
                for i,n in enumerate(NODES): draw_interval(ax,contrast(data,phase,n,metric,comp),i+(ci-.5)*.23,COLORS[ci],['o','s'][ci],'s5-initialization',ledger)
            ax.set_title(f"{'abcd'[mi*2+pi]}  {'正式相位' if pi==0 else '确认相位'}",loc='left',fontweight='bold')
            ax.set_yticks(range(4),NODES); ax.set_ylim(3.5,-.5); ax.set_ylabel('节点数 n')
            ax.set_xlim(bounds[metric]); ax.axvline(0,color='#666666',ls=':',lw=.7)
            ax.set_xlabel('O - U：Y 差（无量纲）' if mi==0 else 'O - U：F 差（百分点）'); ax.grid(axis='x',alpha=.18)
    from matplotlib.lines import Line2D
    fig.legend([Line2D([],[],color=COLORS[i],marker=['o','s'][i],lw=1) for i in range(2)],['DA：O - U','FHS5：O - U'],loc='upper center',ncol=2)
    fig.text(.54,.05,'Y 正值 / F 负值表示 O 较有利；全部16个条件对比保留',ha='center',fontsize=7)
    fig.text(.54,.02,'点态95% percentile区间，未校正；每相位/规模60父图',ha='center',fontsize=7)
    export(fig,'s5-initialization',114,ledger)

def manuscript():
    old=ROOT/'manuscript/joconline-latex/main.tex'
    assert sha(old)==TEX_SHA, 'Original manuscript changed; review anchors first'
    tex=old.read_text(encoding='utf-8')
    insert=(PAPER/'s5-main-section.tex').read_text(encoding='utf-8')
    anchor=r'\subsection{服务收益与协调开销}'
    assert tex.count(anchor)==1
    tex=tex.replace(anchor,insert+'\n\n'+anchor)
    before='后续可增加需求感知构造相对于FHS5种子的直接配对消融，检验搜索增量；在不同请求时域与资金预算下验证趋势；测量多方协调对应的通信和锁定时延。'
    after='四臂补充已将DA相对FHS5的拓扑差与O相对U的资金初态差分别报告，但尚未形成新的盲确认或机制识别。后续应在独立留出父图上预先规定这些对比，并在不同请求时域与资金预算下检验适用范围；多方协调对应的通信和锁定时延仍需实现级测量。'
    assert tex.count(before)==1
    tex=tex.replace(before,after)
    discussion=r'\subsection{统计范围与外部有效性}'
    caution='四臂分析还表明，不能将共同优化协议视为留出收益的保证。有限训练情景的字典序评分与留出风险、均值终点并非同一统计对象；数据支持的是已观察条件下的配置差异，不能据此归因于过拟合、需求偏移或特定路由机制。由于同一父图在多项对比中重复出现，80个点态区间也不能组合成家族确认结论。\n\n'
    assert tex.count(discussion)==1
    tex=tex.replace(discussion,caution+discussion)
    (PAPER/'main.tex').write_text(tex,encoding='utf-8')
    figs=PAPER/'figures'; figs.mkdir(exist_ok=True)
    for source in (ROOT/'manuscript/joconline-latex/figures').glob('*.pdf'):
        shutil.copyfile(source,figs/source.name)
        assert sha(source)==sha(figs/source.name)
    for name in ['s5-arm-means','s5-topology-interaction','s5-initialization']:
        shutil.copyfile(OUT/f'{name}.pdf',figs/f'{name}.pdf')
    save_json(PAPER/'revision-map.json',{'original_tex_sha256':TEX_SHA,'results_sha256':SOURCE_SHA,
        'new_section_sha256':sha(PAPER/'s5-main-section.tex'),'replacements':[{'old':before,'new':after}],
        'additions':['s5-main-section.tex',caution],'original_manuscript_unchanged':sha(old)==TEX_SHA,
        'new_simulations':0,'new_bootstrap_replicates':0})
    preamble=tex.split(r'\begin{document}')[0]
    parts=[preamble,r'\begin{document}',r'\onecolumn',r'\renewcommand{\thefigure}{S\arabic{figure}}',r'\section*{S5：四臂补充图及读图说明}',
        '本补充复用已核验的四臂统计，不产生新的模拟或重抽样。每相位、每规模60父图，3模型各20，7条轨迹先在父图内平均；所有条件均保留。U为节点预算均匀初态，O为原优化初态。两相位标签仅指数据来源，本补充为事后分析。',
        '统计使用Python 3.12.14。每相位、每规模20\\,000次模型分层整父图配对bootstrap，四臂及两个终点共享索引；每模型抽20父图有放回，以模型均值等权汇总。种子2026100705及SHA-256派生副本/模型种子，点估计和区间保留精确有理数；区间为逆经验分布第500和19\\,500顺序统计量，点态95\\%、未校正，无p值。全部160\\,000次副本已经单独算术核验，但该核验不是独立盲科学审查。']
    captions=[
        ('s5-arm-means','四臂绝对均值','a、b为正式与确认相位Y均值，c、d为F均值（百分数）。Y轴放大且非零起点，F轴从零开始；不画误差线。标记只表示各独立规模条件，不连接为时间轨迹。每父图7条轨迹先汇总，3模型等权。图的作用是给出差值所在的绝对水平，不证明臂间等效。'),
        ('s5-topology-interaction','拓扑对比与直接交互','a、b为均匀初态的DA减FHS5，c、d为原优化初态对应差，e、f为两种拓扑差之差。左列为Y差（无量纲），右列为F差（百分点）；圆点为正式、方块为确认。横线是共享索引、模型分层、整父图20\\,000次重抽样所得点态95\\% percentile区间，未校正。共48项完整合并范围对比；交互不是由显著性有无推断。零宽经验区间不证明总体等效。'),
        ('s5-initialization','各拓扑内部的初态对比','a、b为正式、确认相位Y差，c、d为对应F差（百分点）。圆点为DA、方块为FHS5的O减U，横线为点态、未校正95\\%区间。共32项完整合并范围对比；Y正值和F负值表示O较有利。16个时间条件中15负1正只是描述性方向计数，不是16个独立重复或多重校正结论。')]
    for index,(name,title,caption) in enumerate(captions):
        parts += [r'\begin{figure}[ht]\centering',r'\includegraphics[width=170mm]{figures/'+name+'.pdf}',r'\caption{'+title+'。'+caption+'}',r'\end{figure}',r'\clearpage']
        if index==2: parts.pop()
    parts += [r'\section*{源数据和边界}',
        '完整源数据保留240项对比和192项四臂均值，包括160项无区间的同分布、偏移描述对比及128项范围均值。主分析的40项家族复现判据与本补充80项点态区间不同，不得合并解释。Y为首次无路径请求索引截断至H后除以H；末次请求发生事件与窗口内无事件的Y可能相同，但F不同。风险百分点差不是相对风险百分比。固定的是节点初始预算而非每条超边资金，因此图形不识别纯拓扑因果效应。',r'\end{document}']
    (PAPER/'supplement.tex').write_text('\n\n'.join(parts),encoding='utf-8')

def verify_ledger(data,ledger):
    assert len(ledger['marks'])==144
    keys=set()
    for mark in ledger['marks']:
        if mark['kind']=='mean':
            value=mean(data,mark['phase'],mark['node_count'],mark['metric'],mark['arm'])
            assert value==mark['plotted']
            key=('mean',mark['phase'],mark['node_count'],mark['metric'],mark['arm'])
        else:
            row=contrast(data,mark['phase'],mark['node_count'],mark['metric'],mark['comparison'])
            assert row['exact']==mark['exact']
            assert mark['plotted']==[float(Fraction(*row['exact'][k]))*mark['scale'] for k in ['lower','estimate','upper']]
            key=('interval',mark['phase'],mark['node_count'],mark['metric'],mark['comparison'])
        assert key not in keys; keys.add(key)

def main():
    data=load_verified(); configure(); OUT.mkdir(exist_ok=True)
    shutil.copyfile(SOURCE/'results.json',OUT/'source-data.json')
    assert sha(OUT/'source-data.json')==SOURCE_SHA
    ledger={'results_sha256':SOURCE_SHA,'axes':[],'marks':[],'figures':{},
        'complete_combined_comparisons':80,'complete_combined_arm_means':64,
        'subscope_comparisons_in_source':160,'subscope_arm_means_in_source':128,
        'new_simulations':0,'new_bootstrap_replicates':0,'backend':'Python/matplotlib',
        'python_version':sys.version.split()[0],'matplotlib_version':matplotlib.__version__}
    means_figure(data,ledger); topology_figure(data,ledger); initialization_figure(data,ledger)
    verify_ledger(data,ledger); save_json(OUT/'display-ledger.json',ledger)
    manuscript()
    files={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in list(OUT.iterdir())+list(PAPER.rglob('*')) if p.is_file() and p.name not in ['manifest.json']}
    save_json(OUT/'manifest.json',{'results_sha256':SOURCE_SHA,'verification_sha256':sha(SOURCE/'verification.json'),
        'builder_sha256':sha(Path(__file__)),'files':files,'marks_verified':144,'status':'generated-pending-visual-QA'})
    print('Generated 3 complete figure bundles, separate manuscript/supplement sources; 144 marks match verified exact statistics.')

if __name__=='__main__': main()
