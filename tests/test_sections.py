from pathlib import Path

import pytest

from report_qa.ingest.sections import SectionNotFoundError, extract_paragraphs

FIXTURE_HTML = (Path(__file__).parent / "fixtures" / "sample_10k.html").read_text()


def test_risk_factors_paragraphs_are_real_prose_only() -> None:
    paragraphs = extract_paragraphs(FIXTURE_HTML, "TEST", 2025)
    risk_factors = [p for p in paragraphs if p.section == "risk_factors"]

    assert len(risk_factors) == 4
    assert all(p.text.startswith(("The", "Demand")) for p in risk_factors)


def test_running_header_and_page_footer_are_excluded() -> None:
    paragraphs = extract_paragraphs(FIXTURE_HTML, "TEST", 2025)
    texts = [p.text for p in paragraphs]

    assert not any(text.strip() == "Item 1A" for text in texts)
    assert not any("Form 10-K" in text for text in texts)


def test_table_of_contents_entries_are_excluded() -> None:
    paragraphs = extract_paragraphs(FIXTURE_HTML, "TEST", 2025)
    assert all("Table of Contents" not in p.text for p in paragraphs)


def test_mdna_paragraphs_start_after_the_spilled_title() -> None:
    paragraphs = extract_paragraphs(FIXTURE_HTML, "TEST", 2025)
    mdna = [p for p in paragraphs if p.section == "mdna"]

    assert len(mdna) == 3
    assert "Management's Discussion" not in mdna[0].text
    assert mdna[0].text.startswith("The following discussion")


def test_paragraph_ids_are_stable_and_sequential() -> None:
    paragraphs = extract_paragraphs(FIXTURE_HTML, "TEST", 2025)
    risk_factors = [p for p in paragraphs if p.section == "risk_factors"]

    assert [p.paragraph_id for p in risk_factors] == [
        "TEST-2025-risk_factors-0",
        "TEST-2025-risk_factors-1",
        "TEST-2025-risk_factors-2",
        "TEST-2025-risk_factors-3",
    ]
    assert [p.index for p in risk_factors] == [0, 1, 2, 3]


def test_char_count_matches_text_length() -> None:
    paragraphs = extract_paragraphs(FIXTURE_HTML, "TEST", 2025)
    assert all(p.char_count == len(p.text) for p in paragraphs)


def test_missing_section_raises() -> None:
    with pytest.raises(SectionNotFoundError):
        extract_paragraphs("<html><body><p>Nothing relevant here.</p></body></html>", "TEST", 2025)
