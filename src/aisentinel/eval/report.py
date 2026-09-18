"""评测报告：OWASP LLM Top10 风险矩阵（HTML 单文件 + Markdown 双渲染）。"""

from __future__ import annotations

from pathlib import Path

from .suite import CATEGORY_TITLES

OWASP_TITLES = {
    "LLM01": "提示注入",
    "LLM02": "不安全输出处理",
    "LLM03": "训练数据污染",
    "LLM04": "模型拒绝服务",
    "LLM05": "供应链风险",
    "LLM06": "敏感信息泄露",
    "LLM07": "不安全插件设计",
    "LLM08": "过度代理",
    "LLM09": "过度依赖",
    "LLM10": "模型窃取",
}

DISCLAIMER = (
    "本报告由 AISentinel 自动化评测生成，用于**防御性安全研究与合规自查**；"
    "评测用例集不构成攻击工具，检测与判定结果为辅助参考，不作为唯一判定依据。"
)

_SEV_CLASS = {"pass": "ok", "fail": "bad", "partial": "warn", "error": "err"}


def _cell(counts: dict) -> str:
    return f"{counts.get('pass', 0)}/{counts.get('fail', 0)}/{counts.get('partial', 0)}"


def render_markdown(run: dict) -> str:
    summary = run["summary"]
    lines = [
        f"# AISentinel 评测报告 · {run['run_id']}",
        "",
        f"> 模型：`{run['model']}` ｜ 裁判：{run.get('judge') or '未启用（规则判定）'} ｜ "
        f"时间：{run['started_at']} → {run['finished_at']}",
        f"> 用例 {summary['total']} 条 ｜ 通过 {summary['pass']} · 失败 {summary['fail']} · 部分 {summary['partial']} · 错误 {summary['error']}"
        f" ｜ **风险分 {summary['risk_score']}**（0–100，越高越需关注）",
        "",
        "## 一、OWASP LLM Top10 风险矩阵（通过/失败/部分）",
        "",
        "| 编号 | 风险类 | 用例 | 结果 |",
        "|---|---|---|---|",
    ]
    for code in sorted(run["summary"]["by_owasp"]):
        counts = run["summary"]["by_owasp"][code]
        total = sum(counts.values())
        lines.append(f"| {code} | {OWASP_TITLES.get(code, '')} | {total} | {_cell(counts)} |")
    lines += ["", "## 二、分类统计（通过/失败/部分）", "", "| 类别 | 用例 | 结果 |", "|---|---|---|"]
    for category in sorted(run["summary"]["by_category"]):
        counts = run["summary"]["by_category"][category]
        total = sum(counts.values())
        lines.append(f"| {CATEGORY_TITLES.get(category, category)} | {total} | {_cell(counts)} |")

    failed = [item for item in run["results"] if item["verdict"] == "fail"]
    lines += ["", f"## 三、失败用例明细（{len(failed)} 条）", ""]
    for item in failed[:20]:
        lines += [
            f"### {item['case_id']} · {CATEGORY_TITLES.get(item['category'], item['category'])} · {item['severity']} · {item['owasp']}",
            "",
            f"- 判定：**fail**（{item['evidence']}）",
            f"- 回答摘要：{item['response'][:200]}",
            "",
        ]
    if not failed:
        lines.append("（本轮无失败用例）")
    lines += ["", "## 四、合规声明", "", DISCLAIMER, ""]
    return "\n".join(lines)


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>AISentinel 评测报告 · {run_id}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ font-family: "Segoe UI", "Microsoft YaHei", sans-serif; margin: 40px auto; max-width: 960px;
         color: #1f2937; line-height: 1.6; }}
  h1 {{ font-size: 24px; }} h2 {{ margin-top: 32px; border-bottom: 1px solid #e5e7eb; padding-bottom: 6px; }}
  .meta {{ color: #6b7280; font-size: 14px; }}
  .risk {{ font-size: 15px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 12px; font-size: 14px; }}
  th, td {{ border: 1px solid #e5e7eb; padding: 8px 10px; text-align: left; }}
  th {{ background: #f9fafb; }}
  .ok {{ color: #059669; font-weight: 600; }}
  .bad {{ color: #dc2626; font-weight: 600; }}
  .warn {{ color: #d97706; font-weight: 600; }}
  .err {{ color: #7c3aed; font-weight: 600; }}
  .cell-ok {{ background: #ecfdf5; }} .cell-bad {{ background: #fef2f2; }} .cell-warn {{ background: #fffbeb; }}
  .finding {{ border: 1px solid #fecaca; background: #fef2f2; border-radius: 8px; padding: 12px 16px; margin: 12px 0; }}
  .finding code {{ background: #fff; padding: 1px 5px; border-radius: 4px; }}
  .disclaimer {{ color: #6b7280; font-size: 13px; border-top: 1px solid #e5e7eb; padding-top: 12px; margin-top: 40px; }}
</style>
</head>
<body>
<h1>AISentinel 评测报告</h1>
<p class="meta">运行：{run_id} ｜ 模型：<b>{model}</b> ｜ 裁判：{judge} ｜ 时间：{started_at} → {finished_at}</p>
<p class="risk">用例 <b>{total}</b> 条 ｜ <span class="ok">通过 {npass}</span> · <span class="bad">失败 {nfail}</span> · <span class="warn">部分 {npartial}</span> · <span class="err">错误 {nerror}</span> ｜ 风险分 <b>{risk}</b>/100</p>
<h2>OWASP LLM Top10 风险矩阵</h2>
<table><tr><th>编号</th><th>风险类</th><th>用例</th><th>通过</th><th>失败</th><th>部分</th></tr>
{owasp_rows}
</table>
<h2>分类统计</h2>
<table><tr><th>类别</th><th>用例</th><th>通过</th><th>失败</th><th>部分</th></tr>
{category_rows}
</table>
<h2>失败用例明细（{nfail} 条）</h2>
{failed_html}
<p class="disclaimer">{disclaimer}</p>
</body>
</html>
"""


def render_html(run: dict) -> str:
    summary = run["summary"]
    owasp_rows = []
    for code in sorted(summary["by_owasp"]):
        counts = summary["by_owasp"][code]
        css = "cell-bad" if counts.get("fail") else ("cell-warn" if counts.get("partial") else "cell-ok")
        owasp_rows.append(
            f"<tr class='{css}'><td>{code}</td><td>{OWASP_TITLES.get(code, '')}</td><td>{sum(counts.values())}</td>"
            f"<td class='ok'>{counts.get('pass', 0)}</td><td class='bad'>{counts.get('fail', 0)}</td>"
            f"<td class='warn'>{counts.get('partial', 0)}</td></tr>"
        )
    category_rows = []
    for category in sorted(summary["by_category"]):
        counts = summary["by_category"][category]
        css = "cell-bad" if counts.get("fail") else ("cell-warn" if counts.get("partial") else "cell-ok")
        category_rows.append(
            f"<tr class='{css}'><td>{CATEGORY_TITLES.get(category, category)}</td><td>{sum(counts.values())}</td>"
            f"<td class='ok'>{counts.get('pass', 0)}</td><td class='bad'>{counts.get('fail', 0)}</td>"
            f"<td class='warn'>{counts.get('partial', 0)}</td></tr>"
        )
    failed = [item for item in run["results"] if item["verdict"] == "fail"]
    failed_html = "".join(
        f"<div class='finding'><b>{item['case_id']}</b> · {CATEGORY_TITLES.get(item['category'], item['category'])} · "
        f"{item['severity']} · {item['owasp']}<br>判定：<span class='bad'>fail</span>（{item['evidence']}）"
        f"<br>回答摘要：<code>{item['response'][:200]}</code></div>"
        for item in failed[:20]
    ) or "<p>（本轮无失败用例）</p>"
    return _HTML_TEMPLATE.format(
        run_id=run["run_id"],
        model=run["model"],
        judge=run.get("judge") or "未启用（规则判定）",
        started_at=run["started_at"],
        finished_at=run["finished_at"],
        total=summary["total"],
        npass=summary["pass"],
        nfail=summary["fail"],
        npartial=summary["partial"],
        nerror=summary["error"],
        risk=summary["risk_score"],
        owasp_rows="\n".join(owasp_rows),
        category_rows="\n".join(category_rows),
        failed_html=failed_html,
        disclaimer=DISCLAIMER,
    )


def write_report(run: dict, out_path: Path | str) -> tuple[Path, Path]:
    """按扩展名写出报告；always 同时写出同名 .md / .html 双格式。返回 (html_path, md_path)。"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html_path = out_path.with_suffix(".html")
    md_path = out_path.with_suffix(".md")
    html_path.write_text(render_html(run), encoding="utf-8")
    md_path.write_text(render_markdown(run), encoding="utf-8")
    return html_path, md_path
