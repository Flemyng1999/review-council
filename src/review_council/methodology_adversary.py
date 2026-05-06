"""Adversarial methodology audit.

Reads the intro + methods + results chapters in full and asks the strong
model to produce a structured list of hidden assumptions the paper's
conclusions silently depend on, plus a check on whether stated research
goals were actually delivered.

The output `reviews/methodology_adversary.json` is consumed by
`author_review_plan`: every `fatal` and `major` assumption is force-merged
into `must_keep_strategic` with `track = "methodology_adversary"` so the
deliverable author review never silently drops them.

This stage has no deterministic offline equivalent — methodology-level
adversarial reasoning genuinely requires the strong model. When no API key
is available, an offline stub is written that flags the case for manual
methodology review and contains an empty assumptions list.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from review_council.prompts import render_prompt_template
from review_council.providers import CompletionRequest, complete as provider_complete
from review_council.providers.manual_provider import ManualPendingError

DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_PROVIDER = "deepseek"


def run_methodology_adversary(
    *,
    intro_path: Path,
    methods_path: Path,
    results_path: Path,
    output_path: Path,
    prompt_template: Path,
    api_key: str | None,
    model: str = DEFAULT_MODEL,
    base_url: str = "",
    case_id: str = "",
    provider: str = DEFAULT_PROVIDER,
    n_runs: int = 1,
    temperature: float = 0.2,
    external_input: Path | None = None,
    prompt_cache: Path | None = None,
    skip_if_missing: bool = False,
) -> dict:
    """Run the adversary. Returns a status dict suitable for CLI printing.

    `provider`/`n_runs`/`temperature` route through the provider registry.
    `external_input` and `prompt_cache` are wired to the manual provider
    for cross-provider critique without an in-process SDK call. When
    `skip_if_missing=True`, a missing manual response writes a
    `manual_pending` stub and exits 0 — used by workflow stages that
    declare an optional secondary adversary.
    """
    payload = _build_payload(intro_path, methods_path, results_path, case_id)

    if not prompt_template.exists():
        result = _offline_stub(case_id=case_id, provider=provider, model=model, reason="missing_template")
        _write(output_path, result)
        return _summary(output_path, result)

    needs_api_key = provider == "deepseek"
    if needs_api_key and not api_key:
        result = _offline_stub(case_id=case_id, provider=provider, model=model, reason="no_api_key")
        _write(output_path, result)
        return _summary(output_path, result)

    base = render_prompt_template(prompt_template, {"case_id": case_id})
    full_prompt = (
        base.rstrip()
        + "\n\n[Inputs]\n```json\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n```\n"
    )

    runs: list[dict] = []
    last_error: str = ""
    effective_runs = max(1, int(n_runs))
    if provider in {"manual", "external_file"}:
        # External-file mode: one drop-in response per run is impractical;
        # collapse to a single read of `external_input`.
        effective_runs = 1

    for run_index in range(1, effective_runs + 1):
        run_temp = temperature + 0.1 * (run_index - 1) if effective_runs > 1 else temperature
        try:
            response = provider_complete(
                CompletionRequest(
                    prompt=full_prompt,
                    model=model,
                    temperature=run_temp,
                    api_key=api_key,
                    base_url=base_url,
                    external_input_path=external_input,
                    prompt_cache_path=prompt_cache,
                ),
                provider=provider,
            )
            parsed = _extract_json_object(response)
            if not isinstance(parsed, dict):
                raise ValueError("provider response was not a JSON object")
            runs.append(_normalize_run(parsed, run_index=run_index, temperature=run_temp))
        except ManualPendingError as exc:
            stub = _manual_pending_stub(
                case_id=case_id,
                provider=provider,
                model=model,
                prompt_cache=exc.prompt_cache,
                response_path=exc.response_path,
            )
            _write(output_path, stub)
            if skip_if_missing:
                return _summary(output_path, stub)
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            # multi-run: tolerate a single failure; single-run: bail to stub
            if effective_runs == 1:
                stub = _offline_stub(
                    case_id=case_id,
                    provider=provider,
                    model=model,
                    reason=f"provider_failed: {last_error}",
                )
                _write(output_path, stub)
                return _summary(output_path, stub)

    if not runs:
        stub = _offline_stub(
            case_id=case_id,
            provider=provider,
            model=model,
            reason=f"all_runs_failed: {last_error or 'unknown'}",
        )
        _write(output_path, stub)
        return _summary(output_path, stub)

    flat_ha, flat_goals, flat_deps = _collect_flat(provider, runs)
    top_ha, top_goals, top_deps = _dedupe_for_top_level(flat_ha, flat_goals, flat_deps)

    result = {
        "case_id": case_id,
        "provider": provider,
        "model": model,
        "source": "strong_model",
        "n_runs": len(runs),
        "hidden_assumptions": top_ha,
        "unmet_research_goals": top_goals,
        "headline_claim_dependencies": top_deps,
        "runs": runs,
    }
    _write(output_path, result)
    return _summary(output_path, result)


def _summary(output_path: Path, result: dict) -> dict:
    counts = _count_severities(result.get("hidden_assumptions") or [])
    unmet = sum(
        1
        for g in (result.get("unmet_research_goals") or [])
        if g.get("verdict") == "not_delivered"
    )
    return {
        "output": str(output_path),
        "source": result.get("source", "offline"),
        "provider": result.get("provider", ""),
        "n_runs": result.get("n_runs", 0),
        "fatal": counts.get("fatal", 0),
        "major": counts.get("major", 0),
        "moderate": counts.get("moderate", 0),
        "unmet_goals": unmet,
    }


def _collect_flat(
    provider: str, runs: list[dict]
) -> tuple[list[tuple], list[tuple], list[tuple]]:
    flat_ha = [
        (provider, run["run_index"], item)
        for run in runs
        for item in (run.get("hidden_assumptions") or [])
    ]
    flat_goals = [
        (provider, run["run_index"], item)
        for run in runs
        for item in (run.get("unmet_research_goals") or [])
    ]
    flat_deps = [
        (provider, run["run_index"], item)
        for run in runs
        for item in (run.get("headline_claim_dependencies") or [])
    ]
    return flat_ha, flat_goals, flat_deps


def _dedupe_for_top_level(flat_ha, flat_goals, flat_deps):
    """Single-provider dedupe for top-level lists (backwards-compat shape).

    Cross-provider merging happens in `adversary_merge.merge_adversaries`;
    this is the lighter pass that keeps `fatal_and_major_findings()` working
    regardless of how many runs the provider executed.
    """
    from review_council.adversary_merge import _group_by_text, _longest, _highest_severity

    if len(flat_ha) <= 1:
        top_ha = [item for _, _, item in flat_ha]
    else:
        top_ha = []
        for index, group in enumerate(_group_by_text(flat_ha, "assumption", 0.4), start=1):
            canonical = _longest(group, "assumption")
            severities = [str(g[2].get("severity") or "").lower() for g in group]
            top_ha.append(
                {
                    "id": str(canonical.get("id") or f"MA-{index:02d}"),
                    "assumption": canonical.get("assumption", ""),
                    "breakage": canonical.get("breakage", ""),
                    "reported_check": canonical.get("reported_check", ""),
                    "severity": _highest_severity(severities) or "major",
                }
            )

    if len(flat_goals) <= 1:
        top_goals = [item for _, _, item in flat_goals]
    else:
        top_goals = []
        for group in _group_by_text(flat_goals, "stated_goal", 0.4):
            canonical = _longest(group, "stated_goal")
            verdicts = [str(g[2].get("verdict") or "").lower() for g in group]
            # tighten verdict: not_delivered > partial > delivered
            order = {"not_delivered": 0, "partial": 1, "delivered": 2}
            chosen = min(verdicts, key=lambda v: order.get(v, 9)) if verdicts else ""
            top_goals.append(
                {
                    "stated_goal": canonical.get("stated_goal", ""),
                    "evidence_in_paper": canonical.get("evidence_in_paper", "none"),
                    "verdict": chosen,
                }
            )

    if len(flat_deps) <= 1:
        top_deps = [item for _, _, item in flat_deps]
    else:
        top_deps = []
        for index, group in enumerate(_group_by_text(flat_deps, "paper_claim", 0.4), start=1):
            canonical = _longest(group, "paper_claim")
            severities = [str(g[2].get("severity") or "").lower() for g in group]
            dep_set: list[str] = []
            for _, _, item in group:
                for dep in item.get("depends_on_assumptions") or []:
                    if str(dep) and str(dep) not in dep_set:
                        dep_set.append(str(dep))
            top_deps.append(
                {
                    "id": str(canonical.get("id") or f"HCD-{index:02d}"),
                    "paper_claim": canonical.get("paper_claim", ""),
                    "depends_on_assumptions": dep_set,
                    "if_violated_downgrade_to": canonical.get("if_violated_downgrade_to", ""),
                    "severity": _highest_severity(severities) or "major",
                }
            )

    return top_ha, top_goals, top_deps


def fatal_and_major_findings(adversary_path: Path) -> list[dict]:
    """Return the subset of hidden assumptions worth force-merging into must_keep."""
    if not adversary_path or not Path(adversary_path).exists():
        return []
    try:
        data = json.loads(Path(adversary_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    out: list[dict] = []
    for item in data.get("hidden_assumptions") or []:
        if not isinstance(item, dict):
            continue
        sev = str(item.get("severity") or "").lower()
        if sev not in {"fatal", "major"}:
            continue
        out.append(item)
    for goal in data.get("unmet_research_goals") or []:
        if not isinstance(goal, dict):
            continue
        verdict = str(goal.get("verdict") or "").lower()
        if verdict == "not_delivered":
            out.append(
                {
                    "id": "MA-GOAL-" + str(len(out) + 1).zfill(2),
                    "assumption": "研究目标未在论文中兑现：" + str(goal.get("stated_goal") or "")[:160],
                    "breakage": "论文实际执行与引言声明不一致——这是诚信而非难度问题。",
                    "reported_check": str(goal.get("evidence_in_paper") or "none"),
                    "severity": "major",
                }
            )
        elif verdict == "partial":
            out.append(
                {
                    "id": "MA-GOAL-" + str(len(out) + 1).zfill(2),
                    "assumption": "研究目标仅部分兑现：" + str(goal.get("stated_goal") or "")[:160],
                    "breakage": "论文执行与引言声明不完全一致；作者应在结论中明确目标兑现度，或主动调整引言措辞，避免目标-内容失配。",
                    "reported_check": str(goal.get("evidence_in_paper") or "none"),
                    "severity": "major",
                }
            )
    return out


def claim_downgrade_findings(adversary_path: Path) -> list[dict]:
    """Return headline_claim_dependencies as plan-compatible records.

    These are kept separate from hidden_assumptions because they live in a
    distinct rewrite section (§三 「论文核心声明的证据匹配度」), not §二.
    """
    if not adversary_path or not Path(adversary_path).exists():
        return []
    try:
        data = json.loads(Path(adversary_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    out: list[dict] = []
    for item in data.get("headline_claim_dependencies") or []:
        if not isinstance(item, dict):
            continue
        out.append(item)
    return out


# --- helpers ---------------------------------------------------------------


def _build_payload(intro_path: Path, methods_path: Path, results_path: Path, case_id: str) -> dict:
    return {
        "case_id": case_id,
        "introduction": _read_safe(intro_path),
        "methods": _read_safe(methods_path),
        "results": _read_safe(results_path),
    }


def _read_safe(path: Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _normalize_run(parsed: dict, *, run_index: int, temperature: float) -> dict:
    assumptions: list[dict] = []
    for index, item in enumerate(parsed.get("hidden_assumptions") or [], start=1):
        if not isinstance(item, dict):
            continue
        assumptions.append(
            {
                "id": str(item.get("id") or f"MA-{index:02d}"),
                "assumption": str(item.get("assumption") or "").strip(),
                "breakage": str(item.get("breakage") or "").strip(),
                "reported_check": str(item.get("reported_check") or "").strip(),
                "severity": _normalize_severity(item.get("severity")),
            }
        )
    goals: list[dict] = []
    for item in parsed.get("unmet_research_goals") or []:
        if not isinstance(item, dict):
            continue
        verdict = str(item.get("verdict") or "").lower()
        if verdict not in {"delivered", "partial", "not_delivered"}:
            verdict = "partial"
        goals.append(
            {
                "stated_goal": str(item.get("stated_goal") or "").strip(),
                "evidence_in_paper": str(item.get("evidence_in_paper") or "none").strip(),
                "verdict": verdict,
            }
        )
    dependencies: list[dict] = []
    for index, item in enumerate(parsed.get("headline_claim_dependencies") or [], start=1):
        if not isinstance(item, dict):
            continue
        deps = [str(d) for d in (item.get("depends_on_assumptions") or []) if str(d).strip()]
        sev = _normalize_severity(item.get("severity"))
        if sev == "moderate":
            sev = "major"  # claim_downgrade defaults to major
        dependencies.append(
            {
                "id": str(item.get("id") or f"HCD-{index:02d}"),
                "paper_claim": str(item.get("paper_claim") or "").strip(),
                "depends_on_assumptions": deps,
                "if_violated_downgrade_to": str(item.get("if_violated_downgrade_to") or "").strip(),
                "severity": sev,
            }
        )
    return {
        "run_index": run_index,
        "temperature": temperature,
        "hidden_assumptions": assumptions,
        "unmet_research_goals": goals,
        "headline_claim_dependencies": dependencies,
    }


def _offline_stub(*, case_id: str, provider: str = DEFAULT_PROVIDER, model: str = DEFAULT_MODEL, reason: str) -> dict:
    return {
        "case_id": case_id,
        "provider": provider,
        "model": model,
        "source": "offline_stub",
        "reason": reason,
        "note": "Methodology adversary requires the strong model. Manual methodology review required.",
        "n_runs": 0,
        "hidden_assumptions": [],
        "unmet_research_goals": [],
        "headline_claim_dependencies": [],
        "runs": [],
    }


def _manual_pending_stub(
    *,
    case_id: str,
    provider: str,
    model: str,
    prompt_cache: Path | None,
    response_path: Path | None,
) -> dict:
    return {
        "case_id": case_id,
        "provider": provider,
        "model": model,
        "source": "manual_pending",
        "reason": "external_input not yet provided",
        "note": (
            f"Drop the {provider} response into {response_path!s} and re-run."
            + (f" Prompt cached at {prompt_cache!s}." if prompt_cache else "")
        ),
        "prompt_cache_path": str(prompt_cache) if prompt_cache else "",
        "expected_response_path": str(response_path) if response_path else "",
        "n_runs": 0,
        "hidden_assumptions": [],
        "unmet_research_goals": [],
        "headline_claim_dependencies": [],
        "runs": [],
    }


def _normalize_severity(value: object) -> str:
    sev = str(value or "").strip().lower()
    if sev not in {"fatal", "major", "moderate"}:
        return "moderate"
    return sev


def _count_severities(items: list[dict]) -> dict[str, int]:
    out = {"fatal": 0, "major": 0, "moderate": 0}
    for item in items:
        sev = _normalize_severity(item.get("severity"))
        out[sev] = out.get(sev, 0) + 1
    return out


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
