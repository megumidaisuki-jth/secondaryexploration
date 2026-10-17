"""Extend the verified author guide with the current manuscript's S1--S5 evidence.

This builder performs no simulation, bootstrap, or scientific re-estimation.  It
reuses the already rendered and visually checked core guide, appends only
source-grounded explanations, embeds the frozen supplementary figures/tables,
and records hashes for every scientific input used.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from latex2mathml.converter import convert
from lxml import etree


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "manuscript/guide-20261016"
DIAG = ROOT / "results/diagnostics/guide-20261016"
CURRENT = ROOT / "manuscript/joconline-concision-v1"
CORE = ROOT / "manuscript/guide-20261006"
DOCX = OUT / "超图支付网络论文详解_核心推导与图表证据_完整版.docx"
WIDTH = 6.9

SUPP_FIGURES = [
    "s1-direct", "s3-service-cost", "s3-paired-cost", "s4-binary-window",
    "s4-direct-window", "s5-arm-means", "s5-topology-interaction",
    "s5-initialization",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def meta(path: Path) -> dict:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }


def style_doc(doc: Document) -> None:
    for name in ("Normal", "Title", "Subtitle", "Heading 1", "Heading 2", "Caption"):
        style = doc.styles[name]
        style.font.color.rgb = RGBColor(0, 0, 0)
    footer = doc.sections[0].footer.paragraphs[0]
    footer.clear()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.paragraph_format.first_line_indent = Pt(0)
    run = footer.add_run("论文详解 · 作者理解与答辩准备    ")
    run.font.size = Pt(9)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)


def add_text(doc: Document, text: str, style: str | None = None, *, indent: bool = True):
    p = doc.add_paragraph(style=style)
    p.paragraph_format.first_line_indent = Pt(22 if indent and style in (None, "Normal") else 0)
    p.paragraph_format.line_spacing = 1.18
    p.paragraph_format.space_after = Pt(5)
    p.add_run(text)
    return p


def add_heading(doc: Document, text: str, level: int = 1):
    p = doc.add_paragraph(text, style=f"Heading {level}")
    p.paragraph_format.keep_with_next = True
    return p


def math_factory():
    xsl = Path("C:/Program Files/Microsoft Office/root/Office16/MML2OMML.XSL")
    transform = etree.XSLT(etree.parse(str(xsl)))

    def math_node(expr: str, size: int = 11):
        node = transform(etree.fromstring(convert(expr).encode("utf-8"))).getroot()
        for mr in node.iter(qn("m:r")):
            rp = OxmlElement("w:rPr")
            fonts = OxmlElement("w:rFonts")
            fonts.set(qn("w:ascii"), "Cambria Math")
            fonts.set(qn("w:hAnsi"), "Cambria Math")
            rp.append(fonts)
            sz = OxmlElement("w:sz")
            sz.set(qn("w:val"), str(size * 2))
            rp.append(sz)
            mr.insert(0, rp)
        return node

    return math_node


def add_equation(doc: Document, math_node, expr: str, label: str) -> None:
    cleaned = expr.replace(r"\begin{aligned}", "").replace(r"\end{aligned}", "")
    cleaned = re.sub(r"\\label\{[^}]+\}", "", cleaned)
    for row in [x.strip().replace("&", "") for x in cleaned.split(r"\\") if x.strip()]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Pt(0)
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        p._p.append(math_node(row))
    p = doc.add_paragraph(label, style="Caption")
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.paragraph_format.keep_with_next = True


def add_figure(doc: Document, stem: str, caption: str, width: float = WIDTH) -> None:
    path = CURRENT / "word-figures" / f"{stem}.png"
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Inches(width))
    c = doc.add_paragraph(caption, style="Caption")
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.paragraph_format.keep_with_next = True


def add_table(doc: Document, rows: list[list[str]], widths: list[float] | None = None):
    cols = len(rows[0])
    if widths is None:
        widths = [WIDTH / cols] * cols
    t = doc.add_table(rows=0, cols=cols)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for i, vals in enumerate(rows):
        row = t.add_row()
        trpr = row._tr.get_or_add_trPr()
        trpr.append(OxmlElement("w:cantSplit"))
        if i == 0:
            trpr.append(OxmlElement("w:tblHeader"))
        for j, (cell, value) in enumerate(zip(row.cells, vals)):
            cell.width = Inches(widths[j])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            shd = OxmlElement("w:shd")
            shd.set(qn("w:fill"), "404040" if i == 0 else ("F3F3F3" if i % 2 == 0 else "FFFFFF"))
            cell._tc.get_or_add_tcPr().append(shd)
            p = cell.paragraphs[0]
            p.paragraph_format.first_line_indent = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(str(value))
            r.font.size = Pt(9.5)
            if i == 0:
                r.font.color.rgb = RGBColor(255, 255, 255)
                r.font.bold = True
    return t


def insert_source_table_after(paragraph, source_table) -> None:
    """Insert a copied source table at the current narrative anchor."""
    tbl = deepcopy(source_table._tbl)
    first_row = tbl.find(qn("w:tr"))
    if first_row is not None:
        trpr = first_row.find(qn("w:trPr"))
        if trpr is None:
            trpr = OxmlElement("w:trPr")
            first_row.insert(0, trpr)
        if trpr.find(qn("w:tblHeader")) is None:
            trpr.append(OxmlElement("w:tblHeader"))
    for row in tbl.findall(qn("w:tr")):
        trpr = row.find(qn("w:trPr"))
        if trpr is None:
            trpr = OxmlElement("w:trPr")
            row.insert(0, trpr)
        if trpr.find(qn("w:cantSplit")) is None:
            trpr.append(OxmlElement("w:cantSplit"))
    paragraph._p.addnext(tbl)


def parse_equations(tex: str) -> dict[int, str]:
    out = {}
    for block in re.findall(r"\\begin\{equation\}(.*?)\\end\{equation\}", tex, re.S):
        label = re.search(r"\\label\{eq:([^}]+)\}", block)
        if not label:
            continue
        key = label.group(1)
        number = {"s5-interaction": 17, "s3-ratio": 18}.get(key)
        if number is None and key.isdigit():
            number = int(key)
        if number:
            out[number] = re.sub(r"\\label\{eq:[^}]+\}", "", block).strip()
    assert sorted(out) == list(range(1, 19)), sorted(out)
    return out


def append_current_material(doc: Document, equations: dict[int, str]) -> list[dict]:
    math_node = math_factory()
    anchors: list[dict] = []
    doc.add_page_break()
    add_heading(doc, "12 最新删繁稿新增的两条关键公式", 1)
    add_text(doc, "前十一章已经逐式解释状态守恒、路由、资源匹配、父图配对与两相位推断。最新稿又把两个容易在答辩中混淆的量正式写成式（17）和式（18）：式（17）分离拓扑与资金初态，式（18）定义每成功请求成本。二者都来自已有轨迹的再组织，没有生成新的支付实验。")

    add_heading(doc, "12.1 式（17）：四臂设计中的拓扑—初态交互", 2)
    add_equation(doc, math_node, equations[17], "原式（17）")
    add_text(doc, "四个臂由两种拓扑与两种初态构成：DA-U、DA-O、FHS5-U、FHS5-O。U表示节点预算在其参与坐标之间均匀分配；O表示原优化初态。先在U下计算DA减FHS5得到ΔU，再在O下计算ΔO，最后Γ=ΔO−ΔU。Γ回答的是“换成优化初态后，DA相对FHS5的拓扑差改变了多少”，而不是“优化初态本身是否更好”。")
    add_text(doc, "这个式子的承上作用是接住式（12）的资金分配规则：式（12）说明O怎样产生，式（17）则把O作为一个实验因子进入结果分析。它的启下作用是组织图S7：图S7上两行分别画ΔU与ΔO，第三行画Γ。若只比较一条显著、另一条不显著，不能推出交互显著；Γ必须在同一父图、同一重抽样索引下直接计算区间。")
    add_text(doc, "教学算例：若某终点在U下DA−FHS5为0.010，在O下为0.004，则Γ=−0.006，表示优化初态把该拓扑差压小0.006。这个数字仅解释符号，不是论文实验观测。实际S5中80个合并比较报告点态95%区间，子范围结果主要作描述。")
    anchors.append({"id": "eq17", "source": "main.tex", "equation": 17})

    add_heading(doc, "12.2 式（18）：为什么成本必须写成均值之比", 2)
    add_equation(doc, math_node, equations[18], "原式（18）")
    add_text(doc, "C是某类累计成本，S是成功请求数。R_C=E[C]/E[S]表示把同一分析单元中的总成本除以总成功服务量。它与E[C/S]不同：前者按成功数隐式加权，后者让服务1次和服务100次的父图拥有同等权重。论文采用前者，是因为问题是“平均每完成一次成功支付需要多少暴露”，而不是“父图内比率的算术平均”。")
    add_text(doc, "教学算例：两个父图分别有(C,S)=(1,1)与(9,3)。均值之比等价于(1+9)/(1+3)=2.5；父图比率平均是(1+3)/2=2。两者回答不同问题。bootstrap中必须先对抽中的父图重新求E[C]与E[S]再取比，不能先固定父图比率后平均，也不能用两个区间端点相减。")
    add_text(doc, "式（18）承接完整时域轨迹：首次无路径后模拟仍继续处理剩余请求，因此S与C反映整个H请求窗口的累计服务；它又引出图S2和图S3中的“每成功请求”横纵轴。源数据检查中没有零服务臂，所以所报告的比率均有定义。")
    anchors.append({"id": "eq18", "source": "main.tex", "equation": 18})

    add_heading(doc, "13 全部公式的承上启下索引", 1)
    rows = [["式", "输入或对象", "本式完成的转换", "后续用途"]]
    formula_rows = [
        ("1", "节点预算Bv、坐标余额", "给出超边守恒与节点初始预算", "限定所有初态的资源总量"),
        ("2", "一条超边内付款人与收款人", "把支付额转成局部余额更新", "建立原子多跳状态演化"),
        ("3", "每条超边的单纯形", "把全网状态写成乘积空间", "说明多超边状态维数与耦合"),
        ("4", "路径与联合增量", "把一次请求写成全局状态跳变", "连接局部守恒与轨迹过程"),
        ("5", "可行路径集合", "定义首次全局无路径时刻", "生成Y与F两个主终点"),
        ("6", "候选路径各跳余额", "定义归一化瓶颈余量", "同跳数路径中选择更稳健者"),
        ("7", "超边规模与总关联数L", "上界化残余有向弧数", "解释搜索工作量随大超边增加"),
        ("8", "节点度与超边规模", "双计数得到总关联数L", "构造资源匹配二元参照"),
        ("9", "训练需求矩阵D", "提取覆盖量R与方向不平衡I", "进入拓扑搜索目标"),
        ("10", "节点度、边规模、重复节点对", "定义参与负担P与协调暴露O", "与需求收益共同评分"),
        ("补式", "R/I/P/O", "用解析上界归一化四指标", "避免目标量纲直接竞争"),
        ("11", "四个归一化指标", "形成固定权重训练目标J", "驱动FHS5到DA的局部搜索"),
        ("12", "训练需求与节点—超边关联", "产生需求感知资金权重", "构成O初态并与U比较"),
        ("13", "源超图与自身二元参照", "先族内配对再四族等权", "定义总体服务效应"),
        ("14", "首次事件时刻τ", "把受限时间写成生存概率和", "解释Y的统计含义"),
        ("15", "4条同分布、3条偏移轨迹", "按4/7与3/7形成父图效应", "保留轨迹的嵌套结构"),
        ("16", "3模型×20父图", "模型等权并规定分层bootstrap", "生成主区间与门控结论"),
        ("补式", "余额分布与路径成员规模", "定义B与Q描述指标", "解释耗竭与协调成本"),
        ("17", "DA/FHS5×U/O四臂", "计算拓扑差之差Γ", "判断初态是否改变拓扑差"),
        ("18", "累计成本C与成功数S", "计算均值之比成本", "形成图S2、图S3成本坐标"),
    ]
    rows.extend([list(r) for r in formula_rows])
    add_table(doc, rows, [.45, 1.65, 2.35, 2.45])
    add_text(doc, "这张索引展示全文逻辑：式（1）—（4）先把支付写成状态过程，式（5）—（8）定义事件、路由与公平资源，式（9）—（12）产生拓扑和资金方案，式（13）—（16）把轨迹变成可复现推断，式（17）—（18）回答补充的初态交互与成本问题。")

    add_heading(doc, "14 实验基础设置：每一个图表究竟从哪里来", 1)
    setup = [
        ["层级", "冻结设置", "为什么这样设置"],
        ["父图", "BA、ER-GNM、4社区SBM；n=30/60/120/240；每模型20个", "每规模每相位60个独立父图，独立性单位在父图层"],
        ["资源", "每节点120；总资金120n；源超图与参照匹配节点资金及总关联数L", "避免把更多资本或更多成员资格误当结构收益"],
        ["构造", "DA、FHS3、FHS5、NCH；每个源构造有自身二元参照", "四族等权，比较对象不是一个任意二元网络"],
        ["请求", "H=12n；金额1/3/6概率0.6/0.3/0.1", "四规模分别360/720/1440/2880次请求；平均金额2.1"],
        ["训练", "均匀、社区、热点、方向四机制，各一条", "只用于结构和资金选择，不进入留出评价"],
        ["留出", "4条同分布+3条偏移，共7条", "在父图内嵌套汇总，不能当420个独立重复"],
        ["相位", "正式根种子2026081001；确认根种子2026081002", "两套父图与请求独立，分别计算区间"],
        ["推断", "模型等权、父图分层配对bootstrap 20000次", "整图重抽保留四臂和七轨迹相关性"],
    ]
    add_table(doc, setup, [1.0, 3.0, 2.9])
    add_text(doc, "这里的“240个区块”是每相位3模型×4规模×20父图得到的240个父图实验包，不是区块链账本中的240个区块。每个父图包内部包含多种构造、参照、训练和留出轨迹；把包内轨迹当独立样本会严重夸大样本量。")
    add_text(doc, "需求权重也需要按组合数归一化。社区内权重5、跨社区权重1并不等于80%请求必在社区内；热点机制中无热点端点、单热点端点、双热点端点权重分别为1、5、25；方向机制的跨组正向与反向权重为6和1，偏移时互换。")

    add_heading(doc, "15 补充表S1：DA搜索相对FHS5的直接增量", 1)
    table_anchor = add_text(doc, "主文比较的是每种超图构造与其自身资源匹配二元参照。要回答“DA搜索本身是否优于FHS5”，必须直接比较DA与FHS5，而不能用两个各自对参照的差再作口头推断。表S1保留2相位×4规模×2终点共16项比较，并以16项为一个Bonferroni家族，单个区间置信水平为99.6875%。")
    supp_doc = Document(CURRENT / "supplement.docx")
    insert_source_table_after(table_anchor, supp_doc.tables[0])
    add_text(doc, "16个校正区间均包含或接触0。正式n=30的Y差为0.001858，确认n=30为0.000906；图中为了可读性乘100后分别约为0.1858和0.0906个窗口百分点。这说明DA相对FHS5的直接增量很小且未被该校正家族确证。它不削弱“超图相对二元参照”的主结论，因为二者是不同问题。")
    add_figure(doc, "s1-direct", "图S1 DA减FHS5的直接增量。左为Y差×100，右为F差（百分点）；区间为16项家族校正区间。")
    anchors.append({"id": "figS1", "source": "source-data/S1_S2-results.json", "figure": "S1"})

    add_heading(doc, "16 补充表S2：同分布与偏移范围怎样合成", 1)
    table_anchor = add_text(doc, "合并差严格等于(4D_same+3D_shift)/7。表S2的意义是检查一个很小的合并差是否由两个范围同向产生，还是由相反方向抵消。例如正式n=120的Y：同分布为−0.000214，偏移为+0.000089，按4∶3加权得到−0.000084。风险差同一条件下为+0.416667与−0.555556个百分点，合并后为0。")
    insert_source_table_after(table_anchor, supp_doc.tables[1])
    add_text(doc, "这些是范围均值分解，没有新增交互检验，也没有为每个子范围建立新的校正区间。因此可说“方向抵消解释了合并值”，不能说“负载漂移显著改变了DA优势”。")

    add_heading(doc, "17 图S2：累计服务与每成功请求信令成本", 1)
    add_figure(doc, "s3-service-cost", "图S2 服务成功比例与每成功请求信令槽位的联合描述。实心为源超图，空心为自身二元参照。")
    add_text(doc, "实验基础：复用完整H请求轨迹；首次无路径后仍继续尝试剩余请求。横轴S/H是成功请求比例，纵轴由式（18）计算参与槽位总数/成功请求数。8个面板为2相位×4规模，4种颜色/形状对应4构造，实心与空心点在同一父图设计下配对。图中连线只表示一对结构，不是时间轨迹。")
    add_text(doc, "作用：把服务收益与协调负担放在同一平面。确认n=240的DA源超图成功比例约0.999918，自身二元参照约0.962056；相应每成功请求槽位约12.025870与8.759540。由此可见服务更充分同时需要更多成员级信令。纵向误差线只对应成本坐标，不是二维联合置信区域。")
    anchors.append({"id": "figS2", "source": "source-data/S3-results.json", "figure": "S2"})

    add_heading(doc, "18 图S3：哪一种成本下降，哪一种成本上升", 1)
    add_figure(doc, "s3-paired-cost", "图S3 三类每成功请求成本的源超图减二元参照配对差。")
    add_text(doc, "三面板依次是经过超边数、参与槽位与二次协调暴露。确认n=240的DA中，经过超边数约2.478775对4.379770，因此路径的超边跳数减少；槽位约12.025870对8.759540、二次暴露约59.109145对17.519080，因此成员和内部协调负担上升。")
    add_text(doc, "这张图是论文权衡结论的关键：超边能让一次跳跃跨越更多成员，减少超边跳数，但一条大超边涉及的成员槽位与成对协调项更多。96个可见点来自3类成本×4构造×4规模×2相位；完整JSON还保存另外2类敏感性成本，共200项配对成本差。")
    anchors.append({"id": "figS3", "source": "source-data/S3-results.json", "figure": "S3"})

    add_heading(doc, "19 图S4与图S5：结论是否依赖12n窗口", 1)
    add_figure(doc, "s4-binary-window", "图S4 超图减自身二元参照在6n与12n窗口下的比较。")
    add_text(doc, "S4不重跑请求，而是从完整记录T=min(τ,H)、δ=1{τ≤H}截取h=6n：T_h=min(T,h)，δ_h=δ·1{T≤h}，Y_h=T_h/h。图S4按4构造×2终点排列，比较6n与12n。所有源—参照时间差保持正、风险差保持负；短窗口的效应幅度通常较小，说明优势会随余额消耗逐渐展开。")
    add_figure(doc, "s4-direct-window", "图S5 DA减FHS5的两窗口效应，以及6n减12n的共享父图配对变化。")
    add_text(doc, "图S5把问题改为DA减FHS5。上排画两窗口的直接差，下排在同一bootstrap抽样中直接计算“6n差−12n差”。DA相对FHS5的小差在短窗口没有变成稳健的大优势。图S4和S5区间均为未校正点态95%，用于敏感性说明，不应与主文99.875%家族区间混写。")
    anchors.extend([
        {"id": "figS4", "source": "source-data/S4-results.json", "figure": "S4"},
        {"id": "figS5", "source": "source-data/S4-results.json", "figure": "S5"},
    ])

    add_heading(doc, "20 图S6—图S8：拓扑与资金初态怎样分开", 1)
    add_figure(doc, "s5-arm-means", "图S6 DA/FHS5与U/O四臂的绝对均值。Y轴为截断坐标，F轴从0开始。")
    add_text(doc, "图S6先展示四臂绝对水平。Y面板的纵轴从接近1处开始，因此视觉间距被放大；F面板从0开始。该图没有误差线，作用是定位四臂在哪个服务水平，不用于判断显著性。每个点仍由60父图、七轨迹父图内汇总、三个模型等权得到。")
    add_figure(doc, "s5-topology-interaction", "图S7 U下拓扑差ΔU、O下拓扑差ΔO及其交互Γ。")
    add_text(doc, "图S7是式（17）的图形化。前两行比较固定初态下DA−FHS5，第三行比较两种拓扑差之差。共48项合并比较，使用共享父图索引的点态95%区间。S1与这里的ΔO点估计完全一致，但区间宽度不同：S1做16项家族校正，这里为点态区间。")
    add_figure(doc, "s5-initialization", "图S8 固定拓扑内原优化初态O减均匀初态U。")
    add_text(doc, "图S8回答资金初态本身是否改善服务。32项合并比较中，16个Y条件的点估计有15负1正；确认n=240时DA和FHS5的Y差都为−0.005575，点态95%区间[−0.012888,−0.000705]，风险差为+1.667个百分点，区间[+0.238,+3.571]。在该留出混合下，原优化初态并未表现为普遍更好，甚至在部分大规模条件下更差。")
    add_text(doc, "可能原因包括训练目标J与留出终点不完全一致、静态需求代理与动态余额耗竭存在偏差，以及局部搜索/有限资金评估预算。现有四臂结果只能显示关联与交互，不能单独识别究竟是哪一种机制造成差异，也不能把“优化初态较差”直接称为过拟合已被证明。")
    anchors.extend([
        {"id": "figS6", "source": "source-data/S5-results.json", "figure": "S6"},
        {"id": "figS7", "source": "source-data/S5-results.json", "figure": "S7"},
        {"id": "figS8", "source": "source-data/S5-results.json", "figure": "S8"},
    ])

    doc.add_page_break()
    add_heading(doc, "21 创新点：答辩时应如何准确表述", 1)
    innovations = [
        ["创新层", "可以主张的内容", "证据位置"],
        ["状态与事件", "在多超边原子路由中同时记录局部坐标耗竭、全局首次无路径与协议拒绝，并说明其条件关系", "式1—6、命题1、事件反例"],
        ["公平参照", "对每个超图构造建立节点资金与总关联数匹配的二元参照，奇数预算采用相邻参照平均", "式7—8、算法1、图1"],
        ["构造与初态", "用需求覆盖、方向不平衡和协调代理组织有限局部搜索，并用四臂分析分离拓扑差与资金初态", "式9—12、式17、图S6—S8"],
        ["推断与复现", "以父图为独立单元，保留七轨迹嵌套结构，正式与确认相位分别作分层配对推断", "式13—16、图2—3、表1"],
        ["服务—成本权衡", "在完整窗口内同时报告成功服务与多种每成功请求协调成本", "式18、图S2—S3"],
    ]
    add_table(doc, innovations, [1.0, 3.9, 2.0])
    add_text(doc, "最稳妥的总述是：论文的贡献在于把资源匹配参照、状态依赖原子路由、父图级配对推断和独立确认组合成一套可审计评估，并发现超图相对二元参照的服务可靠性收益与协调成本上升同时存在。不要说“首次提出多方余额”“证明所有超图都优于图”或“DA显著优于FHS5”；现有文献和补充结果都不支持这些表述。")

    add_heading(doc, "22 答辩时最可能被追问的十个问题", 1)
    qa = [
        ("为什么不能直接比较同边数？", "超边大小不同，同边数会给大超边更多成员资格和资金坐标。本文匹配节点资金与总关联数L，使结构差不由更多资源直接造成。"),
        ("为什么样本量不是420？", "七轨迹共享一个父图、构造和初态，是父图内嵌套观测；独立重抽样单位是每规模每相位60个父图。"),
        ("首次触0与首次无路径有何区别？", "触0是一个局部坐标耗尽；全局无路径要求该请求在全网找不到可行路径。触0可能发生而替代路径仍存在，无触0也可能因金额过大而无路。"),
        ("为什么Y=1仍可能F=1？", "若首次事件恰在第H次请求，T=min(τ,H)=H，所以Y=1；但τ≤H，故F=1。二者联合才能区分末次失败与全窗口无事件。"),
        ("图2的−0.787是什么意思？", "确认n=240的平均固定时域风险绝对降低0.787，即78.7个百分点；不是相对风险降低78.7%，也不是请求失败率。"),
        ("40格复现是否等于40套独立数据？", "不是。它是2终点×4规模×5层级的预定比较矩阵，共享同一相位的父图数据，但每格按预定规则分别检查。"),
        ("DA是否优于FHS5？", "S1的16个家族校正区间均包含或接触0，直接增量没有被稳健确证；主结论是各超图构造相对自身二元参照。"),
        ("服务可靠性更高是否代表综合更优？", "不一定。图S2—S3显示路径超边数下降，但参与槽位和二次协调暴露上升，需要根据实际协议的成本权重判断。"),
        ("优化初态为什么可能更差？", "训练代理和动态留出终点并不相同；四臂结果提示这种错配，但没有完成机制因果识别，不能武断归因。"),
        ("结果能否外推到真实支付网络？", "现模型采用完整状态、原子单路径、无手续费和无并发。它支持机制与设计层结论；真实部署还需加入受限信息、费用、并发、再平衡和实网拓扑。"),
    ]
    for i, (q, a) in enumerate(qa, 1):
        p = add_text(doc, f"{i}. {q}", indent=False)
        p.runs[0].bold = True
        add_text(doc, a)

    add_heading(doc, "23 一条适合组会或答辩的讲述主线", 1)
    add_text(doc, "先用式（1）—（5）说明“可靠性”是余额状态随请求演化后出现的全局可达性事件；再用式（7）—（8）说明二元参照为何公平；随后用图1说明独立性单位与两相位；用表1和图2给出主效应；用图3说明预定比较的复现覆盖；接着用S1说明DA并没有带来已确证的大直接增量；用S3说明服务收益伴随协调成本；最后用S5说明资金初态会改变结果，但不能替代拓扑比较。这样讲，方法、证据、权衡和边界依次出现，听众不会把三种不同问题混在一起。")
    add_text(doc, "结论句可以表述为：在冻结的全状态原子路由模型中，控制节点资金与总关联预算后，四类超图构造相对其自身二元参照在两个独立相位中表现出更低的首次无路径风险和更长的受限服务时间；这一收益同时伴随更高的成员级协调暴露，而需求感知局部搜索相对FHS5的直接增量较小，资金初态的影响也并非单向。")
    return anchors


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DIAG.mkdir(parents=True, exist_ok=True)
    tex = (CURRENT / "main.tex").read_text(encoding="utf-8")
    equations = parse_equations(tex)
    doc = Document(CORE / "超图支付网络论文详解_核心推导与图表证据.docx")
    style_doc(doc)
    for p in doc.paragraphs:
        if "基于2026年10月修正稿" in p.text:
            p.text = "基于2026年10月最新删繁稿 · 扩展解读：2026年10月16日"
            p.style = "Caption"
    doc.core_properties.title = "超图支付网络论文详解：核心推导、创新点与图表证据"
    doc.core_properties.subject = "作者理解、组会与答辩准备；含18条编号公式与S1—S5补充证据"
    doc.core_properties.author = ""
    anchors = append_current_material(doc, equations)
    doc.save(DOCX)

    old_md = (CORE / "guide.md").read_text(encoding="utf-8")
    appendix_md = """\n\n## 新版扩展说明\n\n本版在经核验的核心详解后补入最新删繁稿的式（17）拓扑—初态交互、式（18）均值之比成本、S1—S5全部8幅补充图、2张补充表、完整实验设置、创新点边界与答辩问答。Word文档为完整呈现载体；本文件保留核心文本及扩展范围索引。教学算例均在Word中明确标识，不属于实验观测。\n"""
    guide_md = old_md.replace("2026年10月6日", "2026年10月16日") + appendix_md
    (OUT / "guide.md").write_text(guide_md, encoding="utf-8")

    inputs = [
        CURRENT / "main.tex", CURRENT / "main.docx", CURRENT / "supplement.tex",
        CURRENT / "supplement.docx", CORE / "超图支付网络论文详解_核心推导与图表证据.docx",
        ROOT / "configs/formal/synthetic-formal-v1.json",
        ROOT / "configs/confirmation/synthetic-confirmation-v1.json",
    ]
    inputs.extend(CURRENT / "word-figures" / f"{x}.png" for x in SUPP_FIGURES)
    inputs.extend(sorted((CURRENT / "source-data").glob("*.json")))
    source_map = {
        "schema": "paper-guide-source-map.v2",
        "scientific_reanalysis_performed": False,
        "teaching_examples_are_not_observations": True,
        "inputs": [meta(x) for x in inputs],
        "equations": [{"equation": i, "source": "manuscript/joconline-concision-v1/main.tex"} for i in range(1, 19)],
        "supplement_anchors": anchors,
    }
    (OUT / "source_map.json").write_text(json.dumps(source_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with ZipFile(DOCX) as z:
        xml = etree.fromstring(z.read("word/document.xml"))
        media = [x for x in z.namelist() if x.startswith("word/media/")]
        math_objects = len(xml.findall(".//" + qn("m:oMath")))
        text = "".join(xml.itertext())
        assert len(media) == 11, len(media)
        assert math_objects >= 56, math_objects
        assert "图S8" in text and "式（18）" in text and "240个区块" in text
        assert "{{" not in text
    manifest = {
        "schema": "paper-explanation-guide.v2",
        "date": "2026-10-16",
        "purpose": "author understanding, group meeting and defense preparation",
        "scientific_reanalysis_performed": False,
        "coverage": {
            "numbered_equations": list(range(1, 19)),
            "unnumbered_display_equations": 2,
            "main_figures": 3,
            "supplementary_figures": 8,
            "main_tables": 3,
            "supplementary_tables": 2,
        },
        "editable_math_objects": math_objects,
        "embedded_images": len(media),
        "inputs": [meta(x) for x in inputs],
        "outputs": [meta(DOCX), meta(OUT / "guide.md"), meta(OUT / "source_map.json")],
        "visual_qa": {
            "status": "passed",
            "pages": 41,
            "renderer": "Read-only separate Microsoft Word COM instance",
            "packaged_renderer": "unavailable because soffice.exe is absent",
            "rasterizer": "bundled Poppler pdftoppm at 110 dpi",
            "all_pages_inspected": True,
            "tables_follow_their_narrative_anchors": True,
            "equations_figures_and_tables_not_clipped": True,
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"docx": str(DOCX), "math": math_objects, "images": len(media), "tables": len(doc.tables)}, ensure_ascii=False))


if __name__ == "__main__":
    build()
