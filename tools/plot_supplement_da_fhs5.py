"""S1 direct-ablation forest plot; all 16 rows retained; no simulated data."""
import csv
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/supplement/da-fhs5-posthoc-v1'
RESULT = OUT / 'results.json'
data = json.loads(RESULT.read_bytes())
verification = json.loads((OUT / 'verification.json').read_bytes())
assert verification['status'] == 'passed'
assert verification['results_sha256'] == hashlib.sha256(RESULT.read_bytes()).hexdigest()
rows = data['comparisons']
assert len(rows) == 16
font_manager.fontManager.addfont('C:/Windows/Fonts/msyh.ttc')
plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
                     'font.size': 8, 'axes.labelsize': 8, 'axes.titlesize': 9,
                     'svg.fonttype': 'none', 'pdf.fonttype': 42,
                     'axes.unicode_minus': False, 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.linewidth': .7, 'legend.frameon': False})
fig, axes = plt.subplots(1, 2, figsize=(6.692913386, 4.133858268))  # 170 x 105 mm
fig.subplots_adjust(left=.105, right=.975, bottom=.23, top=.80, wspace=.28)
colors = {'formal': '#33638D', 'confirmation': '#C27B35'}
markers = {'formal': 'o', 'confirmation': 's'}
metrics = ['normalized_restricted_tau_nopath', 'failure_risk']
for col, (ax, metric) in enumerate(zip(axes, metrics)):
    for r in rows:
        if r['metric'] != metric:
            continue
        y = [30, 60, 120, 240].index(r['node_count']) + (-.12 if r['phase'] == 'formal' else .12)
        values = r['display']; center = values['estimate']*100
        lo, hi = values['adjusted_lower']*100, values['adjusted_upper']*100
        assert lo <= center <= hi
        ax.errorbar(center, y, xerr=[[center-lo], [hi-center]], fmt=markers[r['phase']], color=colors[r['phase']],
                    markersize=4.1, capsize=2.5, elinewidth=1, markeredgewidth=.7)
    ax.axvline(0, color='#666666', linestyle='--', linewidth=.7, zorder=0)
    ax.set_yticks([0, 1, 2, 3], ['30', '60', '120', '240'])
    ax.set_ylim(3.45, -.45)
    ax.set_title('归一化受限时间' if col == 0 else '首次无路径风险', pad=11)
    ax.set_xlabel('DA − FHS5 的 ΔY × 100\n正值有利于 DA' if col == 0 else 'DA − FHS5 的 ΔF（百分点）\n负值有利于 DA', labelpad=8)
    ax.text(-.12, 1.065, 'a' if col == 0 else 'b', transform=ax.transAxes, fontsize=9, fontweight='bold')
    ax.tick_params(width=.7, length=3)
axes[0].set_ylabel('节点数')
axes[0].set_xlim(-.10, .55)
axes[1].set_xlim(-3.9, .45)
handles = [Line2D([], [], color=colors[p], marker=markers[p], linestyle='none', markersize=4,
                  label='正式相位' if p == 'formal' else '确认相位') for p in colors]
fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(.55,.95), ncol=2)
fig.text(.5,.035,'后验探索性分析 · 每点 60 个独立父图 · 全部 16 项校正区间均包含零', ha='center', fontsize=7)
base = OUT / 'figure-s1-da-fhs5'
fig.savefig(base.with_suffix('.svg'), facecolor='white')
fig.savefig(base.with_suffix('.pdf'), facecolor='white')
fig.savefig(base.with_suffix('.tiff'), dpi=600, facecolor='white', pil_kwargs={'compression': 'tiff_lzw'})
fig.savefig(base.with_suffix('.png'), dpi=300, facecolor='white')
plt.close(fig)
with (OUT / 'figure-s1-source.csv').open('w', encoding='utf-8-sig', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow(['phase', 'nodes', 'metric', 'independent_parents', 'estimate', 'adjusted_lower', 'adjusted_upper', 'plot_multiplier', 'exact_estimate', 'exact_lower', 'exact_upper'])
    for r in rows:
        d = r['display']; e = r['exact']
        writer.writerow([r['phase'], r['node_count'], r['metric'], 60, d['estimate'], d['adjusted_lower'], d['adjusted_upper'], 100, str(e['estimate']), str(e['adjusted_lower']), str(e['adjusted_upper'])])
print(base.with_suffix('.png'))
