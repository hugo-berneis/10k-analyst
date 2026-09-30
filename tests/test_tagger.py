from report_qa.decision_mock import MockDecisionClient
from report_qa.ingest.sections import Paragraph
from report_qa.tagging.tagger import Tag, tag_paragraph, tag_paragraphs
from report_qa.tagging.topics import load_topics

TOPICS = ["liquidity", "credit", "cyber"]


def _paragraph(text: str = "Some risk factor text.") -> Paragraph:
    return Paragraph(
        paragraph_id="TEST-2025-risk_factors-0",
        ticker="TEST",
        fiscal_year=2025,
        section="risk_factors",
        index=0,
        text=text,
    )


def test_tag_paragraph_picks_one_of_the_given_topics() -> None:
    client = MockDecisionClient()
    tag = tag_paragraph(client, _paragraph(), TOPICS)

    assert isinstance(tag, Tag)
    assert tag.topic in TOPICS
    assert 0.0 <= tag.topic_confidence <= 1.0
    assert 0.0 <= tag.tone <= 1.0
    assert 0.0 <= tag.tone_confidence <= 1.0


def test_tag_paragraph_never_sends_options_jev_cant_pick() -> None:
    client = MockDecisionClient()
    tag = tag_paragraph(client, _paragraph(), TOPICS)
    assert tag.topic in TOPICS  # Jev's choice() can only return a given option


def test_tag_paragraph_is_deterministic_for_the_same_text() -> None:
    client = MockDecisionClient()
    first = tag_paragraph(client, _paragraph("Repeated text"), TOPICS)
    second = tag_paragraph(client, _paragraph("Repeated text"), TOPICS)
    assert first == second


def test_tag_paragraphs_tags_every_paragraph_in_order() -> None:
    client = MockDecisionClient()
    paragraphs = [_paragraph(f"Risk factor number {i}") for i in range(5)]
    tags = tag_paragraphs(client, paragraphs, TOPICS, batch_size=2)
    assert len(tags) == 5
    assert all(isinstance(t, Tag) for t in tags)


def test_load_topics_returns_the_configured_labels() -> None:
    topics = load_topics()
    assert "liquidity" in topics
    assert "other" in topics
    assert len(topics) == len(set(topics))  # no duplicates
