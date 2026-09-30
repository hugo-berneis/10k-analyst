"""Jev relevance filter: drops a candidate only when Jev is confidently sure
it's irrelevant. An uncertain "not relevant" is kept rather than dropped, so
a wrong-but-confident answer is never caused by silently losing context.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from report_qa.decision import DecisionClient
from report_qa.retrieval.search import RetrievedParagraph

logger = logging.getLogger(__name__)

RELEVANCE_QUESTION_TEMPLATE = "Is this paragraph relevant to answering: {question}"


@dataclass(frozen=True)
class RelevanceResult:
    paragraph: RetrievedParagraph
    relevant: bool
    confidence: float
    kept: bool
    reason: str


def filter_relevance(
    client: DecisionClient,
    question: str,
    candidates: list[RetrievedParagraph],
    drop_confidence: float,
) -> list[RelevanceResult]:
    results = []
    for candidate in candidates:
        decision = client.noul(
            candidate.text, RELEVANCE_QUESTION_TEMPLATE.format(question=question)
        )
        relevant = bool(decision.value)

        if relevant:
            kept, reason = True, "relevant"
        elif decision.confidence >= drop_confidence:
            kept, reason = False, "dropped_confidently_irrelevant"
        else:
            kept, reason = True, "kept_despite_low_confidence_irrelevant"

        logger.info(
            "%s: relevant=%s confidence=%.2f kept=%s (%s)",
            candidate.paragraph_id,
            relevant,
            decision.confidence,
            kept,
            reason,
        )
        results.append(
            RelevanceResult(
                paragraph=candidate,
                relevant=relevant,
                confidence=decision.confidence,
                kept=kept,
                reason=reason,
            )
        )
    return results
