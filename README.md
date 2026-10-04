# 10k-analyst

## Author / Contact

- Hugo Berneis — hugo@berneis.com
- GitHub: HBerneis

## Bug Tracker

- None yet.

## Known Issues

- Catches hallucinations; doesn't eliminate them.
- Prose only — financial tables and statements aren't parsed.
- Small scope: a handful of companies, for demonstration.
- Some filers (JPMorgan, Chevron) structure their MD&A as a page-number pointer into a separate "wrap" section instead of writing it inline under Item 7. Ingestion doesn't follow that pointer. Chevron was left out of the MVP list for this reason; JPMorgan is included anyway because its Item 1A ingests cleanly — only its MD&A is a near-empty stub.
- The numeric check can false-flag a real number if it's paraphrased rather than repeated verbatim in the cited paragraph.
- Jev itself is weak at numbers, counting, dates, and literal reading — the architecture never asks Jev to do arithmetic; every number in an answer is checked by plain code instead.
- The groundedness gate is conservative out of the box — most grounded, correctly-cited answers land as "flagged" rather than "confident" with the default threshold.
- Without `JEV_API_KEY` set, the pipeline still runs end-to-end via `MockDecisionClient`, a deterministic stand-in whose verdicts aren't meaningful.

## Instructions to Build

- Requires [Docker](https://www.docker.com/) and [uv](https://docs.astral.sh/uv/) installed first; `uv` installs the pinned Python 3.12 itself.
- Requires an [Anthropic API key](https://console.anthropic.com/).

```bash
git clone https://github.com/<your-username>/10k-analyst.git
cd 10k-analyst
cp .env.example .env       # add your API keys and SEC contact email
docker compose up -d       # starts Postgres + pgvector
uv sync                    # installs dependencies (Python 3.12, via uv)
uv run python scripts/ingest.py         # pull filings from EDGAR
uv run python scripts/tag_and_embed.py  # tag + embed into Postgres
```

## Instructions to Run

- Demo UI:

```bash
uv run streamlit run streamlit_app.py
```

Opens at `http://localhost:8501`. Ask a question, pick an optional ticker/year/section, and see the answer, citations, verdict, and which chunks were kept or dropped.

- API:

```bash
uv run uvicorn report_qa.app:app --reload
```

```bash
curl -s localhost:8000/ask -H 'content-type: application/json' -d '{
  "question": "What does the company say about cybersecurity risk?",
  "ticker": "AAPL", "fiscal_year": 2025
}' | jq
```

- Reproduce the results table:

```bash
uv run python scripts/run_eval.py
```

Uses real Jev if `JEV_API_KEY` is set in `.env`, otherwise falls back to `MockDecisionClient` automatically.

## Instructions to Run Test Suite(s)

```bash
uv run pytest
uv run ruff check .
```
