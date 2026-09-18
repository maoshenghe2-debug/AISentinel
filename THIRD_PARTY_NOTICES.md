# 第三方组件与许可说明

本项目以 **Apache-2.0** 发布（见 `LICENSE`）。运行时依赖与参考项如下：

| 组件 | 许可 | 使用方式 |
|---|---|---|
| Typer / Rich | MIT | Python CLI 与终端渲染 |
| PyYAML | MIT | 用例库 / 策略 / 字段白名单解析 |
| Pillow | HPND | 图像元数据（EXIF / XMP / 文本块）解析 |
| jsonschema | MIT | 数据契约校验（LabelCheckRecord / 用例 / EvalResult） |
| FastAPI / Uvicorn | MIT / BSD | 护栏代理服务（默认绑定 127.0.0.1） |
| httpx | BSD-3-Clause | 模型适配器（Ollama / OpenAI 兼容） |
| garak（可选 `[redteam]`） | Apache-2.0 | 对照评测引擎（子进程 / 库调用，v1.1 集成） |
| guardrails-ai（参考） | Apache-2.0 | 输出侧校验设计参考（API 设计对照） |

许可红线：不链接 / 不捆绑 GPL 组件；外部模型与数据集各自遵循其原始许可，权重不入库（由脚本按需拉取）。
