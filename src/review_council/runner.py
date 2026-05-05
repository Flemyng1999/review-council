"""Stage-based workflow runner.

Reads a YAML recipe under `docs/workflows/<case_type>.yaml`, walks its stages,
and executes them idempotently against the existing review-council CLI.

Design rules:

- Stages are declarative: `(needs, produces, command, positional, flags)` for
  single stages; `(fanout_pattern, produces_template, ...)` for batched ones.
- A stage is skipped when all `produces` files already exist, unless `--force`.
- Human gates are never auto-fulfilled. They print their instruction and leave
  their output to the human; subsequent runs notice when the file appears.
- Path arguments use case-relative form (`reviews/issue_graph.json`); the
  runner resolves them to absolute paths against the case directory.

The runner does not change CWD; CLI handlers receive absolute paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from review_council.rubrics import parse_yaml_lite
from review_council.segment.risk import load_risk_table


CASE_DIRS = (
    "normalized",
    "units",
    "reviews",
    "evidence",
    "comments",
    "decision",
    "frozen",
    "provenance",
    "source",
)


@dataclass
class Stage:
    id: str
    description: str = ""
    needs: list[str] = field(default_factory=list)
    produces: list[str] = field(default_factory=list)
    command: str = ""
    positional: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    fanout_pattern: str = ""
    produces_template: str = ""
    positional_template: list[str] = field(default_factory=list)
    flags_template: list[str] = field(default_factory=list)
    risk_threshold: float = 0.0
    risk_table: str = ""
    gate: str = ""
    instruction: str = ""


@dataclass
class Workflow:
    name: str
    case_type: str
    description: str
    stages: list[Stage]


@dataclass
class StageResult:
    stage_id: str
    status: str  # ok | up_to_date | gate | skipped | error | not_selected
    detail: str = ""


def load_workflow(workflow_path: Path) -> Workflow:
    data = parse_yaml_lite(workflow_path.read_text(encoding="utf-8"))
    stages: list[Stage] = []
    for raw in data.get("stages", []) or []:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        stages.append(
            Stage(
                id=str(raw.get("id", "")),
                description=str(raw.get("description", "")),
                needs=_as_list(raw.get("needs")),
                produces=_as_list(raw.get("produces")),
                command=str(raw.get("command", "")),
                positional=_as_list(raw.get("positional")),
                flags=_as_list(raw.get("flags")),
                fanout_pattern=str(raw.get("fanout_pattern", "")),
                produces_template=str(raw.get("produces_template", "")),
                positional_template=_as_list(raw.get("positional_template")),
                flags_template=_as_list(raw.get("flags_template")),
                risk_threshold=_coerce_float(raw.get("risk_threshold", 0.0)),
                risk_table=str(raw.get("risk_table", "")),
                gate=str(raw.get("gate", "")),
                instruction=str(raw.get("instruction", "")),
            )
        )
    return Workflow(
        name=str(data.get("name", workflow_path.stem)),
        case_type=str(data.get("case_type", "")),
        description=str(data.get("description", "")),
        stages=stages,
    )


def workflow_path_for(case_type: str, workflows_dir: Path) -> Path:
    return workflows_dir / f"{case_type}.yaml"


def run_workflow(
    case_path: Path,
    workflow: Workflow,
    cli_main: Callable[[list[str]], int],
    *,
    force: bool = False,
    only: set[str] | None = None,
    until: str | None = None,
) -> list[StageResult]:
    manifest = _read_manifest_scalars(case_path / "manifest.yaml")
    base_subs = {
        "case_id": manifest.get("case_id", case_path.name),
        "case_type": manifest.get("case_type", workflow.case_type),
    }

    results: list[StageResult] = []
    for stage in workflow.stages:
        if only is not None and stage.id not in only:
            results.append(StageResult(stage.id, "not_selected"))
            continue

        if stage.fanout_pattern:
            result = _run_fanout(case_path, stage, base_subs, cli_main, force)
        else:
            result = _run_single(case_path, stage, base_subs, cli_main, force)
        results.append(result)

        if until and stage.id == until:
            break

    return results


def _run_single(
    case_path: Path,
    stage: Stage,
    subs: dict[str, str],
    cli_main: Callable[[list[str]], int],
    force: bool,
) -> StageResult:
    produces_paths = [case_path / _sub(p, subs) for p in stage.produces]
    outputs_present = bool(produces_paths) and all(p.exists() for p in produces_paths)

    if stage.gate == "human":
        if outputs_present:
            return StageResult(stage.id, "ok", "human output present")
        return StageResult(stage.id, "gate", stage.instruction or "human input required")

    if not force and outputs_present:
        return StageResult(stage.id, "up_to_date")

    if not stage.command:
        return StageResult(stage.id, "skipped", "no command defined")

    needs_missing = [n for n in stage.needs if not (case_path / _sub(n, subs)).exists()]
    if needs_missing:
        return StageResult(stage.id, "blocked", f"missing inputs: {needs_missing}")

    argv = _build_argv(stage.command, stage.positional, stage.flags, subs, case_path)
    rc = _invoke(cli_main, argv)
    if rc != 0:
        return StageResult(stage.id, "error", f"exit code {rc}")

    if produces_paths and not all(p.exists() for p in produces_paths):
        missing = [str(p.relative_to(case_path)) for p in produces_paths if not p.exists()]
        return StageResult(stage.id, "error", f"missing outputs: {missing}")
    return StageResult(stage.id, "ok")


def _run_fanout(
    case_path: Path,
    stage: Stage,
    subs: dict[str, str],
    cli_main: Callable[[list[str]], int],
    force: bool,
) -> StageResult:
    units = sorted(p for p in case_path.glob(stage.fanout_pattern) if not p.name.startswith("._"))
    if not units:
        return StageResult(stage.id, "blocked", f"no matches for {stage.fanout_pattern}")

    if not stage.command:
        return StageResult(stage.id, "skipped", "no command defined")

    filter_detail = ""
    if stage.risk_threshold > 0 and stage.risk_table:
        risk_path = case_path / stage.risk_table
        risk_scores = load_risk_table(risk_path)
        before = len(units)
        units = [
            u
            for u in units
            if risk_scores.get(f"{u.parent.name}/{u.stem}", 0.0) >= stage.risk_threshold
        ]
        filter_detail = f"risk>={stage.risk_threshold} kept {len(units)}/{before}; "
        if not units:
            return StageResult(stage.id, "skipped", f"{filter_detail.rstrip('; ')}")

    ran = 0
    skipped = 0
    errors: list[str] = []
    for unit in units:
        stem = unit.stem
        rel_unit = unit.relative_to(case_path).as_posix()
        unit_subs = dict(subs)
        unit_subs["unit"] = rel_unit
        unit_subs["stem"] = stem
        rel_output = _sub(stage.produces_template, unit_subs) if stage.produces_template else ""
        unit_subs["output"] = rel_output
        output_path = case_path / rel_output if rel_output else None

        if not force and output_path and output_path.exists():
            skipped += 1
            continue

        argv = _build_argv(
            stage.command,
            stage.positional_template,
            stage.flags_template,
            unit_subs,
            case_path,
        )
        rc = _invoke(cli_main, argv)
        if rc != 0:
            errors.append(f"{stem} (exit {rc})")
            continue
        if output_path and not output_path.exists():
            errors.append(f"{stem} (no output)")
            continue
        ran += 1

    detail = f"{filter_detail}{ran} ran, {skipped} up-to-date, {len(errors)} errors out of {len(units)}"
    if errors and ran == 0:
        return StageResult(stage.id, "error", detail)
    if ran == 0:
        return StageResult(stage.id, "up_to_date", detail)
    return StageResult(stage.id, "ok", detail)


def _invoke(cli_main: Callable[[list[str]], int], argv: list[str]) -> int:
    try:
        return int(cli_main(argv) or 0)
    except SystemExit as exc:
        return int(exc.code or 0)


def _build_argv(
    command: str,
    positional: list[str],
    flags: list[str],
    subs: dict[str, str],
    case_path: Path,
) -> list[str]:
    argv: list[str] = [command]
    for arg in positional:
        argv.append(_resolve_arg(_sub(arg, subs), case_path))
    for flag in flags:
        argv.append(_resolve_arg(_sub(flag, subs), case_path))
    return argv


def _resolve_arg(arg: str, case_path: Path) -> str:
    if arg.startswith("--") and "=" in arg:
        key, _, value = arg.partition("=")
        return f"{key}={_resolve_value(value, case_path)}"
    if arg.startswith("--"):
        return arg
    return _resolve_value(arg, case_path)


def _resolve_value(value: str, case_path: Path) -> str:
    if value in CASE_DIRS or any(value.startswith(directory + "/") for directory in CASE_DIRS):
        return str((case_path / value).resolve())
    return value


def _sub(text: str, subs: dict[str, str]) -> str:
    out = text
    for key, value in subs.items():
        out = out.replace("{" + key + "}", str(value))
    return out


def _read_manifest_scalars(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(" "):
            continue
        if ":" not in line:
            continue
        key, _, raw_value = line.partition(":")
        value = raw_value.strip().strip("'\"")
        if value and not value.startswith("["):
            out[key.strip()] = value
    return out


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _coerce_float(value: object) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def format_results_table(results: list[StageResult]) -> str:
    width = max((len(r.stage_id) for r in results), default=10)
    lines = [f"{'Stage':<{width}}  Status        Detail"]
    lines.append(f"{'-' * width}  ------------  ------")
    for r in results:
        lines.append(f"{r.stage_id:<{width}}  {r.status:<12}  {r.detail}")
    return "\n".join(lines)
