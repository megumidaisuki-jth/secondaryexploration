"""Reproducible manuscript displays from archived, complete synthetic evidence.

No raw-block reads, simulations, bootstrap reruns, or result-dependent selection.
Run from the project root: python -m tools.build_results_displays
"""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import json
from pathlib import Path
import platform

from tools import export_source_data as source

ROOT = source.ROOT
OUT = ROOT / "manuscript/generated/synthetic-v1"
SOURCE_SHA = "50fd83d81d54cfaf7198b3307f10a51d4a1f555b94ab06975e2d3b0b3d8e30f4"
SOURCE_FP = "d82d90b43938efead325d1d2773f064b32e557d6776f3851c2cb7d37b0e5857d"
METRICS = ("failure_risk", "normalized_restricted_tau_nopath")
SIZES = (30, 60, 120, 240)
FAMILIES = ("demand-aware", "fhs3", "fhs5", "global", "nch")
IDS = tuple(f"{m}.n{n:04d}.{s}" for m in METRICS for n in SIZES for s in FAMILIES)
STATES = ("independently_confirmed", "formal_only", "confirmation_only", "neither")
SHORT = {"beneficial": "B", "harmful": "H", "inconclusive": "I"}
LABELS = {"failure_risk": "Failure risk", "normalized_restricted_tau_nopath": "Restricted no-path time / H"}
STATISTICS = (
    "Each contrast uses n=60 independent parent graphs per phase: 20 BA, 20 ER-GNM, "
    "and 20 fixed-count SBM graphs. Seven held-out traffic traces are nested within "
    "each parent and do not increase n. Contrasts are source minus the equal mean "
    "of its registered resource-matched binary arms; global contrasts equally average "
    "the four source-family contrasts. Failure-risk differences are probability "
    "differences (negative is beneficial); restricted no-path time is divided by "
    "H=12 times node count (positive is beneficial). Bounds are multiplicity-adjusted "
    "percentile interval bounds from 20,000 parent-stratified bootstrap resamples, "
    "with adjusted empirical probability 1/1600 in each tail and local confidence "
    "parameter 159/160. The studywise 95% family covers 40 contrasts separately "
    "within each phase, not 80 jointly; phases are not pooled. Exact fractions, "
    "all 40 contrasts per phase, and JSON source pointers are in numerical-registry.json "
    "and the linked Source Data. No p values are inferred from bounds."
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def frac(value):
    require(isinstance(value, list) and len(value) == 2, "invalid fraction")
    require(all(type(x) is int for x in value) and value[1] > 0, "invalid fraction components")
    return Fraction(*value)


def decimal(value):
    """Exact integer rounding to three places, ties to even, no negative zero."""
    v = frac(value)
    scaled = round(v * 1000)
    return ("-" if scaled < 0 else "") + f"{abs(scaled)//1000}.{abs(scaled)%1000:03d}"


def interval_direction(row):
    lo, hi = frac(row["lower"]), frac(row["upper"])
    require(lo <= hi, "reversed bounds")
    direction = row["beneficial_direction"]
    require(direction in ("positive", "negative"), "invalid beneficial direction")
    if lo <= 0 <= hi:
        return "inconclusive"
    return "beneficial" if (lo > 0) == (direction == "positive") else "harmful"


def point_direction(row):
    value = frac(row["estimate"])
    if value == 0:
        return "zero"
    return "beneficial" if (value > 0) == (row["beneficial_direction"] == "positive") else "harmful"


def check_registry(data):
    """Independent exact-arithmetic reporting checks, including gates and states."""
    intervals = {}
    for phase in source.PHASES:
        rows = data["phase_data"][phase]["registered_intervals"]
        require(tuple(r["contrast_id"] for r in rows) == IDS, f"{phase}: incomplete/reordered registry")
        intervals[phase] = {r["contrast_id"]: r for r in rows}
        for row in rows:
            expected_direction = "negative" if row["metric"] == "failure_risk" else "positive"
            require(row["beneficial_direction"] == expected_direction, "beneficial direction differs")
            require(row["phase"] == phase and row["parent_count"] == 60, "phase or n differs")
            require(row["stratum_parent_counts"] == [["barabasi_albert", 20], ["er_gnm", 20], ["sbm_fixed_count", 20]], "strata differ")
            require(row["resamples"] == 20000 and row["confidence_level"] == [159, 160], "bootstrap contract differs")
            require(row["tail_probability"] == row["adjusted_tail_probability"] == [1, 1600], "tails differ")
            global_id = f"{row['metric']}.n{row['node_count']:04d}.global"
            is_global = row["contrast_id"] == global_id
            require(row["tier"] == ("global" if is_global else "secondary"), "tier differs")
            gate = "not_applicable" if is_global else ("open" if interval_direction(intervals[phase][global_id]) == "beneficial" else "closed")
            require(row["gate_state"] == gate, "global gate differs")
            require(row["beneficial_effect_supported"] == (interval_direction(row) == "beneficial" and gate != "closed"), "support flag differs")
    records = data["cross_phase_replication_records"]
    require(tuple(r["contrast_id"] for r in records) == IDS, "replication registry differs")
    for rep in records:
        successes, points = [], []
        for phase in source.PHASES:
            row = intervals[phase][rep["contrast_id"]]
            for field in ("metric", "node_count", "tier", "beneficial_direction"):
                require(rep[field] == row[field], f"replication {field} differs")
            direction = interval_direction(row)
            success = direction == "beneficial" and row["gate_state"] != "closed"
            require(rep[f"{phase}_interval_direction"] == direction, "replication direction differs")
            require(rep[f"{phase}_gate_state"] == row["gate_state"], "replication gate differs")
            require(rep[f"{phase}_phase_success"] == success, "phase success differs")
            point = point_direction(row)
            require(rep[f"{phase}_point_direction"] == point, "point direction differs")
            successes.append(success)
            points.append(point)
        state = "independently_confirmed" if all(successes) else "formal_only" if successes[0] else "confirmation_only" if successes[1] else "neither"
        require(rep["replication_state"] == state, "replication state differs")
        agreement = "one_or_both_zero" if "zero" in points else f"same_{points[0]}" if points[0] == points[1] else "opposite"
        require(rep["point_sign_agreement"] == agreement, "point agreement differs")
    return intervals


def load_checked():
    from tools.formal_inference import validate_phase_evidence, validate_replication_evidence
    from tools.formal_descriptive_projection import validate_phase_projection
    require(source.digest(source.OUTPUT) == SOURCE_SHA, "archived Source Data bytes changed")
    data = source.load_json(source.OUTPUT)
    body = {k: v for k, v in data.items() if k != "content_fingerprint"}
    require(data["content_fingerprint"] == SOURCE_FP == source.canonical_digest(body), "Source Data fingerprint differs")
    require(data == source.build(), "Source Data no longer matches source evidence")
    evidences = {}
    for phase in source.PHASES:
        paths = source.phase_paths(phase)
        evidence = source.load_json(paths["phase_evidence"])
        validate_phase_evidence(evidence)
        projection = source.load_json(paths["descriptive_evidence"])
        validate_phase_projection(projection)
        summary = source.load_json(paths["run_summary"])
        require(summary["completed_block_count"] == summary["expected_block_count"] == 240, "block count differs")
        require(evidence["source_fingerprints"]["run_summary"] == summary["summary_fingerprint"] == projection["source_fingerprints"]["run_summary"], "summary binding differs")
        evidences[phase] = evidence
    replication = source.load_json(ROOT / "results/inference/formal-confirmation-replication-evidence.json")
    validate_replication_evidence(replication)
    for phase in source.PHASES:
        require(replication[f"{phase}_evidence_fingerprint"] == evidences[phase]["evidence_fingerprint"], "cross-phase source binding differs")
    for stage, receipt in data["independent_replay_receipts"].items():
        path = ROOT / receipt["output"]
        require(receipt["stage"] == stage and receipt["exit_code"] == 0, "replay receipt identity differs")
        require(path.stat().st_size == receipt["output_bytes"] and source.digest(path) == receipt["output_sha256"], "replay receipt bytes differ")
    check_registry(data)
    return data


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def numerical_outputs(data):
    phase_rows = []
    for phase in source.PHASES:
        for index, row in enumerate(data["phase_data"][phase]["registered_intervals"]):
            phase_rows.append({**{k: v for k, v in row.items() if k != "bootstrap_values"},
                "source_pointer": f"/phase_data/{phase}/registered_intervals/{index}",
                "interval_direction": interval_direction(row),
                "display": {k: decimal(row[k]) for k in ("estimate", "lower", "upper")}})
    reps = [{**row, "source_pointer": f"/cross_phase_replication_records/{i}"}
            for i, row in enumerate(data["cross_phase_replication_records"])]
    write_json(OUT / "numerical-registry.json", {"source_sha256": SOURCE_SHA,
        "source_content_fingerprint": SOURCE_FP, "phase_intervals": phase_rows,
        "cross_phase_replication": reps,
        "note": "Bootstrap arrays remain in canonical Source Data; no registered contrast omitted."})
    indexed = {(r["phase"], r["contrast_id"]): r for r in phase_rows}
    table = []
    md = ["# Table 1 | Global resource-matched contrasts", "", STATISTICS, "",
        "| Endpoint | Nodes | Formal estimate [lower, upper] | Formal direction | Confirmation estimate [lower, upper] | Confirmation direction | n per phase (BA+ER+SBM) | Replication state |",
        "|---|---:|---|---|---|---|---|---|"]
    for rep in reps:
        if rep["tier"] != "global":
            continue
        f, c = (indexed[(p, rep["contrast_id"])] for p in source.PHASES)
        table.append({"contrast_id": rep["contrast_id"], "formal": f, "confirmation": c, "replication": rep})
        def text(r):
            d = r["display"]
            return f"{d['estimate']} [{d['lower']}, {d['upper']}]"
        md.append(f"| {LABELS[rep['metric']]} | {rep['node_count']} | {text(f)} | {f['interval_direction']} | {text(c)} | {c['interval_direction']} | 60 (20+20+20) | {rep['replication_state'].replace('_', ' ')} |")
    require(len(table) == 8, "global table row count differs")
    write_json(OUT / "table-1.json", table)
    (OUT / "table-1.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def render(data):
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Patch
    from matplotlib.lines import Line2D
    mpl.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 7, "axes.titlesize": 8, "axes.labelsize": 7,
        "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
        "svg.fonttype": "none", "pdf.fonttype": 42, "svg.hashsalt": "synthetic-v1",
        "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6})
    def save(fig, name):
        fig.savefig(OUT / f"{name}.svg", metadata={"Date": None})
        fig.savefig(OUT / f"{name}.pdf", metadata={"CreationDate": None, "ModDate": None})
        fig.savefig(OUT / f"{name}.png", dpi=300)
        plt.close(fig)

    # Figure 1: result-free code-native schematic, not an AI-generated image.
    fig, ax = plt.subplots(figsize=(183/25.4, 77/25.4))
    fig.subplots_adjust(left=.025, right=.975, bottom=.06, top=.97)
    ax.set(xlim=(0, 1), ylim=(0, 1)); ax.axis("off")
    def box(x, y, w, h, title, content):
        ax.add_patch(Rectangle((x, y), w, h, facecolor="#eef2f5", edgecolor="#83929e", linewidth=.7))
        ax.text(x+w/2, y+h-.035, title, ha="center", va="top", weight="bold")
        ax.text(x+w/2, y+h/2-.025, content, ha="center", va="center", linespacing=1.45)
    box(.01, .62, .29, .34, "Independent parent graphs", "Sizes: 30, 60, 120, 240\n20 BA + 20 ER-GNM + 20 SBM\n60 parents per size and phase")
    box(.355, .62, .29, .34, "Paired held-out traffic", "7 traces nested per parent\nResource-matched binary arms\nFour source-family contrasts")
    box(.70, .62, .29, .34, "Registered endpoints", "Failure risk at horizon H\nRestricted no-path time / H\nH = 12 × node count")
    box(.10, .20, .34, .26, "Formal phase", "240 blocks; 40 contrasts\nParent-stratified adjusted bounds")
    box(.56, .20, .34, .26, "Independent confirmation phase", "New phase; same frozen analysis\n240 blocks; 40 contrasts")
    ax.plot([.27,.84,.84], [.54,.54,.62], color="#526578", linewidth=.9)
    ax.text(.50,.565,"Same registered protocol, separate phase data",ha="center",va="bottom")
    for start, end in [((.30,.79),(.355,.79)), ((.645,.79),(.70,.79)),
                       ((.73,.54),(.73,.46)), ((.27,.54),(.27,.46))]:
        ax.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "->", "color": "#526578", "lw": .9})
    ax.text(.5, .065, "Separate phase families → complete 40-contrast replication registry → source-linked displays", ha="center")
    save(fig, "figure-1-design")

    intervals = check_registry(data)
    colors, markers = ("#246b8e", "#b46528"), ("o", "s")
    fig, axes = plt.subplots(1, 2, figsize=(183/25.4, 82/25.4))
    fig.subplots_adjust(left=.09, right=.98, bottom=.28, top=.81, wspace=.28)
    for panel, (ax, metric) in enumerate(zip(axes, METRICS)):
        ax.text(-.12, 1.19, "ab"[panel], transform=ax.transAxes, weight="bold", fontsize=8)
        ax.set_title(LABELS[metric], pad=13)
        for j, phase in enumerate(source.PHASES):
            for i, size in enumerate(SIZES):
                row = intervals[phase][f"{metric}.n{size:04d}.global"]
                y = i + (-.13 if j == 0 else .13)
                lo, hi, estimate = (float(frac(row[k])) for k in ("lower", "upper", "estimate"))
                ax.plot([lo, hi], [y, y], color=colors[j], linewidth=1.2)
                ax.plot(estimate, y, marker=markers[j], color=colors[j], markersize=4)
        left, right = ax.get_xlim()
        span = max(right, 0) - min(left, 0)
        ax.set_xlim(min(left, 0)-.06*span, max(right, 0)+.06*span)
        ax.axvline(0, linestyle="--", linewidth=.7, color="#626262")
        ax.set_yticks(range(4), [str(n) for n in SIZES]); ax.set_ylim(3.55, -.55)
        ax.set_ylabel("Node count")
        ax.set_xlabel("Source − matched binary reference")
        ax.text(.5, -.34, "← Beneficial (lower risk)" if metric == "failure_risk" else "Beneficial (longer service) →", transform=ax.transAxes, ha="center")
        ax.xaxis.set_major_locator(mpl.ticker.MaxNLocator(5))
        ax.xaxis.set_major_formatter(mpl.ticker.FormatStrFormatter("%.3f"))
    fig.legend([Line2D([0],[0],color=c,marker=m,linewidth=1) for c,m in zip(colors,markers)],
        ["Formal", "Confirmation"], loc="lower center", bbox_to_anchor=(.5,.015), ncol=2, frameon=False)
    save(fig, "figure-2-global-contrasts")

    palette = {"independently_confirmed": "#c2d8e3", "formal_only": "#ead6b5", "confirmation_only": "#d6cbe2", "neither": "#ededed"}
    reps = {r["contrast_id"]: r for r in data["cross_phase_replication_records"]}
    fig, ax = plt.subplots(figsize=(183/25.4, 115/25.4))
    fig.subplots_adjust(left=.28, right=.985, bottom=.29, top=.9)
    for i, (metric, size) in enumerate((m,n) for m in METRICS for n in SIZES):
        for j, family in enumerate(FAMILIES):
            rep = reps[f"{metric}.n{size:04d}.{family}"]
            ax.add_patch(Rectangle((j-.5, i-.5), 1, 1, facecolor=palette[rep["replication_state"]], edgecolor="white", linewidth=1))
            for p, phase in enumerate(source.PHASES):
                if rep[f"{phase}_gate_state"] == "closed":
                    ax.add_patch(Rectangle((j-.5+p*.5,i-.5),.5,1,fill=False,hatch="///",edgecolor="#666666",linewidth=.5))
            ax.text(j, i, "F:" + SHORT[rep["formal_interval_direction"]] + "   C:" + SHORT[rep["confirmation_interval_direction"]], ha="center", va="center")
    ax.set(xlim=(-.5,4.5), ylim=(7.5,-.5))
    ax.set_xticks(range(5), ["Demand-aware", "FHS3", "FHS5", "Global", "NCH"])
    ax.xaxis.tick_top(); ax.tick_params(length=0, pad=7)
    ax.set_yticks(range(8), [f"{'Failure risk' if m=='failure_risk' else 'No-path time / H'} · {n}" for m in METRICS for n in SIZES])
    for spine in ax.spines.values(): spine.set_visible(False)
    ax.axhline(3.5, color="white", linewidth=3)
    fig.legend([Patch(facecolor=palette[s],edgecolor="#aaaaaa") for s in STATES],
        [s.replace("_", " ").capitalize() for s in STATES], loc="lower center", bbox_to_anchor=(.53,.155), ncol=2, frameon=False)
    fig.text(.5,.12,"F / C: formal / confirmation. Interval direction: B beneficial; H harmful; I inconclusive.",ha="center")
    fig.text(.5,.078,"Hatched phase half-cell: secondary gate closed. Unhatched secondary: gate open.",ha="center")
    fig.text(.5,.038,"Global gates are not applicable. Column and row order follow the complete registered registry.",ha="center")
    save(fig, "figure-3-replication-matrix")
    return mpl.__version__


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    data = load_checked()
    if args.check_only:
        print("PASS: source hashes, evidence structure, five receipts, 80 intervals, 40 replication states")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    numerical_outputs(data)
    version = render(data)
    counts = dict(Counter(r["replication_state"] for r in data["cross_phase_replication_records"]))
    captions = ["# Figure captions", "", "## Figure 1 | Registered design and evidence flow", "",
        "Result-free schematic of the synthetic benchmark. Independent parent graphs feed paired held-out traffic and resource-matched comparisons. Formal and confirmation evidence are analysed separately before the complete cross-phase registry is displayed. Traces and binary arms are not independent graph replicates.", "",
        "## Figure 2 | Global resource-matched service contrasts", "",
        "a Failure-risk difference. b Normalized restricted no-path-time difference. Blue circles show formal estimates and orange squares confirmation estimates; horizontal lines show adjusted bounds. The dashed line is zero. All four registered sizes appear in each panel.", "", STATISTICS, "",
        "## Figure 3 | Complete cross-phase replication registry", "",
        "Every row is one endpoint and node-count hierarchy, with its five contrasts. Cell fill denotes replication state only. F and C identify phases; B, H and I denote beneficial, harmful and inconclusive adjusted intervals. A hatched phase half-cell denotes a closed secondary gate; an unhatched secondary cell is open. Global gates are not applicable. Independently confirmed requires beneficial intervals and applicable open gates in both phases; other states do not imply equivalence.", "", STATISTICS, ""]
    (OUT / "captions.md").write_text("\n".join(captions), encoding="utf-8")
    files = [OUT / name for name in ("numerical-registry.json", "table-1.json", "table-1.md", "captions.md")]
    files += [OUT / f"{name}.{ext}" for name in ("figure-1-design", "figure-2-global-contrasts", "figure-3-replication-matrix") for ext in ("svg", "pdf", "png")]
    write_json(OUT / "manifest.json", {"schema_version": "manuscript-displays.v1", "source_sha256": SOURCE_SHA,
        "source_content_fingerprint": SOURCE_FP, "generator_sha256": source.digest(Path(__file__)),
        "python": platform.python_version(), "matplotlib": version,
        "validation": "archived-source binding, structural evidence validation, exact reporting checks; no new raw replay",
        "phase_interval_rows": 80, "replication_rows": 40, "global_table_rows": 8,
        "replication_state_counts": counts,
        "files": {p.name: {"bytes": p.stat().st_size, "sha256": source.digest(p)} for p in files}})
    print(json.dumps({"output": str(OUT), "replication_state_counts": counts, "files": len(files)}, sort_keys=True))


if __name__ == "__main__":
    main()
