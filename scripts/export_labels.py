#!/usr/bin/env python3
"""Exports paragraph tags to `exports/paragraph_labels.jsonl` for Project 2.

Usage:
    uv run scripts/export_labels.py
"""

from __future__ import annotations

import json
from pathlib import Path

from report_qa.config import get_settings
from report_qa.db import connect, init_schema

OUTPUT_PATH = Path("exports/paragraph_labels.jsonl")

COLUMNS = (
    "paragraph_id",
    "ticker",
    "fiscal_year",
    "section",
    "paragraph_index",
    "topic",
    "topic_confidence",
    "tone",
    "tone_confidence",
)


def main() -> None:
    settings = get_settings()
    conn = connect(settings.database_url)
    init_schema(conn)

    with conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(COLUMNS)} FROM paragraphs ORDER BY paragraph_id")
        rows = cur.fetchall()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(dict(zip(COLUMNS, row, strict=True))) + "\n")

    print(f"Wrote {len(rows)} paragraph labels to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
