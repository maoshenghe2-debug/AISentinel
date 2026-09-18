"""AISentinel · 大模型安全评测与 AI 内容鉴别平台。

模块规划：
- ``aisentinel.doctor``      环境自检（依赖 / Ollama / 用例库 / egress 审计）
- ``aisentinel.eval``        红队评测套件（用例库 + 执行器 + 双轨评分）
- ``aisentinel.guard``       运行时护栏（输入注入检测 / 输出 PII 与违规过滤 / 策略引擎）
- ``aisentinel.detect``      AIGC 鉴别（★ 标识核验器：元数据 / 隐式标识三态判定）
- ``aisentinel.compliance``  合规自查报告（暂行办法 + 标识办法条款映射）
"""

__version__ = "0.1.0"
__author__ = "Maosheng He (maoshenghe2-debug)"
