"""Score per-section review risk for DeepSeek fanout filtering.

The score is a length-normalized weighted sum of keyword hits across categories
relevant to vegetation remote sensing, agriculture, and environmental physics.
Sections with high method, validation, statistics, or data density score high;
introductions, literature reviews, and acknowledgments score low.

Defaults are intentionally simple and deterministic. Future per-discipline
weights can move to a YAML config without changing callers.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


KEYWORD_CATEGORIES: dict[str, tuple[float, tuple[str, ...]]] = {
    "method": (
        3.0,
        (
            "反演", "inversion", "模型", "model", "算法", "algorithm",
            "公式", "equation", "参数", "parameter", "方法", "method",
            "PROSPECT", "PROSAIL", "SAIL", "PLSR", "回归", "regression",
            "拟合", "随机森林", "random forest", "training", "训练",
        ),
    ),
    "validation": (
        3.0,
        (
            "验证", "validation", "validate", "不确定度", "uncertainty",
            "误差", "error", "RMSE", "MAE", "R^2", "R²", "ubRMSE",
            "MAPE", "KGE", "置信", "confidence", "leakage", "泄漏",
        ),
    ),
    "statistics": (
        3.0,
        (
            "显著", "significan", "因果", "causal", "p<", "p =",
            "假设", "hypothesis", "bias", "偏倚", "control", "对照",
            "interval",
        ),
    ),
    "data": (
        2.0,
        (
            "数据", "data", "样本", "sample", "训练集", "测试集",
            "training set", "test set", "validation set", "ground truth",
            "标签", "label", "dataset", "Sentinel", "Landsat", "MODIS",
            "Hyperspectral", "高光谱", "无人机", "UAV", "WorldView",
        ),
    ),
    "results": (
        2.0,
        ("结果", "result", "table", "figure", "图", "表"),
    ),
    "low_risk": (
        0.2,
        (
            "引言", "introduction", "综述", "literature", "背景",
            "background", "致谢", "acknowledg", "参考文献", "reference",
        ),
    ),
}


@dataclass(frozen=True)
class RiskScore:
    unit_id: str
    score: float
    line_count: int
    hits: dict[str, int] = field(default_factory=dict)


_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)


def score_text(text: str) -> tuple[float, dict[str, int]]:
    body = _FRONTMATTER_RE.sub("", text, count=1)
    lower = body.lower()
    hits: dict[str, int] = {}
    raw_score = 0.0
    for category, (weight, keywords) in KEYWORD_CATEGORIES.items():
        category_hits = 0
        for keyword in keywords:
            occurrences = lower.count(keyword.lower())
            if occurrences:
                category_hits += occurrences
        if category_hits:
            hits[category] = category_hits
            raw_score += category_hits * weight
    line_count = max(body.count("\n"), 1)
    density = raw_score / max(line_count / 100.0, 1.0)
    return density, hits


def compute_risk_table(units_root: Path) -> list[RiskScore]:
    scores: list[RiskScore] = []
    for path in sorted(units_root.rglob("*.md")):
        if path.name.startswith("._") or path.name == "index.md":
            continue
        text = path.read_text(encoding="utf-8")
        score, hits = score_text(text)
        unit_id = f"{path.parent.name}/{path.stem}"
        scores.append(
            RiskScore(
                unit_id=unit_id,
                score=score,
                line_count=text.count("\n"),
                hits=hits,
            )
        )
    return scores


def write_risk_table(units_root: Path, output_path: Path | None = None) -> Path:
    target = output_path or (units_root / "risk.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    scores = compute_risk_table(units_root)
    payload = {
        "units": [
            {
                "unit_id": s.unit_id,
                "score": round(s.score, 3),
                "line_count": s.line_count,
                "hits": s.hits,
            }
            for s in sorted(scores, key=lambda r: -r.score)
        ]
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def load_risk_table(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {entry["unit_id"]: float(entry.get("score", 0.0)) for entry in data.get("units", [])}
