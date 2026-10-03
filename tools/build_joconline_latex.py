"""Mechanical, evidence-preserving Markdown to two-column XeLaTeX conversion.

No simulation or inference. Original Markdown/Word and vector figures are retained.
Run from the repository with the bundled artifact Python.
"""
from pathlib import Path
from fractions import Fraction
import hashlib
import json
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'manuscript/joconline-expanded'
OUT = ROOT / 'manuscript/joconline-latex'

PREAMBLE = r'''% !TeX program = xelatex
% Journal-style author manuscript, not an official publisher class.
% Compile main.tex from this directory with XeLaTeX (twice) or Tectonic.
\documentclass[UTF8,a4paper,twocolumn,fontset=none,zihao=5]{ctexart}
\usepackage[top=20mm,bottom=20mm,left=18mm,right=18mm,columnsep=7mm]{geometry}
\usepackage{amsmath,amssymb,booktabs,graphicx,tabularx,array}
\usepackage{caption,enumitem,needspace,balance}
\usepackage{cite}
\newcommand{\upcite}[1]{\textsuperscript{\cite{#1}}}
\usepackage{xurl}
\usepackage[hidelinks,bookmarksnumbered]{hyperref}
\IfFontExistsTF{SimSun}{\setCJKmainfont{SimSun}[AutoFakeBold=2]}{\setCJKmainfont{FandolSong-Regular}[BoldFont=FandolSong-Bold]}
\IfFontExistsTF{SimHei}{\setCJKsansfont{SimHei}[AutoFakeBold=2]}{\setCJKsansfont{FandolHei-Regular}[BoldFont=FandolHei-Bold]}
\IfFontExistsTF{SimSun}{\setCJKmonofont{SimSun}}{\setCJKmonofont{FandolSong-Regular}}
\setmainfont{texgyretermes-regular.otf}[BoldFont=texgyretermes-bold.otf,ItalicFont=texgyretermes-italic.otf,BoldItalicFont=texgyretermes-bolditalic.otf]
\setsansfont{texgyreheros-regular.otf}[BoldFont=texgyreheros-bold.otf]
\ctexset{section={format=\large\sffamily\bfseries,beforeskip=9pt,afterskip=5pt},
 subsection={format=\normalsize\sffamily\bfseries,beforeskip=7pt,afterskip=3pt}}
\setlength{\parindent}{2em}
\setlength{\parskip}{0pt}
\linespread{1.06}
\setlength{\abovedisplayskip}{5pt plus 1pt minus 1pt}
\setlength{\belowdisplayskip}{5pt plus 1pt minus 1pt}
\setlength{\textfloatsep}{10pt plus 2pt minus 2pt}
\setlength{\dbltextfloatsep}{10pt plus 2pt minus 2pt}
\setlength{\floatsep}{8pt plus 2pt minus 2pt}
\renewcommand{\topfraction}{0.93}
\renewcommand{\dbltopfraction}{0.93}
\renewcommand{\textfraction}{0.06}
\renewcommand{\floatpagefraction}{0.80}
\renewcommand{\dblfloatpagefraction}{0.80}
\setcounter{topnumber}{3}
\setcounter{dbltopnumber}{3}
\makeatletter
\setlength{\@fptop}{0pt}
\setlength{\@fpsep}{10pt}
\setlength{\@fpbot}{0pt plus 1fil}
\makeatother
\captionsetup{font=small,labelsep=quad,skip=4pt}
\setlist[enumerate]{leftmargin=1.8em,nosep,label=\arabic*.}
\newcolumntype{Y}{>{\centering\arraybackslash}X}
\newcommand{\algtitle}[1]{\par\Needspace{6\baselineskip}\smallskip\noindent\textbf{#1}\par\smallskip}
\emergencystretch=1em
\raggedbottom
\pagestyle{plain}
\setcounter{section}{-1}
\hypersetup{pdftitle={资源匹配下超图支付网络的服务可靠性},pdfauthor={作者待填}}
\begin{document}
'''

