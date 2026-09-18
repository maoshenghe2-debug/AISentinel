"""AISentinel CLI 入口（aisentinel doctor | detect | eval | guard | compliance | demo）。"""

from __future__ import annotations

import json as jsonlib
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .doctor import STATUS_FAIL, STATUS_OK, STATUS_WARN, run_doctor

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

app = typer.Typer(
    name="aisentinel",
    help="AISentinel · 大模型安全评测与 AI 内容鉴别平台（红队评测 / 运行时护栏 / 内容标识核验）",
    no_args_is_help=True,
)
console = Console()

_STATUS_STYLE = {STATUS_OK: "[green]就绪[/green]", STATUS_WARN: "[yellow]缺失[/yellow]", STATUS_FAIL: "[red]不满足[/red]"}
_VERDICT_STYLE = {"has_label": "green", "suspected_cleaned": "yellow", "no_label": "white"}


@app.callback()
def _root() -> None:
    """AISentinel CLI。"""


@app.command()
def doctor(
    as_json: bool = typer.Option(False, "--json", help="以 JSON 输出（供 CI/脚本消费）"),
    egress: bool = typer.Option(False, "--egress", help="附加 egress 审计（列出本次自检触达的网络目标）"),
) -> None:
    """环境自检：9 项检查（含 Ollama / 用例库 / egress 审计）。"""
    report = run_doctor(egress=egress)
    if as_json:
        console.print_json(jsonlib.dumps(report, ensure_ascii=False))
    else:
        table = Table(title=f"AISentinel 环境自检 · v{__version__} · {report['platform']}")
        table.add_column("检查项", style="cyan", no_wrap=True)
        table.add_column("状态", no_wrap=True)
        table.add_column("详情", overflow="fold")
        table.add_column("建议", style="dim", overflow="fold")
        for item in report["checks"]:
            table.add_row(item["name"], _STATUS_STYLE[item["status"]], item["detail"], item["fix"])
        console.print(table)
        summary = report["summary"]
        console.print(f"就绪 {summary['ok']} · 缺失 {summary['warn']} · 不满足 {summary['fail']} → 退出码 {report['exit_code']}")
    raise typer.Exit(code=report["exit_code"])


detect_app = typer.Typer(help="AIGC 鉴别（★ 标识核验：三态判定 + CSV 证据）", no_args_is_help=True)
app.add_typer(detect_app, name="detect")


def _render_label_card(record) -> None:
    """三态结论卡（产品化核心组件，PRD §5.2）。"""
    style = _VERDICT_STYLE.get(record.verdict, "white")
    lines = [
        f"结论：[bold {style}]{record.verdict_label}[/bold {style}]（{record.verdict}） ｜ 置信：{record.confidence}",
        f"文件：{record.file}",
        f"格式：{record.format or '未知'} ｜ 大小：{record.size} 字节 ｜ sha256：{record.sha256[:16]}…",
    ]
    groups = record.groups
    hit_lines = []
    for group_name, title in (("provider", "服务提供者标识"), ("synthesis", "生成合成属性"), ("content_id", "内容编号")):
        for item in groups.get(group_name, []):
            hit_lines.append(f"  [{title}] {item['field']}：{item['value_preview']}（{item['source']}）")
    lines.append("命中证据：" if hit_lines else "命中证据：无")
    lines.extend(hit_lines)
    if record.traces:
        lines.append("痕迹信号：")
        for trace in record.traces:
            lines.append(f"  · {trace['kind']}／{trace['detail']}")
    lines.append("标准依据：" + "；".join(record.standard_refs[:2]) + " 等")
    console.print(Panel("\n".join(lines), title="标识核验结论", border_style=style))


@detect_app.command("file")
def detect_file(
    path: str = typer.Argument(..., help="待核验文件（png/jpg/jpeg/webp）"),
    as_json: bool = typer.Option(False, "--json", help="以 JSON 输出完整记录"),
) -> None:
    """核验单个文件的标识三态结论（对照《标识生成合成内容标识办法》）。"""
    from pathlib import Path as _Path

    from .detect.label import validate_record, verify_label

    target = _Path(path)
    if not target.is_file():
        console.print(f"[red]文件不存在：{path}[/red]")
        raise typer.Exit(code=2)
    record = verify_label(target, validate=True)
    if as_json:
        console.print_json(jsonlib.dumps(record.to_dict(), ensure_ascii=False))
        return
    _render_label_card(record)
    validate_record(record.to_dict())  # 二次校验（schema 已内置）


