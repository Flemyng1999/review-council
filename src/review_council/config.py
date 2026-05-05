"""Local runtime configuration."""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def get_config_value(name: str, config_path: Path | None = None) -> str | None:
    if value := os.environ.get(name):
        return value
    if config_path is None:
        config_path = Path("config/secrets.local.env")
    return load_env_file(config_path).get(name)
