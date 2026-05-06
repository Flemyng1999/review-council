"""DeepSeek OpenAI-compatible chat API client."""

from __future__ import annotations

import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_BASE = 1.5  # seconds


@dataclass(frozen=True)
class DeepSeekRequest:
    api_key: str
    prompt: str
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    reasoning_effort: str | None = None
    thinking: bool | None = None
    temperature: float = 0.2


def _is_retryable_http(code: int) -> bool:
    return code == 429 or 500 <= code < 600


def _is_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return _is_retryable_http(exc.code)
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (ssl.SSLError, socket.timeout, ConnectionError, OSError)):
            return True
        text = str(reason or "")
        if "EOF" in text or "timed out" in text or "reset" in text.lower():
            return True
        return False
    if isinstance(exc, (ssl.SSLError, socket.timeout, ConnectionError, TimeoutError)):
        return True
    return False


def chat_completion(
    request: DeepSeekRequest,
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_base: float = DEFAULT_BACKOFF_BASE,
    sleep: Callable[[float], None] = time.sleep,
    opener: Callable | None = None,
) -> str:
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

    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
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
            _open = opener or urllib.request.urlopen
            with _open(http_request, timeout=120) as response:
                payload = json.loads(response.read().decode("utf-8"))
            try:
                return str(payload["choices"][0]["message"]["content"])
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError(f"Unexpected DeepSeek API response shape: {payload}") from exc
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if not _is_retryable_http(exc.code) or attempt >= max_attempts:
                detail = ""
                try:
                    detail = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    pass
                raise RuntimeError(f"DeepSeek API HTTP {exc.code}: {detail}") from exc
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if not _is_retryable_exception(exc) or attempt >= max_attempts:
                raise
        sleep(backoff_base * (2 ** (attempt - 1)))

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("DeepSeek chat_completion exhausted retries without an exception")
