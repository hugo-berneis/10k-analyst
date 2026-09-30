"""End-to-end ask pipeline: retrieve -> relevance filter -> answer -> verify -> gate."""

from __future__ import annotations

import time
from dataclasses import dataclass

import psycopg

from report_qa.answer.citations import extract_cited_ids, resolve_citations
from report_qa.answer.groundedness import GroundednessResult, Verdict, check_groundedness
from report_qa.answer.llm import AnswerLLM
from report_qa.answer.numeric_check import find_unsupported_numbers
from report_qa.answer.prompt import build_answer_prompt
from report_qa.decision import DecisionClient
from report_qa.retrieval.relevance import RelevanceResult, filter_relevance
from report_qa.retrieval.search import search
from report_qa.tagging.embeddings import Embedder
from report_qa.thresholds import Thresholds

NO_RELEVANT_CONTEXT_ANSWER = "I don't have enough relevant information to answer this question."


@dataclass(frozen=True)
class AskResult:
    question: str
    answer: str
    verdict: Verdict
    citations: list[str]
    unknown_citations: list[str]
    unsupported_numbers: list[str]
    jev_grounded: bool
    jev_confidence: float
    relevance_log: list[RelevanceResult]
    retrieval_ms: float
    answer_ms: float
    total_ms: float


def ask(
    conn: psycopg.Connection,
    embedder: Embedder,
    decision_client: DecisionClient,
    llm: AnswerLLM,
    thresholds: Thresholds,
    question: str,
    ticker: str | None = None,
    fiscal_year: int | None = None,
    topic: str | None = None,
    section: str | None = None,
) -> AskResult:
    start = time.perf_counter()

    candidates = search(
        conn,
        embedder,
        question,
        thresholds.retrieval_top_k,
        ticker=ticker,
        fiscal_year=fiscal_year,
        topic=topic,
        section=section,
    )
    relevance_log = filter_relevance(
        decision_client, question, candidates, thresholds.relevance_drop_confidence
    )
    kept = [r.paragraph for r in relevance_log if r.kept]
    retrieval_ms = (time.perf_counter() - start) * 1000

    answer_start = time.perf_counter()
    if not kept:
        answer_text = NO_RELEVANT_CONTEXT_ANSWER
        cited_ids: list[str] = []
        unknown_citations: list[str] = []
        unsupported_numbers: list[str] = []
        groundedness = GroundednessResult(Verdict.ABSTAINED, False, 0.0, [], [])
    else:
        prompt = build_answer_prompt(question, kept)
        answer_text = llm.answer(prompt)
        cited_ids = extract_cited_ids(answer_text)
        cited_paragraphs, unknown_citations = resolve_citations(cited_ids, kept)
        cited_text = " ".join(p.text for p in cited_paragraphs)
        unsupported_numbers = find_unsupported_numbers(answer_text, cited_text)
        groundedness = check_groundedness(
            decision_client,
            answer_text,
            cited_text,
            unsupported_numbers,
            unknown_citations,
            thresholds.groundedness_threshold,
        )
        cited_ids = [p.paragraph_id for p in cited_paragraphs]
    answer_ms = (time.perf_counter() - answer_start) * 1000
    total_ms = (time.perf_counter() - start) * 1000

    return AskResult(
        question=question,
        answer=answer_text,
        verdict=groundedness.verdict,
        citations=cited_ids,
        unknown_citations=unknown_citations,
        unsupported_numbers=unsupported_numbers,
        jev_grounded=groundedness.jev_grounded,
        jev_confidence=groundedness.jev_confidence,
        relevance_log=relevance_log,
        retrieval_ms=retrieval_ms,
        answer_ms=answer_ms,
        total_ms=total_ms,
    )
