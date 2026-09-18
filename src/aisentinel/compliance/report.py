"""合规自查报告：条款 → 功能 → 复核方式（Markdown + HTML 双渲染）。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

MAPPING_PATH = Path(__file__).parent / "mapping.yaml"

DISCLAIMER = (
    "本报告由 AISentinel 自动生成，用于工具能力与法规条款的**对照自查**，不构成法律意见；"
    "引用条文以官方发布文本为准，条款适用性请结合具体业务场景由合规专业人员复核。"
)


def load_mapping(path: Path | str | None = None) -> dict:
    with open(path or MAPPING_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _grouped(items: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for item in items:
        groups.setdefault(item["source"], []).append(item)
    return groups


def render_markdown(doc: dict, *, generated_at: str | None = None, version: str = "") -> str:
    items = doc.get("items") or []
    stamp = generated_at or datetime.now(UTC).isoformat(timespec="seconds")
    lines = [
        "# AISentinel 合规自查报告",
        "",
        f"> 生成时间：{stamp} ｜ 工具版本：{version} ｜ 条款映射：{len(items)} 条",
        "> 法规基准：《生成式人工智能服务管理暂行办法》· 《人工智能生成合成内容标识办法》· "
        "《互联网信息服务深度合成管理规定》· GB 45438-2025（强制性国标）",
        "",
        "## 一、条款映射",
        "",
    ]
    for source, group_items in _grouped(items).items():
        lines += [f"### {source}", "", "| 条款 | 合规要求 | AISentinel 功能 | 复核方式 |", "|---|---|---|---|"]
        for item in group_items:
            lines.append(f"| {item['article']} | {item['requirement']} | {item['feature']} | `{item['verify']}` |")
        lines.append("")
    lines += ["## 二、声明与边界", "", DISCLAIMER, ""]
    return "\n".join(lines)


def render_html(doc: dict, *, generated_at: str | None = None, version: str = "") -> str:
    items = doc.get("items") or []
    stamp = generated_at or datetime.now(UTC).isoformat(timespec="seconds")
    sections = []
    for source, group_items in _grouped(items).items():
        rows = "\n".join(
            "<tr>"
            f"<td class='art'>{item['article']}</td>"
            f"<td>{item['requirement']}</td>"
            f"<td>{item['feature']}</td>"
            f"<td><code>{item['verify']}</code></td>"
            "</tr>"
            for item in group_items
        )
        sections.append(
            f"<h2>{source}</h2><table><thead><tr><th>条款</th><th>合规要求</th><th>AISentinel 功能</th><th>复核方式</th></tr></thead><tbody>{rows}</tbody></table>"
        )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>AISentinel 合规自查报告</title>
<style>
  body {{ font-family: system-ui, "Segoe UI", "Microsoft YaHei", sans-serif; margin: 2rem auto; max-width: 1080px; color: #1f2933; padding: 0 1rem; }}
  h1 {{ font-size: 1.6rem; }}
  h2 {{ font-size: 1.15rem; margin-top: 1.8rem; border-left: 4px solid #2b6cb0; padding-left: .6rem; }}
  .meta {{ color: #52606d; font-size: .92rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: .6rem; font-size: .9rem; }}
  th, td {{ border: 1px solid #cbd2d9; padding: .45rem .6rem; text-align: left; vertical-align: top; }}
  th {{ background: #f0f4f8; }}
  .art {{ white-space: nowrap; font-weight: 600; }}
  code {{ background: #f0f4f8; padding: .1rem .3rem; border-radius: 4px; font-size: .85em; }}
  .note {{ background: #fffbea; border: 1px solid #f0e5b0; padding: .7rem .9rem; border-radius: 6px; margin-top: 1.2rem; font-size: .9rem; }}
</style>
</head>
<body>
<h1>AISentinel 合规自查报告</h1>
<p class="meta">生成时间：{stamp} ｜ 工具版本：{version} ｜ 条款映射：{len(items)} 条<br>
法规基准：《生成式人工智能服务管理暂行办法》· 《人工智能生成合成内容标识办法》· 《互联网信息服务深度合成管理规定》· GB 45438-2025（强制性国标）</p>
{''.join(sections)}
<div class="note">{DISCLAIMER}</div>
</body>
</html>
"""


def write_report(out_path: Path | str, *, doc: dict | None = None, version: str = "") -> tuple[Path, Path]:
    """写出报告（.html 与 .md 双份），返回 (html_path, md_path)。"""
    doc = doc or load_mapping()
    out = Path(out_path)
    if out.suffix.lower() == ".md":
        md_path = out
        html_path = out.with_suffix(".html")
    else:
        html_path = out if out.suffix.lower() == ".html" else out.with_suffix(".html")
        md_path = html_path.with_suffix(".md")
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    html_path.write_text(render_html(doc, generated_at=stamp, version=version), encoding="utf-8")
    md_path.write_text(render_markdown(doc, generated_at=stamp, version=version), encoding="utf-8")
    return html_path, md_path
