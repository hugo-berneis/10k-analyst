from dataclasses import dataclass, field

from report_qa.decision import Decision
from report_qa.retrieval.relevance import filter_relevance
from report_qa.retrieval.search import RetrievedParagraph


@dataclass
class _QueueClient:
    """A DecisionClient stand-in that returns queued noul() answers in order."""

    decisions: list[Decision]
    calls: int = field(default=0, init=False)

    def choice(self, state, question, options):  # noqa: ANN001, ARG002
        raise NotImplementedError

    def score(self, state, question):  # noqa: ANN001, ARG002
        raise NotImplementedError

    def noul(self, state, question) -> Decision:  # noqa: ANN001, ARG002
        decision = self.decisions[self.calls]
        self.calls += 1
        return decision


def _paragraph(paragraph_id: str) -> RetrievedParagraph:
    return RetrievedParagraph(
        paragraph_id=paragraph_id,
        ticker="TEST",
        fiscal_year=2025,
        section="risk_factors",
        text="Some paragraph text.",
        topic="other",
        tone=0.5,
        distance=0.1,
    )


def test_relevant_chunk_is_kept() -> None:
    client = _QueueClient([Decision(value=True, confidence=0.9)])
    results = filter_relevance(client, "question?", [_paragraph("A")], drop_confidence=0.8)
    assert results[0].kept is True
    assert results[0].reason == "relevant"


def test_confidently_irrelevant_chunk_is_dropped() -> None:
    client = _QueueClient([Decision(value=False, confidence=0.9)])
    results = filter_relevance(client, "question?", [_paragraph("A")], drop_confidence=0.8)
    assert results[0].kept is False
    assert results[0].reason == "dropped_confidently_irrelevant"


def test_uncertainly_irrelevant_chunk_is_kept_not_dropped() -> None:
    client = _QueueClient([Decision(value=False, confidence=0.5)])
    results = filter_relevance(client, "question?", [_paragraph("A")], drop_confidence=0.8)
    assert results[0].kept is True
    assert results[0].reason == "kept_despite_low_confidence_irrelevant"


def test_confidence_exactly_at_threshold_drops() -> None:
    client = _QueueClient([Decision(value=False, confidence=0.8)])
    results = filter_relevance(client, "question?", [_paragraph("A")], drop_confidence=0.8)
    assert results[0].kept is False


def test_each_candidate_gets_its_own_decision() -> None:
    client = _QueueClient(
        [
            Decision(value=True, confidence=0.9),
            Decision(value=False, confidence=0.9),
            Decision(value=False, confidence=0.1),
        ]
    )
    results = filter_relevance(
        client,
        "question?",
        [_paragraph("A"), _paragraph("B"), _paragraph("C")],
        drop_confidence=0.8,
    )
    assert [r.kept for r in results] == [True, False, True]
