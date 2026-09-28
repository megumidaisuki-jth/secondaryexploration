"""Exact descriptive reporting summaries; no new inference or raw-block replay."""
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
import json

from tools import export_source_data as source
from tools import build_results_displays as display

OUT = source.ROOT / "manuscript/generated/results-writing-v1"
MODELS = ("barabasi_albert", "er_gnm", "sbm_fixed_count")


def pair(value):
    return [value.numerator, value.denominator]


def describe(values):
    return {"count":len(values), "mean":pair(sum(values, Fraction())/len(values)),
            "minimum":pair(min(values)), "maximum":pair(max(values)),
            "negative":sum(v<0 for v in values), "zero":sum(v==0 for v in values),
            "positive":sum(v>0 for v in values)}


def build(data):
    result = {"source_sha256": display.SOURCE_SHA, "source_content_fingerprint": display.SOURCE_FP,
              "scope":"descriptive-reporting-only; no new intervals, tests, or simulations", "phases":{}}
    for phase in source.PHASES:
        p = data["phase_data"][phase]
        base = f"/phase_data/{phase}"
        groups = defaultdict(list)
        for i, row in enumerate(p["parent_model_values"]):
            groups[(row["metric"],row["node_count"],row["source_family"],row["parent_model"])].append((i,row))
        parent_summaries = []
        for key, rows in sorted(groups.items()):
            values = [display.frac(r["combined_parent_value"]) for _,r in rows]
            display.require(len(rows)==20 and len({r['parent_graph_id'] for _,r in rows})==20, "parent stratum differs")
            parent_summaries.append(dict(zip(("metric","node_count","source_family","parent_model"),key),
                **describe(values), source_pointers=[f"{base}/parent_model_values/{i}" for i,_ in rows]))
        display.require(len(parent_summaries)==120, "parent group count differs")
        coverage=[]
        for i, row in enumerate(p["event_coverage_q0_10"]):
            display.require(row["quantile_estimate"] is None and len(row["parents"])==20, "coverage contract differs")
            flags=[x["source_and_all_binary_q0.10_identified"] for x in row["parents"]]
            display.require(all(flags)==row["all_parents_q0.10_identified"], "coverage gate differs")
            coverage.append({**{k:v for k,v in row.items() if k!='parents'},
                "identified_parent_count":sum(flags), "source_pointer":f"{base}/event_coverage_q0_10/{i}"})
        activity=[]
        for i,row in enumerate(p['activity_sensitivity']):
            strata=[]
            for s in row['strata']:
                values=[display.frac(v) for _,v in s['parent_values']]
                display.require(len(values)==s['parent_count'], "activity count differs")
                display.require(s['mean']==(pair(sum(values,Fraction())/len(values)) if values else None), "activity mean differs")
                strata.append({k:v for k,v in s.items() if k!='parent_values'})
            expected=pair(sum((display.frac(s['mean']) for s in strata),Fraction())/3) if all(s['parent_count'] for s in strata) else None
            display.require(expected==row['equal_model_descriptive_mean'], "activity aggregation differs")
            activity.append({**{k:v for k,v in row.items() if k!='strata'},'strata':strata,
                             'source_pointer':f"{base}/activity_sensitivity/{i}"})
        descriptors=[]
        for i,row in enumerate(p['descriptive_summaries']):
            strata=[]
            for s in row['strata']:
                values=[display.frac(v) for _,v in s['parent_values']]
                display.require(len(values)==s['parent_count']==20, "descriptor count differs")
                display.require(pair(sum(values,Fraction())/20)==s['mean'], "descriptor mean differs")
                strata.append({k:v for k,v in s.items() if k!='parent_values'})
            display.require(pair(sum((display.frac(s['mean']) for s in strata),Fraction())/3)==row['equal_model_mean'], "descriptor aggregation differs")
            descriptors.append({**{k:v for k,v in row.items() if k!='strata'},'strata':strata,
                                'source_pointer':f"{base}/descriptive_summaries/{i}"})
        metric_ranges={}
        for metric in sorted({r['metric'] for r in descriptors}):
            rows=[r for r in descriptors if r['metric']==metric]
            display.require(len(rows)==16, "descriptor registry differs")
            metric_ranges[metric]=describe([display.frac(r['equal_model_mean']) for r in rows])
        # These ranges/counts summarize all 16 size-by-family cells, not an inferential estimand.
        runtime=p['runtime_and_environment']
        for total,key in [('total_generation_ns','generation_ns'),('total_exact_validation_ns','validation_ns')]:
            display.require(runtime[total]==sum(r[key] for r in runtime['blocks']), "runtime sum differs")
        result['phases'][phase]={"parent_stratum_summaries":parent_summaries,"event_coverage":coverage,
            "activity_sensitivity":activity,"descriptive_summaries":descriptors,"descriptor_cell_ranges":metric_ranges,
            "runtime":{**{k:v for k,v in runtime.items() if k!='blocks'},
                "generation_block_hours":pair(Fraction(runtime['total_generation_ns'],3600000000000)),
                "exact_validation_block_hours":pair(Fraction(runtime['total_exact_validation_ns'],3600000000000)),
                "source_pointer":f"{base}/runtime_and_environment",
                "interpretation":"sum of within-block perf_counter durations; not end-to-end wall time or CPU time",
                "whole_run_peak_memory":None}}
    return result