@detect_app.command("dir")
def detect_dir(
    directory: str = typer.Argument(..., help="待核验目录（批量）"),
    out: str = typer.Option("label_check.csv", "--out", help="CSV 证据输出路径"),
) -> None:
    """批量核验目录并输出 CSV 证据（三态判定 + 证据字段）。"""
    from pathlib import Path as _Path

    from .detect.csvout import records_to_csv
    from .detect.label import verify_dir

    target = _Path(directory)
    if not target.is_dir():
        console.print(f"[red]目录不存在：{directory}[/red]")
        raise typer.Exit(code=2)
    records = verify_dir(target)
    if not records:
        console.print("[yellow]目录中没有可核验的图片文件（png/jpg/jpeg/webp）[/yellow]")
        raise typer.Exit(code=4)
    count = records_to_csv(records, out)
    table = Table(title=f"标识核验 · {count} 个文件")
    table.add_column("文件", overflow="fold")
    table.add_column("结论", no_wrap=True)
    table.add_column("证据数", justify="right")
    table.add_column("痕迹", justify="right")
    for record in records:
        evidence = sum(len(items) for items in record.groups.values())
        style = _VERDICT_STYLE.get(record.verdict, "white")
        table.add_row(record.file, f"[{style}]{record.verdict_label}[/{style}]", str(evidence), str(len(record.traces)))
    console.print(table)
    console.print(f"CSV 证据：[bold]{out}[/bold]")


eval_app = typer.Typer(help="红队安全评测（用例库 / 执行器 / 双轨评分 / 风险矩阵）", no_args_is_help=True)
app.add_typer(eval_app, name="eval")


@eval_app.command("run")
def eval_run(
    model: str = typer.Option("mock://", "--model", help="模型规格：mock:// / ollama:<模型> / openai:<模型>"),
    limit: int = typer.Option(None, "--limit", help="只跑前 N 条（冒烟）"),
    concurrency: int = typer.Option(4, "--concurrency", min=1, max=32, help="并发数"),
    out: str = typer.Option("eval_report.html", "--out", help="报告输出路径（同时产出 .html 与 .md）"),
    judge_model: str = typer.Option(None, "--judge", help="启用裁判模型（默认关闭；启用后评测数据将发送至对应端点）"),
    as_json: bool = typer.Option(False, "--json", help="输出运行摘要 JSON"),
) -> None:
    """执行一轮评测：用例库 → 执行器 → 双轨评分 → 风险矩阵报告。"""
    from .eval.executor import run_eval
    from .eval.models import get_adapter
    from .eval.report import write_report
    from .eval.suite import load_suite

    try:
        cases = load_suite()
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=4) from exc
    if not cases:
        console.print("[yellow]用例库为空（eval/suites/ 下暂无用例）[/yellow]")
        raise typer.Exit(code=4)

    try:
        adapter = get_adapter(model)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    judge = None
    if judge_model:
        judge = get_adapter(judge_model)
        console.print(f"[yellow]裁判模型已启用：{judge.name} —— 评测数据将发送至对应端点，请确认合规后再继续。[/yellow]")

    console.print(f"评测开始：{len(cases)} 条用例 ｜ 模型 {adapter.name} ｜ 并发 {concurrency}")

    def progress(done: int, total: int, case_id: str) -> None:
        if done % max(1, total // 10) == 0 or done == total:
            console.print(f"  进度 {done}/{total}（{case_id}）")

    run = run_eval(cases, adapter, limit=limit, concurrency=concurrency, judge=judge, progress=progress)
    summary = run["summary"]
    html_path, md_path = write_report(run, out)

    table = Table(title=f"评测结果 · {run['model']} · 风险分 {summary['risk_score']}/100")
    table.add_column("指标", no_wrap=True)
    table.add_column("值", justify="right")
    table.add_row("用例总数", str(summary["total"]))
    table.add_row("通过 / 失败 / 部分 / 错误", f"{summary['pass']} / {summary['fail']} / {summary['partial']} / {summary['error']}")
    table.add_row("OWASP 覆盖", f"{len(summary['by_owasp'])} 类")
    console.print(table)
    console.print(f"报告：[bold]{html_path}[/bold]（Markdown：{md_path}）")
    if as_json:
        console.print_json(jsonlib.dumps({key: run[key] for key in ("run_id", "model", "summary")}, ensure_ascii=False))


@eval_app.command("validate")
def eval_validate() -> None:
    """校验用例库（schema + 计数统计）。"""
    from .eval.suite import CATEGORY_TITLES as EVAL_TITLES
    from .eval.suite import load_suite, suite_stats

    try:
        cases = load_suite()
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=4) from exc
    stats = suite_stats(cases)
    table = Table(title=f"用例库校验通过 · 共 {stats['total']} 条")
    table.add_column("类别")
    table.add_column("数量", justify="right")
    for category, count in sorted(stats["by_category"].items()):
        table.add_row(EVAL_TITLES.get(category, category), str(count))
    console.print(table)
    console.print(f"OWASP 覆盖：{', '.join(sorted(stats['by_owasp']))}")


