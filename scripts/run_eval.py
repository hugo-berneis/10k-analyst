#!/usr/bin/env python3
"""Runs the Phase 4 evaluation: gold questions + deliberately-unsupported answers.

Metrics (per CLAUDE.md): recall@5 with/without the Jev relevance filter, the
groundedness gate's precision/recall on unsupported answers, abstention rate,
p50/p95 latency, and cost per query. Prints a table and saves
`eval/results.json`.

Only `eval/gold_questions.yaml` (Hugo-approved) counts as gold -- see
`eval/candidate_questions.yaml` for the full draft set Claude proposed.

Usage:
    uv run scripts/run_eval.py
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import yaml

from report_qa.answer.citations import extract_cited_ids, resolve_citations
from report_qa.answer.groundedness import Verdict, check_groundedness
from report_qa.answer.llm import AnswerLLM
from report_qa.answer.numeric_check import find_unsupported_numbers
from report_qa.answer.pipeline import ask
from report_qa.config import get_settings
from report_qa.db import connect, init_schema
from report_qa.decision import get_decision_client
from report_qa.retrieval.relevance import filter_relevance
from report_qa.retrieval.search import RetrievedParagraph, search
from report_qa.tagging.embeddings import Embedder
from report_qa.thresholds import load_thresholds

GOLD_QUESTIONS_PATH = Path("eval/gold_questions.yaml")
UNSUPPORTED_FIXTURES_PATH = Path("eval/unsupported_answer_fixtures.yaml")
RESULTS_PATH = Path("eval/results.json")
RECALL_K = 5

# Confirmed 2026-06-04 via the claude-api skill's cached pricing table.
HAIKU_PRICE_PER_MTOK = {"input": 1.00, "output": 5.00}


def load_yaml(path: Path) -> list[dict]:
    return yaml.safe_load(path.read_text())


def fetch_paragraphs_by_id(conn, paragraph_ids: list[str]) -> dict[str, RetrievedParagraph]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT paragraph_id, ticker, fiscal_year, section, text, topic, tone
            FROM paragraphs WHERE paragraph_id = ANY(%s)
            """,
            (paragraph_ids,),
        )
        rows = cur.fetchall()
    return {
        row[0]: RetrievedParagraph(
            paragraph_id=row[0],
            ticker=row[1],
            fiscal_year=row[2],
            section=row[3],
            text=row[4],
            topic=row[5],
            tone=row[6],
            distance=0.0,
        )
        for row in rows
    }


def evaluate_gold_questions(conn, embedder, client, llm, thresholds, gold_questions: list[dict]):
    records = []
    for item in gold_questions:
        gold_ids = set(item["gold_paragraph_ids"])

        top5 = search(
            conn,
            embedder,
            item["question"],
            top_k=RECALL_K,
            ticker=item["ticker"],
            fiscal_year=item["fiscal_year"],
        )
        top5_ids = {p.paragraph_id for p in top5}
        relevance = filter_relevance(
            client, item["question"], top5, thresholds.relevance_drop_confidence
        )
        kept_ids = {r.paragraph.paragraph_id for r in relevance if r.kept}

        result = ask(
            conn,
            embedder,
            client,
            llm,
            thresholds,
            item["question"],
            ticker=item["ticker"],
            fiscal_year=item["fiscal_year"],
        )
        usage = llm.last_usage
        cost = (
            usage.input_tokens / 1e6 * HAIKU_PRICE_PER_MTOK["input"]
            + usage.output_tokens / 1e6 * HAIKU_PRICE_PER_MTOK["output"]
            if usage
            else None
        )

        records.append(
            {
                "id": item["id"],
                "question": item["question"],
                "recalled_at_5_without_filter": bool(gold_ids & top5_ids),
                "recalled_at_5_with_filter": bool(gold_ids & kept_ids),
                "verdict": result.verdict.value,
                "citations": result.citations,
                "total_ms": result.total_ms,
                "cost_usd": cost,
            }
        )
    return records


