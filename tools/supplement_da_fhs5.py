"""Exact archive-only S1 reanalysis. No simulation imports or raw block reads.

Checkpoint per 500 bootstrap replicates. --stop-after-chunks demonstrates pause;
creating PAUSE in the output directory requests pause at the next chunk boundary.
Remove PAUSE explicitly to resume. Invalid/stale locks are never auto-deleted.
"""
import argparse
from collections import defaultdict
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/supplement/da-fhs5-posthoc-v1.json"
DEFAULT_OUT = ROOT / "results/supplement/da-fhs5-posthoc-v1"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with tmp.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def save(path, value):
    atomic(path, encoded(value))


def rational(value):
    if not (isinstance(value, list) and len(value) == 2 and all(type(v) is int for v in value) and value[1] > 0):
        raise ValueError("invalid rational")
    return Fraction(*value)


def pair_delta(a, b, metric):
    fields = ("node_count", "parent_model", "parent_replicate", "parent_graph_id", "regime_id", "scope", "horizon", "paired_manifest_fingerprint", "binary_arm_count")
    if any(a[k] != b[k] for k in fields):
        raise ValueError("paired metadata mismatch")
    arms = lambda r: sorted(item[0] for item in r["binary_arm_events"])
    if arms(a) != arms(b) or len(arms(a)) != a["binary_arm_count"] or len(set(arms(a))) != len(arms(a)):
        raise ValueError("binary references differ")
    if not a["binary_arm_count"]:
        raise ValueError("missing binary reference")
    delta = rational(a["value"]) - rational(b["value"])
    if abs(delta) > 1:
        raise ValueError("out of range contrast")
    scale = a["horizon"] if metric == "normalized_restricted_tau_nopath" else 1
    integer = delta * scale
    if integer.denominator != 1:
        raise ValueError("shared-reference cancellation is not an integer event difference")
    return integer.numerator


def extract(phase, config):
    source = ROOT / f"results/inference/{phase}-phase-evidence.json"
    raw = source.read_bytes()
    if sha(raw) != config["source_sha256"][phase]:
        raise ValueError("source hash changed")
    evidence = json.loads(raw)
    receipt = json.loads((ROOT / f"results/diagnostics/independent-replay/20260922-v1/{phase}-phase.success.json").read_bytes())
    assert receipt["exit_code"] == 0 and receipt["output_sha256"] == sha(raw) and receipt["output_bytes"] == len(raw)
    assert evidence["status"] == "complete-strict-replay"
    registry = {r["block_key"] for r in evidence["block_registry"]}
    assert len(registry) == len(evidence["block_registry"]) == 240
    paired = defaultdict(dict)
    for r in evidence["trace_contrasts"]:
        if r["source_family"] not in ("demand-aware", "fhs5"):
            continue
        key = (r["parent_graph_id"], r["regime_id"], r["metric"])
        if r["source_family"] in paired[key]:
            raise ValueError("duplicate source row")
        paired[key][r["source_family"]] = r
    assert len(paired) == 3360
    parents, traces = {}, []
    manifests = {}
    for key, pair in sorted(paired.items()):
        assert set(pair) == {"demand-aware", "fhs5"}
        a, b = pair["demand-aware"], pair["fhs5"]
        metric = key[2]
        assert metric in config["metrics"] and a["parent_graph_id"] in registry
        assert a["horizon"] == 12 * a["node_count"]
        fingerprint = a["paired_manifest_fingerprint"]
        owner = key[:2]
        assert fingerprint not in manifests or manifests[fingerprint] == owner
        manifests[fingerprint] = owner
        integer = pair_delta(a, b, metric)
        parent = parents.setdefault(key[0], {"phase": phase, "parent_graph_id": key[0], "node_count": a["node_count"], "parent_model": a["parent_model"], "parent_replicate": a["parent_replicate"], "horizon": a["horizon"], "trace_integer_deltas": {}})
        assert all(parent[k] == a[k] for k in ("node_count", "parent_model", "parent_replicate", "horizon"))
        parent["trace_integer_deltas"].setdefault(metric, []).append(integer)
        traces.append({"phase": phase, "parent_graph_id": key[0], "node_count": a["node_count"], "parent_model": a["parent_model"], "regime_id": key[1], "scope": a["scope"], "metric": metric, "horizon": a["horizon"], "paired_manifest_fingerprint": fingerprint, "binary_arm_ids": sorted(x[0] for x in a["binary_arm_events"]), "integer_delta": integer})
    assert len(parents) == 240 and set(parents) == registry and len(manifests) == 1680
    archived_parent = {(r["parent_graph_id"], r["metric"], r["source_family"]): r for r in evidence["parent_contrasts"] if r["source_family"] in ("demand-aware", "fhs5")}
    for p in parents.values():
        p["integer_totals"] = []
        for metric in config["metrics"]:
            vals = p["trace_integer_deltas"][metric]
            assert len(vals) == 7
            subset = [r for r in traces if r["parent_graph_id"] == p["parent_graph_id"] and r["metric"] == metric]
            assert len({r["regime_id"] for r in subset}) == 7
            assert sum(r["scope"] == "same_distribution" for r in subset) == 4
            assert sum(r["scope"] == "distribution_shift" for r in subset) == 3
            total = sum(vals)
            p["integer_totals"].append(total)
            scale = p["horizon"] if metric == config["metrics"][0] else 1
            old_a = archived_parent[p["parent_graph_id"], metric, "demand-aware"]
            old_b = archived_parent[p["parent_graph_id"], metric, "fhs5"]
            assert Fraction(total, 7 * scale) == rational(old_a["combined_parent_value"]) - rational(old_b["combined_parent_value"])
        del p["trace_integer_deltas"]
    for n in config["node_counts"]:
        for model in config["models"]:
            group = [p for p in parents.values() if p["node_count"] == n and p["parent_model"] == model]
            assert len(group) == 20 and sorted(p["parent_replicate"] for p in group) == list(range(20))
    return sorted(parents.values(), key=lambda p: (p["node_count"], p["parent_model"], p["parent_replicate"])), traces


