# 10k-analyst

**An AI analyst for SEC 10-K filings, built to catch hallucinations.**

## The idea

Most "AI for investing" tools hand a filing to a chatbot and hope the answer is right — risky in finance, where one made-up number can mislead an entire analysis. This project splits the work instead: fast, bounded judgments (*is this paragraph relevant? is this answer grounded?*) go to **Jev**, a confidence-scored "System One" decision model that can never answer outside the options it's given; open-ended writing goes to an **LLM**, which must cite the paragraphs it used; and every number in the answer is checked against the source text by **plain code**, since neither model should be trusted with arithmetic. The result is a pipeline where every step either shows its confidence or shows its work, and low-confidence answers get flagged instead of presented as fact.

## How it works

```mermaid
flowchart LR
    A[SEC EDGAR<br/>10-K filings] --> B[Extract Risk Factors<br/>+ MD&A sections]
    B --> C[Jev tags each paragraph<br/>risk topic + tone]
    C --> D[(Postgres + pgvector)]
    Q[Your question] --> E[Vector search]
    D --> E
    E --> F[Jev relevance filter]
    F --> G[LLM writes cited answer]
    G --> H[Code checks every number<br/>against the source]
    H --> I[Jev groundedness check]
    I -->|confident| J[Answer + citations]
    I -->|not confident| K[Flagged or withheld]
```

1. **Ingest:** Pull 10-K filings from SEC EDGAR and keep the two sections that matter most for risk: Item 1A (Risk Factors) and Item 7 (Management's Discussion & Analysis).
2. **Tag:** Jev labels every paragraph with a risk topic and a tone score, each with a confidence value.
3. **Retrieve:** Find candidate paragraphs with vector search, then let Jev filter for relevance.
4. **Answer:** An LLM writes an answer that must cite the paragraphs it used.
5. **Verify:** Code confirms every figure appears in the cited text, and Jev checks whether the answer is actually supported. If not, the system says so.

## Results

*From `scripts/run_eval.py` against 20 human-approved gold questions and 10 deliberately-unsupported answer fixtures. No numbers are estimated. Full results: `eval/results.json`.*

| Metric | Result |
|---|---|
| Filings / paragraphs processed | 12 filings (6 companies × 2 years) → 3,246 paragraphs |
| Retrieval recall@5 (with vs. without Jev filter) | 0.85 / 0.85 (identical for now — see note below) |
| Fabricated numbers / hallucinated citations caught by the gate | 100% (7/7) — this check is plain code, not Jev, so it's real today |
| Abstention rate / gate precision | 0.55 / 0.36 — not yet meaningful, see note below |
| p50 / p95 latency per question | 2.1s / 4.0s |
| Cost per question | $0.0025 (Claude Haiku 4.5) |

Recall is identical with and without the Jev filter, and abstention/precision are noisy, because relevance and groundedness are still judged by `MockDecisionClient` — a deterministic stand-in with no real understanding of the text (see Limitations). The numeric-check and citation-hallucination results don't depend on Jev at all, so those are genuine.

## Tech stack

Python · FastAPI · PostgreSQL + pgvector · sentence-transformers · Jev (TypeSafe) · Claude API · Streamlit · Docker

## Getting started

Requires [Docker](https://www.docker.com/) and [uv](https://docs.astral.sh/uv/) installed first; `uv` installs the pinned Python 3.12 itself. You'll also need an [Anthropic API key](https://console.anthropic.com/).

**1. Setup and data pipeline:**

```bash
git clone https://github.com/<your-username>/10k-analyst.git
cd 10k-analyst
cp .env.example .env       # add your API keys and SEC contact email
docker compose up -d       # starts Postgres + pgvector
uv sync                    # installs dependencies (Python 3.12, via uv)
uv run pytest              # smoke tests should pass without Jev or a live DB
uv run ruff check .        # lint
uv run python scripts/ingest.py         # pull filings from EDGAR
uv run python scripts/tag_and_embed.py  # tag + embed into Postgres
```

**2. Try it — demo UI:**

```bash
uv run streamlit run streamlit_app.py
```

Opens at `http://localhost:8501`. Ask a question, pick an optional ticker/year/section, and see the answer, citations, verdict, and which retrieved chunks were kept or dropped and why.

**3. Or hit the API directly:**

```bash
uv run uvicorn report_qa.app:app --reload
```

```bash
curl -s localhost:8000/ask -H 'content-type: application/json' -d '{
  "question": "What does the company say about cybersecurity risk?",
  "ticker": "AAPL", "fiscal_year": 2025
}' | jq
```

**4. Reproduce the results table:**

```bash
uv run python scripts/run_eval.py
```

Relevance and groundedness verdicts currently come from `MockDecisionClient`, not real Jev — see Limitations.

## Roadmap

- [x] Project scaffold + local database
- [x] EDGAR ingestion (Risk Factors + MD&A)
- [x] Paragraph tagging + embeddings
- [x] Retrieval, answering, and verification
- [x] Evaluation on a hand-checked question set
- [x] Demo UI

## Limitations

- **Catches hallucinations; doesn't eliminate them.** The verification step reduces unsupported answers, and the evaluation measures how many still slip through.
- **Prose only.** Financial tables and statements aren't parsed yet.
- **Small scope:** a handful of companies, for demonstration.
- **Some filers structure their MD&A as a page-number pointer into a separate "wrap" section instead of writing it inline under Item 7** (seen in JPMorgan's and Chevron's 10-Ks). Ingestion doesn't follow that pointer, so such filers are left out of the MVP list rather than silently ingested with empty MD&A.
- **The numeric check can false-flag a real number** if it's paraphrased rather than repeated verbatim in the cited paragraph (e.g. a year mentioned in the answer but not restated in the cited sentence). It's a substring heuristic, not semantic matching, so it errs toward flagging rather than missing a real hallucination.
- **Relevance and groundedness verdicts are currently from `MockDecisionClient`**, not real Jev, so they're structurally correct (the gating logic works) but not yet semantically meaningful.
- **Jev itself is weak at numbers, counting, dates, and literal reading** — that's a known property of the model, not a bug. It's why this architecture never asks Jev to do arithmetic: Jev only ever picks from a fixed option list or returns a bounded score, and every number in an answer is checked by plain code (`answer/numeric_check.py`) instead.

## Disclaimer

This is a personal research project, not investment advice.
