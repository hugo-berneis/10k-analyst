"""Loads the fixed risk-topic label set from `config/topics.yaml`."""

from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "topics.yaml"


def load_topics(path: Path = DEFAULT_CONFIG_PATH) -> list[str]:
    raw = yaml.safe_load(path.read_text())
    return list(raw["topics"])
