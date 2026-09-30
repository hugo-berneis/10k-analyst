"""Top-k vector similarity search over tagged, embedded paragraphs.

Note: `conn` must have pgvector's type registered (`db.init_schema` does
this), otherwise passing a Python list as the query embedding will fail to
adapt to the `vector` column type.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg
from pgvector import Vector

from report_qa.tagging.embeddings import Embedder

# Only these columns can be filtered on; values are always parameterized,
# so this allowlist just fixes which WHERE clauses can ever be built.
_FILTER_COLUMNS = ("ticker", "fiscal_year", "topic", "section")


@dataclass(frozen=True)
class RetrievedParagraph:
    paragraph_id: str
    ticker: str
    fiscal_year: int
    section: str
    text: str
    topic: str
    tone: float
    distance: float  # cosine distance to the query; lower is more similar


def search(
    conn: psycopg.Connection,
    embedder: Embedder,
    question: str,
    top_k: int,
    ticker: str | None = None,
    fiscal_year: int | None = None,
    topic: str | None = None,
    section: str | None = None,
) -> list[RetrievedParagraph]:
    [query_embedding] = embedder.embed([question])
    query_vector = Vector(query_embedding)
    filters = {"ticker": ticker, "fiscal_year": fiscal_year, "topic": topic, "section": section}
    active_filters = {k: v for k, v in filters.items() if v is not None}

    where_sql = ""
    if active_filters:
        clauses = [f"{column} = %({column})s" for column in active_filters]
        where_sql = f"WHERE {' AND '.join(clauses)}"

    sql = f"""
        SELECT paragraph_id, ticker, fiscal_year, section, text, topic, tone,
               embedding <=> %(query_embedding)s AS distance
        FROM paragraphs
        {where_sql}
        ORDER BY embedding <=> %(query_embedding)s
        LIMIT %(top_k)s
    """

    with conn.cursor() as cur:
        cur.execute(sql, {**active_filters, "query_embedding": query_vector, "top_k": top_k})
        rows = cur.fetchall()

    return [
        RetrievedParagraph(
            paragraph_id=row[0],
            ticker=row[1],
            fiscal_year=row[2],
            section=row[3],
            text=row[4],
            topic=row[5],
            tone=row[6],
            distance=row[7],
        )
        for row in rows
    ]
