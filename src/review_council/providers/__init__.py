"""LLM provider registry.

The registry is intentionally small: every provider is a callable
`(CompletionRequest) -> str`. Built-in providers register themselves on
import. The registry is the single seam every strong-model stage goes
through, so that swapping `--provider deepseek` for `--provider claude`
or `--provider manual` does not require touching stage code.

This is not a plugin system. It is a routing table for two real backends
(deepseek for production, manual for cross-provider via external file
drop-off) and two stubs (openai/claude) that raise with a clear hint
pointing at the manual route.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class CompletionRequest:
    prompt: str
    model: str = ""
    temperature: float = 0.2
    api_key: str | None = None
    base_url: str = ""
    external_input_path: Path | None = None
    prompt_cache_path: Path | None = None
    extra: dict = field(default_factory=dict)


ProviderFunc = Callable[[CompletionRequest], str]

_REGISTRY: dict[str, ProviderFunc] = {}


def register(name: str, func: ProviderFunc) -> None:
    _REGISTRY[name] = func


def is_registered(name: str) -> bool:
    return name in _REGISTRY


def list_providers() -> list[str]:
    return sorted(_REGISTRY)


def complete(request: CompletionRequest, *, provider: str) -> str:
    impl = _REGISTRY.get(provider)
    if impl is None:
        raise ValueError(
            f"unknown provider {provider!r}; registered: {list_providers()}"
        )
    return impl(request)


# Bootstrap: import provider modules so they self-register.
def _bootstrap() -> None:
    # Imports are local so a missing optional dependency in one provider
    # does not crash registration of the others.
    from review_council.providers import deepseek_adapter  # noqa: F401
    from review_council.providers import manual_provider  # noqa: F401
    from review_council.providers import openai_provider  # noqa: F401
    from review_council.providers import claude_provider  # noqa: F401


_bootstrap()
