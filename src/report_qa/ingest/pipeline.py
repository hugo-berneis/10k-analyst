"""Orchestrates: company list -> EDGAR filings -> tagged paragraphs -> JSONL."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from report_qa.ingest.companies import CompanyConfig
from report_qa.ingest.edgar import EdgarClient
from report_qa.ingest.sections import Paragraph, SectionNotFoundError, extract_paragraphs

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = Path("data/processed/paragraphs.jsonl")


def ingest_company(client: EdgarClient, ticker: str, filings_per_company: int) -> list[Paragraph]:
    """Fetch and extract paragraphs for one company's most recent 10-Ks."""
    cik = client.get_cik(ticker)
    filings = client.list_10k_filings(ticker, cik, limit=filings_per_company)
    paragraphs: list[Paragraph] = []
    for filing in filings:
        path = client.download_filing(filing)
        html = path.read_text(encoding="utf-8", errors="replace")
        try:
            filing_paragraphs = extract_paragraphs(html, ticker, filing.fiscal_year)
        except SectionNotFoundError:
            logger.warning(
                "Skipping %s FY%s (%s): could not locate Item 1A/Item 7 headings",
                ticker,
                filing.fiscal_year,
                filing.accession_number,
            )
            continue
        logger.info(
            "%s FY%s: %d risk_factors, %d mdna paragraphs",
            ticker,
            filing.fiscal_year,
            sum(1 for p in filing_paragraphs if p.section == "risk_factors"),
            sum(1 for p in filing_paragraphs if p.section == "mdna"),
        )
        paragraphs.extend(filing_paragraphs)
    return paragraphs


def ingest_all(client: EdgarClient, config: CompanyConfig) -> list[Paragraph]:
    all_paragraphs: list[Paragraph] = []
    for ticker in config.tickers:
        all_paragraphs.extend(ingest_company(client, ticker, config.filings_per_company))
    return all_paragraphs


def write_jsonl(paragraphs: list[Paragraph], path: Path = DEFAULT_OUTPUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for paragraph in paragraphs:
            record = asdict(paragraph)
            record["char_count"] = paragraph.char_count
            f.write(json.dumps(record) + "\n")
