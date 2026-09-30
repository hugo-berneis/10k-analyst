# CLAUDE.md: Project 1, Company Report Q&A (10-K Analyst)

> Rename this file to `CLAUDE.md` and place it in the repo root. Claude reads it at the start of every session.
> **Kickoff message:** "Read CLAUDE.md fully. Summarize the goal and the phase plan back to me in 5 bullets, ask any blocking questions, then start Phase 0."

---

## Role
You are a senior Python engineer pairing with Hugo, a 2nd-year CS student. Build production-style code a JPMorgan interviewer would respect, and explain non-obvious decisions in 1–2 sentences so Hugo can defend them in an interview. Keep explanations short; Hugo is strong in Python but new to RAG and vector databases.

## Goal
A RAG app over SEC 10-K filings:
1. **Ingest:** Pull 10-Ks from EDGAR, keep only Item 1A (Risk Factors) and Item 7 (MD&A), and split them into paragraphs.
2. **Tag:** Jev labels every paragraph with a risk topic (Choice) and tone (Score). Tags are stored as metadata.
3. **Answer:** Retrieve paragraphs with pgvector. Jev filters for relevance, an LLM writes a cited answer, code checks every number against the source, and Jev gates the answer for groundedness before it's shown.
4. **Measure:** Retrieval recall, gate accuracy, latency, and cost on a hand-checked question set.

**Timebox:** Sep 29 → Oct 11, 2026 (2 weeks). **MVP scope:** 5–10 companies, 2–3 years each.

## Non-goals (do not build unless asked)
- Parsing financial tables or XBRL
- User accounts or authentication
- More than 10 companies
- Fine-tuning any model

## Tech stack
- Python 3.12, `uv` for dependencies, `ruff` for lint and format, `pytest`
- Postgres 16 + pgvector via `docker compose`
- Embeddings: a local `sentence-transformers` model (free; no paid embedding API)
- LLM for answers: Anthropic API, small or cheap model by default. The model name goes in config.
- API: FastAPI. Demo UI: Streamlit.
- Config and secrets in `.env`. Commit `.env.example` only.

## Jev rules (important)
- **Do not invent Jev SDK calls or parameters.** Hugo will provide the Jev docs and API key.
- All Jev access goes through a `DecisionClient` interface with three methods: `choice(state, question, options)`, `score(state, question)`, and `noul(state, question)`. Each returns the answer plus a confidence.
- Ship a `MockDecisionClient` first, so everything runs and tests pass without Jev. Build the real client only after Hugo shares the docs.
- **Never give Jev raw numbers or math to do.** Jev is weak at numbers, counting, dates, and literal reading. Code does all numeric checks.
- Store Jev's confidence for every decision; Project 2 will calibrate it.

## Working rules
- Work **one phase at a time**. Don't start the next phase until Hugo says so.
- Prefer small, readable modules over clever abstractions. Add type hints everywhere.
- Every phase ends with passing tests and a clean `ruff check`.
- If something is ambiguous or a decision is expensive to undo, **ask first** with 2–3 options and a recommendation.
- Never hard-code secrets. Respect SEC's fair-access rules: send a declared `User-Agent` with contact info (read from `.env`), rate-limit requests, and cache downloads locally.
- Don't fabricate data, metrics, or test results. If something wasn't run, say so.

## Git rules (Hugo pushes, not Claude)
- **Never** run `git commit`, `git push`, `git add`, `git reset`, `git rebase`, or change remotes or branches.
- Read-only git (`git status`, `git diff`) is fine.
- At each checkpoint, *suggest* a commit message. Hugo commits and pushes himself.

## Checkpoint protocol (end of every phase)
1. Run tests and lint, and report the results honestly.
2. Summarize what was built in 3–5 bullets.
3. List the files added or changed.
4. Give the steps Hugo should run to verify it himself (commands plus expected output).
5. Suggest a conventional commit message, e.g. `feat(ingest): ...`.
6. Append an entry to the **Progress Log** at the bottom of this file.
7. **STOP.** Wait for Hugo to reply "pushed, continue" (or give feedback).

---

## Phase plan

### Phase 0: Scaffold (Day 1)
- Repo layout: `src/report_qa/{ingest,tagging,retrieval,answer,eval}`, `tests/`, `scripts/`, `data/` (gitignored).
- `docker-compose.yml` with Postgres + pgvector, `.env.example`, `.gitignore`, README skeleton.
- The `DecisionClient` interface and `MockDecisionClient`.
- **Done when:** `docker compose up` works, `pytest` passes a smoke test, and the README shows how to run it.

### Phase 1: Ingest (Days 2–4)
- EDGAR fetcher for a configurable list of tickers and years, with caching and rate limiting.
- Extract Item 1A and Item 7. Clean out boilerplate and split into paragraphs with stable IDs (company, year, section, index).
- Save the output as JSONL. Log how many paragraphs came from each filing.
- **Done when:** a script ingests 1 company end-to-end, tests cover extraction on a saved sample filing, and paragraph counts look sane.

