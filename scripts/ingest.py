#!/usr/bin/env python3
"""Ingests the configured companies' 10-Ks into `data/processed/paragraphs.jsonl`.

Usage:
    uv run scripts/ingest.py
    uv run scripts/ingest.py --tickers AAPL --filings-per-company 1
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from report_qa.config import get_settings
from report_qa.ingest.companies import DEFAULT_CONFIG_PATH, CompanyConfig, load_company_config
from report_qa.ingest.edgar import EdgarClient
from report_qa.ingest.pipeline import DEFAULT_OUTPUT_PATH, ingest_all, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tickers",
        nargs="+",
        help="Override the tickers in config/companies.yaml (e.g. --tickers AAPL MSFT)",
    )
    parser.add_argument(
        "--filings-per-company",
        type=int,
        help="Override how many recent 10-Ks to fetch per company",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args()
    settings = get_settings()

    config = load_company_config(DEFAULT_CONFIG_PATH)
    if args.tickers:
        config = CompanyConfig(
            tickers=[t.upper() for t in args.tickers],
            filings_per_company=config.filings_per_company,
        )
    if args.filings_per_company:
        config = CompanyConfig(tickers=config.tickers, filings_per_company=args.filings_per_company)

    with EdgarClient(user_agent=settings.sec_user_agent) as client:
        paragraphs = ingest_all(client, config)

    write_jsonl(paragraphs, args.output)
    print(
        f"Wrote {len(paragraphs)} paragraphs from {len(config.tickers)} companies to {args.output}"
    )


if __name__ == "__main__":
    main()
