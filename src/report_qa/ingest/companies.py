"""Loads the MVP ticker list from `config/companies.yaml`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "companies.yaml"


@dataclass(frozen=True)
class CompanyConfig:
    tickers: list[str]
    filings_per_company: int


def load_company_config(path: Path = DEFAULT_CONFIG_PATH) -> CompanyConfig:
    raw = yaml.safe_load(path.read_text())
    return CompanyConfig(
        tickers=[ticker.upper() for ticker in raw["tickers"]],
        filings_per_company=int(raw["filings_per_company"]),
    )