def main():
    display.require(source.digest(source.OUTPUT)==display.SOURCE_SHA, "Source Data byte hash differs")
    data=source.load_json(source.OUTPUT)
    display.check_registry(data)
    result=build(data)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'evidence-summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    md=['# Descriptive Results support','',
        'All values are descriptive source-minus-registered-binary contrasts. No new tests or intervals are computed. Exact fractions and source pointers are in [evidence-summary.json](evidence-summary.json).','']
    for phase,p in result['phases'].items():
        md += [f'## {phase.capitalize()}', '', '### Parent-model means (all 120 cells)', '',
            '| Endpoint | Nodes | Source family | Parent model | n | Mean | Minimum parent | Maximum parent |', '|---|---:|---|---|---:|---:|---:|---:|']
        for r in p['parent_stratum_summaries']:
            md.append(f"| {r['metric']} | {r['node_count']} | {r['source_family']} | {r['parent_model']} | {r['count']} | {display.decimal(r['mean'])} | {display.decimal(r['minimum'])} | {display.decimal(r['maximum'])} |")
        md += ['', '### Event coverage (all 96 cells)', '', '| Nodes | Model | Source family | Traffic scope | Identified parents / 20 |', '|---:|---|---|---|---:|']
        for r in p['event_coverage']:
            md.append(f"| {r['node_count']} | {r['parent_model']} | {r['source_family']} | {r['scope']} | {r['identified_parent_count']} / 20 |")
        md += ['', '### Activity sensitivity (all 16 groups, including empty strata)', '', '| Endpoint | Nodes | Activity | BA / ER-GNM / SBM counts | Equal-model mean |', '|---|---:|---|---|---:|']
        for r in p['activity_sensitivity']:
            counts=' / '.join(str(s['parent_count']) for s in r['strata'])
            mean=display.decimal(r['equal_model_descriptive_mean']) if r['equal_model_descriptive_mean'] is not None else 'Unavailable (empty stratum)'
            md.append(f"| {r['metric']} | {r['node_count']} | {r['topology_activity']} | {counts} | {mean} |")
        md += ['', '### All 13 descriptor ranges across 16 size-by-family cells', '',
            'Counts refer to signs of equal-model cell means, not independent replications or statistical support. Full cell/stratum values remain in the JSON and Source Data.', '',
            '| Descriptor | Minimum | Maximum | Negative / zero / positive cells |', '|---|---:|---:|---|']
        for metric,r in p['descriptor_cell_ranges'].items():
            md.append(f"| {metric} | {display.decimal(r['minimum'])} | {display.decimal(r['maximum'])} | {r['negative']} / {r['zero']} / {r['positive']} |")
        r=p['runtime']
        md += ['', f"Generation: {display.decimal(r['generation_block_hours'])} block-hours; exact validation: {display.decimal(r['exact_validation_block_hours'])} block-hours. These are summed measured block durations, not elapsed study duration. Whole-run peak memory is unavailable in the canonical summary.", '']
    (OUT/'descriptive-support.md').write_text('\n'.join(md).rstrip()+'\n',encoding='utf-8',newline='\n')
    manifest={'source_sha256':display.SOURCE_SHA,'generator_sha256':source.digest(Path(__file__)),
        'files':{n:source.digest(OUT/n) for n in ('evidence-summary.json','descriptive-support.md')}}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'output':str(OUT),'phase_count':2,'parent_stratum_rows':240,'coverage_rows':192,'activity_groups':32,'descriptive_cells':416}))


if __name__=='__main__':
    main()
