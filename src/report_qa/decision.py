"""Interface to Jev, our System-One decision model.

Every call to Jev goes through `DecisionClient` so the rest of the codebase
never depends on the Jev SDK directly. Jev is only ever given a fixed set of
options to choose from or a bounded score to assign -- never raw numbers or
open-ended text generation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from report_qa.config import Settings


@dataclass(frozen=True)
class Decision:
    """A single Jev decision: an answer plus how confident Jev is in it."""

    value: str | float | bool
    confidence: float


@dataclass(frozen=True)
class ChoiceQuestion:
    question: str
    options: list[str]


@dataclass(frozen=True)
class ScoreQuestion:
    question: str
    criteria: list[str]


@dataclass(frozen=True)
class NoulQuestion:
    question: str


Question = ChoiceQuestion | ScoreQuestion | NoulQuestion


@runtime_checkable
class DecisionClient(Protocol):
    """Everything the rest of the app is allowed to ask Jev to do."""

    def choice(self, state: str, question: str, options: list[str]) -> Decision:
        """Pick one of `options` for `question`, given context `state`."""
        ...

    def score(self, state: str, question: str, criteria: list[str]) -> Decision:
        """Place `state` on the ordered rubric `criteria` (low to high), for `question`.

        `criteria` are level descriptions, not numbers -- Jev is weak at
        numbers, so it's given concrete situations to match against, not a
        scale to estimate a position on.
        """
        ...

    def noul(self, state: str, question: str) -> Decision:
        """Answer a yes/no question (e.g. relevance, groundedness)."""
        ...

    def ask_many(self, state: str, questions: Mapping[str, Question]) -> dict[str, Decision]:
        """Answer several named questions about the same `state` in one round trip.

        Prefer this over separate choice()/score()/noul() calls whenever more
        than one question is being asked about the same state -- real Jev
        answers them together in a single request (TypeSafe's own benchmark:
        ~10x faster and ~12x cheaper than asking separately). `choice()`,
        `score()`, and `noul()` stay as single-question convenience wrappers.
        """
        ...


def get_decision_client(settings: Settings) -> DecisionClient:
    """Real Jev if `JEV_API_KEY` is set, otherwise the deterministic mock."""
    if settings.jev_api_key:
        from report_qa.decision_jev import JevDecisionClient

        return JevDecisionClient(
            api_key=settings.jev_api_key,
            base_url=settings.jev_base_url,
            model=settings.jev_model,
        )

    from report_qa.decision_mock import MockDecisionClient

    return MockDecisionClient()
