"""DeepSeek OpenAI-compatible chat API client."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"


@dataclass(frozen=True)
class DeepSeekRequest:
    api_key: str
    prompt: str
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    reasoning_effort: str | None = None
    thinking: bool | None = None
    temperature: float = 0.2


def chat_completion(request: DeepSeekRequest) -> str:
    body: dict[str, object] = {
        "model": request.model,
        "messages": [{"role": "user", "content": request.prompt}],
        "stream": False,
        "temperature": request.temperature,
    }
    if request.reasoning_effort:
        body["reasoning_effort"] = request.reasoning_effort
    if request.thinking is not None:
        body["thinking"] = {"type": "enabled" if request.thinking else "disabled"}

    url = request.base_url.rstrip("/") + "/chat/completions"
    http_request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {request.api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(http_request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API HTTP {exc.code}: {detail}") from exc

    try:
        return str(payload["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected DeepSeek API response shape: {payload}") from exc