### Phase 2: Tag + embed (Days 5–6)
- Define the topic label set in config, e.g. liquidity, credit, regulatory, cyber, macro, competition, operations, legal, other. Confirm the list with Hugo before coding.
- Jev tagging runs in batches. Store topic, tone, and their confidences.
- Store embeddings in pgvector along with the metadata columns.
- **Done when:** all paragraphs are tagged and embedded (mock or real Jev), and a SQL query can filter by company, year, and topic.

### Phase 3: Retrieve + answer + guard (Days 7–9)
- Retrieval: top-k vector search, with optional metadata filters.
- Jev relevance filter (Noul per chunk). **Keep low-confidence chunks** rather than dropping them. Log which chunks were kept and why.
- LLM answer that must cite paragraph IDs.
- Numeric check: pull numbers out of the answer and confirm each one appears in the cited paragraphs. Flag any mismatch.
- Groundedness gate (Jev Noul). Below the threshold, the system abstains or shows the answer with a warning.
- The threshold lives in a config file so Project 2 can replace it later.
- FastAPI endpoint `POST /ask`.
- **Done when:** `/ask` returns an answer with citations, a groundedness verdict, and timing.

### Phase 4: Evaluate (Days 10–12)
- Claude drafts about 30 candidate questions with gold paragraph IDs. **Hugo reviews and keeps about 20.** Only human-approved items count as gold.
- Also build a set of deliberately *unsupported* answers to test the gate.
- Metrics: recall@k with and without the Jev filter, the gate's precision and recall on unsupported answers, abstention rate, p50/p95 latency, and cost per query.
- Export the paragraph tags as `exports/paragraph_labels.jsonl`. Project 2 uses this file.
- **Done when:** `scripts/run_eval.py` prints a metrics table and saves `eval/results.json`.

### Phase 5: Demo + README (Days 13–14)
- A Streamlit page: ask a question and see the answer, citations, verdict, and which chunks were kept or dropped.
- README: a 3-sentence pitch, an architecture diagram (Mermaid), the results table from real runs only, how to run it, and known limitations, including where Jev is weak.
- **Done when:** a fresh clone runs following only the README.

---

## Metrics to record (for the resume)
recall@k (with and without the filter) · gate precision/recall · abstention rate · p50/p95 latency · cost per query · number of paragraphs tagged

