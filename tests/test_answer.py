from dataclasses import dataclass

from report_qa.answer.citations import extract_cited_ids, resolve_citations
from report_qa.answer.groundedness import Verdict, check_groundedness
from report_qa.answer.numeric_check import extract_numbers, find_unsupported_numbers
from report_qa.decision import Decision
from report_qa.retrieval.search import RetrievedParagraph


@dataclass
class _FakeClient:
    """A DecisionClient stand-in that always returns a fixed noul() answer."""

    noul_value: bool
    noul_confidence: float

    def choice(self, state, question, options):  # noqa: ANN001, ARG002
        raise NotImplementedError

    def score(self, state, question):  # noqa: ANN001, ARG002
        raise NotImplementedError

    def noul(self, state, question) -> Decision:  # noqa: ANN001, ARG002
        return Decision(value=self.noul_value, confidence=self.noul_confidence)


def _paragraph(paragraph_id: str, text: str = "Some source text.") -> RetrievedParagraph:
    ticker, fiscal_year, section, index = paragraph_id.split("-")
    return RetrievedParagraph(
        paragraph_id=paragraph_id,
        ticker=ticker,
        fiscal_year=int(fiscal_year),
        section=section,
        text=text,
        topic="other",
        tone=0.5,
        distance=0.1,
    )


# --- citations ---------------------------------------------------------


def test_extract_cited_ids_single_bracket_per_id() -> None:
    text = "Sales grew [AAPL-2025-mdna-3]. Costs fell [AAPL-2025-mdna-4]."
    assert extract_cited_ids(text) == ["AAPL-2025-mdna-3", "AAPL-2025-mdna-4"]


def test_extract_cited_ids_handles_comma_separated_multi_id_brackets() -> None:
    text = "Risks include disruption [AAPL-2025-risk_factors-7, AAPL-2025-risk_factors-8]."
    assert extract_cited_ids(text) == ["AAPL-2025-risk_factors-7", "AAPL-2025-risk_factors-8"]


def test_extract_cited_ids_deduplicates_in_order() -> None:
    text = "[AAPL-2025-mdna-3] again [AAPL-2025-mdna-3]"
    assert extract_cited_ids(text) == ["AAPL-2025-mdna-3"]


def test_resolve_citations_splits_known_from_hallucinated() -> None:
    context = [_paragraph("AAPL-2025-mdna-3")]
    resolved, unknown = resolve_citations(["AAPL-2025-mdna-3", "AAPL-2025-mdna-999"], context)
    assert [p.paragraph_id for p in resolved] == ["AAPL-2025-mdna-3"]
    assert unknown == ["AAPL-2025-mdna-999"]


# --- numeric_check -------------------------------------------------------


def test_extract_numbers_ignores_numbers_inside_citation_brackets() -> None:
    text = "Net sales grew 6% [AAPL-2025-mdna-3, AAPL-2025-mdna-4]."
    assert extract_numbers(text) == ["6"]


def test_find_unsupported_numbers_catches_a_fabricated_figure() -> None:
    answer = "The company opened 9999 new stores [WMT-2025-mdna-1]."
    source = "The company opened 500 new stores during the year."
    assert find_unsupported_numbers(answer, source) == ["9999"]


def test_extract_numbers_ignores_sec_form_type_names() -> None:
    text = "I would need excerpts from Apple's 10-K filing, their 10-Q, or an 8-K."
    assert extract_numbers(text) == []


def test_find_unsupported_numbers_empty_when_all_numbers_match() -> None:
    answer = "Revenue grew 6% to $391 billion [AAPL-2025-mdna-3]."
    source = "Revenue increased 6% to $391 billion compared to the prior year."
    assert find_unsupported_numbers(answer, source) == []


# --- groundedness --------------------------------------------------------


def test_groundedness_confident_when_grounded_and_no_code_issues() -> None:
    client = _FakeClient(noul_value=True, noul_confidence=0.9)
    result = check_groundedness(client, "answer", "source", [], [], threshold=0.6)
    assert result.verdict == Verdict.CONFIDENT


def test_groundedness_flagged_when_jev_confidence_is_below_threshold() -> None:
    client = _FakeClient(noul_value=True, noul_confidence=0.3)
    result = check_groundedness(client, "answer", "source", [], [], threshold=0.6)
    assert result.verdict == Verdict.FLAGGED


def test_groundedness_abstained_when_confidently_not_grounded() -> None:
    client = _FakeClient(noul_value=False, noul_confidence=0.9)
    result = check_groundedness(client, "answer", "source", [], [], threshold=0.6)
    assert result.verdict == Verdict.ABSTAINED


def test_hallucinated_citation_forces_abstain_even_if_jev_is_confident() -> None:
    client = _FakeClient(noul_value=True, noul_confidence=0.99)
    result = check_groundedness(
        client, "answer", "source", [], unknown_citations=["FAKE-2025-mdna-0"], threshold=0.6
    )
    assert result.verdict == Verdict.ABSTAINED


def test_unsupported_number_forces_at_least_flagged() -> None:
    client = _FakeClient(noul_value=True, noul_confidence=0.99)
    result = check_groundedness(
        client,
        "answer",
        "source",
        unsupported_numbers=["9999"],
        unknown_citations=[],
        threshold=0.6,
    )
    assert result.verdict == Verdict.FLAGGED
