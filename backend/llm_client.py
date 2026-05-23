from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class LLMClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    base_url: str
    model: str


def _env_first(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _resolve_llm_config() -> LLMConfig:
    api_key = _env_first("LLM_API_KEY", "DEEPSEEK_API_KEY")
    if not api_key:
        raise LLMClientError("missing LLM_API_KEY or DEEPSEEK_API_KEY")

    model = _env_first("LLM_MODEL_ID", "LLM_MODEL", "DEEPSEEK_MODEL") or "deepseek-chat"
    base_url = _env_first("LLM_BASE_URL", "DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
    return LLMConfig(api_key=api_key, base_url=base_url.rstrip("/"), model=model)


def analyze_with_deepseek(prompt: str, timeout_sec: int = 60) -> dict[str, Any]:
    config = _resolve_llm_config()
    endpoint = f"{config.base_url}/chat/completions"

    body = {
        "model": config.model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一名资深 AI 实验分析师。"
                    "请始终使用中文输出，内容要简洁、可执行。"
                    "请按以下结构输出："
                    "1) 总结 "
                    "2) 关键发现 "
                    "3) 风险与失败模式 "
                    "4) 下一步建议（3-5 条）"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            payload = json.loads(raw)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise LLMClientError(f"deepseek http error {e.code}: {detail[:500]}") from e
    except urllib.error.URLError as e:
        raise LLMClientError(f"deepseek network error: {e.reason}") from e
    except Exception as e:  # pragma: no cover
        raise LLMClientError(f"deepseek request failed: {e}") from e

    try:
        analysis = payload["choices"][0]["message"]["content"]
        if not isinstance(analysis, str) or not analysis.strip():
            raise ValueError("empty analysis")
    except Exception as e:
        raise LLMClientError("deepseek response missing choices[0].message.content") from e

    return {"analysis": analysis, "model": config.model}
