"""doctor 环境自检测试（结构 / egress 审计 / suite 降级）。"""

from __future__ import annotations

from aisentinel.doctor import run_doctor

EXPECTED_KEYS = {"python", "platform", "deps", "detect", "ollama", "suite", "disk", "workdir", "egress"}


def test_doctor_structure():
    report = run_doctor(probe_ollama=False)
    keys = {item["key"] for item in report["checks"]}
    assert len(report["checks"]) >= 8
    assert keys >= EXPECTED_KEYS
    assert report["exit_code"] in (0, 1, 3)
    assert report["summary"]["ok"] >= 3


def test_doctor_egress_audit_reports_local_only():
    report = run_doctor(egress=True, probe_ollama=False)
    egress = next(item for item in report["checks"] if item["key"] == "egress")
    assert "127.0.0.1" in egress["detail"] or "localhost" in egress["detail"]
    assert "零遥测" in egress["detail"]


def test_doctor_suite_check_degrades_gracefully():
    report = run_doctor(probe_ollama=False)
    suite = next(item for item in report["checks"] if item["key"] == "suite")
    assert suite["status"] in ("就绪", "缺失")  # 用例库未就绪时为「缺失」而非「不满足」
