# 10k-analyst

## Author / Contact

- Hugo Berneis — hugo@berneis.com
- GitHub: HBerneis

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
