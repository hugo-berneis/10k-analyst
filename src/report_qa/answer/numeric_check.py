"""Confirms every number in the LLM's answer literally appears in the
paragraphs it cited. Neither the LLM nor Jev is trusted with arithmetic or
literal number reading -- this is the one check plain code does, always.
"""

from __future__ import annotations

import re

from report_qa.answer.citations import CITATION_PATTERN

_NUMBER_PATTERN = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")

# SEC filing-type names, not figures -- "Apple's 10-K filing" shouldn't flag
# "10" as an unsupported number. Found live via the Streamlit demo: the LLM
# referenced "10-K" in an answer and the plain digit-matching regex above
# had no way to know it wasn't a financial figure.
_FORM_TYPE_PATTERN = re.compile(r"\b(10-K|10-Q|8-K|6-K|20-F|S-1|S-3|S-4)\b", re.IGNORECASE)


def _normalize(number: str) -> str:
    return number.replace(",", "").replace("$", "").replace("%", "")


def extract_numbers(text: str) -> list[str]:
    """Numeric tokens in `text`, excluding citation indices and SEC form-type names."""
    without_citations = CITATION_PATTERN.sub("", text)
    without_form_types = _FORM_TYPE_PATTERN.sub("", without_citations)
    return [_normalize(match) for match in _NUMBER_PATTERN.findall(without_form_types)]


def find_unsupported_numbers(answer_text: str, cited_text: str) -> list[str]:
    """Numbers in the answer that don't appear anywhere in the cited source text."""
    source_numbers = set(extract_numbers(cited_text))
    return [n for n in extract_numbers(answer_text) if n not in source_numbers]
