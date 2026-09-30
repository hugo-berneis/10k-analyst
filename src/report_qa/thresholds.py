"""Loads retrieval/answer-gate knobs from `config/thresholds.yaml`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "thresholds.yaml"


@dataclass(frozen=True)
class Thresholds:
    retrieval_top_k: int
    relevance_drop_confidence: float
    groundedness_threshold: float


def load_thresholds(path: Path = DEFAULT_CONFIG_PATH) -> Thresholds:
    raw = yaml.safe_load(path.read_text())
    return Thresholds(
        retrieval_top_k=int(raw["retrieval_top_k"]),
        relevance_drop_confidence=float(raw["relevance_drop_confidence"]),
        groundedness_threshold=float(raw["groundedness_threshold"]),
    )