# Unicode mathematical strings in the Word-oriented source need real TeX math.
MATH = {
 'T=min(τnp,H)':r'T=\min(\tau_{\mathrm{np}},H)',
 'Z∈{Y,F}':r'Z\in\{Y,F\}', 'n=|V|':r'n=|V|',
 'G=(V,E)':r'G=(V,E)', 'e∈𝓔':r'e\in\mathcal E', 'v∈e':r'v\in e',
 'H=12n':r'H=12n', '3(n−3)':r'3(n-3)', 'mᵤᵥ>0':r'm_{uv}>0',
 'Y=T/H':r'Y=T/H', 'F=δ':r'F=\delta', 'T=H':r'T=H',
 'δ=0':r'\delta=0', 'δ=1':r'\delta=1', 'Kf':r'K_f',
 'q=0.10':r'q=0.10', 'L−1':r'L-1', 'L+1':r'L+1',
 '𝓗=(V,𝓔)':r'\mathcal H=(V,\mathcal E)',
 'xₑⱼ,ᵥⱼ₋₁(t−1)≥aₜ':r'x_{e_j,v_{j-1}}(t-1)\geq a_t',
 'qₜ=(sₜ,dₜ,aₜ)':r'q_t=(s_t,d_t,a_t)',
 'P=(v₀,e₁,v₁,…,eℓ,vℓ)':r'P=(v_0,e_1,v_1,\ldots,e_\ell,v_\ell)',
 'v₀=sₜ':r'v_0=s_t','vℓ=dₜ':r'v_\ell=d_t','vⱼ₋₁,vⱼ∈eⱼ':r'v_{j-1},v_j\in e_j',
 'xₑ,ᵥ(t)':r'x_{e,v}(t)','τdep':r'\tau_{\mathrm{dep}}','τnp':r'\tau_{\mathrm{np}}',
 'τrej':r'\tau_{\mathrm{rej}}','Dᵤᵥ':r'D_{uv}','mᵤᵥ':r'm_{uv}',
 'Cₑ':r'C_e','Bᵥ':r'B_v','𝓟ₜ':r'\mathcal P_t','𝓔':r'\mathcal E',
 '𝓗':r'\mathcal H','δ':r'\delta','∈':r'\in','∶':':','×':r'\times',
 '≥':r'\geq','≤':r'\leq','−':'-',
}

# Remove only repeated framing/interpretation, not data, equations, algorithms,
# assumptions, adverse cases, modification disclosure or inferential limits.
# The complete expanded manuscript remains unchanged and recoverable.
OMIT_PREFIXES = (
 '从工程问题看，',
 '全文组织如下：',
 '这一区分决定了不同研究结果',
 '路由算法比较还需要保持',
 '现有拓扑、路由和重平衡研究分别强调',
 '该写法把随机输入、路由选择',
 '在应用解释上，',
 '各构造拥有自己的参照也是必要的。',
 '3类父图承担结构分层',
 '同一父图内，构造及参照共享',
 '总体门控制构造族结果的确认性解释',
 '两类主终点分别描述有限时域',
 '描述性指标与主要终点之间同样',
 '对于运维应用，这一框架',
 '在相同节点资金与总参与关系下，',
 '独立确认增强的是在相同生成机制',
 '极端尾部区间依赖有限重抽样',
 '这些补充对应不同尚未解决的问题。',
)

def text(s, citations=True):
    """Escape prose while preserving existing inline mathematics and URLs."""
    held=[]
    def hold(v):
        held.append(v)
        return f'ZZTOKEN{len(held)-1}ZZ'
    s=re.sub(r'\$([^$]+)\$',lambda m:hold('$'+m[1]+'$'),s)
    s=re.sub(r'https://[^\s）]+',lambda m:hold(r'\url{'+m[0].rstrip('.')+'}'+('.' if m[0].endswith('.') else '')),s)
    for k in sorted(MATH,key=len,reverse=True):
        s=s.replace(k,hold('$'+MATH[k]+'$'))
    s=s.replace('&',r'\&').replace('%',r'\%').replace('_',r'\_').replace('#',r'\#').replace('{',r'\{').replace('}',r'\}')
    if citations:
        def cite(m):
            nums=[]
            for part in m[1].split(','):
                if '-' in part:
                    a,b=map(int,part.split('-'));nums.extend(range(a,b+1))
                else:nums.append(int(part))
            return r'\upcite{'+','.join('r'+str(i) for i in nums)+'}'
        s=re.sub(r'\[(\d+(?:[-,]\d+)*)\]',cite,s)
    for i,v in enumerate(held):s=s.replace(f'ZZTOKEN{i}ZZ',v)
    return s

