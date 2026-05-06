"""Manual / external_file provider.

Reads a previously-generated LLM response from `external_input_path`.
If the response file does not yet exist, writes the rendered prompt to
`prompt_cache_path` (when provided) and raises `ManualPendingError` so
the caller can either skip the stage gracefully or instruct the user to
generate the response in an external LLM and re-run.

This is the path that supports cross-provider critique without requiring
us to embed every vendor SDK. It is deliberately minimal: drop the
response in, re-run, the rest of the pipeline (redaction, validator,
plan integration) takes over.
"""

from __future__ import annotations

from pathlib import Path

from review_council.providers import CompletionRequest, register


class ManualPendingError(RuntimeError):
    """Raised when the manual provider's external response file is missing."""

    def __init__(self, prompt_cache: Path | None, response_path: Path | None) -> None:
        self.prompt_cache = prompt_cache
        self.response_path = response_path
        msg = (
            f"manual provider response not found at {response_path!r}."
        )
        if prompt_cache:
            msg += (
                f" Prompt cached at {prompt_cache!r}. Run it in your external "
                f"LLM, write the response to the response path, and re-run."
            )
        else:
            msg += (
                " Provide --prompt-cache so the prompt can be written for"
                " external execution."
            )
        super().__init__(msg)


def _manual_complete(req: CompletionRequest) -> str:
    response_path = req.external_input_path
    if response_path is None:
        raise RuntimeError(
            "manual provider requires --external-input <path> pointing to an"
            " LLM response file (or to the path where one will be dropped)."
        )

    response_path = Path(response_path)
    if response_path.exists() and response_path.is_file():
        return response_path.read_text(encoding="utf-8")

    prompt_cache = Path(req.prompt_cache_path) if req.prompt_cache_path else None
    if prompt_cache is not None:
        prompt_cache.parent.mkdir(parents=True, exist_ok=True)
        prompt_cache.write_text(req.prompt, encoding="utf-8")

    raise ManualPendingError(prompt_cache=prompt_cache, response_path=response_path)


register("manual", _manual_complete)
register("external_file", _manual_complete)
