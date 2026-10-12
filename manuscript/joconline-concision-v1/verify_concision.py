"""Report/verify an apply_patch-edited manuscript; no scientific recalculation."""
from pathlib import Path
import hashlib
import difflib
import importlib.util
import json
import re
import subprocess
import sys
import zipfile
from lxml import etree
from pypdf import PdfReader

ROOT=Path('E:/second')
BASE=ROOT/'manuscript/joconline-submission-v1'
STAGE=Path(__file__).resolve().parent
OUT=STAGE if (STAGE/'main.tex').exists() else STAGE/'joconline-concision-v1'
QA=STAGE/'qa' if OUT!=STAGE else ROOT/'results/diagnostics/joconline-concision-20261012'
PYTHON=Path(sys.executable)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def han(text):
    return len(re.findall('[\u4e00-\u9fff]',text))

def check():
    baseline=json.loads((BASE/'manifest.json').read_bytes())
    for item in baseline['files']:
        path=ROOT/item['path']
        assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],path
    changes=[]; counts={}
    for name in ('main','supplement'):
        old=(BASE/(name+'.tex')).read_text('utf-8')
        new=(OUT/(name+'.tex')).read_text('utf-8')
        for pattern in [r'\\begin\{equation\}.*?\\end\{equation\}',r'\\\[.*?\\\]',r'\\begin\{tabular\*?\}.*?\\end\{tabular\*?\}']:
            assert re.findall(pattern,old,re.S)==re.findall(pattern,new,re.S),(name,pattern)
        assert re.findall(r'\\includegraphics\[[^]]*\]\{([^}]+)\}',old)==re.findall(r'\\includegraphics\[[^]]*\]\{([^}]+)\}',new)
        if name=='main':
            assert old.split(r'\begin{thebibliography}')[1]==new.split(r'\begin{thebibliography}')[1]
            # All distinct decimal anchors survive; duplicates in caveats may go.
            assert set(re.findall(r'\d+\.\d+',old))<=set(re.findall(r'\d+\.\d+',new))
            for marker in ['路径的节点与超边均不重复','第13和第19988','未证明有限样本精确覆盖率','15个区块后','S1–S5均为事后补充分析','全部80项合并比较均报告，未作多重比较校正','预算恰为L','区块实际经历的时长','配对差','亦不证明等效','初末失衡','不是实测时延或费用']:
                assert marker in new,marker
            for removed in ['本文不声称首次','该命题不包含停止时间大小或拓扑优劣','如果进一步建立扩散近似','避免通过更换事件名称制造形式上的理论推广']:
                assert removed not in new,removed
            assert len(re.findall(r'\\begin\{equation\}',new))==18
        lines_old=old.splitlines();lines_new=new.splitlines()
        for kind,a,b,c,d in difflib.SequenceMatcher(None,lines_old,lines_new,autojunk=False).get_opcodes():
            if kind=='equal':continue
            changes.append(dict(file=name+'.tex',operation=kind,old_line=a+1,new_line=c+1,
                original='\n'.join(lines_old[a:b]),revised='\n'.join(lines_new[c:d])))
        counts[name]=dict(original_han=han(old),revised_han=han(new),net_han_removed=han(old)-han(new),
                          reduction_percent=round(100*(han(old)-han(new))/han(old),2))
    for folder in ('figures','source-data'):
        for path in (BASE/folder).iterdir():
            assert path.read_bytes()==(OUT/folder/path.name).read_bytes(),path
    if (OUT/'manifest.json').exists():
        manifest=json.loads((OUT/'manifest.json').read_bytes())
        assert manifest['schema']=='joconline-concision-v1'
        for item in manifest['files']:
            path=OUT/item['path']
            assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],path
        print('Read-only recheck passed: baseline, protected content and sealed payload.')
        return
    dump(OUT/'concision-checks.json',dict(date='2026-10-12',baseline_verified_files=len(baseline['files']),
        baseline_manifest_sha256=sha(BASE/'manifest.json'),scope='prose-only editorial revision',
        new_simulations=0,new_bootstrap_replicates=0,numbered_equations_preserved=18,
        unnumbered_display_equations_preserved=2,scientific_figures_byte_preserved=11,
        scientific_json_byte_preserved=9,all_table_cells_unchanged=True,bibliography_unchanged=True,
        change_hunks=len(changes),counts=counts))
    dump(OUT/'changes.json',changes)
    sections={'main.tex':'主稿','supplement.tex':'补充材料'}
    report=['# 删繁修订逐项记录','',
        '删除标准：句子是否提供新的定义、证据、推导、比较解释或具体限制。只重复否认未曾提出的主张、解释写作意图或交付过程的句子删除。必要定义、方法条件和统计范围保留；相同限制只在合适位置说明一次。','',
        '合并了引言的重复贡献段，将原第5.8节的规模与时域问题并入第6.3节；其他主要章节、18个编号公式、2个展示公式、所有表内数据和11幅图保持。删除的是正文和图注的冗余解释，不删除不利结果。','']
    for name,stats in counts.items():
        report.append(f"{sections[name+'.tex']}：中文汉字由{stats['original_han']}降至{stats['revised_han']}，净减少{stats['net_han_removed']}（{stats['reduction_percent']}%）。这是源文件汉字计数，不是期刊正文篇幅统计。")
    report.extend(['','## 保留的必要解释','',
        '首次触零与首次无路径的区别、完整残余路径搜索、原子提交、参与关系预算、奇数预算参照、父图重抽样单位、点态/家族校正区间、事后分析身份、冻结修订时间线、低分位覆盖不足、协调计数与实际费用的区别。它们改变模型或结论的解释，具有论证作用。','',
        '## 本轮术语','',
        '|术语|保持的含义|','|---|---|','|首次余额耗尽|局部坐标首次触零|','|首次无路径|当前请求的可行路径集合为空|',
        '|DA / FHS3 / FHS5 / NCH|沿用原构造族名称|','|Y / F|归一化受限无路径时间 / 固定时域首次无路径指标|',
        '|点态95%区间|S3–S5的未校正区间|','|家族校正区间|主要比较及S1声明的Bonferroni分配|','',
        '## 逐项原文与修订',''])
    for n,item in enumerate(changes,1):
        report.extend([f"### {n} {sections[item['file']]} 原稿第{item['old_line']}行",'',
            '原文：','```tex',item['original'],'```','','修订：','```tex',item['revised'] or '（删除）','```',''])
    (OUT/'changes.md').write_text('\n'.join(report).rstrip()+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(counts=counts,change_hunks=len(changes)),ensure_ascii=False))

