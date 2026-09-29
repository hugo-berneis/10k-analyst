"""Interface to Jev, our System-One decision model.

Every call to Jev goes through `DecisionClient` so the rest of the codebase
never depends on the Jev SDK directly. Jev is only ever given a fixed set of
options to choose from or a bounded score to assign -- never raw numbers or
open-ended text generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Decision:
    """A single Jev decision: an answer plus how confident Jev is in it."""

    value: str | float | bool
    confidence: float


@runtime_checkable
class DecisionClient(Protocol):
    """Everything the rest of the app is allowed to ask Jev to do."""

    def choice(self, state: str, question: str, options: list[str]) -> Decision:
        """Pick one of `options` for `question`, given context `state`."""
        ...

    def score(self, state: str, question: str) -> Decision:
        """Return a bounded score (e.g. tone) for `question` given `state`."""
        ...

    def noul(self, state: str, question: str) -> Decision:
        """Answer a yes/no question (e.g. relevance, groundedness)."""
        ...
