"""Demo UI: ask a question, see the answer, citations, verdict, and which
chunks were kept or dropped by the relevance filter.

Run with: uv run streamlit run streamlit_app.py
"""

from __future__ import annotations

import streamlit as st

from report_qa.answer.llm import AnswerLLM
from report_qa.answer.pipeline import ask
from report_qa.config import get_settings
from report_qa.db import connect, init_schema
from report_qa.decision import get_decision_client
from report_qa.tagging.embeddings import Embedder
from report_qa.thresholds import load_thresholds

VERDICT_DISPLAY = {
    "confident": ("✅", st.success),
    "flagged": ("⚠️", st.warning),
    "abstained": ("⛔", st.error),
}


@st.cache_resource
def get_resources():
    settings = get_settings()
    conn = connect(settings.database_url)
    init_schema(conn)
    return {
        "conn": conn,
        "embedder": Embedder(settings.embedding_model),
        "decision_client": get_decision_client(settings),
        "llm": AnswerLLM(settings.anthropic_api_key, settings.anthropic_model),
        "thresholds": load_thresholds(),
    }


@st.cache_data(ttl=60)
def get_filter_options(_conn):
    with _conn.cursor() as cur:
        cur.execute("SELECT DISTINCT ticker FROM paragraphs ORDER BY ticker")
        tickers = [row[0] for row in cur.fetchall()]
        cur.execute("SELECT DISTINCT fiscal_year FROM paragraphs ORDER BY fiscal_year DESC")
        years = [row[0] for row in cur.fetchall()]
    return tickers, years


st.set_page_config(page_title="10k-analyst", page_icon="📊")
st.title("10k-analyst")
st.caption(
    "Ask a question about a company's SEC 10-K risk factors or MD&A. "
    "Answers are gated: low-confidence answers are flagged or withheld, not presented as fact."
)

resources = get_resources()
tickers, years = get_filter_options(resources["conn"])

with st.form("ask_form"):
    question = st.text_input("Question", placeholder="What does the company say about...")
    col1, col2, col3 = st.columns(3)
    ticker = col1.selectbox("Ticker", ["Any", *tickers])
    fiscal_year = col2.selectbox("Fiscal year", ["Any", *years])
    section = col3.selectbox("Section", ["Any", "risk_factors", "mdna"])
    submitted = st.form_submit_button("Ask")

if submitted and question:
    with st.spinner("Retrieving, answering, and verifying..."):
        result = ask(
            resources["conn"],
            resources["embedder"],
            resources["decision_client"],
            resources["llm"],
            resources["thresholds"],
            question,
            ticker=None if ticker == "Any" else ticker,
            fiscal_year=None if fiscal_year == "Any" else int(fiscal_year),
            section=None if section == "Any" else section,
        )

    icon, verdict_fn = VERDICT_DISPLAY[result.verdict.value]
    verdict_fn(f"{icon} Verdict: **{result.verdict.value}**")

    st.markdown(result.answer)

    if result.unknown_citations:
        st.error(
            f"Hallucinated citations (not in the retrieved context): {result.unknown_citations}"
        )
    if result.unsupported_numbers:
        st.error(
            "Numbers in the answer not found in the cited source text: "
            f"{result.unsupported_numbers}"
        )

    st.subheader("Citations")
    if result.citations:
        for citation_id in result.citations:
            st.code(citation_id)
    else:
        st.write("None.")

    st.subheader("Retrieved chunks: kept vs. dropped")
    st.caption("A chunk is only dropped when Jev is confidently sure it's irrelevant.")
    for entry in result.relevance_log:
        icon = "✅ kept" if entry.kept else "❌ dropped"
        st.text(
            f"{icon} — {entry.paragraph.paragraph_id} "
            f"(relevant={entry.relevant}, confidence={entry.confidence:.2f}, {entry.reason})"
        )

    st.caption(
        f"Jev grounded={result.jev_grounded} confidence={result.jev_confidence:.2f} · "
        f"retrieval {result.retrieval_ms:.0f}ms · answer {result.answer_ms:.0f}ms · "
        f"total {result.total_ms:.0f}ms"
    )
