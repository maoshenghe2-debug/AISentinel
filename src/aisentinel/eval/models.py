"""模型适配器：``mock://``（离线可复现）· ``ollama:<模型>`` · ``openai:<模型>``（OpenAI 兼容）。

- 本机服务一律 ``trust_env=False`` 直连（绝不经过系统代理）；
- ``mock://`` 使用内置固定回答集（``mock_responses.yaml``），可在 CI 离线运行。
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import yaml

OLLAMA_URL = "http://127.0.0.1:11434"
MOCK_RESPONSES_PATH = Path(__file__).parent / "mock_responses.yaml"

REFUSAL_FALLBACK = "抱歉，我无法协助该请求。出于安全与合规考虑，我不能执行或提供此类内容。"


class MockAdapter:
    """固定回答集适配器（按用例 id 匹配；缺省返回标准拒答）。"""

    def __init__(self, responses: dict | None = None):
        if responses is None:
            doc = yaml.safe_load(MOCK_RESPONSES_PATH.read_text(encoding="utf-8")) or {}
            responses = dict(doc.get("responses") or {})
        self.responses = responses
        self.name = "mock://"

    def generate(self, prompt: str, case_id: str = "") -> str:
        return self.responses.get(case_id, self.responses.get("__default__", REFUSAL_FALLBACK))


class OllamaAdapter:
    """本机 Ollama（/api/chat）。"""

    def __init__(
        self,
        model: str = "gemma4:12b",
        timeout: int = 600,
        temperature: float = 0.2,
        num_predict: int = 256,
        think: bool | None = False,
    ):
        self.model = model
        self.name = f"ollama:{model}"
        self.timeout = timeout
        self.temperature = temperature
        self.num_predict = num_predict
        self.think = think

    def generate(self, prompt: str, case_id: str = "") -> str:
        payload: dict = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": self.num_predict},
        }
        if self.think is not None:
            payload["think"] = self.think
        resp = httpx.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
            timeout=self.timeout,
            trust_env=False,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


class OpenAIAdapter:
    """任意 OpenAI 兼容服务（base_url + api_key 走环境变量或参数）。"""

    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None, timeout: int = 120):
        self.model = model
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.timeout = timeout
        self.name = f"openai:{model}"

    def generate(self, prompt: str, case_id: str = "") -> str:
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def get_adapter(spec: str):
    """解析模型规格：``mock://`` / ``ollama:gemma4:12b`` / ``openai:<模型>``。"""
    if spec in ("mock://", "mock"):
        return MockAdapter()
    if spec.startswith("ollama:"):
        return OllamaAdapter(model=spec.split(":", 1)[1] or "gemma4:12b")
    if spec.startswith("openai:"):
        return OpenAIAdapter(model=spec.split(":", 1)[1])
    raise ValueError(f"未知模型规格：{spec}（支持 mock:// / ollama:<模型> / openai:<模型>）")
