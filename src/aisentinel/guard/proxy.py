"""FastAPI 护栏代理（OpenAI 兼容 ``/v1/chat/completions``）；默认仅监听 127.0.0.1。"""

from __future__ import annotations

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .. import __version__
from .engine import Guard

OLLAMA_V1 = "http://127.0.0.1:11434/v1/chat/completions"
MOCK_REPLY = "已收到您的请求并完成处理。如需人工支持，请拨打客服电话 13800138000。"
MOCK_CANARY = "内部配置回显：密钥串 AISENTINEL-CANARY，请勿外传。"


def _upstream_reply(spec: str, text: str) -> str:
    """获取上游回复：mock://（内置演示）或 ollama:<模型>（本机直连）。"""
    if spec.startswith("mock"):
        return MOCK_CANARY if "泄露" in text else MOCK_REPLY
    if spec.startswith("ollama:"):
        model = spec.split(":", 1)[1] or "gemma4:12b"
        resp = httpx.post(
            OLLAMA_V1,
            json={"model": model, "messages": [{"role": "user", "content": text}], "temperature": 0.2},
            timeout=120,
            trust_env=False,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    raise ValueError(f"未知上游规格：{spec}（支持 mock:// / ollama:<模型>）")


def create_app(policy_path=None, upstream: str = "mock://") -> FastAPI:
    """构造护栏代理应用（策略路径 + 上游规格可配）。"""
    guard = Guard(policy_path)
    app = FastAPI(
        title="AISentinel Guard",
        version=__version__,
        description="运行时护栏：输入注入检测 / 输出 PII 脱敏与违规拦截（OpenAI 兼容代理）",
    )

    @app.get("/healthz")
    def healthz() -> dict:
        return {
            "status": "ok",
            "upstream": upstream,
            "bind": guard.bind,
            "policy_version": guard.policy.get("version", ""),
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        payload = await request.json()
        messages = payload.get("messages") or []
        user_text = "\n".join(
            str(item.get("content", "")) for item in messages if isinstance(item, dict) and item.get("role") == "user"
        )
        decision_in = guard.check_input(user_text)
        if decision_in.action == "block":
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "type": "aisentinel_blocked",
                        "stage": "input",
                        "message": "请求被 AISentinel 护栏拦截（提示注入类风险）",
                        "hits": decision_in.to_meta()["hits"],
                    }
                },
            )
        model_text = _upstream_reply(upstream, decision_in.text)
        decision_out = guard.check_output(model_text)
        content = "[AISentinel] 输出已被拦截（检测到敏感内容，已阻断）。" if decision_out.action == "block" else decision_out.text
        return {
            "id": "chatcmpl-aisentinel",
            "object": "chat.completion",
            "model": payload.get("model", f"aisentinel-guard/{upstream}"),
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
            ],
            "aisentinel": {"input": decision_in.to_meta(), "output": decision_out.to_meta()},
        }

    return app
