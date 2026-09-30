"""FastAPI app exposing the ask pipeline as `POST /ask`.

Run with: uv run uvicorn report_qa.app:app --reload
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from report_qa.answer.llm import AnswerLLM
from report_qa.answer.pipeline import ask as run_ask
from report_qa.config import get_settings
from report_qa.db import connect, init_schema
from report_qa.decision_mock import MockDecisionClient
from report_qa.tagging.embeddings import Embedder
from report_qa.thresholds import load_thresholds


class AskRequest(BaseModel):
    question: str
    ticker: str | None = None
    fiscal_year: int | None = None
    topic: str | None = None
    section: str | None = None


class RelevanceLogEntry(BaseModel):
    paragraph_id: str
    relevant: bool
    confidence: float
    kept: bool
    reason: str


class AskResponse(BaseModel):
    question: str
    answer: str
    verdict: str
    citations: list[str]
    unknown_citations: list[str]
    unsupported_numbers: list[str]
    jev_grounded: bool
    jev_confidence: float
    relevance_log: list[RelevanceLogEntry]
    retrieval_ms: float
    answer_ms: float
    total_ms: float


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    conn = connect(settings.database_url)
    init_schema(conn)

    app.state.conn = conn
    app.state.embedder = Embedder(settings.embedding_model)
    # No real Jev client yet -- see CLAUDE.md's Jev rules.
    app.state.decision_client = MockDecisionClient()
    app.state.llm = AnswerLLM(settings.anthropic_api_key, settings.anthropic_model)
    app.state.thresholds = load_thresholds()
    yield
    conn.close()


app = FastAPI(title="10k-analyst", lifespan=lifespan)


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(request: AskRequest) -> AskResponse:
    result = run_ask(
        app.state.conn,
        app.state.embedder,
        app.state.decision_client,
        app.state.llm,
        app.state.thresholds,
        request.question,
        ticker=request.ticker,
        fiscal_year=request.fiscal_year,
        topic=request.topic,
        section=request.section,
    )
    return AskResponse(
        question=result.question,
        answer=result.answer,
        verdict=result.verdict.value,
        citations=result.citations,
        unknown_citations=result.unknown_citations,
        unsupported_numbers=result.unsupported_numbers,
        jev_grounded=result.jev_grounded,
        jev_confidence=result.jev_confidence,
        relevance_log=[
            RelevanceLogEntry(
                paragraph_id=r.paragraph.paragraph_id,
                relevant=r.relevant,
                confidence=r.confidence,
                kept=r.kept,
                reason=r.reason,
            )
            for r in result.relevance_log
        ],
        retrieval_ms=result.retrieval_ms,
        answer_ms=result.answer_ms,
        total_ms=result.total_ms,
    )
