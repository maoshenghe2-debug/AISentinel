"""护栏基准测评：拦截率 / 误报率 / P95 延迟（固定样本集，可复现）。"""

from __future__ import annotations

import time
from pathlib import Path

import yaml

from .engine import Guard

BENCH_PATH = Path(__file__).parent / "bench_samples.yaml"


def load_bench_samples(path: Path | str | None = None) -> list[dict]:
    with open(path or BENCH_PATH, encoding="utf-8") as handle:
        doc = yaml.safe_load(handle) or {}
    return doc.get("samples") or []


def run_bench(guard: Guard | None = None, repeats: int = 20) -> dict:
    """执行基准测评。

    - 拦截率：正样本（expect=block/mask）被判为非 allow 的比例；
    - 误报率：负样本（expect=allow）被判为非 allow 的比例；
    - P95 延迟：所有样本的 check 延迟（毫秒）95 分位。
    """
    guard = guard or Guard()
    samples = load_bench_samples()
    positives = [s for s in samples if s["expect"] != "allow"]
    negatives = [s for s in samples if s["expect"] == "allow"]

    def decide(sample: dict):
        checker = guard.check_input if sample["stage"] == "input" else guard.check_output
        return checker(sample["text"])

    latencies: list[float] = []
    for sample in samples:
        for _ in range(max(1, repeats)):
            start = time.perf_counter()
            decide(sample)
            latencies.append((time.perf_counter() - start) * 1000)

    hit = sum(1 for sample in positives if decide(sample).action != "allow")
    fp = sum(1 for sample in negatives if decide(sample).action != "allow")
    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95) - 1] if latencies else 0.0
    return {
        "samples": len(samples),
        "positives": len(positives),
        "negatives": len(negatives),
        "hit_rate": round(hit / len(positives), 4) if positives else 0.0,
        "false_positive_rate": round(fp / len(negatives), 4) if negatives else 0.0,
        "latency_p95_ms": round(p95, 3),
        "latency_avg_ms": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
        "repeats": repeats,
    }