def indices(config, phase, n, replicate, model):
    key = f'{config["bootstrap_seed"]}|{phase}|{n}|{replicate}|{model}'
    rng = random.Random(int.from_bytes(hashlib.sha256(key.encode()).digest(), "big"))
    return [rng.randrange(20) for _ in range(20)]


def bootstrap_chunk(config, phase, n, strata, start, stop):
    values = []
    for rep in range(start, stop):
        accum = [0, 0]
        for model in config["models"]:
            for idx in indices(config, phase, n, rep, model):
                row = strata[model][idx]
                accum[0] += row[0]
                accum[1] += row[1]
        values.append(accum)
    return values


def qrank(ordered, probability):
    rank = max(1, math.ceil(len(ordered) * probability))
    return ordered[rank - 1]


def summary(config, phase, n, parents, draws):
    out = []
    for column, metric in enumerate(config["metrics"]):
        denominator = 60 * 7 * (12 * n if column == 0 else 1)
        totals = [p["integer_totals"][column] for p in parents]
        sorted_draws = sorted(r[column] for r in draws)
        tail = Fraction(*config["adjusted_tail_probability"])
        exact = {"estimate": Fraction(sum(totals), denominator),
                 "adjusted_lower": Fraction(qrank(sorted_draws, tail), denominator),
                 "adjusted_upper": Fraction(qrank(sorted_draws, 1 - tail), denominator),
                 "unadjusted_lower": Fraction(qrank(sorted_draws, Fraction(1, 40)), denominator),
                 "unadjusted_upper": Fraction(qrank(sorted_draws, Fraction(39, 40)), denominator)}
        lower, upper = exact["adjusted_lower"], exact["adjusted_upper"]
        favorable = lower > 0 if column == 0 else upper < 0
        adverse = upper < 0 if column == 0 else lower > 0
        out.append({"phase": phase, "node_count": n, "metric": metric, "parents": 60,
                    "parents_by_model": {m: 20 for m in config["models"]},
                    "exact": {k: [v.numerator, v.denominator] for k, v in exact.items()},
                    "display": {k: float(v) for k, v in exact.items()},
                    "parent_delta_sign_counts": {"negative": sum(v < 0 for v in totals), "zero": sum(v == 0 for v in totals), "positive": sum(v > 0 for v in totals)},
                    "adjusted_interval_direction": "favorable" if favorable else "adverse" if adverse else "includes_zero",
                    "degenerate_empirical_bootstrap": sorted_draws[0] == sorted_draws[-1]})
    return out


