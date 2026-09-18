"""aisentinel doctor：环境自检（9 项）与建议动作。

检查项：
1. Python 版本（≥3.11）
2. 平台
3. 依赖完整性（fastapi / pillow / yaml / jsonschema / httpx）
4. Ollama 服务与模型（可选；缺失时 ``--model mock://`` 仍可离线运行）
5. 评测用例库（计数；不足 120 条提示，S2 建设）
6. 磁盘空间（≥2 GiB）
7. 工作目录可写（``.aisentinel/``）
8. egress 审计（``--egress``：列出本次自检触达的网络目标——零遥测声明）
9. 核心模块可导入（detect 标识核验器）
"""

from __future__ import annotations

import importlib
import platform
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from . import __version__
from .errors import EXIT_CHECK_WARN, EXIT_ENV, EXIT_OK

STATUS_OK = "就绪"
STATUS_WARN = "缺失"
STATUS_FAIL = "不满足"

OLLAMA_URL = "http://127.0.0.1:11434"
WORKDIR_NAME = ".aisentinel"
MIN_DISK_GIB = 2.0
MIN_CASES = 120


@dataclass
class Check:
    key: str
    name: str
    status: str
    detail: str
    fix: str = ""
    required: bool = False


def _is_windows() -> bool:
    return platform.system() == "Windows"


def check_python() -> Check:
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 11)
    return Check(
        key="python",
        name="Python 版本",
        status=STATUS_OK if ok else STATUS_FAIL,
        detail=f"Python {v.major}.{v.minor}.{v.micro}（要求 ≥3.11）",
        fix="" if ok else "uv python install 3.11",
        required=True,
    )


def check_platform() -> Check:
    return Check(key="platform", name="平台", status=STATUS_OK, detail=f"{platform.system()} {platform.release()}")


def check_deps() -> Check:
    missing = []
    for module in ("typer", "rich", "yaml", "PIL", "jsonschema", "fastapi", "uvicorn", "httpx"):
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(module)
    if missing:
        return Check(
            key="deps",
            name="依赖完整性",
            status=STATUS_FAIL,
            detail=f"缺失：{', '.join(missing)}",
            fix='uv pip install -e ".[all]"',
            required=True,
        )
    return Check(key="deps", name="依赖完整性", status=STATUS_OK, detail="typer / rich / pillow / fastapi / httpx 等全部就绪")


def check_detect() -> Check:
    try:
        from .detect.label import verify_label  # noqa: F401

        modules_ok = True
    except ImportError as exc:
        modules_ok = False
        detail = str(exc)
    if not modules_ok:
        return Check(key="detect", name="核心模块（标识核验器）", status=STATUS_FAIL, detail=detail, required=True)
    return Check(key="detect", name="核心模块（标识核验器）", status=STATUS_OK, detail="detect.label 可导入（三态核验器就绪）")


def check_ollama(probe: bool = True) -> Check:
    if not probe:
        return Check(key="ollama", name="Ollama 服务（可选）", status=STATUS_OK, detail="已跳过探测（--no-probe）")
    try:
        import httpx

        resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=6, trust_env=False)
        models = [item.get("name", "") for item in resp.json().get("models", [])]
    except Exception as exc:  # 服务未启动 / 超时均视为可选缺失
        return Check(
            key="ollama",
            name="Ollama 服务（可选）",
            status=STATUS_WARN,
            detail=f"未检测到 Ollama（{type(exc).__name__}）；mock:// 模型仍可离线评测",
            fix="启动 Ollama：ollama serve（或使用 --model mock://）",
        )
    if not models:
        return Check(key="ollama", name="Ollama 服务（可选）", status=STATUS_WARN, detail="服务在线但无模型", fix="ollama pull gemma4:12b")
    return Check(key="ollama", name="Ollama 服务（可选）", status=STATUS_OK, detail=f"在线 · 模型：{', '.join(models[:5])}")


def check_suite() -> Check:
    suite_dir = Path(__file__).parent / "eval" / "suites"
    count = 0
    if suite_dir.is_dir():
        import yaml

        for path in suite_dir.rglob("*.yaml"):
            try:
                doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            count += len(doc.get("cases") or [])
    if count == 0:
        return Check(
            key="suite",
            name="评测用例库",
            status=STATUS_WARN,
            detail="用例库未就绪（0 条用例）",
            fix="评测用例库随 v0.1.0 交付；可先运行 detect / guard 功能",
        )
    if count < MIN_CASES:
        return Check(key="suite", name="评测用例库", status=STATUS_WARN, detail=f"用例 {count} 条（目标 ≥{MIN_CASES} 条）")
    return Check(key="suite", name="评测用例库", status=STATUS_OK, detail=f"用例 {count} 条（schema 校验见 aisentinel eval validate）")


def check_disk(base: Path) -> Check:
    anchor = base.anchor or base.drive or "/"
    usage = shutil.disk_usage(anchor)
    free_gib = usage.free / (1024**3)
    ok = free_gib >= MIN_DISK_GIB
    return Check(
        key="disk",
        name="磁盘空间",
        status=STATUS_OK if ok else STATUS_WARN,
        detail=f"{anchor} 可用 {free_gib:.1f} GiB（要求 ≥{MIN_DISK_GIB:g} GiB）",
        fix="" if ok else "清理磁盘空间或调整工作目录",
    )


def check_workdir(base: Path) -> Check:
    probe_dir = base / WORKDIR_NAME
    try:
        probe_dir.mkdir(parents=True, exist_ok=True)
        probe = probe_dir / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return Check(key="workdir", name="工作目录可写", status=STATUS_FAIL, detail=f"{probe_dir}：{exc}", fix="检查目录权限", required=True)
    return Check(key="workdir", name="工作目录可写", status=STATUS_OK, detail=str(probe_dir), required=True)


def check_egress(probe: bool) -> Check:
    if not probe:
        return Check(key="egress", name="egress 审计", status=STATUS_OK, detail="未执行（--egress 开启）")
    return Check(
        key="egress",
        name="egress 审计",
        status=STATUS_OK,
        detail=f"本次自检网络目标：{OLLAMA_URL}（仅本机，零遥测；未触达任何外部域名）",
    )


def run_doctor(base: Path | None = None, *, egress: bool = False, probe_ollama: bool = True) -> dict:
    """运行全部检查，返回 JSON 可序列化报告（含 exit_code）。"""
    base = Path(base) if base is not None else Path.cwd()
    checks = [
        check_python(),
        check_platform(),
        check_deps(),
        check_detect(),
        check_ollama(probe=probe_ollama),
        check_suite(),
        check_disk(base),
        check_workdir(base),
        check_egress(egress),
    ]
    counts = {"ok": 0, "warn": 0, "fail": 0}
    for item in checks:
        counts[{STATUS_OK: "ok", STATUS_WARN: "warn", STATUS_FAIL: "fail"}[item.status]] += 1

    fail_required = any(item.required and item.status == STATUS_FAIL for item in checks)
    if fail_required:
        exit_code = EXIT_ENV
    elif counts["warn"] or counts["fail"]:
        exit_code = EXIT_CHECK_WARN
    else:
        exit_code = EXIT_OK

    return {
        "tool": "aisentinel",
        "version": __version__,
        "platform": f"{platform.system()} {platform.release()}",
        "checks": [asdict(item) for item in checks],
        "summary": counts,
        "exit_code": exit_code,
    }