def word():
    assert not (OUT/'manifest.json').exists(),'Preserve sealed outputs.'
    QA.mkdir(exist_ok=True)
    spec=importlib.util.spec_from_file_location('prior_export',ROOT/'tools/build_joconline_submission_revision.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.OUT=OUT;module.QA=QA;module.word()
    ns={'m':'http://schemas.openxmlformats.org/officeDocument/2006/math','w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    for name in ('main','supplement'):
        with zipfile.ZipFile(OUT/(name+'.docx')) as archive:
            xml=etree.fromstring(archive.read('word/document.xml'))
            text=''.join(xml.xpath('//w:t/text()|//m:t/text()',namespaces=ns))
            if name=='main':
                displays=xml.xpath('//m:oMathPara',namespaces=ns)
                numbers=[]
                for element in displays:
                    value=''.join(element.xpath('.//m:t/text()',namespaces=ns))
                    numbers+=re.findall(r'\((\d+)\)',value[-12:])
                assert numbers==[str(i) for i in range(1,19)],numbers
                assert '式18取成本均值' in text
                assert 's3-ratio' not in text

def seal():
    assert not (OUT/'manifest.json').exists(),'Preserve existing seal.'
    check()
    files=sorted(p for p in OUT.rglob('*') if p.is_file() and p.name not in ['manifest.json','source-package.zip'] and p.suffix not in ['.log','.aux','.out','.gz'])
    page_counts={name:len(PdfReader(OUT/(name+'.pdf')).pages) for name in ['main','supplement']}
    previews={name:len(PdfReader(QA/('word-'+name)/'manuscript-preview.pdf').pages) for name in ['main','supplement']}
    records=[dict(path=p.relative_to(OUT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
    dump(OUT/'manifest.json',dict(schema='joconline-concision-v1',date='2026-10-12',
        status='editorial-and-visual-QA-complete-not-final-submission',pdf_pages=page_counts,
        word_preview_pages=previews,baseline_manifest_sha256=sha(BASE/'manifest.json'),
        files=records,new_simulations=0,new_bootstrap_replicates=0))
    with zipfile.ZipFile(OUT/'source-package.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in files+[OUT/'manifest.json']:archive.write(path,path.relative_to(OUT).as_posix())
    print(json.dumps(dict(pdf_pages=page_counts,word_preview_pages=previews,payload_files=len(records)),ensure_ascii=False))

if __name__=='__main__':
    {'check':check,'word':word,'seal':seal}[sys.argv[1]]()
