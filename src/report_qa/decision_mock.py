"""A fake `DecisionClient` so the pipeline runs before Jev is wired in.

Real Jev calls are non-deterministic and cost money, so tests and local runs
use this instead. Answers are derived from a hash of the inputs rather than
fixed, so different paragraphs exercise different downstream branches
(e.g. both the "relevant" and "not relevant" paths get hit) without being
random between runs.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

from report_qa.decision import ChoiceQuestion, Decision, NoulQuestion, Question, ScoreQuestion


def _stable_unit_interval(*parts: str) -> float:
    """Map arbitrary strings to a reproducible float in [0, 1)."""
    digest = hashlib.sha256("\x1f".join(parts).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


class MockDecisionClient:
    """Deterministic stand-in for Jev. Confidence is fixed and configurable."""

    def __init__(self, confidence: float = 0.6) -> None:
        self.confidence = confidence

    def choice(self, state: str, question: str, options: list[str]) -> Decision:
        if not options:
            raise ValueError("choice() requires at least one option")
        index = int(_stable_unit_interval(state, question, "choice") * len(options))
        return Decision(value=options[min(index, len(options) - 1)], confidence=self.confidence)

    def score(self, state: str, question: str, criteria: list[str]) -> Decision:
        if not criteria:
            raise ValueError("score() requires at least one criterion")
        value = _stable_unit_interval(state, question, "score", str(len(criteria)))
        return Decision(value=value, confidence=self.confidence)

    def noul(self, state: str, question: str) -> Decision:
        value = _stable_unit_interval(state, question, "noul") >= 0.5
        return Decision(value=value, confidence=self.confidence)

    def ask_many(self, state: str, questions: Mapping[str, Question]) -> dict[str, Decision]:
        """No real batching to gain here -- just answers each one locally."""
        answers = {}
        for key, q in questions.items():
            if isinstance(q, ChoiceQuestion):
                answers[key] = self.choice(state, q.question, q.options)
            elif isinstance(q, ScoreQuestion):
                answers[key] = self.score(state, q.question, q.criteria)
            elif isinstance(q, NoulQuestion):
                answers[key] = self.noul(state, q.question)
            else:
                raise TypeError(f"Unknown question type: {type(q)!r}")
        return answers