def equation(block):
    formula=block.strip('$ ').strip()
    n=int(re.search(r'\\tag\{(\d+)\}',formula)[1])
    formula=re.sub(r'\\tag\{\d+\}', '', formula).strip()
    # Break long expressions semantically rather than shrink the mathematical font.
    replacements={
      1:r'\begin{aligned} C_e&=\sum_{v\in e}x_{e,v}(t),\\ \sum_{e\ni v}x_{e,v}(0)&=B_v.\end{aligned}',
      2:r'\begin{aligned}x_{e_j,v_{j-1}}(t)&=x_{e_j,v_{j-1}}(t-1)-a_t,\\x_{e_j,v_j}(t)&=x_{e_j,v_j}(t-1)+a_t.\end{aligned}',
      3:r'\begin{aligned}\mathcal X&=\prod_{e\in\mathcal E}\mathcal X_e,\\\mathcal X_e&=\left\{(x_{e,v})_{v\in e}\geq0:\sum_{v\in e}x_{e,v}=C_e\right\}.\end{aligned}',
      9:r'\begin{aligned}R&=\sum_{u<v:m_{uv}>0}\min(D_{uv},D_{vu}),\\I&=\sum_{u<v:m_{uv}>0}|D_{uv}-D_{vu}|.\end{aligned}',
      10:r'\begin{aligned}P&=\sum_{u\in V}\binom{\deg_{\mathcal H}(u)}{2},\\O&=\sum_{e\in\mathcal E}\binom{|e|}{2}+\sum_{u<v}\binom{m_{uv}}{2}.\end{aligned}',
      12:r'\begin{aligned}w_{e,u}={}&1+\sum_{v\in e\setminus\{u\}}(D_{uv}+D_{vu})\\&+\sum_{v\in e\setminus\{u\}}|D_{uv}-D_{vu}|.\end{aligned}',
      13:r'\begin{aligned}d_f^{(Z)}&=Z_f-\frac{1}{K_f}\sum_{k=1}^{K_f}Z_{f,k}^{(B)},\\d_{\mathrm{global}}^{(Z)}&=\frac{1}{4}\sum_f d_f^{(Z)}.\end{aligned}',
      14:r'\begin{aligned}\mathbb E[Y]&=\frac{1}{H}\sum_{t=0}^{H-1}\Pr(\tau_{\mathrm{np}}>t),\\\mathbb E[F]&=\Pr(\tau_{\mathrm{np}}\leq H).\end{aligned}',
      15:r'\begin{aligned}D_{m,i,f}^{(Z)}={}&\frac{4}{7}\frac{1}{4}\sum_{r\in\mathcal R_0}d_{m,i,r,f}^{(Z)}\\&+\frac{3}{7}\frac{1}{3}\sum_{r\in\mathcal R_1}d_{m,i,r,f}^{(Z)}.\end{aligned}',
    }
    return '\n'+r'\begin{equation}'+f'\n{replacements.get(n,formula)}\n'+rf'\label{{eq:{n}}}\end{{equation}}'+'\n'