def evaluate_unsupported_fixtures(conn, client, thresholds, fixtures: list[dict]):
    all_ids = [pid for fixture in fixtures for pid in fixture["context_paragraph_ids"]]
    paragraphs_by_id = fetch_paragraphs_by_id(conn, all_ids)

    records = []
    for fixture in fixtures:
        context = [paragraphs_by_id[pid] for pid in fixture["context_paragraph_ids"]]
        cited_ids = extract_cited_ids(fixture["fake_answer"])
        cited_paragraphs, unknown_citations = resolve_citations(cited_ids, context)
        cited_text = " ".join(p.text for p in cited_paragraphs)
        unsupported_numbers = find_unsupported_numbers(fixture["fake_answer"], cited_text)

        groundedness = check_groundedness(
            client,
            fixture["fake_answer"],
            cited_text,
            unsupported_numbers,
            unknown_citations,
            thresholds.groundedness_threshold,
        )
        records.append(
            {
                "id": fixture["id"],
                "category": fixture["category"],
                "verdict": groundedness.verdict.value,
                "caught": groundedness.verdict != Verdict.CONFIDENT,
            }
        )
    return records


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(pct * (len(ordered) - 1))))
    return ordered[index]


def summarize(
    gold_records: list[dict], fixture_records: list[dict], paragraphs_tagged: int
) -> dict:
    n_gold = len(gold_records)
    recall_without_filter = sum(r["recalled_at_5_without_filter"] for r in gold_records) / n_gold
    recall_with_filter = sum(r["recalled_at_5_with_filter"] for r in gold_records) / n_gold
    abstention_rate = sum(r["verdict"] == "abstained" for r in gold_records) / n_gold

    latencies = [r["total_ms"] for r in gold_records]
    costs = [r["cost_usd"] for r in gold_records if r["cost_usd"] is not None]

    code_verifiable = [r for r in fixture_records if r["category"] != "unsupported_claim"]
    semantic_only = [r for r in fixture_records if r["category"] == "unsupported_claim"]
    false_positives = sum(r["verdict"] != "confident" for r in gold_records)
    true_positives = sum(r["caught"] for r in fixture_records)

    return {
        "n_gold_questions": n_gold,
        "n_unsupported_fixtures": len(fixture_records),
        "paragraphs_tagged": paragraphs_tagged,
        f"recall_at_{RECALL_K}_without_filter": round(recall_without_filter, 3),
        f"recall_at_{RECALL_K}_with_filter": round(recall_with_filter, 3),
        "gate_recall_code_verifiable": round(
            sum(r["caught"] for r in code_verifiable) / len(code_verifiable), 3
        )
        if code_verifiable
        else None,
        "gate_recall_semantic": round(
            sum(r["caught"] for r in semantic_only) / len(semantic_only), 3
        )
        if semantic_only
        else None,
        "gate_precision": round(true_positives / (true_positives + false_positives), 3)
        if (true_positives + false_positives)
        else None,
        "abstention_rate": round(abstention_rate, 3),
        "p50_latency_ms": round(percentile(latencies, 0.5), 1),
        "p95_latency_ms": round(percentile(latencies, 0.95), 1),
        "avg_cost_per_query_usd": round(statistics.mean(costs), 6) if costs else None,
    }


def print_table(summary: dict, *, using_mock: bool) -> None:
    print("\n=== Phase 4 Evaluation ===")
    for key, value in summary.items():
        print(f"{key:45s} {value}")
    print()
    if using_mock:
        print("Note: gate_recall_semantic is not meaningful yet -- it reflects")
        print("MockDecisionClient's arbitrary judgments, not real semantic")
        print("groundedness checking. Set JEV_API_KEY and re-run for real numbers.")
    else:
        print("Note: run against real Jev -- all metrics reflect real judgments.")


def main() -> None:
    settings = get_settings()
    conn = connect(settings.database_url)
    init_schema(conn)
    embedder = Embedder(settings.embedding_model)
    client = get_decision_client(settings)
    llm = AnswerLLM(settings.anthropic_api_key, settings.anthropic_model)
    thresholds = load_thresholds()

    gold_questions = load_yaml(GOLD_QUESTIONS_PATH)
    fixtures = load_yaml(UNSUPPORTED_FIXTURES_PATH)

    print(f"Running {len(gold_questions)} gold questions through the real pipeline...")
    gold_records = evaluate_gold_questions(conn, embedder, client, llm, thresholds, gold_questions)

    print(f"Running {len(fixtures)} unsupported-answer fixtures through the gate...")
    fixture_records = evaluate_unsupported_fixtures(conn, client, thresholds, fixtures)

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM paragraphs")
        paragraphs_tagged = cur.fetchone()[0]

    summary = summarize(gold_records, fixture_records, paragraphs_tagged)
    print_table(summary, using_mock=not settings.jev_api_key)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(
        json.dumps(
            {
                "summary": summary,
                "gold_questions": gold_records,
                "unsupported_fixtures": fixture_records,
            },
            indent=2,
        )
    )
    print(f"Saved {RESULTS_PATH}")


if __name__ == "__main__":
    main()
