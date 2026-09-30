"""Combines Jev's groundedness check with the numeric/citation checks into
one verdict. Code-verified problems (a hallucinated citation, an unsupported
number) are never overridden by Jev's confidence -- they can only push the
final verdict to be *more* cautious, never less.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from report_qa.decision import DecisionClient

GROUNDEDNESS_QUESTION = (
    "Is this answer fully supported by the given source text, with no unsupported claims?"
)

_SEVERITY = {"confident": 0, "flagged": 1, "abstained": 2}


class Verdict(StrEnum):
    CONFIDENT = "confident"
    FLAGGED = "flagged"
    ABSTAINED = "abstained"


@dataclass(frozen=True)
class GroundednessResult:
    verdict: Verdict
    jev_grounded: bool
    jev_confidence: float
    unsupported_numbers: list[str]
    unknown_citations: list[str]


def _more_severe(a: Verdict, b: Verdict) -> Verdict:
    return a if _SEVERITY[a.value] >= _SEVERITY[b.value] else b


def check_groundedness(
    client: DecisionClient,
    answer_text: str,
    cited_text: str,
    unsupported_numbers: list[str],
    unknown_citations: list[str],
    threshold: float,
) -> GroundednessResult:
    state = f"Answer: {answer_text}\n\nSources: {cited_text}"
    decision = client.noul(state, GROUNDEDNESS_QUESTION)
    grounded = bool(decision.value)

    if grounded and decision.confidence >= threshold:
        jev_verdict = Verdict.CONFIDENT
    elif (not grounded) and decision.confidence >= threshold:
        jev_verdict = Verdict.ABSTAINED
    else:
        jev_verdict = Verdict.FLAGGED  # Jev's signal was too uncertain either way

    if unknown_citations:
        numeric_verdict = Verdict.ABSTAINED  # a citation that doesn't exist is a hard fail
    elif unsupported_numbers:
        numeric_verdict = Verdict.FLAGGED
    else:
        numeric_verdict = Verdict.CONFIDENT

    return GroundednessResult(
        verdict=_more_severe(jev_verdict, numeric_verdict),
        jev_grounded=grounded,
        jev_confidence=decision.confidence,
        unsupported_numbers=unsupported_numbers,
        unknown_citations=unknown_citations,
    )
