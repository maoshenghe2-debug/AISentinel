"""评测用例库加载与校验（schema 驱动，CI 全量校验）。

用例文件：``suites/<category>.yaml``；每个文件顶部含 version/category，
``cases`` 列表逐条对照 ``case.schema.json`` 校验。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

SUITES_DIR = Path(__file__).parent / "suites"
CASE_SCHEMA_PATH = Path(__file__).parent / "case.schema.json"

CATEGORY_TITLES = {
    "prompt_injection": "提示注入",
    "jailbreak": "越狱攻击",
    "data_leak": "信息泄露",
    "tool_abuse": "工具滥用",
    "content_safety": "内容安全",
}


@dataclass
class TestCase:
    __test__ = False  # 防止 pytest 误收集（Test* 前缀类）

    id: str
    category: str
    severity: str
    prompt: str
    check: dict
    owasp: str = ""
    atlas: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "severity": self.severity,
            "prompt": self.prompt,
            "check": self.check,
            "owasp": self.owasp,
            "atlas": self.atlas,
            "notes": self.notes,
        }


def validate_case(case: dict) -> None:
    """对照 schema 校验单条用例；失败抛 ValueError。"""
    schema = json.loads(CASE_SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(Draft7Validator(schema).iter_errors(case), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(f"{list(err.path)}: {err.message}" for err in errors[:3])
        raise ValueError(f"用例 {case.get('id', '?')} schema 校验失败：{detail}")


def load_suite(suites_dir: Path | None = None) -> list[TestCase]:
    """加载全部用例（含 schema 校验），按 (category, id) 排序。"""
    root = suites_dir or SUITES_DIR
    cases: list[TestCase] = []
    seen: set[str] = set()
    for path in sorted(root.rglob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for raw in doc.get("cases", []):
            validate_case(raw)
            if raw["id"] in seen:
                raise ValueError(f"用例 id 重复：{raw['id']}（{path.name}）")
            seen.add(raw["id"])
            cases.append(
                TestCase(
                    id=raw["id"],
                    category=raw["category"],
                    severity=raw["severity"],
                    prompt=raw["prompt"],
                    check=raw["check"],
                    owasp=raw.get("owasp", ""),
                    atlas=raw.get("atlas", ""),
                    notes=raw.get("notes", ""),
                )
            )
    return sorted(cases, key=lambda item: (item.category, item.id))


def suite_stats(cases: list[TestCase]) -> dict:
    """统计：总数 / 分类 / OWASP 覆盖 / 分级。"""
    by_category: dict[str, int] = {}
    by_owasp: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for case in cases:
        by_category[case.category] = by_category.get(case.category, 0) + 1
        by_owasp[case.owasp] = by_owasp.get(case.owasp, 0) + 1
        by_severity[case.severity] = by_severity.get(case.severity, 0) + 1
    return {
        "total": len(cases),
        "by_category": by_category,
        "by_owasp": by_owasp,
        "by_severity": by_severity,
    }
