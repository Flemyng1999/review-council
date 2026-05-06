"""Stage-based workflow runner.

Reads a YAML recipe under `docs/workflows/<case_type>.yaml`, walks its stages,
and executes them idempotently against the existing review-council CLI.

Design rules:

- Stages are declarative: `(needs, produces, command, positional, flags)` for
  single stages; `(fanout_pattern, produces_template, ...)` for batched ones.
- Up-to-date is decided by stage metadata fingerprint, not just `produces`
  existence. Fingerprint = hash(input files + args + workflow file + model).
- Human gates are never auto-fulfilled. They print their instruction and leave
  their output to the human; subsequent runs notice when the file appears.
- Fanout stages support per-unit resume: completed outputs are kept across
  runs and only missing/stale units are re-executed. If some units fail the
  stage status is reported as `partial`.
- Path arguments use case-relative form (`reviews/issue_graph.json`); the
  runner resolves them to absolute paths against the case directory.

Metadata location: `<case>/.review_council/stages/<stage_id>.json` for single
stages, `<case>/.review_council/fanout/<stage_id>.json` for fanouts. API keys
are never written to metadata.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
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

META_DIR = ".review_council"
SECRET_FLAG_PREFIXES = ("--api-key", "--token", "--config")


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
    source_path: Path | None = None


@dataclass
class StageResult:
    stage_id: str
    status: str  # ok | up_to_date | gate | skipped | error | partial | not_selected | blocked
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
        source_path=workflow_path,
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
    workflow_hash = _hash_file(workflow.source_path) if workflow.source_path else ""

    results: list[StageResult] = []
    for stage in workflow.stages:
        if only is not None and stage.id not in only:
            results.append(StageResult(stage.id, "not_selected"))
            continue

        if stage.fanout_pattern:
            result = _run_fanout(case_path, stage, base_subs, cli_main, force, workflow_hash)
        else:
            result = _run_single(case_path, stage, base_subs, cli_main, force, workflow_hash)
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
    workflow_hash: str,
) -> StageResult:
    produces_paths = [case_path / _sub(p, subs) for p in stage.produces]
    outputs_present = bool(produces_paths) and all(p.exists() for p in produces_paths)

    if stage.gate == "human":
        if outputs_present:
            return StageResult(stage.id, "ok", "human output present")
        return StageResult(stage.id, "gate", stage.instruction or "human input required")

    if not stage.command:
        return StageResult(stage.id, "skipped", "no command defined")

    fingerprint = _single_fingerprint(case_path, stage, subs, workflow_hash)
    meta_path = _stage_meta_path(case_path, stage.id)
    cached = _load_meta(meta_path)
    if (
        not force
        and outputs_present
        and cached
        and cached.get("fingerprint") == fingerprint
        and cached.get("status") == "ok"
    ):
        return StageResult(stage.id, "up_to_date")

    needs_missing = [n for n in stage.needs if not (case_path / _sub(n, subs)).exists()]
    if needs_missing:
        return StageResult(stage.id, "blocked", f"missing inputs: {needs_missing}")

    argv = _build_argv(stage.command, stage.positional, stage.flags, subs, case_path)
    started = _now_iso()
    rc = _invoke(cli_main, argv)
    finished = _now_iso()

    if rc != 0:
        _write_meta(
            meta_path,
            _meta_payload(stage, fingerprint, started, finished, "error", argv, extra={"exit_code": rc}),
        )
        return StageResult(stage.id, "error", f"exit code {rc}")

    if produces_paths and not all(p.exists() for p in produces_paths):
        missing = [str(p.relative_to(case_path)) for p in produces_paths if not p.exists()]
        _write_meta(
            meta_path,
            _meta_payload(stage, fingerprint, started, finished, "error", argv,
                          extra={"missing_outputs": missing}),
        )
        return StageResult(stage.id, "error", f"missing outputs: {missing}")

    _write_meta(meta_path, _meta_payload(stage, fingerprint, started, finished, "ok", argv))
    return StageResult(stage.id, "ok")


def _run_fanout(
    case_path: Path,
    stage: Stage,
    subs: dict[str, str],
    cli_main: Callable[[list[str]], int],
    force: bool,
    workflow_hash: str,
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

    fanout_meta_path = _fanout_meta_path(case_path, stage.id)
    cached = _load_meta(fanout_meta_path) or {}
    cached_units: dict[str, dict] = cached.get("units", {}) if isinstance(cached, dict) else {}

    common_fp = _fanout_common_fingerprint(case_path, stage, subs, workflow_hash)

    ran = 0
    skipped = 0
    errors: list[str] = []
    failed_units: list[str] = []
    new_units_meta: dict[str, dict] = {}
    total = len(units)
    for index, unit in enumerate(units, start=1):
        stem = unit.stem
        rel_unit = unit.relative_to(case_path).as_posix()
        unit_subs = dict(subs)
        unit_subs["unit"] = rel_unit
        unit_subs["stem"] = stem
        rel_output = _sub(stage.produces_template, unit_subs) if stage.produces_template else ""
        unit_subs["output"] = rel_output
        output_path = case_path / rel_output if rel_output else None

        unit_fp = _hash_combine([common_fp, _hash_file(unit)])
        prev = cached_units.get(stem, {}) if isinstance(cached_units, dict) else {}
        prev_fp = prev.get("fingerprint") if isinstance(prev, dict) else None

        up_to_date = (
            not force
            and output_path
            and output_path.exists()
            and prev_fp == unit_fp
            and prev.get("status") == "ok"
        )
        if up_to_date:
            skipped += 1
            new_units_meta[stem] = prev
            _progress(stage.id, index, total, stem, "skip")
            continue

        _progress(stage.id, index, total, stem, "run")
        argv = _build_argv(
            stage.command,
            stage.positional_template,
            stage.flags_template,
            unit_subs,
            case_path,
        )
        started = _now_iso()
        rc = _invoke(cli_main, argv)
        finished = _now_iso()
        if rc != 0:
            errors.append(f"{stem} (exit {rc})")
            failed_units.append(stem)
            new_units_meta[stem] = {
                "fingerprint": unit_fp,
                "status": "error",
                "exit_code": rc,
                "started_at": started,
                "finished_at": finished,
            }
            _progress(stage.id, index, total, stem, "fail")
            continue
        if output_path and not output_path.exists():
            errors.append(f"{stem} (no output)")
            failed_units.append(stem)
            new_units_meta[stem] = {
                "fingerprint": unit_fp,
                "status": "error",
                "missing_output": rel_output,
                "started_at": started,
                "finished_at": finished,
            }
            _progress(stage.id, index, total, stem, "fail")
            continue
        ran += 1
        new_units_meta[stem] = {
            "fingerprint": unit_fp,
            "status": "ok",
            "output": rel_output,
            "started_at": started,
            "finished_at": finished,
        }
        _progress(stage.id, index, total, stem, "ok")

    detail = (
        f"{filter_detail}{ran} ran, {skipped} up-to-date, {len(errors)} errors out of {total}"
    )
    if failed_units:
        detail += f"; failed: {', '.join(failed_units)}"

    if errors and ran == 0 and skipped == 0:
        status = "error"
    elif errors:
        status = "partial"
    elif ran == 0:
        status = "up_to_date"
    else:
        status = "ok"

    _write_meta(
        fanout_meta_path,
        {
            "stage_id": stage.id,
            "command": stage.command,
            "fingerprint": common_fp,
            "status": status,
            "ran": ran,
            "skipped": skipped,
            "errors": len(errors),
            "failed_units": failed_units,
            "total_units": total,
            "units": new_units_meta,
            "updated_at": _now_iso(),
        },
    )

    print(
        f"[{stage.id}] summary: total={total} ran={ran} skipped={skipped} "
        f"failed={len(errors)} status={status}",
        flush=True,
    )
    if failed_units:
        print(f"[{stage.id}] failed units: {', '.join(failed_units)}", flush=True)

    return StageResult(stage.id, status, detail)


def _progress(stage_id: str, index: int, total: int, stem: str, event: str) -> None:
    print(f"[{stage_id}] {index}/{total} {stem}: {event}", flush=True)


def _invoke(cli_main: Callable[[list[str]], int], argv: list[str]) -> int:
    try:
        return int(cli_main(argv) or 0)
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:  # noqa: BLE001
        print(f"[runner] command {argv[:1]} raised: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1


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
    status_width = max(12, max((len(r.status) for r in results), default=12))
    lines = [f"{'Stage':<{width}}  {'Status':<{status_width}}  Detail"]
    lines.append(f"{'-' * width}  {'-' * status_width}  ------")
    for r in results:
        lines.append(f"{r.stage_id:<{width}}  {r.status:<{status_width}}  {r.detail}")
    return "\n".join(lines)


# --- metadata / hashing ----------------------------------------------------


def _stage_meta_path(case_path: Path, stage_id: str) -> Path:
    return case_path / META_DIR / "stages" / f"{stage_id}.json"


def _fanout_meta_path(case_path: Path, stage_id: str) -> Path:
    return case_path / META_DIR / "fanout" / f"{stage_id}.json"


def _load_meta(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_meta(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _meta_payload(
    stage: Stage,
    fingerprint: str,
    started: str,
    finished: str,
    status: str,
    argv: list[str],
    *,
    extra: dict | None = None,
) -> dict:
    payload = {
        "stage_id": stage.id,
        "command": stage.command,
        "args": _redact_args(argv),
        "fingerprint": fingerprint,
        "model": _extract_flag(argv, "--model"),
        "base_url": _extract_flag(argv, "--base-url"),
        "started_at": started,
        "finished_at": finished,
        "status": status,
    }
    if extra:
        payload.update(extra)
    return payload


def _redact_args(argv: list[str]) -> list[str]:
    out: list[str] = []
    for arg in argv:
        if any(arg.startswith(prefix) for prefix in SECRET_FLAG_PREFIXES):
            key = arg.split("=", 1)[0]
            out.append(f"{key}=<redacted>")
        else:
            out.append(arg)
    return out


def _extract_flag(argv: list[str], name: str) -> str:
    for arg in argv:
        if arg == name:
            continue
        if arg.startswith(name + "="):
            return arg[len(name) + 1 :]
    return ""


def _single_fingerprint(case_path: Path, stage: Stage, subs: dict[str, str], workflow_hash: str) -> str:
    parts = [
        "single",
        stage.command,
        workflow_hash,
        json.dumps([_sub(p, subs) for p in stage.positional], sort_keys=True),
        json.dumps([_sub(f, subs) for f in stage.flags], sort_keys=True),
    ]
    for need in stage.needs:
        path = case_path / _sub(need, subs)
        parts.append(_hash_path(path))
    for tmpl in _template_paths_from_flags(stage.flags, subs, case_path):
        parts.append(_hash_file(tmpl))
    return _hash_combine(parts)


def _fanout_common_fingerprint(
    case_path: Path, stage: Stage, subs: dict[str, str], workflow_hash: str
) -> str:
    parts = [
        "fanout",
        stage.command,
        workflow_hash,
        json.dumps([_sub(p, subs) for p in stage.positional_template], sort_keys=True),
        json.dumps([_sub(f, subs) for f in stage.flags_template], sort_keys=True),
        str(stage.risk_threshold),
        stage.risk_table,
    ]
    if stage.risk_table:
        parts.append(_hash_file(case_path / _sub(stage.risk_table, subs)))
    for tmpl in _template_paths_from_flags(stage.flags_template, subs, case_path):
        parts.append(_hash_file(tmpl))
    return _hash_combine(parts)


def _template_paths_from_flags(flags: list[str], subs: dict[str, str], case_path: Path) -> list[Path]:
    out: list[Path] = []
    for raw in flags:
        flag = _sub(raw, subs)
        for prefix in (
            "--template=",
            "--paper-shape=",
            "--claims=",
            "--claim-matrix=",
            "--draft=",
            "--external-input=",
            "--input=",
        ):
            if flag.startswith(prefix):
                value = flag[len(prefix) :]
                path = Path(value) if Path(value).is_absolute() else (case_path / value)
                if not path.exists():
                    repo_candidate = Path(value)
                    if repo_candidate.exists():
                        path = repo_candidate
                out.append(path)
    return out


def _hash_combine(parts: list[str]) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def _hash_path(path: Path) -> str:
    if not path.exists():
        return f"missing:{path.name}"
    if path.is_file():
        return _hash_file(path)
    if path.is_dir():
        h = hashlib.sha256()
        for fp in sorted(path.rglob("*")):
            if not fp.is_file() or fp.name.startswith("._"):
                continue
            try:
                rel = fp.relative_to(path).as_posix()
            except ValueError:
                rel = fp.name
            h.update(rel.encode("utf-8"))
            h.update(b"\0")
            try:
                h.update(fp.read_bytes())
            except OSError:
                h.update(b"<unreadable>")
            h.update(b"\0")
        return h.hexdigest()
    return f"other:{path.name}"


def _hash_file(path: Path | None) -> str:
    if path is None or not path.exists() or not path.is_file():
        return ""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""
