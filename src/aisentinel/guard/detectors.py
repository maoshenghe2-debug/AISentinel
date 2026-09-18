"""护栏检测器：策略加载、规则编译与匹配。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_POLICY_PATH = Path(__file__).parent / "policies" / "default.yaml"
ACTION_ORDER = {"allow": 0, "alert": 1, "mask": 2, "block": 3}


@dataclass
class RuleHit:
    """一次规则命中。"""

    rule_id: str
    category: str
    action: str
    stage: str
    match: str
    pattern: str

    def to_dict(self) -> dict:
        return {
            "rule": self.rule_id,
            "category": self.category,
            "action": self.action,
            "stage": self.stage,
            "match": self.match,
        }


class RuleSet:
    """某一阶段（input/output）的编译后规则集。"""

    def __init__(self, stage: str, rules: list[dict]):
        self.stage = stage
        self.rules: list[dict] = []
        for raw in rules:
            self.rules.append({**raw, "_re": re.compile(raw["pattern"])})

    def match(self, text: str) -> list[RuleHit]:
        hits: list[RuleHit] = []
        for rule in self.rules:
            found = rule["_re"].search(text)
            if found:
                hits.append(
                    RuleHit(
                        rule_id=rule["id"],
                        category=rule["category"],
                        action=rule["action"],
                        stage=self.stage,
                        match=found.group(0)[:80],
                        pattern=rule["pattern"],
                    )
                )
        return hits


def load_policy(path: Path | str | None = None) -> dict:
    """加载策略 YAML（默认内置 default.yaml）。"""
    with open(path or DEFAULT_POLICY_PATH, encoding="utf-8") as handle:
        policy = yaml.safe_load(handle) or {}
    for stage in ("input", "output"):
        for rule in policy.get(stage) or []:
            for field in ("id", "category", "action", "pattern"):
                if field not in rule:
                    raise ValueError(f"策略规则缺少字段 {field}：{rule}")
            if rule["action"] not in ACTION_ORDER:
                raise ValueError(f"未知 action：{rule['action']}（规则 {rule['id']}）")
    return policy


def compile_rule_sets(policy: dict) -> tuple[RuleSet, RuleSet]:
    return (
        RuleSet("input", policy.get("input") or []),
        RuleSet("output", policy.get("output") or []),
    )
