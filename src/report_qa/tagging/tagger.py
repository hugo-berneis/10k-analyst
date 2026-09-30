"""Tags paragraphs with a risk topic and a tone score via a DecisionClient.

Jev only ever sees a paragraph's text plus a fixed option list (`choice`) or
a bounded scoring question (`score`) -- never raw numbers, dates, or an
open-ended question it could answer outside those bounds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from report_qa.decision import DecisionClient
from report_qa.ingest.sections import Paragraph

logger = logging.getLogger(__name__)

TOPIC_QUESTION = "What risk topic does this paragraph primarily discuss?"
TONE_QUESTION = "How negative or alarming is this paragraph's tone, from 0 (neutral) to 1 (severe)?"


@dataclass(frozen=True)
class Tag:
    topic: str
    topic_confidence: float
    tone: float
    tone_confidence: float


def tag_paragraph(client: DecisionClient, paragraph: Paragraph, topics: list[str]) -> Tag:
    topic_decision = client.choice(paragraph.text, TOPIC_QUESTION, topics)
    tone_decision = client.score(paragraph.text, TONE_QUESTION)
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
) -> list[Tag]:
    """Tag paragraphs in batches, logging progress every `batch_size` items."""
    tags = []
    for i, paragraph in enumerate(paragraphs, start=1):
        tags.append(tag_paragraph(client, paragraph, topics))
        if i % batch_size == 0 or i == len(paragraphs):
            logger.info("Tagged %d/%d paragraphs", i, len(paragraphs))
    return tags
