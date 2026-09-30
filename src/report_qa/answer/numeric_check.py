"""Confirms every number in the LLM's answer literally appears in the
paragraphs it cited. Neither the LLM nor Jev is trusted with arithmetic or
literal number reading -- this is the one check plain code does, always.
"""

from __future__ import annotations

import re

from report_qa.answer.citations import CITATION_PATTERN

_NUMBER_PATTERN = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")


def _normalize(number: str) -> str:
    return number.replace(",", "").replace("$", "").replace("%", "")


def extract_numbers(text: str) -> list[str]:
    """Numeric tokens in `text`, excluding the index inside [paragraph_id] citations."""
    without_citations = CITATION_PATTERN.sub("", text)
    return [_normalize(match) for match in _NUMBER_PATTERN.findall(without_citations)]


def find_unsupported_numbers(answer_text: str, cited_text: str) -> list[str]:
    """Numbers in the answer that don't appear anywhere in the cited source text."""
    source_numbers = set(extract_numbers(cited_text))
    return [n for n in extract_numbers(answer_text) if n not in source_numbers]