def run(args):
    raw_config = args.config.read_bytes()
    config = json.loads(raw_config)
    assert config["bootstrap_replicates"] == 20000 and config["chunk_size"] == 500
    assert config["new_family_comparisons"] == 16
    assert Fraction(*config["adjusted_tail_probability"]) == Fraction(*config["family_alpha"]) / (2 * 16)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    lock = output / "RUNNING.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, encoded({"pid": os.getpid(), "argv": sys.argv})); os.close(fd)
    started = time.monotonic()
    completed = 0
    binding = {"config_sha256": sha(raw_config), "analysis_script_sha256": sha(Path(__file__).read_bytes()), "source_sha256": config["source_sha256"], "python_version": platform.python_version()}
    def status(state, **kwargs):
        save(output / "progress.json", {"state": state, "completed_bootstrap_chunks": completed, "total_bootstrap_chunks": 320, "bootstrap_percent": round(completed / 320 * 100, 3), "elapsed_seconds_this_invocation": round(time.monotonic() - started, 3), **kwargs})
    try:
        existing = output / "binding.json"
        if existing.exists():
            assert json.loads(existing.read_bytes()) == binding, "resume binding changed"
        else:
            save(existing, binding)
        status("validating-inputs")
        by_phase = {}
        for phase in ("formal", "confirmation"):
            parents, traces = extract(phase, config)
            by_phase[phase] = parents
            for name, data in (("parents", parents), ("traces", traces)):
                target = output / f"{phase}-{name}.json"
                if target.exists():
                    assert target.read_bytes() == encoded(data), "derived input changed"
                else:
                    save(target, data)
        results = []
        newly_computed = 0
        for phase, all_parents in by_phase.items():
            for n in config["node_counts"]:
                parents = [p for p in all_parents if p["node_count"] == n]
                strata = {m: [p["integer_totals"] for p in parents if p["parent_model"] == m] for m in config["models"]}
                draws = []
                for start in range(0, 20000, 500):
                    if (output / "PAUSE").exists():
                        status("paused-at-chunk-boundary", phase=phase, node_count=n)
                        return
                    target = output / "checkpoints" / f"{phase}-n{n:04d}-{start:05d}.json"
                    meta = {"binding_sha256": sha(encoded(binding)), "phase": phase, "node_count": n, "start": start, "stop": start + 500}
                    if target.exists():
                        checkpoint = json.loads(target.read_bytes())
                        assert checkpoint["meta"] == meta and checkpoint["values_sha256"] == sha(encoded(checkpoint["values"]))
                        vals = checkpoint["values"]
                    else:
                        vals = bootstrap_chunk(config, phase, n, strata, start, start + 500)
                        save(target, {"meta": meta, "values": vals, "values_sha256": sha(encoded(vals))})
                        newly_computed += 1
                    assert len(vals) == 500 and all(len(row) == 2 and all(type(v) is int for v in row) for row in vals)
                    draws.extend(vals)
                    completed += 1
                    status("bootstrapping", phase=phase, node_count=n, replicate_complete=start + 500)
                    if args.stop_after_chunks and newly_computed >= args.stop_after_chunks:
                        status("paused-at-chunk-boundary", phase=phase, node_count=n)
                        print(f"Paused safely after {completed}/320 chunks.", flush=True)
                        return
                results.extend(summary(config, phase, n, parents, draws))
                print(f"{phase} n={n}: {completed}/320 chunks complete", flush=True)
        save(output / "results.json", {"analysis": config["interpretation"], "binding": binding, "comparisons": results, "limitations": config["limitations"]})
        report = ["# DA 与 FHS5 直接配对消融", "", "后验探索性分析。每行60个独立父图，3模型层各20个；父图内7轨迹等权。两个相位分开，不合并。", "", "20000次父图分层配对bootstrap；新增16项家族Bonferroni校正，单区间名义99.6875%，家族名义95%。区间为百分位近似，不保证有限样本精确覆盖。正ΔY、负ΔF有利。", "", "|相位|规模|终点|DA−FHS5|校正区间|父图负/零/正|", "|---|---:|---|---:|---|---|"]
        for r in results:
            d = r["display"]; s = r["parent_delta_sign_counts"]
            label = "ΔY" if r["metric"] == config["metrics"][0] else "ΔF"
            report.append(f'|{r["phase"]}|{r["node_count"]}|{label}|{d["estimate"]:.6f}|[{d["adjusted_lower"]:.6f}, {d["adjusted_upper"]:.6f}]|{s["negative"]}/{s["zero"]}/{s["positive"]}|')
        report.extend(["", "## 解释边界", "", "本分析计算的是训练后DA方案与FHS5方案的直接差异，不是与二元参照的效果。相位都已有结果披露，因此不把本次结果写成事先注册的新确认性消融。没有计算或虚构p值。", "", "零区间只说明经验重抽样分布退化，不证明总体等效；不跨零也不证明拓扑因果机制或真实部署收益。所有点估计、区间端点和bootstrap分子另存为精确有理数或整数。", "", "运行完成不等于独立科学审计通过；另见verification.json中的复算范围。", ""])
        atomic(output / "report.md", "\n".join(report).encode("utf-8"))
        status("generated-pending-verification", comparisons=16)
    except Exception as exc:
        status("stopped-on-error", error=repr(exc))
        raise
    finally:
        lock.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--stop-after-chunks", type=int, default=0)
    run(parser.parse_args())
