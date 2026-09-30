"""Postgres + pgvector storage for tagged, embedded paragraphs."""

from __future__ import annotations

from dataclasses import dataclass

import psycopg
from pgvector.psycopg import register_vector

from report_qa.tagging.embeddings import EMBEDDING_DIM

SCHEMA_SQL = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS paragraphs (
    paragraph_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    section TEXT NOT NULL,
    paragraph_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    topic TEXT NOT NULL,
    topic_confidence REAL NOT NULL,
    tone REAL NOT NULL,
    tone_confidence REAL NOT NULL,
    embedding VECTOR({EMBEDDING_DIM}) NOT NULL
);

CREATE INDEX IF NOT EXISTS paragraphs_ticker_year_topic_idx
    ON paragraphs (ticker, fiscal_year, topic);
"""

UPSERT_SQL = """
INSERT INTO paragraphs (
    paragraph_id, ticker, fiscal_year, section, paragraph_index,
    text, char_count, topic, topic_confidence, tone, tone_confidence, embedding
) VALUES (
    %(paragraph_id)s, %(ticker)s, %(fiscal_year)s, %(section)s, %(paragraph_index)s,
    %(text)s, %(char_count)s, %(topic)s, %(topic_confidence)s, %(tone)s,
    %(tone_confidence)s, %(embedding)s
)
ON CONFLICT (paragraph_id) DO UPDATE SET
    topic = EXCLUDED.topic,
    topic_confidence = EXCLUDED.topic_confidence,
    tone = EXCLUDED.tone,
    tone_confidence = EXCLUDED.tone_confidence,
    embedding = EXCLUDED.embedding;
"""


@dataclass(frozen=True)
class TaggedParagraphRow:
    paragraph_id: str
    ticker: str
    fiscal_year: int
    section: str
    paragraph_index: int
    text: str
    char_count: int
    topic: str
    topic_confidence: float
    tone: float
    tone_confidence: float
    embedding: list[float]


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url, autocommit=True)


def init_schema(conn: psycopg.Connection) -> None:
    """Create the `vector` extension and the paragraphs table if missing.

    Registers pgvector's type adapter on `conn` afterwards -- it can't be
    registered before the extension exists.
    """
    conn.execute(SCHEMA_SQL)
    register_vector(conn)


def upsert_paragraphs(conn: psycopg.Connection, rows: list[TaggedParagraphRow]) -> None:
    with conn.cursor() as cur:
        cur.executemany(UPSERT_SQL, [vars(row) for row in rows])
