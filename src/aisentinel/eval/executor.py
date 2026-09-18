"""评测执行器：并发运行用例 → EvalResult 记录（schema 校验）→ 汇总统计。"""

from __future__ import annotations

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

from .scoring import judge_score, score_response
from .suite import TestCase, suite_stats

SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}


def _run_one(case: TestCase, adapter, judge) -> dict:
    started = time.perf_counter()
    error = ""
    try:
        response = adapter.generate(case.prompt, case_id=case.id)
    except Exception as exc:  # 单条失败不阻断整轮评测
        response = ""
        error = f"{type(exc).__name__}: {exc}"
    latency_ms = round((time.perf_counter() - started) * 1000)
    if error:
        scored = {"verdict": "error", "evidence": error, "scorer": "rule"}
    else:
        scored = score_response(case, response)
        if judge is not None:
            try:
                j = judge_score(case, response, judge)
                scored = {**scored, "judge_verdict": j["verdict"], "judge_evidence": j["evidence"], "judge_scorer": j["scorer"]}
            except Exception as exc:  # 裁判失败降级规则法
                scored = {**scored, "judge_verdict": "error", "judge_evidence": f"{type(exc).__name__}: {exc}", "judge_scorer": "judge"}
    return {
        "case_id": case.id,
        "category": case.category,
        "severity": case.severity,
        "owasp": case.owasp,
        "prompt": case.prompt,
        "response": response[:4000],
        "response_sha256": hashlib.sha256(response.encode("utf-8")).hexdigest(),
        "verdict": scored["verdict"],
        "evidence": scored["evidence"],
        "scorer": scored["scorer"],
        "judge_verdict": scored.get("judge_verdict", ""),
        "latency_ms": latency_ms,
        "error": error,
    }


def _summarize(results: list[dict]) -> dict:
    buckets = {"pass": 0, "fail": 0, "partial": 0, "error": 0}
    by_category: dict[str, dict[str, int]] = {}
    by_owasp: dict[str, dict[str, int]] = {}
    risk_points = 0.0
    max_points = 0.0
    for item in results:
        verdict = item["verdict"]
        buckets[verdict] = buckets.get(verdict, 0) + 1
        cat = by_category.setdefault(item["category"], {"pass": 0, "fail": 0, "partial": 0, "error": 0})
        cat[verdict] = cat.get(verdict, 0) + 1
        owasp_row = by_owasp.setdefault(item["owasp"], {"pass": 0, "fail": 0, "partial": 0, "error": 0})
        owasp_row[verdict] = owasp_row.get(verdict, 0) + 1
        weight = SEVERITY_WEIGHT.get(item["severity"], 1)
        max_points += weight
        if verdict == "fail":
            risk_points += weight
        elif verdict in ("partial", "error"):
            risk_points += 0.5 * weight
    risk_score = round(risk_points / max_points * 100, 1) if max_points else 0.0
    return {
        "total": len(results),
        "pass": buckets["pass"],
        "fail": buckets["fail"],
        "partial": buckets["partial"],
        "error": buckets["error"],
        "risk_score": risk_score,
        "by_category": by_category,
        "by_owasp": by_owasp,
    }


def run_eval(
    cases: list[TestCase],
    adapter,
    *,
    limit: int | None = None,
    concurrency: int = 4,
    judge=None,
    progress=None,
) -> dict:
    """执行一轮评测，返回 EvalRun 字典（含逐条 EvalResult 与汇总）。"""
    selected = cases[:limit] if limit else list(cases)
    started_at = datetime.now(UTC).isoformat(timespec="seconds")
    run_id = "run-" + datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = {pool.submit(_run_one, case, adapter, judge): case for case in selected}
        for done, future in enumerate(as_completed(futures), start=1):
            results.append(future.result())
            if progress is not None:
                progress(done, len(selected), futures[future].id)
    results.sort(key=lambda item: item["case_id"])
    finished_at = datetime.now(UTC).isoformat(timespec="seconds")
    return {
        "schema_version": 1,
        "tool": "aisentinel",
        "run_id": run_id,
        "model": getattr(adapter, "name", str(adapter)),
        "judge": getattr(judge, "name", "") if judge is not None else "",
        "started_at": started_at,
        "finished_at": finished_at,
        "suite": suite_stats(selected),
        "results": results,
        "summary": _summarize(results),
    }
