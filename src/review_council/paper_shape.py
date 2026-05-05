"""Paper-shape stage: forced gestalt judgment before any defect listing.

Reads the whole-manuscript unit and asks the model the three anchor
questions: best version, current shape, top three transformation actions.
The output is consumed by `meta_review_issues` so every comment can be
checked against the question "does fixing this move the paper toward its
best version?"
"""

from __future__ import annotations

from pathlib import Path

from review_council.prompts import render_prompt_template
from review_council.providers.deepseek import DEFAULT_BASE_URL, DEFAULT_MODEL, DeepSeekRequest, chat_completion


def run_paper_shape(
    *,
    unit_path: Path,
    output_path: Path,
    prompt_template: Path,
    api_key: str,
    case_id: str = "",
    case_type: str = "",
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
) -> Path:
    unit_text = unit_path.read_text(encoding="utf-8")
    prompt = render_prompt_template(
        prompt_template,
        {"case_id": case_id, "case_type": case_type},
    )
    prompt = prompt.rstrip() + "\n\n[Supplied manuscript text]\n" + unit_text
    response = chat_completion(
        DeepSeekRequest(api_key=api_key, prompt=prompt, model=model, base_url=base_url, temperature=0.2)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(response.rstrip() + "\n", encoding="utf-8")
    return output_path
