"""护栏引擎：输入/输出检查、动作裁决（block > mask > alert > allow）与脱敏。

设计要点：
- 多命中时取最高优先级动作；
- mask 命中逐条替换为 ``[已脱敏]``；
- ``sanitize_for_log`` 保证日志不落原文（先按输出 PII 规则脱敏）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .detectors import ACTION_ORDER, RuleSet, compile_rule_sets, load_policy

MASK_REPLACEMENT = "[已脱敏]"
BLOCK_REPLACEMENT = "[AISentinel] 内容已被护栏拦截。"


@dataclass
class GuardDecision:
    """一次护栏裁决结果。"""

    stage: str
    action: str
    hits: list[dict] = field(default_factory=list)
    text: str = ""

    def to_dict(self) -> dict:
        return {"stage": self.stage, "action": self.action, "hits": self.hits}

    def to_meta(self) -> dict:
        """用于响应元数据的精简视图（不含命中原文）。"""
        return {
            "stage": self.stage,
            "action": self.action,
            "hits": [{"rule": hit["rule"], "category": hit["category"], "action": hit["action"]} for hit in self.hits],
        }


class Guard:
    """策略驱动的输入/输出护栏。"""

    def __init__(self, policy_path: Path | str | None = None):
        self.policy = load_policy(policy_path)
        self.input_rules, self.output_rules = compile_rule_sets(self.policy)
        self.bind = str(self.policy.get("bind", "127.0.0.1"))

    def check_input(self, text: str) -> GuardDecision:
        return self._check(text, self.input_rules, "input")

    def check_output(self, text: str) -> GuardDecision:
        return self._check(text, self.output_rules, "output")

    def _check(self, text: str, ruleset: RuleSet, stage: str) -> GuardDecision:
        text = text or ""
        hits = ruleset.match(text)
        action = "allow"
        for hit in hits:
            if ACTION_ORDER[hit.action] > ACTION_ORDER[action]:
                action = hit.action
        out = text
        if action == "mask":
            for hit in hits:
                if hit.action == "mask":
                    out = re.sub(hit.pattern, MASK_REPLACEMENT, out)
        elif action == "block":
            out = BLOCK_REPLACEMENT
        return GuardDecision(stage=stage, action=action, hits=[hit.to_dict() for hit in hits], text=out)

    def sanitize_for_log(self, text: str, limit: int = 200) -> str:
        """日志安全化：按输出 PII 规则脱敏后再截断（日志不落原文）。"""
        out = text or ""
        for rule in self.output_rules.rules:
            if rule["category"] == "pii":
                out = rule["_re"].sub(MASK_REPLACEMENT, out)
        return out[:limit]