def tables():
    manifest=json.loads((SRC/'manifest.json').read_text(encoding='utf-8'))
    for rel,key in (
        ('manuscript/generated/synthetic-v1/table-1.json','source_table_sha256'),
        ('manuscript/generated/results-writing-v1/evidence-summary.json','source_descriptive_sha256'),
    ):
        if hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=manifest[key]:
            raise ValueError(f'Scientific input changed: {rel}')
    table=json.loads((ROOT/'manuscript/generated/synthetic-v1/table-1.json').read_text(encoding='utf-8'))
    desc=json.loads((ROOT/'manuscript/generated/results-writing-v1/evidence-summary.json').read_text(encoding='utf-8'))
    result={}
    lines=[r'\begin{table*}[t]\centering',r'\caption{总体配对效应及多重比较校正区间}\label{tab:1}',
           r'\small\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lccc}\toprule',
           r'终点 & 节点数 & 正式相位估计［区间］ & 确认相位估计［区间］\\\midrule']
    for row in table:
        vals=['失败风险' if row['formal']['metric']=='failure_risk' else r'受限时间$/H$',str(row['formal']['node_count'])]
        for p in ('formal','confirmation'):
            d=row[p]['display'];vals.append('$'+d['estimate']+r'\;['+d['lower']+', '+d['upper']+']$')
        lines.append(' & '.join(vals)+r'\\')
    lines += [r'\bottomrule\end{tabular*}',r'\par\smallskip\footnotesize 每相位每行含60个独立父图；风险差为负、受限时间差为正表示有利方向。',r'\end{table*}']
    result['GLOBAL']='\n'.join(lines)
    lines=[r'\begin{table}[t]\centering',r'\caption{总体失败风险差的父图模型分层均值}\label{tab:2}',
           r'\small\begin{tabular*}{\columnwidth}{@{\extracolsep{\fill}}clrr}\toprule',r'节点数 & 父图模型 & 正式 & 确认\\\midrule']
    for n in (30,60,120,240):
        for model,label in [('barabasi_albert','BA'),('er_gnm','ER-GNM'),('sbm_fixed_count','SBM')]:
            vals=[str(n),label]
            for p in ('formal','confirmation'):
                r=next(r for r in desc['phases'][p]['parent_stratum_summaries'] if r['metric']=='failure_risk' and r['source_family']=='global' and r['node_count']==n and r['parent_model']==model)
                z=round(Fraction(*r['mean'])*1000)
                vals.append('$'+('-' if z<0 else '')+f'{abs(z)//1000}.{abs(z)%1000:03d}'+'$')
            lines.append(' & '.join(vals)+r'\\')
    lines += [r'\bottomrule\end{tabular*}',r'\par\smallskip\footnotesize 每格含20个父图；SBM为固定边数SBM。仅为描述性均值，不是新增显著性检验。',r'\end{table}']
    result['MODEL']='\n'.join(lines)
    lines=[r'\begin{table}[t]\centering',r'\caption{需求感知搜索的改变与未改变父图数}\label{tab:3}',
           r'\small\begin{tabular*}{\columnwidth}{@{\extracolsep{\fill}}crrrr}\toprule',r'&\multicolumn{2}{c}{正式相位}&\multicolumn{2}{c}{确认相位}\\',
           r'节点数&改变&未改变&改变&未改变\\\midrule']
    for n in (30,60,120,240):
        vals=[str(n)]
        for p in ('formal','confirmation'):
            for activity in ('changed','unchanged'):
                r=next(r for r in desc['phases'][p]['activity_sensitivity'] if r['metric']=='failure_risk' and r['node_count']==n and r['topology_activity']==activity)
                vals.append(str(sum(t['parent_count'] for t in r['strata'])))
        lines.append(' & '.join(vals)+r'\\')
    lines += [r'\bottomrule\end{tabular*}',r'\par\smallskip\footnotesize 每规模每相位共60个父图；改变相对于FHS5种子定义，不表示服务改善。',r'\end{table}']
    result['ACTIVITY']='\n'.join(lines)
    return result

