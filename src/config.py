from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from .paths import CONFIG_PATH, ROOT_DIR


DEFAULT_CONFIG: dict[str, Any] = {
    "hotkey": {"transcribe": "ctrl+`", "translate": "ctrl+b"},
    "target_language": "zh",
    "postprocess": True,
    "pipeline_api": {"url": "ws://127.0.0.1:8765/ws/pipeline", "timeout": 300},
    "recorder": {"sample_rate": 16000, "channels": 1, "input_mode": "system_audio"},
    "realtime": {"show_partial_words": False},
    "hotwords_file": "data/hotwords.txt",
    "history_file": "data/history.json",
    "openai": {"api_key": ""},
}


def _merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def get_nested(data: dict[str, Any], dotted: str, default: Any = None) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def set_nested(data: dict[str, Any], dotted: str, value: Any) -> None:
    cur = data
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = cur.get(part)
        if not isinstance(node, dict):
            node = {}
            cur[part] = node
        cur = node
    cur[parts[-1]] = value


class ConfigStore:
    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self.data = self.load()

    def resolve(self, value: str | Path) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return ROOT_DIR / path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            self.data = deepcopy(DEFAULT_CONFIG)
            self.save()
            return self.data
        raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        self.data = _merge(DEFAULT_CONFIG, raw)
        return self.data

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(self.data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    def get(self, dotted: str, default: Any = None) -> Any:
        return get_nested(self.data, dotted, default)

    def set(self, dotted: str, value: Any) -> dict[str, Any]:
        set_nested(self.data, dotted, value)
        self.save()
        return self.public_config()

    def public_config(self) -> dict[str, Any]:
        cfg = deepcopy(self.data)
        key = get_nested(cfg, "openai.api_key", "")
        if isinstance(cfg.get("openai"), dict):
            cfg["openai"]["has_api_key"] = bool(key)
            cfg["openai"]["api_key"] = ""
        return cfg
