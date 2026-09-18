# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.1.0] - 2026-09-18

### Added
- **标识核验器（★）**：对照《人工智能生成合成内容标识办法》（第四条显式 / 第五条隐式 / 第六条核验 /
  第十条不得否认篡改）的三态判定——`has_label` / `suspected_cleaned` / `no_label`；
  解析 PNG 文本块、EXIF、XMP、JPEG COM、C2PA 数据；字段白名单 + 值提示双层判定；
  `LabelCheckRecord` schema 校验 + CSV 证据字段（批量核验）。
- **红队评测套件**：124 条中文用例（提示注入 28 / 越狱 28 / 信息泄露 24 / 工具滥用 20 / 内容安全 24），
  覆盖 OWASP LLM Top10 中 8 类；`TestCase`/`EvalResult` schema 校验；
  模型适配器 `mock://`（离线）/ `ollama:<模型>` / `openai:<模型>`（OpenAI 兼容）；
  双轨评分（规则判定默认 + 可选裁判模型，启用前显式提示数据出境）+ Cohen's κ 工具；
  OWASP 风险矩阵报告（HTML 单文件 + Markdown）。
- **运行时护栏**：策略引擎（输入注入 5 类规则 + 输出 PII/违规拦截），
  动作裁决 `block > mask > alert > allow`，日志安全化；
  FastAPI OpenAI 兼容代理（默认仅监听 127.0.0.1）；
  基准测评（20 正 + 20 负固定样本集 → 拦截率 100% / 误报率 0% / P95 0.007 ms）。
- **合规自查**：18 条法规条款 → 功能 → 复核方式映射（《生成式人工智能服务管理暂行办法》·
  《人工智能生成合成内容标识办法》·《互联网信息服务深度合成管理规定》· GB 45438-2025），
  Markdown + HTML 双渲染报告。
- **demo**：四幕端到端演示（护栏 → 标识核验 → 红队评测 → 合规自查），mock 模式 0.24 s。
- **doctor**：9 项环境自检（含 Ollama 探测与 `--egress` 审计），退出码语义化。
- CI：ubuntu × Python 3.11/3.12（ruff + pytest + doctor smoke）。

### Tests
- 31 项测试：标识核验（5 类矩阵 + 阴性集 + schema + CSV）· 评测（用例库/评分/mock 端到端/κ）·
  护栏（检测器/裁决优先级/代理/基准）· 合规与 demo 冒烟 · doctor。

[0.1.0]: https://github.com/maoshenghe2-debug/AISentinel/releases/tag/v0.1.0