## Decisions log
<!-- Append: date · decision · why · alternatives considered -->
- 2026-09-28 · Pinned the project to Python 3.12 via `uv python install 3.12` + `.python-version`, even though the machine's system Python is 3.14.4 · matches this file's tech-stack spec exactly and keeps the dev environment reproducible · alternative considered: target 3.14 system Python (rejected, spec explicitly says 3.12).
- 2026-09-28 · Default `ANTHROPIC_MODEL` in `.env.example` set to `claude-haiku-4-5-20251001` · Hugo confirmed a cheap/small default is fine to start; Haiku keeps per-paragraph and per-query cost low for a project with a "code checks the numbers" verification step anyway · alternative: Sonnet by default (more capable, costs more; can be swapped later since the model name lives in config).
- 2026-09-28 · `DecisionClient`/`MockDecisionClient` live as flat modules (`decision.py`, `decision_mock.py`) rather than a `decision/` subpackage · CLAUDE.md's Phase 0 repo layout only lists `{ingest,tagging,retrieval,answer,eval}` as subpackages; the decision interface is a small, cross-cutting dependency of several of them, not a phase of its own · alternative: a `decision/` package (rejected as unnecessary structure for two small files).
- 2026-09-29 · MVP list changed from the originally proposed AAPL/MSFT/JPM/XOM/PFE/WMT to AAPL/MSFT/V/KO/PFE/WMT · found live during Phase 1: (1) XOM's ticker was reassigned to a newly formed `ExxonMobil Holdings Corp` CIK in mid-2026 that hasn't filed a 10-K yet, so the old ticker can't be resolved to any recent filing; (2) both JPM and Chevron (the first XOM replacement tried) structure Item 7 as a one-line pointer ("MD&A appears on pages 46–160 of this report") into a differently-headed "wrap" section rather than inline text, which our label-based extractor can't follow · alternative considered: teach the extractor to resolve page-number cross-references into the wrap section (rejected — disproportionate effort to special-case 1–2 filers in a 6-company MVP; documented as a known limitation instead of built around).
- 2026-09-29 · Section boundaries are found by pairing every "Item 1A" candidate with its nearest following "Item 1B"/"Item 1C" candidate and keeping the pair with the *largest* gap between them, rather than "last occurrence before the body, first after" · found live during Phase 1: Microsoft repeats the bare item label as a running page header throughout the section body (not just once in the table of contents), which broke a simple last/first-occurrence rule; the real section is always separated from the next by far more body text than any repeated bare labels are from each other, regardless of how many times they repeat · alternative: filter candidates by heading length instead (tried first, rejected — Walmart and Pfizer split a heading's title into a separate tag from its "Item N." label, so the label alone is too short to distinguish from a repeated header).
- 2026-09-29 · When a heading's title lands in its own block, separate from the "Item N" label, up to 2 leading blocks are dropped from the section if they don't end in terminal punctuation, before the length-based paragraph filter runs · found live during Phase 1: a split-off title (e.g. "Management's Discussion and Analysis of Financial Condition and Results of Operations") is long enough to survive the 40-character paragraph filter, so without this it silently became a fake first "paragraph" for Microsoft, Pfizer, and Walmart · alternative: hardcode the expected title string per item (rejected — fragile against filer-specific wording).
- 2026-09-29 · Topic label set is the CLAUDE.md base 9 plus `supply_chain` and `labor` (11 total), defined in `config/topics.yaml` · Hugo confirmed; Apple/Walmart lean heavily on supply-chain risk language and Walmart/Coca-Cola on workforce risk, which would otherwise all get flattened into the generic `operations` label · alternative: the base 9 only (rejected as less precise for this specific company mix).
- 2026-09-29 · Tone is a single 0–1 "how negative/alarming" score from Jev's `score()`, not a signed sentiment scale · risk-factor and MD&A language is almost never positive, so a signed scale would waste range; 0–1 severity is simpler to threshold on later (e.g. flagging paragraphs above 0.8) · alternative: -1 (positive) to +1 (negative) (rejected as added complexity with no expected use for the positive half).
- 2026-09-29 · `paragraph_index` (not `index`) is the Postgres column name for a paragraph's position within its section · `INDEX` reads awkwardly next to Postgres's own `CREATE INDEX`, even though it isn't a reserved word · alternative: quote `"index"` everywhere (rejected — easy to forget a quote and get a confusing error).

## Progress log
<!-- Claude appends one entry per checkpoint: date · phase · summary · test status · open issues -->
- 2026-09-28 · Phase 0: Scaffold · Set up the `uv`-managed project (Python 3.12), `src/report_qa/{ingest,tagging,retrieval,answer,eval}` package skeleton, `docker-compose.yml` (Postgres 16 + pgvector), `.env.example`, `.gitignore`, the `DecisionClient` protocol, and a deterministic `MockDecisionClient`. · Tests: `pytest` 6/6 passing, `ruff check` and `ruff format --check` clean. · Open issues: Docker isn't installed on this dev machine, so `docker compose up` itself hasn't been run/verified yet — Hugo to install Docker Desktop and confirm the DB starts. MVP ticker/year list still to be chosen before Phase 1.
- 2026-09-29 · Phase 1: Ingest · Built the EDGAR client (`ingest/edgar.py`: ticker → CIK → recent 10-Ks → cached document download, rate-limited to ~3 req/s with a declared User-Agent), the Item 1A/Item 7 section extractor (`ingest/sections.py`, see Decisions log for the heuristics), and the pipeline + CLI (`ingest/pipeline.py`, `scripts/ingest.py`). Ran it end-to-end against live EDGAR for all 6 MVP companies (AAPL, MSFT, V, KO, PFE, WMT), 2 filings each. · Tests: `pytest` 13/13 passing (including a synthetic fixture in `tests/fixtures/sample_10k.html` that exercises the TOC/running-header/split-title edge cases found in real filings), `ruff check` and `ruff format --check` clean. · Result: 3,246 paragraphs written to `data/processed/paragraphs.jsonl` from 12 filings; per-filing counts ranged from 89–546 risk-factors paragraphs and 48–319 MD&A paragraphs, all manually spot-checked as real prose. · Open issues: none blocking. Known limitation for later (README): filers that structure Item 7 as a page-number pointer into a separate "wrap" section (seen in JPM, Chevron) aren't handled and were avoided rather than parsed.
- 2026-09-29 · Phase 2: Tag + embed · Started the Postgres+pgvector container (`docker compose up -d`, confirmed healthy). Built the 11-label topic config (`config/topics.yaml`), the tagger (`tagging/tagger.py`, using `MockDecisionClient`'s `choice`/`score` only), the embedder (`tagging/embeddings.py`, local `all-MiniLM-L6-v2`, 384 dims), the Postgres schema and upsert layer (`db.py`), and the CLI (`scripts/tag_and_embed.py`). Ran it end-to-end: all 3,246 Phase 1 paragraphs tagged and embedded, stored in Postgres. · Tests: `pytest` 18/18 passing (tagger tests use `MockDecisionClient` only, no live DB or model download needed — matches the Phase 0 bar), `ruff check` and `ruff format --check` clean. · Verified done-criteria: `SELECT ticker, fiscal_year, topic, COUNT(*), AVG(tone) FROM paragraphs WHERE ticker='AAPL' AND fiscal_year=2025 ... GROUP BY topic` returns sane per-topic counts and tone averages; all 11 topics and all 6 tickers appear in the table (3,246 rows, `vector_dims(embedding) = 384`). · Open issues: none blocking. Tags are from `MockDecisionClient`, not real Jev — re-tag once Hugo shares Jev docs/API key.
