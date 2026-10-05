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

## Confidence Thresholds (from confidence-audit)

[confidence-audit](../confidence-audit) (Project 2) calibrates Jev's and an LLM's confidence
on held-out finance classification tasks and exports frozen thresholds to
`../confidence-audit/exports/thresholds.json`, validated against
`../confidence-audit/configs/thresholds.schema.json`:

```json
[
  {
    "task": "financial_sentiment",
    "model": "llm-mock",
    "tau_low": 0.7,
    "tau_high": 0.7,
    "target": { "coverage": 0.8, "error_rate": 0.1 },
    "date": "2026-10-04",
    "run_id": "20261004T200428Z"
  }
]
```

- `tau_high` — above this confidence, trust Jev's decision outright.
- `tau_low` — below this confidence, reject/abstain; don't show the result.
- Between the two — still shown, but flagged low-confidence.

This is the same shape as the two independent gates already in
`config/thresholds.yaml` (`relevance_drop_confidence` rejects below 0.8;
`groundedness_threshold` accepts above 0.6) — confidence-audit's export is
meant to calibrate those numbers against real data instead of guessing them.

**Not wired up automatically yet.** `exports/` isn't committed in either
repo, and `thresholds.py` here still reads flat values from
`config/thresholds.yaml` by hand. Loading `tau_low`/`tau_high` per
task/model from `exports/thresholds.json` instead is follow-up work, not
yet implemented.

## Instructions to Run Test Suite(s)

```bash
uv run pytest
uv run ruff check .
```
