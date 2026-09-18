# AISentinel · 大模型安全评测与 AI 内容鉴别平台

> 红队评测 → 运行时护栏 → 内容标识核验 → 合规自查：面向大模型应用安全与 AIGC 治理的一体化工具链。

[![CI](https://github.com/maoshenghe2-debug/AISentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/maoshenghe2-debug/AISentinel/actions/workflows/ci.yml)
![license](https://img.shields.io/badge/license-Apache--2.0-blue)
![python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)

## 定位

AISentinel 面向 **AI 安全研究、评测与合规自查**场景，提供四段式能力：

1. **红队安全评测**（`aisentinel eval`）—— 中文用例库（注入 / 越狱 / 泄露 / 工具滥用 / 内容安全）+ 模型适配器（Ollama / OpenAI 兼容 / `mock://`）+ 双轨评分（规则 + 可选裁判模型）+ OWASP LLM Top10 风险矩阵报告
2. **运行时护栏**（`aisentinel guard`）—— 输入注入检测 / 输出 PII 与违规过滤 / YAML 策略引擎（拦截 / 脱敏 / 告警）+ OpenAI 兼容代理（默认绑定 `127.0.0.1`）
3. **内容标识核验 ★**（`aisentinel detect`）—— 对照《人工智能生成合成内容标识办法》核验文件元数据隐式标识：**三态判定**（有标识 / 疑似被清理 / 无标识）+ CSV 证据字段
4. **合规自查报告**（`aisentinel compliance`）—— 《暂行办法》+《标识办法》条款映射（功能点 → 法规条目 → 支撑证据 → 差距建议）

## 快速上手

```bash
uv venv --python 3.11
uv pip install -e ".[all]"

aisentinel doctor                     # 环境自检（含 Ollama / 用例库 / egress 审计）
aisentinel detect file sample.png     # ★ 标识核验（三态结论卡）
aisentinel detect dir imgs/ --out label_check.csv
aisentinel eval run --model mock://   # 离线可复现评测
aisentinel demo                       # 一键演示（≤15 分钟）
```

## 环境约定

| 项 | 约定 |
|---|---|
| 默认依赖 | 轻量（typer / rich / pillow / fastapi / httpx）；`[redteam]`=garak，`[ml]`=numpy+scikit-learn |
| 模型 | 本机 Ollama（如 `gemma4:12b`）或任意 OpenAI 兼容服务；**`mock://` 适配器离线可进 CI** |
| 隐私 | 零遥测；本地服务默认绑定 `127.0.0.1`；日志默认不落原文（`doctor --egress` 可审计） |

## 合规声明

- 本项目用于 **AI 安全研究、评测与合规自查**，不对任何第三方系统实施攻击；
- 评测用例集供防御性研究与效果验证使用，使用者须遵守《生成式人工智能服务管理暂行办法》《人工智能生成合成内容标识办法》等法律法规；
- 检测结果为**辅助参考**，不作为唯一判定依据。

## 许可

Apache-2.0（见 `LICENSE`；第三方依赖见 `THIRD_PARTY_NOTICES.md`）。
