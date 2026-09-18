"""aisentinel.eval：红队安全评测套件（用例库 / 执行器 / 双轨评分 / 风险矩阵）。"""

from .executor import run_eval
from .models import MockAdapter, OllamaAdapter, OpenAIAdapter, get_adapter
from .report import render_html, render_markdown, write_report
from .scoring import cohen_kappa, score_response
from .suite import CATEGORY_TITLES, TestCase, load_suite, suite_stats

__all__ = [
    "CATEGORY_TITLES",
    "MockAdapter",
    "OllamaAdapter",
    "OpenAIAdapter",
    "TestCase",
    "cohen_kappa",
    "get_adapter",
    "load_suite",
    "render_html",
    "render_markdown",
    "run_eval",
    "score_response",
    "suite_stats",
    "write_report",
]
