from __future__ import annotations

import io
import re
from typing import BinaryIO

import pandas as pd

from .models import DatasetType


COLUMN_ALIASES = {
    "url": ["url", "page", "target url", "target", "landing page", "page url"],
    "source_url": ["source url", "referring page", "referring page url", "backlink url"],
    "keyword": ["keyword", "query", "search query"],
    "position": ["position", "current position", "rank", "ranking position"],
    "previous_position": ["previous position", "prev position", "old position"],
    "impressions": ["impressions", "search volume", "volume"],
    "clicks": ["clicks"],
    "ctr": ["ctr", "click through rate", "click-through rate"],
    "traffic": ["traffic", "organic traffic", "current traffic"],
    "previous_traffic": ["previous traffic", "traffic previous", "prev traffic"],
    "competitor": ["competitor", "competitor domain", "competing domain", "domain", "site", "root domain"],
    "common_keywords": ["common keywords", "common keyword", "intersecting keywords"],
    "unique_keywords": ["unique keywords", "unique keyword", "competitor unique keywords"],
    "organic_pages": ["organic pages", "pages"],
    "status": ["status", "http status", "link status"],
}


def parse_csv(file: BinaryIO) -> pd.DataFrame:
    content = file.read()
    if not content:
        raise ValueError("Uploaded file is empty.")

    df = _read_csv_with_fallback_encodings(content)
    if df.empty:
        raise ValueError("CSV has no rows.")

    df = df.rename(columns={col: _normalize_column(col) for col in df.columns})
    df = _apply_aliases(df)
    df = df.dropna(how="all").reset_index(drop=True)
    return df


def validate_dataset(dataset_type: DatasetType, df: pd.DataFrame) -> None:
    required = {
        "organic_keywords": {"keyword"},
        "top_pages": {"url"},
        "backlinks": set(),
        "broken_backlinks": set(),
        "competitors": set(),
    }

    missing = required[dataset_type] - set(df.columns)
    if missing:
        raise ValueError(
            f"{dataset_type} CSV is missing required columns: {', '.join(sorted(missing))}"
        )

    if dataset_type == "competitors" and not {"keyword", "competitor"}.intersection(df.columns):
        raise ValueError(
            "competitors CSV needs either a keyword column for content-gap exports or a "
            "competitor/domain column for Ahrefs Organic competitors exports."
        )


def _read_csv_with_fallback_encodings(content: bytes) -> pd.DataFrame:
    encodings = ["utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "cp1252", "latin1"]
    separators: list[str | None] = [None, ",", "\t", ";"]
    last_error: Exception | None = None

    for encoding in encodings:
        for separator in separators:
            try:
                kwargs = {"encoding": encoding}
                if separator is None:
                    kwargs.update({"sep": None, "engine": "python"})
                else:
                    kwargs.update({"sep": separator})

                df = pd.read_csv(io.BytesIO(content), **kwargs)
                if len(df.columns) == 1 and _looks_like_split_needed(df.columns[0]):
                    continue
                return df
            except (UnicodeError, pd.errors.ParserError, ValueError) as exc:
                last_error = exc

    raise ValueError(
        "Could not read CSV. UTF-16, UTF-8, tab, comma, and semicolon parsing all failed. "
        "Please check that the file is a text CSV/TSV export and not an Excel workbook."
    ) from last_error


def _looks_like_split_needed(column_name: str) -> bool:
    return any(separator in str(column_name) for separator in [",", "\t", ";"])


def _normalize_column(column: str) -> str:
    normalized = column.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


def _apply_aliases(df: pd.DataFrame) -> pd.DataFrame:
    reverse_aliases = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            reverse_aliases[_normalize_column(alias)] = canonical

    rename_map = {}
    for column in df.columns:
        canonical = reverse_aliases.get(column)
        if canonical and canonical not in df.columns:
            rename_map[column] = canonical

    return df.rename(columns=rename_map)


def to_number(series: pd.Series, default: float = 0) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(default)
