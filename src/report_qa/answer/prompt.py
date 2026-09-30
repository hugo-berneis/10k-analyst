"""Builds the prompt for the one open-ended step in this pipeline: writing
a cited answer. The LLM only ever sees the paragraphs retrieval kept, and
must cite every claim by paragraph ID rather than rely on outside knowledge.
"""

from __future__ import annotations

from report_qa.retrieval.search import RetrievedParagraph

SYSTEM_PROMPT = """You are a financial analyst assistant answering questions about SEC 10-K filings.

Rules:
- Only use the source paragraphs given to you. Do not use outside knowledge.
- Every factual claim must be followed by the paragraph ID it came from, in square \
brackets, e.g. [AAPL-2025-risk_factors-3].
- If the sources don't contain enough information to answer, say so plainly instead \
of guessing.
- Never invent or restate a number that is not explicitly present in the sources."""


def build_answer_prompt(question: str, paragraphs: list[RetrievedParagraph]) -> str:
    sources = "\n\n".join(f"[{p.paragraph_id}] {p.text}" for p in paragraphs)
    return (
        f"Question: {question}\n\n"
        f"Sources:\n{sources}\n\n"
        "Answer the question using only the sources above, citing paragraph IDs."
    )
