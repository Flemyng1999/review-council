"""Editorial layer that turns the cheap-scan + meta-review pipeline into a
deliverable author-facing review.

This module sits one level above `compose_author_review`. It owns three
high-leverage decisions that the cheap layer cannot make:

1. **Plan**: pick the paper's best form, the three overall revision
   directions, the strategic comments that must survive, the detail pool that
   must be cleaned up, and the comments to demote/drop.
2. **Rewrite**: produce a polished, voice-consistent author Markdown that
   leads with overall direction, then strategic blocks, then concentrated
   detail clean-up.
3. **Redact**: strip every internal-process token (DeepSeek, meta-review,
   ISS-####, paper_shape, Transformation Action N, rubric ids, English
   severity tokens, etc.) before the author ever sees the file.

The strong-model path is used when an API key is available; otherwise the
deterministic offline path keeps the workflow runnable and tests reproducible.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from review_council.author_review import (
    clean_author_text,
    compose_author_review,
)
from review_council.methodology_adversary import (
    claim_downgrade_findings,
    fatal_and_major_findings,
)
from review_council.prompts import render_prompt_template

# Internal-process tokens that must never appear in the author-facing output.
# Patterns are conservative; they do not eat ordinary words.
INTERNAL_TOKEN_PATTERNS: tuple[str, ...] = (
    r"\b(?:ISS|CLM|CMT|MET|REP|EVD|CLR|NOV|SIG|COH|IND|FND|INT|BAS|MERGE-A|MERGE-HCD|MA|HCD|HA)-\d{2,4}\b",
    # Cross-provider model and vendor names — never leak which model wrote what.
    r"\bDeepSeek\b",
    r"\bdeepseek[-_a-z0-9]*\b",
    r"\bClaude\b",
    r"\bAnthropic\b",
    r"\bChatGPT\b",
    r"\bGPT[\w-]*\b",
    r"\bOpenAI\b",
    r"\bGemini\b",
    # Internal pipeline nouns.
    r"\bmeta[\s-]review\b",
    r"\bissue[\s-]graph\b",
    r"\bclaim[/_\s-]?evidence[\s-]?matrix\b",
    r"\bpaper[_\s-]?shape\b",
    r"\bTransformation Action\s*\d*\b",
    r"\brubric(?:s|\s+id)?\b",
    r"\bcheap reviewers?\b",
    r"\b(?:blocking|major|moderate|minor)\b",
    # Stage / pipeline names that may bleed into model output.
    r"\bmethodology[_\s-]adversary\b",
    r"\bauthor[_\s-]review[_\s-]plan\b",
    r"\bauthor[_\s-]editorial[_\s-]rewrite\b",
)

VOICE_PROFILES: dict[str, dict[str, str]] = {
    "reviewer": {
        "opening": "以下是本论文的审稿意见。",
        "guideline": (
            "中性、第三人称、专业审稿人语气；多用「建议」「应」「可考虑」；"
            "结论先行，再给出依据；避免讨好或攻击。"
        ),
    },
    "senior_peer": {
        "opening": "下面这些是同实验室博士生帮你过一遍论文整理出来的修改建议。",
        "guideline": (
            "用博士生师兄帮本科生把关的语气：自然、直接、有用，不套话也不讨好；"
            "避免明显的「我」开头；用「这里」「这一段」「这一章」指代位置；"
            "结论先讲，再给具体建议；语气友好但不弱化问题严重程度。"
        ),
    },
}

DEFAULT_VOICE = "senior_peer"


# --- redaction --------------------------------------------------------------


def find_internal_tokens(text: str) -> list[str]:
    """Return every internal-process token appearing in `text`."""
    out: list[str] = []
    for pattern in INTERNAL_TOKEN_PATTERNS:
        out.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    return out


def redact_internal_tokens(text: str) -> str:
    """Strip internal-process tokens from `text`.

    Runs `clean_author_text` (which already replaces the common ones in
    Chinese phrasing), then removes any residual id-shaped tokens, English
    severity words, and process nouns that the cleaner left behind.
    """
    cleaned = clean_author_text(text)
    cleaned = re.sub(
        r"\b(?:ISS|CLM|CMT|MET|REP|EVD|CLR|NOV|SIG|COH|IND|FND|INT|BAS|MERGE-A|MERGE-HCD|MA|HCD|HA)-\d{2,4}\b",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\bdeepseek[-_a-z0-9]*\b", "模型审查", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bclaude\b", "模型审查", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\banthropic\b", "模型审查", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bchatgpt\b", "模型审查", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bgpt[\w-]*\b", "模型审查", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bopenai\b", "模型审查", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bgemini\b", "模型审查", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bmethodology[_\s-]adversary\b", "方法论审稿", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bauthor[_\s-]review[_\s-]plan\b", "审稿计划", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bauthor[_\s-]editorial[_\s-]rewrite\b", "审稿改写", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bmeta[\s-]review\b", "综合审查", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bissue[\s-]graph\b", "问题清单", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\bclaim[/_\s-]?evidence[\s-]?matrix\b", "证据对照表", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(r"\bpaper[_\s-]?shape\b", "总体修改方向", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bTransformation Action\s*\d*\b", "总体修改方向", cleaned)
    cleaned = re.sub(r"\brubric(?:s|\s+id)?\b", "评审维度", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bcheap reviewers?\b", "局部审查", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bblocking\b", "优先修改", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bmajor\b", "重点修改", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bmoderate\b", "建议修改", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bminor\b", "细节修改", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip() + "\n"


# --- plan -------------------------------------------------------------------


def build_author_review_plan(
    *,
    paper_shape_path: Path,
    meta_comments_path: Path,
    detail_audit_path: Path,
    output_json_path: Path,
    output_md_path: Path,
    voice: str = DEFAULT_VOICE,
    api_key: str | None = None,
    prompt_template: Path | None = None,
    model: str = "",
    base_url: str = "",
    methodology_adversary_path: Path | None = None,
) -> dict:
    """Produce an editorial plan (JSON + Markdown).

    The plan is *not* the author review; it is the editor's worksheet that
    drives the rewrite stage. Always writes both artifacts.

    When `methodology_adversary_path` points at a valid adversary JSON, every
    fatal/major hidden assumption and every not-delivered research goal is
    force-merged into `must_keep_strategic` with `track =
    "methodology_adversary"`. These are non-negotiable: they survive even
    when the strong-model path is taken.
    """
    paper_shape_md = (
        paper_shape_path.read_text(encoding="utf-8") if paper_shape_path.exists() else ""
    )
    meta_comments = _safe_load_list(meta_comments_path)
    detail_payload = _safe_load_dict(detail_audit_path)
    detail_items = [
        item for item in (detail_payload.get("items") or []) if isinstance(item, dict)
    ]
    adversary_findings = (
        fatal_and_major_findings(methodology_adversary_path) if methodology_adversary_path else []
    )
    claim_downgrades = (
        claim_downgrade_findings(methodology_adversary_path) if methodology_adversary_path else []
    )
    needs_human_decision = _load_needs_human_decision(methodology_adversary_path)

    plan = _plan_offline(
        paper_shape_md, meta_comments, detail_items, voice, adversary_findings, claim_downgrades
    )
    if needs_human_decision:
        plan["human_decision_needed"] = needs_human_decision

    if api_key and prompt_template and prompt_template.exists():
        try:
            plan = _plan_via_strong_model(
                offline_plan=plan,
                paper_shape_md=paper_shape_md,
                meta_comments=meta_comments,
                detail_items=detail_items,
                template=prompt_template,
                api_key=api_key,
                model=model,
                base_url=base_url,
                voice=voice,
            )
            plan["source"] = "strong_model"
            # Re-merge adversary findings into the strong-model plan: the model
            # might have dropped them, but they are non-negotiable.
            if adversary_findings or claim_downgrades:
                plan["must_keep_strategic"] = _force_merge_adversary(
                    plan.get("must_keep_strategic") or [],
                    adversary_findings,
                    claim_downgrades,
                )
        except Exception as exc:  # noqa: BLE001
            plan["source"] = "offline"
            plan["fallback_reason"] = f"{type(exc).__name__}: {exc}"

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.write_text(_render_plan_md(plan), encoding="utf-8")
    return {
        "output_json": str(output_json_path),
        "output_md": str(output_md_path),
        "voice": voice,
        "source": plan.get("source", "offline"),
        "must_keep": len(plan.get("must_keep_strategic", [])),
        "detail_pool": len(plan.get("detail_pool", [])),
    }


def _plan_offline(
    paper_shape_md: str,
    meta_comments: list[dict],
    detail_items: list[dict],
    voice: str,
    adversary_findings: list[dict] | None = None,
    claim_downgrades: list[dict] | None = None,
) -> dict:
    revision_directions = _extract_directions_from_md(paper_shape_md)
    must_keep: list[dict] = []
    demote: list[dict] = []
    if adversary_findings:
        must_keep.extend(_adversary_records(adversary_findings))
    if claim_downgrades:
        must_keep.extend(_claim_downgrade_records(claim_downgrades))
    for c in meta_comments:
        priority = str(c.get("revision_priority") or "").lower()
        severity = str(c.get("final_severity") or c.get("severity") or "").lower()
        track = str(c.get("track") or "")
        record = {
            "id": str(c.get("id", "")),
            "track": track,
            "summary": (str(c.get("comment") or "")[:240]).strip(),
            "priority": priority,
            "severity": severity,
        }
        if priority == "high" or severity in {"blocking", "major"}:
            must_keep.append(record)
        elif priority == "low" or severity in {"minor"}:
            demote.append(record)
    detail_pool = [
        {
            "category": str(item.get("category", "")),
            "category_label": str(item.get("category_label", "")),
            "priority": str(item.get("priority", "")),
            "text": (str(item.get("text") or "")[:200]).strip(),
        }
        for item in detail_items
    ]
    profile = VOICE_PROFILES.get(voice, VOICE_PROFILES[DEFAULT_VOICE])
    return {
        "best_form": _extract_best_form(paper_shape_md),
        "revision_directions": revision_directions,
        "must_keep_strategic": must_keep[:15],
        "detail_pool": detail_pool,
        "demote_or_drop": demote[:30],
        "voice": voice,
        "voice_guidelines": profile["guideline"],
        "source": "offline",
    }


def _plan_via_strong_model(
    *,
    offline_plan: dict,
    paper_shape_md: str,
    meta_comments: list[dict],
    detail_items: list[dict],
    template: Path,
    api_key: str,
    model: str,
    base_url: str,
    voice: str,
) -> dict:
    from review_council.providers.deepseek import DeepSeekRequest, chat_completion

    prompt = render_prompt_template(template, {"voice": voice})
    payload = {
        "voice": voice,
        "voice_guidelines": offline_plan["voice_guidelines"],
        "paper_shape": paper_shape_md,
        "meta_comments": meta_comments,
        "detail_items": detail_items,
        "offline_plan": offline_plan,
        "methodology_adversary_must_keep": [
            r for r in (offline_plan.get("must_keep_strategic") or [])
            if isinstance(r, dict) and r.get("from_adversary")
        ],
    }
    full = (
        prompt.rstrip()
        + "\n\n[Inputs]\n```json\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n```\nReturn the plan as a JSON object only.\n"
    )
    response = chat_completion(
        DeepSeekRequest(api_key=api_key, prompt=full, model=model, base_url=base_url)
    )
    parsed = _extract_json_object(response)
    if not isinstance(parsed, dict):
        raise ValueError("strong-model plan response was not a JSON object")
    parsed.setdefault("voice", voice)
    parsed.setdefault("voice_guidelines", offline_plan["voice_guidelines"])
    return parsed


# --- rewrite ----------------------------------------------------------------


def run_author_editorial_rewrite(
    *,
    paper_shape_path: Path,
    plan_path: Path,
    meta_comments_path: Path,
    detail_audit_path: Path,
    source_map_path: Path,
    output_md_path: Path,
    voice: str = DEFAULT_VOICE,
    api_key: str | None = None,
    prompt_template: Path | None = None,
    model: str = "",
    base_url: str = "",
    provider: str = "deepseek",
    external_input: Path | None = None,
    prompt_cache: Path | None = None,
) -> dict:
    """Produce the canonical author-facing Markdown.

    Provider routing: when `provider != deepseek`, the call goes through
    the registry (manual/external_file/openai/claude). The manual path
    lets a cross-provider rewrite be dropped in as a file — the redaction
    + validator pass still runs over it before write.

    Strong-model path: render the rewrite prompt and call the chosen
    provider. Offline fallback: reuse `compose_author_review` and add a
    voice-consistent opener. Either way, redaction is always applied last
    and a leak audit is returned. A non-empty `leaks` list signals the
    output should not be considered final.
    """
    from review_council.providers import CompletionRequest, complete as provider_complete
    from review_council.providers.manual_provider import ManualPendingError

    used_strong = False
    used_provider = ""
    body = ""

    use_strong = bool(prompt_template and prompt_template.exists())
    if provider == "deepseek" and not api_key:
        use_strong = False  # cannot call deepseek without a key
    if provider in {"manual", "external_file"} and external_input is None:
        use_strong = False  # manual mode without target is meaningless

    if use_strong:
        try:
            body = _rewrite_via_provider(
                paper_shape_path=paper_shape_path,
                plan_path=plan_path,
                meta_comments_path=meta_comments_path,
                detail_audit_path=detail_audit_path,
                voice=voice,
                template=prompt_template,
                api_key=api_key,
                model=model,
                base_url=base_url,
                provider=provider,
                external_input=external_input,
                prompt_cache=prompt_cache,
                provider_complete=provider_complete,
                request_cls=CompletionRequest,
            )
            used_strong = True
            used_provider = provider
        except ManualPendingError:
            # Surface the prompt-cache-and-skip behaviour without writing
            # a half-baked rewrite. Caller can re-run after dropping the
            # external response in.
            raise
        except Exception:  # noqa: BLE001
            body = ""

    if not body:
        body = _rewrite_offline(
            paper_shape_path=paper_shape_path,
            plan_path=plan_path,
            meta_comments_path=meta_comments_path,
            detail_audit_path=detail_audit_path,
            source_map_path=source_map_path,
            voice=voice,
        )
        used_provider = used_provider or "offline"

    final_text = redact_internal_tokens(body)
    leaks = find_internal_tokens(final_text)

    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.write_text(final_text, encoding="utf-8")
    return {
        "output": str(output_md_path),
        "voice": voice,
        "used_strong": used_strong,
        "provider": used_provider,
        "leaks": leaks,
        "chars": len(final_text),
    }


def _rewrite_via_provider(
    *,
    paper_shape_path: Path,
    plan_path: Path,
    meta_comments_path: Path,
    detail_audit_path: Path,
    voice: str,
    template: Path,
    api_key: str | None,
    model: str,
    base_url: str,
    provider: str,
    external_input: Path | None,
    prompt_cache: Path | None,
    provider_complete,
    request_cls,
) -> str:
    profile = VOICE_PROFILES.get(voice, VOICE_PROFILES[DEFAULT_VOICE])
    prompt = render_prompt_template(
        template,
        {"voice": voice, "voice_guidelines": profile["guideline"]},
    )
    payload = {
        "voice": voice,
        "voice_guidelines": profile["guideline"],
        "paper_shape": paper_shape_path.read_text(encoding="utf-8")
        if paper_shape_path.exists()
        else "",
        "plan": _safe_load_dict(plan_path),
        "meta_comments": _safe_load_list(meta_comments_path),
        "detail_audit": _safe_load_dict(detail_audit_path),
    }
    full = (
        prompt.rstrip()
        + "\n\n[Inputs]\n```json\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n```\nReturn the final author-facing Markdown only. No JSON, no commentary.\n"
    )
    response = provider_complete(
        request_cls(
            prompt=full,
            model=model,
            temperature=0.2,
            api_key=api_key,
            base_url=base_url,
            external_input_path=external_input,
            prompt_cache_path=prompt_cache,
        ),
        provider=provider,
    )
    return response.strip()


def _rewrite_offline(
    *,
    paper_shape_path: Path,
    plan_path: Path,
    meta_comments_path: Path,
    detail_audit_path: Path,
    source_map_path: Path,
    voice: str,
) -> str:
    profile = VOICE_PROFILES.get(voice, VOICE_PROFILES[DEFAULT_VOICE])
    plan = _safe_load_dict(plan_path)
    adversary_comments = _adversary_to_synthetic_comments(plan.get("must_keep_strategic") or [])

    with tempfile.TemporaryDirectory() as td:
        compose_md = Path(td) / "compose.md"
        merged_meta_path = meta_comments_path
        if adversary_comments:
            merged = list(_safe_load_list(meta_comments_path))
            merged = adversary_comments + merged
            merged_meta_path = Path(td) / "meta_with_adversary.json"
            merged_meta_path.write_text(
                json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        compose_author_review(
            paper_shape_path=paper_shape_path,
            strategic_comments_path=merged_meta_path,
            detail_audit_path=detail_audit_path,
            source_map_path=source_map_path,
            output_md_path=compose_md,
            output_json_path=None,
        )
        composed = compose_md.read_text(encoding="utf-8")

    plan = _safe_load_dict(plan_path)
    directions = plan.get("revision_directions") or _extract_directions_from_md(
        paper_shape_path.read_text(encoding="utf-8") if paper_shape_path.exists() else ""
    )

    parts: list[str] = ["# 审稿意见", "", profile["opening"], ""]
    if directions:
        parts.append("## 总体修改方向")
        parts.append("")
        for i, goal in enumerate(directions[:3], start=1):
            parts.append(f"{i}. {goal}")
        parts.append("")

    # Reuse compose_author_review's body but drop its top heading + duplicate goals.
    body_lines = composed.splitlines()
    skip_until_section = True
    for line in body_lines:
        if skip_until_section:
            if line.startswith("## ") and "总体修改方向" not in line:
                skip_until_section = False
            else:
                continue
        parts.append(line)

    return "\n".join(parts).rstrip() + "\n"


# --- adversary integration -------------------------------------------------


def _adversary_records(findings: list[dict]) -> list[dict]:
    """Convert methodology-adversary findings into must_keep_strategic records."""
    out: list[dict] = []
    for item in findings:
        if not isinstance(item, dict):
            continue
        sev = str(item.get("severity") or "").lower()
        priority = "high"
        severity_token = "blocking" if sev == "fatal" else "major"
        assumption = str(item.get("assumption") or "").strip()
        breakage = str(item.get("breakage") or "").strip()
        summary_parts = [p for p in [assumption, breakage] if p]
        out.append(
            {
                "id": str(item.get("id") or ""),
                "track": "methodology_adversary",
                "summary": (" ｜ ".join(summary_parts))[:400],
                "priority": priority,
                "severity": severity_token,
                "from_adversary": True,
            }
        )
    return out


def _claim_downgrade_records(claim_downgrades: list[dict]) -> list[dict]:
    """Convert headline_claim_dependencies into must_keep_strategic records.

    Track is `claim_downgrade` so the rewrite stage can route them to a
    dedicated §三 subsection ("论文核心声明的证据匹配度") rather than
    mixing them with the §二 hidden-assumption block.
    """
    out: list[dict] = []
    for item in claim_downgrades:
        if not isinstance(item, dict):
            continue
        sev = str(item.get("severity") or "major").lower()
        severity_token = "blocking" if sev == "fatal" else "major"
        deps = item.get("depends_on_assumptions") or []
        deps_str = ", ".join(str(d) for d in deps) if deps else "—"
        summary = (
            f"论文 headline：{str(item.get('paper_claim') or '').strip()} "
            f"｜ 依赖于假设 {deps_str} ｜ 若该依赖不成立，应降级为："
            f"{str(item.get('if_violated_downgrade_to') or '').strip()}"
        )
        out.append(
            {
                "id": str(item.get("id") or ""),
                "track": "claim_downgrade",
                "summary": summary[:500],
                "priority": "high",
                "severity": severity_token,
                "from_adversary": True,
                "claim_downgrade": True,
                "paper_claim": str(item.get("paper_claim") or "").strip(),
                "depends_on_assumptions": [str(d) for d in deps],
                "if_violated_downgrade_to": str(item.get("if_violated_downgrade_to") or "").strip(),
            }
        )
    return out


def _adversary_to_synthetic_comments(must_keep: list[dict]) -> list[dict]:
    """Turn adversary records back into strategic-comment shape so the offline
    rewrite surfaces them under §二、方法与可复现性 (or §三、结果解释与证据强度
    for claim_downgrade records)."""
    out: list[dict] = []
    for record in must_keep:
        if not isinstance(record, dict) or not record.get("from_adversary"):
            continue
        summary = str(record.get("summary") or "")
        if record.get("claim_downgrade"):
            out.append(
                {
                    "id": str(record.get("id") or ""),
                    "track": "results_validation",
                    "comment": summary,
                    "recommendation": (
                        "在结果讨论或结论里主动声明该 headline 的成立条件；"
                        "如果依赖的假设未论证，请把 headline 降级到上面给出的形态，"
                        "或补一个最小对照实验论证依赖项。"
                    ),
                    "final_severity": str(record.get("severity") or "major"),
                    "revision_priority": str(record.get("priority") or "high"),
                }
            )
            continue
        out.append(
            {
                "id": str(record.get("id") or ""),
                "track": "methods",
                "comment": summary,
                "recommendation": "在方法或讨论里直接处理这个隐藏假设：补对照实验、补论证、或在局限性章节坦白其影响。",
                "final_severity": str(record.get("severity") or "major"),
                "revision_priority": str(record.get("priority") or "high"),
            }
        )
    return out


def _force_merge_adversary(
    existing: list[dict],
    findings: list[dict],
    claim_downgrades: list[dict] | None = None,
) -> list[dict]:
    """Make sure adversary findings appear in must_keep_strategic.

    The strong model might have dropped them when re-shaping the plan; we
    re-attach any missing ones to the front so they always survive into the
    rewrite stage.
    """
    have_ids = {str(r.get("id", "")) for r in existing if isinstance(r, dict)}
    adversary_records = _adversary_records(findings)
    missing = [r for r in adversary_records if r["id"] not in have_ids]
    if claim_downgrades:
        downgrade_records = _claim_downgrade_records(claim_downgrades)
        missing += [r for r in downgrade_records if r["id"] not in have_ids]
    return missing + list(existing)


# --- helpers ---------------------------------------------------------------


def _render_plan_md(plan: dict) -> str:
    lines: list[str] = ["# 编辑计划（内部）", ""]
    if plan.get("best_form"):
        lines += ["## 论文最佳形态", "", plan["best_form"], ""]
    directions = plan.get("revision_directions") or []
    if directions:
        lines += ["## 三条总体修改方向", ""]
        for i, goal in enumerate(directions[:3], start=1):
            lines.append(f"{i}. {goal}")
        lines.append("")
    must_keep = plan.get("must_keep_strategic") or []
    if must_keep:
        lines += ["## 必须保留的战略问题", ""]
        for r in must_keep:
            track = r.get("track", "-") or "-"
            lines.append(f"- ({track}) {r.get('summary','')}")
        lines.append("")
    detail_pool = plan.get("detail_pool") or []
    if detail_pool:
        lines += ["## 细节池", ""]
        for d in detail_pool[:30]:
            label = d.get("category_label") or d.get("category") or "-"
            lines.append(f"- [{label}] {d.get('text','')}")
        lines.append("")
    demote = plan.get("demote_or_drop") or []
    if demote:
        lines += ["## 可降级或删除", ""]
        for r in demote:
            lines.append(f"- ({r.get('track','-') or '-'}) {r.get('summary','')}")
        lines.append("")
    lines += [f"## 口吻：{plan.get('voice','')}", "", plan.get("voice_guidelines", ""), ""]
    return "\n".join(lines).rstrip() + "\n"


def _extract_directions_from_md(md: str) -> list[str]:
    if not md:
        return []
    lines = md.splitlines()
    start = -1
    for i, line in enumerate(lines):
        if "Transformation" in line or "修改方向" in line:
            start = i + 1
            break
    if start < 0:
        return []
    out: list[str] = []
    current: list[str] = []
    for line in lines[start:]:
        s = line.strip()
        if s.startswith("## ") and current:
            break
        if re.match(r"^\d+\.\s+", s):
            if current:
                out.append(" ".join(current).strip())
            current = [re.sub(r"^\d+\.\s+", "", s)]
        elif current and s:
            current.append(s)
    if current:
        out.append(" ".join(current).strip())
    return out[:3]


def _extract_best_form(md: str) -> str:
    if not md:
        return ""
    m = re.search(r"##\s*Best[^\n]*\n(.+?)(?=\n##|\Z)", md, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        m = re.search(r"##\s*最佳[^\n]*\n(.+?)(?=\n##|\Z)", md, flags=re.DOTALL)
    return (m.group(1).strip() if m else "")[:600]


def _safe_load_list(path: Path | None) -> list[dict]:
    if not path or not Path(path).exists():
        return []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _safe_load_dict(path: Path | None) -> dict:
    if not path or not Path(path).exists():
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_needs_human_decision(path: Path | None) -> list[dict]:
    """Pass `needs_human_decision` from a merged adversary file straight through.

    Single-source adversary files do not carry this field; only the merged
    output (from `merge-methodology-adversaries`) does. This is the
    mechanism that surfaces conflict / single-provider-fatal items in
    the plan without forcing the rewrite stage to invent its own
    detection logic.
    """
    data = _safe_load_dict(path)
    items = data.get("needs_human_decision") or []
    return [item for item in items if isinstance(item, dict)]


def _extract_json_object(text: str) -> object:
    fence = re.search(r"```(?:json)?\s*\n(.+?)\n```", text, flags=re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None
