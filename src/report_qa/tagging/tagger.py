"""Tags paragraphs with a risk topic and a tone score via a DecisionClient.

Jev only ever sees a paragraph's text plus a fixed option list (`choice`) or
a bounded scoring question (`score`) -- never raw numbers, dates, or an
open-ended question it could answer outside those bounds.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from report_qa.decision import ChoiceQuestion, DecisionClient, ScoreQuestion
from report_qa.ingest.sections import Paragraph

logger = logging.getLogger(__name__)

TOPIC_QUESTION = "What risk topic does this paragraph primarily discuss?"
TONE_QUESTION = "How negative or alarming is this paragraph's tone?"

# Ordered low-to-high rubric for the tone Score question. Jev places the
# paragraph against these described situations, not a numeric scale --
# it's weak at numbers, so the scale itself is expressed as concrete
# situations instead (per TypeSafe's Score primitive guidance).
TONE_CRITERIA = [
    "Neutral or informational language; no concerning or cautionary tone.",
    "Mildly cautious; routine risk-disclosure language, no specific adverse outcome described.",
    "Negative; describes a specific, plausible adverse impact on the business.",
    "Severe or alarming; describes a risk with major, urgent, or potentially existential impact.",
]


@dataclass(frozen=True)
class Tag:
    topic: str
    topic_confidence: float
    tone: float
    tone_confidence: float


def tag_paragraph(client: DecisionClient, paragraph: Paragraph, topics: list[str]) -> Tag:
    # One round trip for both questions, not two -- see decision_jev.py.
    answers = client.ask_many(
        paragraph.text,
        {
            "topic": ChoiceQuestion(question=TOPIC_QUESTION, options=topics),
            "tone": ScoreQuestion(question=TONE_QUESTION, criteria=TONE_CRITERIA),
        },
    )
    topic_decision = answers["topic"]
    tone_decision = answers["tone"]
    return Tag(
        topic=str(topic_decision.value),
        topic_confidence=topic_decision.confidence,
        tone=float(tone_decision.value),
        tone_confidence=tone_decision.confidence,
    )


def tag_paragraphs(
    client: DecisionClient,
    paragraphs: list[Paragraph],
    topics: list[str],
    batch_size: int = 50,
    max_workers: int = 10,
) -> list[tuple[Paragraph, Tag]]:
    """Tag paragraphs concurrently, logging progress every `batch_size` items.

    Paragraphs are independent I/O-bound work (network calls), so a thread
    pool is used rather than a sequential loop -- tagging all 3,246 Phase 1
    paragraphs sequentially took ~25 minutes; found live that this was the
    dominant cost, not per-call latency. Results come back in the original
    paragraph order regardless of completion order.

    A single paragraph that fails (e.g. a transient network error) is
    skipped, logged, and doesn't lose the rest of a long-running batch --
    found live when a ~6,500-call real-Jev run hit one transient timeout
    and an earlier all-or-nothing version of this function lost everything.
    """

    def _tag_one(paragraph: Paragraph) -> Tag | None:
        try:
            return tag_paragraph(client, paragraph, topics)
        except Exception:
            logger.warning("Failed to tag %s, skipping", paragraph.paragraph_id, exc_info=True)
            return None

    results: list[Tag | None] = [None] * len(paragraphs)
    completed = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(_tag_one, paragraph): i for i, paragraph in enumerate(paragraphs)
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            tag = future.result()
            results[index] = tag
            completed += 1
            if tag is None:
                failed += 1
            if completed % batch_size == 0 or completed == len(paragraphs):
                logger.info(
                    "Tagged %d/%d paragraphs (%d failed)", completed, len(paragraphs), failed
                )

    return [(p, t) for p, t in zip(paragraphs, results, strict=True) if t is not None]