guard_app = typer.Typer(help="运行时护栏（输入注入检测 / 输出 PII 脱敏 / 违规拦截）", no_args_is_help=True)
app.add_typer(guard_app, name="guard")


@guard_app.command("check")
def guard_check(
    text: str = typer.Option(..., "--text", help="待检测文本"),
    stage: str = typer.Option("input", "--stage", help="检测阶段：input / output"),
    policy: str = typer.Option(None, "--policy", help="策略文件路径（默认内置 default.yaml）"),
    as_json: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    """单文本护栏检测（用于联调 / 演示）。"""
    from .guard.engine import Guard

    guard = Guard(policy)
    decision = guard.check_input(text) if stage == "input" else guard.check_output(text)
    color = {"allow": "green", "alert": "yellow", "mask": "yellow", "block": "red"}.get(decision.action, "white")
    console.print(f"[{color}]{decision.action}[/{color}] · 阶段 {decision.stage} · 命中 {len(decision.hits)} 条")
    for hit in decision.hits:
        console.print(f"  · {hit['rule']}（{hit['category']}）命中：{hit['match']}")
    if decision.action == "mask":
        console.print(f"脱敏结果：{decision.text}")
    if decision.action == "block":
        console.print(f"拦截文案：{decision.text}")
    if as_json:
        console.print_json(jsonlib.dumps({"decision": decision.to_dict(), "text": decision.text}, ensure_ascii=False))


@guard_app.command("bench")
def guard_bench(
    repeats: int = typer.Option(20, "--repeats", min=1, max=500, help="延迟测评重复次数"),
    policy: str = typer.Option(None, "--policy", help="策略文件路径"),
    as_json: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    """基准测评：拦截率 / 误报率 / P95 延迟。"""
    from .guard.bench import run_bench
    from .guard.engine import Guard

    metrics = run_bench(Guard(policy), repeats=repeats)
    table = Table(title="护栏基准测评（固定样本集）")
    table.add_column("指标", no_wrap=True)
    table.add_column("值", justify="right")
    table.add_row("样本（正 / 负）", f"{metrics['positives']} / {metrics['negatives']}")
    table.add_row("拦截率", f"{metrics['hit_rate'] * 100:.1f}%")
    table.add_row("误报率", f"{metrics['false_positive_rate'] * 100:.1f}%")
    table.add_row("P95 延迟", f"{metrics['latency_p95_ms']} ms")
    table.add_row("平均延迟", f"{metrics['latency_avg_ms']} ms")
    console.print(table)
    if as_json:
        console.print_json(jsonlib.dumps(metrics, ensure_ascii=False))


@guard_app.command("serve")
def guard_serve(
    host: str = typer.Option(None, "--host", help="监听地址（默认取策略 bind=127.0.0.1）"),
    port: int = typer.Option(8877, "--port", help="监听端口"),
    upstream: str = typer.Option("mock://", "--upstream", help="上游：mock:// / ollama:<模型>"),
    policy: str = typer.Option(None, "--policy", help="策略文件路径"),
) -> None:
    """启动护栏代理（OpenAI 兼容；默认仅监听 127.0.0.1）。"""
    import uvicorn

    from .guard.engine import Guard
    from .guard.proxy import create_app

    bind = host or Guard(policy).bind
    console.print(f"护栏代理启动：http://{bind}:{port}（upstream={upstream}）")
    uvicorn.run(create_app(policy, upstream), host=bind, port=port, log_level="warning")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
