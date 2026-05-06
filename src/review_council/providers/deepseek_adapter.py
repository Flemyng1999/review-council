"""Adapter exposing the existing DeepSeek client through the provider registry."""

from __future__ import annotations

from review_council.providers import CompletionRequest, register
from review_council.providers.deepseek import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DeepSeekRequest,
    chat_completion,
)


def _deepseek_complete(req: CompletionRequest) -> str:
    if not req.api_key:
        raise RuntimeError(
            "deepseek provider requires DEEPSEEK_API_KEY (passed via api_key)"
        )
    return chat_completion(
        DeepSeekRequest(
            api_key=req.api_key,
            prompt=req.prompt,
            model=req.model or DEFAULT_MODEL,
            base_url=req.base_url or DEFAULT_BASE_URL,
            temperature=req.temperature,
        )
    )


register("deepseek", _deepseek_complete)
