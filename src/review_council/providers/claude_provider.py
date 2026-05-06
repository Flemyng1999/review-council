"""Stub adapter for the Anthropic / Claude provider.

Registered so `--provider claude` resolves, but invocation raises with
a clear message pointing to the manual fallback. Same rationale as the
openai stub: keep the seam visible without committing to an SDK
dependency now.
"""

from __future__ import annotations

from review_council.providers import CompletionRequest, register


def _claude_complete(req: CompletionRequest) -> str:
    raise NotImplementedError(
        "claude provider is registered but not yet wired to a real SDK. "
        "Use --provider manual --external-input <path> --prompt-cache <path> to "
        "run the prompt in Claude and drop the response back."
    )


register("claude", _claude_complete)
