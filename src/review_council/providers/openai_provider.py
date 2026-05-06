"""Stub adapter for the OpenAI / GPT provider.

Registered so `--provider openai` and `--provider gpt` resolve, but
invocation raises with a clear message pointing to the manual fallback.
This keeps the code path discoverable without forcing an SDK
dependency on the project today.
"""

from __future__ import annotations

from review_council.providers import CompletionRequest, register


def _openai_complete(req: CompletionRequest) -> str:
    raise NotImplementedError(
        "openai/gpt provider is registered but not yet wired to a real SDK. "
        "Use --provider manual --external-input <path> --prompt-cache <path> to "
        "run the prompt in your OpenAI client and drop the response back."
    )


register("openai", _openai_complete)
register("gpt", _openai_complete)