def build():
    manifest=json.loads((SRC/'manifest.json').read_text(encoding='utf-8'))
    source=(SRC/'manuscript-zh.md').read_text(encoding='utf-8')
    assert hashlib.sha256((SRC/'manuscript-zh.md').read_bytes()).hexdigest()==manifest['files']['manuscript-zh.md']['sha256']
    blocks=re.split(r'\n\s*\n',source.strip())
    out=[PREAMBLE,r'\twocolumn[{\begin{minipage}{\textwidth}']
    pre,body=source.split('## 0 引言',1)
    for block in re.split(r'\n\s*\n',pre.strip()):
        if block.startswith('# '):out.append(r'\begin{center}\zihao{2}\bfseries '+text(block[2:])+r'\end{center}')
        elif block.startswith('## '):out.append(r'\begin{center}\large\bfseries '+text(block[3:])+r'\end{center}')
        elif block.startswith(('作者姓名','（作者单位','AUTHOR','Affiliations')):out.append(r'\begin{center}\small '+text(block)+r'\end{center}')
        else:out.append(r'{\small\noindent '+text(block)+r'\par}\vspace{3pt}')
    out.append(r'\vspace{7pt}\end{minipage}}]')
    body='## 0 引言'+body
    bib=False; algorithm=False; skip_caption=False
    omitted=[]
    tabs=tables()
    for block in re.split(r'\n\s*\n',body.strip()):
        if block.startswith(OMIT_PREFIXES):
            omitted.append(block)
            continue
        if algorithm and not block.startswith('步骤'):
            out.append(r'\end{enumerate}');algorithm=False
        if skip_caption and re.match(r'^图\d',block):skip_caption=False;continue
        if block.startswith('## 参考文献'):
            out.append(r'\begin{thebibliography}{99}\small\raggedright\setlength{\itemsep}{2pt}');bib=True
        elif block.startswith('## 作者简介'):
            out.append(r'\end{thebibliography}\section*{作者简介}');bib=False
        elif bib:
            m=re.match(r'\[(\d+)\]\s*(.*)',block,flags=re.S)
            out.append(r'\bibitem{r'+m[1]+'} '+text(m[2],citations=False))
        elif block.startswith('### '):out.append(r'\subsection{'+text(re.sub(r'^### \d+\.\d+\s*','',block))+'}')
        elif block.startswith('## '):
            name=re.sub(r'^## (?:\d+\s+)?','',block)
            out.append((r'\section*{' if name=='数据与代码' else r'\section{')+text(name)+'}')
        elif block.startswith('$$'):out.append(equation(block))
        elif block.startswith('{{TABLE_'):out.append(tabs[block[8:-2]])
        elif block.startswith('表1　'):continue  # table caption/note represented in the float
        elif block.startswith('!['):
            m=re.match(r'!\[图(\d+) ([^]]+)\]\(figures/([^)]+)\)',block)
            n,title,filename=m.groups()
            captions={
              '1':'每规模每相位含60个独立父图；同一父图内7条留出轨迹为嵌套测量，两相位分别推断。',
              '2':'(a)固定时域失败风险差；(b)归一化受限无路径时间差。圆点为正式相位，方点为确认相位；水平线为校正区间，虚线为零差。每个估计含60个父图，重抽样20000次。',
              '3':'每格对应一项预定比较。“双相位”表示校正区间均有利且适用的总体门均开启；不表示超图构造之间的两两排序。'}
            out += [r'\begin{figure*}[t]\centering',r'\includegraphics[width=170mm]{figures/'+Path(filename).with_suffix('.pdf').name+'}',r'\caption{'+text(title+'。'+captions[n])+r'}\label{fig:'+n+'}',r'\end{figure*}']
            skip_caption=True
        elif block.startswith('算法'):
            out.append(r'\algtitle{'+text(block)+r'}\begin{enumerate}');algorithm=True
        elif block.startswith('步骤'):
            out.append(r'\item '+text(re.sub(r'^步骤\d+　','',block)))
        elif block.startswith(('命题','证明')):
            m=re.match(r'^([^　]+)　(.*)',block,re.S)
            out.append(r'\noindent\textbf{'+m[1]+'} '+text(m[2])+r'\par')
        else:out.append(text(block)+'\n')
    out.append(r'\end{document}')
    OUT.mkdir(exist_ok=True)
    (OUT/'figures').mkdir(exist_ok=True)
    for p in (SRC/'figures').glob('*.pdf'):
        key=str(p.relative_to(SRC))
        assert hashlib.sha256(p.read_bytes()).hexdigest()==manifest['files'][key]['sha256']
        shutil.copy2(p,OUT/'figures'/p.name)
    (OUT/'main.tex').write_text('\n\n'.join(out)+'\n',encoding='utf-8')
    (OUT/'compression-map.json').write_text(json.dumps({'source':'manuscript/joconline-expanded/manuscript-zh.md','omitted_repeated_paragraphs':omitted,'omitted_han_characters':len(re.findall(r'[\u4e00-\u9fff]',''.join(omitted)))},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Built main.tex from unchanged expanded source; 16 equations, 3 figures, 3 tables, 15 references.')

if __name__=='__main__':build()
