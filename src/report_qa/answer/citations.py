"""Parses which paragraph IDs the LLM actually cited, and separates out any
that don't correspond to a paragraph it was actually given as context --
a hallucinated citation, not just an unsupported claim.
"""

from __future__ import annotations

import re

from report_qa.retrieval.search import RetrievedParagraph

_ID = r"[A-Z]+-\d{4}-[a-z_]+-\d+"

# The LLM sometimes cites several paragraphs in one bracket, comma-separated
# ("[AAPL-2025-risk_factors-7, AAPL-2025-risk_factors-8]") instead of one
# bracket per ID. Matching the whole group, not just a single ID, means
# `.sub("", text)` (used by numeric_check) blanks out the *entire* bracket --
# otherwise a multi-ID bracket wouldn't match at all, and its embedded
# paragraph-index numbers would leak into the answer's numeric check.
CITATION_PATTERN = re.compile(rf"\[({_ID}(?:,\s*{_ID})*)\]")


def extract_cited_ids(answer_text: str) -> list[str]:
    """Distinct paragraph IDs cited in `answer_text`, in order of first appearance."""
    seen: list[str] = []
    for group in CITATION_PATTERN.findall(answer_text):
        for cid in (part.strip() for part in group.split(",")):
            if cid not in seen:
                seen.append(cid)
    return seen


def resolve_citations(
    cited_ids: list[str], context: list[RetrievedParagraph]
) -> tuple[list[RetrievedParagraph], list[str]]:
    """Split cited IDs into paragraphs that were really given as context vs.
    IDs that weren't -- the latter is a hallucinated citation."""
    context_by_id = {p.paragraph_id: p for p in context}
    cited_paragraphs = [context_by_id[cid] for cid in cited_ids if cid in context_by_id]
    unknown_ids = [cid for cid in cited_ids if cid not in context_by_id]
    return cited_paragraphs, unknown_ids
