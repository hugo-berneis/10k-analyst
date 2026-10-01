#!/usr/bin/env python3
"""Tags and embeds `data/processed/paragraphs.jsonl`, then stores it in Postgres.

Uses real Jev if `JEV_API_KEY` is set, otherwise `MockDecisionClient`
(see `report_qa.decision.get_decision_client`).

Usage:
    uv run scripts/tag_and_embed.py
    uv run scripts/tag_and_embed.py --input data/processed/paragraphs.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from report_qa.config import get_settings
from report_qa.db import TaggedParagraphRow, connect, init_schema, upsert_paragraphs
from report_qa.decision import get_decision_client
from report_qa.ingest.sections import Paragraph
from report_qa.tagging.embeddings import Embedder
from report_qa.tagging.tagger import tag_paragraphs
from report_qa.tagging.topics import load_topics

DEFAULT_INPUT_PATH = Path("data/processed/paragraphs.jsonl")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    return parser.parse_args()


def read_paragraphs(path: Path) -> list[Paragraph]:
    paragraphs = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            paragraphs.append(
                Paragraph(
                    paragraph_id=record["paragraph_id"],
                    ticker=record["ticker"],
                    fiscal_year=record["fiscal_year"],
                    section=record["section"],
                    index=record["index"],
                    text=record["text"],
                )
            )
    return paragraphs


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args()
    settings = get_settings()

    paragraphs = read_paragraphs(args.input)
    topics = load_topics()
    print(f"Loaded {len(paragraphs)} paragraphs, {len(topics)} topic labels")

    client = get_decision_client(settings)
    tagged = tag_paragraphs(client, paragraphs, topics)
    if len(tagged) < len(paragraphs):
        print(f"Warning: {len(paragraphs) - len(tagged)} paragraphs failed to tag and were skipped")

    embedder = Embedder(settings.embedding_model)
    embeddings = embedder.embed([p.text for p, _ in tagged])

    rows = [
        TaggedParagraphRow(
            paragraph_id=p.paragraph_id,
            ticker=p.ticker,
            fiscal_year=p.fiscal_year,
            section=p.section,
            paragraph_index=p.index,
            text=p.text,
            char_count=p.char_count,
            topic=tag.topic,
            topic_confidence=tag.topic_confidence,
            tone=tag.tone,
            tone_confidence=tag.tone_confidence,
            embedding=embedding,
        )
        for (p, tag), embedding in zip(tagged, embeddings, strict=True)
    ]

    conn = connect(settings.database_url)
    init_schema(conn)
    upsert_paragraphs(conn, rows)
    conn.close()

    print(f"Stored {len(rows)} tagged, embedded paragraphs in Postgres")


if __name__ == "__main__":
    main()
