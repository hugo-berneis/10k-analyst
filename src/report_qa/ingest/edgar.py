"""Thin client for SEC EDGAR: ticker -> CIK -> recent 10-K filings -> document.

Everything goes through `_get`, which attaches the declared `User-Agent` SEC
requires (https://www.sec.gov/os/webmaster-faq#developers) and rate-limits
requests. Every response that matters for reproducibility is cached to disk,
so re-running ingestion doesn't hit EDGAR again for filings we already have.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

TICKER_INDEX_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
DOCUMENT_URL = "https://www.sec.gov/Archives/edgar/data/{cik_short}/{accession_nodash}/{document}"

FORM_10K = "10-K"


@dataclass(frozen=True)
class FilingRef:
    """Enough to locate and label one 10-K filing."""

    ticker: str
    cik: str
    accession_number: str
    filing_date: str
    report_date: str
    primary_document: str

    @property
    def fiscal_year(self) -> int:
        return int(self.report_date[:4])

    @property
    def accession_nodash(self) -> str:
        return self.accession_number.replace("-", "")


class EdgarClient:
    def __init__(
        self,
        user_agent: str,
        cache_dir: Path = Path("data"),
        min_interval_seconds: float = 0.3,
        sleep_fn=time.sleep,
    ) -> None:
        if not user_agent:
            raise ValueError("SEC requires a declared User-Agent, e.g. 'app-name you@example.com'")
        self._headers = {"User-Agent": user_agent}
        self._cache_dir = Path(cache_dir)
        self._min_interval = min_interval_seconds
        self._sleep_fn = sleep_fn
        self._last_request_at: float | None = None
        self._client = httpx.Client(headers=self._headers, timeout=30.0)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> EdgarClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _get(self, url: str) -> httpx.Response:
        if self._last_request_at is not None:
            elapsed = time.monotonic() - self._last_request_at
            remaining = self._min_interval - elapsed
            if remaining > 0:
                self._sleep_fn(remaining)
        response = self._client.get(url)
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        return response

    def _cached_json(self, cache_path: Path, url: str) -> dict:
        if cache_path.exists():
            return json.loads(cache_path.read_text())
        data = self._get(url).json()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data))
        return data

    def get_cik(self, ticker: str) -> str:
        """Look up the zero-padded 10-digit CIK for a ticker."""
        index = self._cached_json(
            self._cache_dir / "cache" / "company_tickers.json", TICKER_INDEX_URL
        )
        ticker = ticker.upper()
        for entry in index.values():
            if entry["ticker"].upper() == ticker:
                return f"{entry['cik_str']:010d}"
        raise ValueError(f"Ticker {ticker!r} not found in SEC's company_tickers.json")

    def list_10k_filings(self, ticker: str, cik: str, limit: int) -> list[FilingRef]:
        """Most recent `limit` 10-K filings for a company, newest first."""
        submissions = self._cached_json(
            self._cache_dir / "cache" / "submissions" / f"{cik}.json",
            SUBMISSIONS_URL.format(cik=cik),
        )
        recent = submissions["filings"]["recent"]
        filings = []
        for form, accession, filed, reported, document in zip(
            recent["form"],
            recent["accessionNumber"],
            recent["filingDate"],
            recent["reportDate"],
            recent["primaryDocument"],
            strict=True,
        ):
            if form == FORM_10K:
                filings.append(
                    FilingRef(
                        ticker=ticker,
                        cik=cik,
                        accession_number=accession,
                        filing_date=filed,
                        report_date=reported,
                        primary_document=document,
                    )
                )
        return filings[:limit]

    def download_filing(self, filing: FilingRef) -> Path:
        """Fetch a filing's primary document, using the on-disk cache if present."""
        cache_path = (
            self._cache_dir
            / "raw"
            / filing.ticker
            / f"{filing.accession_number}_{filing.primary_document}"
        )
        if cache_path.exists():
            return cache_path
        cik_short = str(int(filing.cik))
        url = DOCUMENT_URL.format(
            cik_short=cik_short,
            accession_nodash=filing.accession_nodash,
            document=filing.primary_document,
        )
        response = self._get(url)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(response.content)
        return cache_path
