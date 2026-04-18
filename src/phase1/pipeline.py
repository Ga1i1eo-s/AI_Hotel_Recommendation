from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from datasets import load_dataset
from sqlalchemy import create_engine


DATASET_ID = "ManikaSaini/zomato-restaurant-recommendation"
TARGET_TABLE = "restaurants"


@dataclass
class IngestionConfig:
    data_dir: Path = Path("data")
    report_dir: Path = Path("reports")
    sqlite_path: Path = Path("data/catalog.db")
    dataset_id: str = DATASET_ID


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _normalize_cuisine(value: Any) -> list[str]:
    text = _normalize_text(value).lower()
    if not text:
        return []
    parts = re.split(r"[,/|]", text)
    cuisines = []
    seen = set()
    for part in parts:
        item = part.strip()
        if item and item not in seen:
            seen.add(item)
            cuisines.append(item.title())
    return cuisines


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    match = re.search(r"\d+(\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    if number is None:
        return None
    return int(number)


def _budget_band(avg_cost_for_two: float | None) -> str | None:
    if avg_cost_for_two is None:
        return None
    if avg_cost_for_two <= 800:
        return "low"
    if avg_cost_for_two <= 2000:
        return "medium"
    return "high"


def _match_first_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lookup = {column.lower(): column for column in df.columns}
    for candidate in candidates:
        if candidate.lower() in lookup:
            return lookup[candidate.lower()]
    return None


def _extract_from_columns(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    column = _match_first_column(df, candidates)
    if column is None:
        return pd.Series([None] * len(df))
    return df[column]


def load_source_dataset(dataset_id: str) -> pd.DataFrame:
    dataset = load_dataset(dataset_id)
    split_name = "train" if "train" in dataset else list(dataset.keys())[0]
    return dataset[split_name].to_pandas()


def map_to_canonical_schema(raw_df: pd.DataFrame) -> pd.DataFrame:
    name = _extract_from_columns(raw_df, ["restaurant_name", "name", "restaurant"])
    city = _extract_from_columns(raw_df, ["city", "listed_in(city)", "location", "locality"])
    area = _extract_from_columns(raw_df, ["locality", "area", "location", "address"])
    cuisines = _extract_from_columns(raw_df, ["cuisines", "cuisine"])
    cost = _extract_from_columns(
        raw_df,
        ["average_cost_for_two", "cost_for_two", "approx_cost(for two people)", "cost"],
    )
    rating = _extract_from_columns(raw_df, ["aggregate_rating", "rating", "rate", "votes_rating"])
    rating_count = _extract_from_columns(raw_df, ["votes", "rating_count", "user_rating_votes"])

    canonical = pd.DataFrame(
        {
            "name": name,
            "city": city,
            "area": area,
            "cuisines": cuisines,
            "avg_cost_for_two": cost,
            "rating": rating,
            "rating_count": rating_count,
        }
    )

    canonical["name"] = canonical["name"].map(_normalize_text)
    canonical["city"] = canonical["city"].map(lambda value: _normalize_text(value).title())
    canonical["area"] = canonical["area"].map(lambda value: _normalize_text(value).title())
    canonical["cuisines"] = canonical["cuisines"].map(_normalize_cuisine)
    canonical["avg_cost_for_two"] = canonical["avg_cost_for_two"].map(_to_float)
    canonical["rating"] = canonical["rating"].map(_to_float).clip(lower=0, upper=5)
    canonical["rating_count"] = canonical["rating_count"].map(_to_int).fillna(0).astype(int)
    canonical["budget_band"] = canonical["avg_cost_for_two"].map(_budget_band)
    canonical["attributes"] = "{}"
    canonical["source_updated_at"] = datetime.now(timezone.utc).isoformat()

    canonical = canonical[canonical["name"] != ""].copy()
    canonical["restaurant_id"] = [
        str(uuid.uuid5(uuid.NAMESPACE_URL, f"{row['name']}|{row['city']}|{row['area']}"))
        for _, row in canonical.iterrows()
    ]
    canonical = canonical.drop_duplicates(subset=["restaurant_id"]).reset_index(drop=True)

    canonical = canonical[
        [
            "restaurant_id",
            "name",
            "city",
            "area",
            "cuisines",
            "avg_cost_for_two",
            "budget_band",
            "rating",
            "rating_count",
            "attributes",
            "source_updated_at",
        ]
    ]
    return canonical


def write_sqlite(canonical_df: pd.DataFrame, sqlite_path: Path, table_name: str = TARGET_TABLE) -> None:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    for_write = canonical_df.copy()
    for_write["cuisines"] = for_write["cuisines"].map(json.dumps)
    engine = create_engine(f"sqlite:///{sqlite_path}")
    with engine.begin() as connection:
        for_write.to_sql(table_name, connection, if_exists="replace", index=False)


def build_quality_report(raw_df: pd.DataFrame, canonical_df: pd.DataFrame) -> dict[str, Any]:
    nulls = canonical_df.isna().sum().to_dict()
    empty_name_count = int((canonical_df["name"].astype(str).str.strip() == "").sum())
    duplicate_ids = int(canonical_df.duplicated(subset=["restaurant_id"]).sum())
    return {
        "raw_row_count": int(len(raw_df)),
        "canonical_row_count": int(len(canonical_df)),
        "empty_name_count": empty_name_count,
        "duplicate_restaurant_id_count": duplicate_ids,
        "null_count_by_field": {key: int(value) for key, value in nulls.items()},
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def run_phase1(config: IngestionConfig) -> dict[str, Any]:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.report_dir.mkdir(parents=True, exist_ok=True)

    raw_df = load_source_dataset(config.dataset_id)
    canonical_df = map_to_canonical_schema(raw_df)
    write_sqlite(canonical_df, config.sqlite_path)
    report = build_quality_report(raw_df, canonical_df)

    report_path = config.report_dir / "phase1_data_quality_report.json"
    with report_path.open("w", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2)

    sample_path = config.data_dir / "canonical_restaurants_sample.csv"
    canonical_df.head(200).to_csv(sample_path, index=False)

    return {
        "report_path": str(report_path),
        "sample_path": str(sample_path),
        "sqlite_path": str(config.sqlite_path),
        "raw_row_count": report["raw_row_count"],
        "canonical_row_count": report["canonical_row_count"],
    }

