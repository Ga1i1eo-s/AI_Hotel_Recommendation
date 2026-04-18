from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from src.phase2.schemas import CanonicalPreferences, PreferenceValidationRequest
from src.phase2.service import validate_preferences
from src.phase3.schemas import CandidateItem, CandidateShortlistResponse


DEFAULT_CONFIG_PATH = Path("config/phase3_scoring.json")
FIXED_SHORTLIST_SIZE = 20


def _load_phase3_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    if not config_path.exists():
        return {
            "weights": {
                "cuisine_match": 0.35,
                "rating_norm": 0.30,
                "budget_fit": 0.20,
                "popularity_norm": 0.15,
            },
            "default_shortlist_size": 20,
            "min_desired_candidates": 20,
            "dedup_strategy": "name_area",
        }
    with config_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _candidate_dedup_key(candidate: CandidateItem, strategy: str) -> str:
    if strategy == "restaurant_id":
        return candidate.restaurant_id.strip().lower()
    if strategy == "name":
        return candidate.name.strip().lower()
    # default: name_area
    name_key = candidate.name.strip().lower()
    area_key = candidate.area.strip().lower()
    return f"{name_key}|{area_key}"


def _parse_cuisines(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass
    return []


def _fetch_catalog_rows(sqlite_path: Path) -> list[dict[str, Any]]:
    if not sqlite_path.exists():
        raise FileNotFoundError(
            "Catalog DB not found. Run Phase 1 first using `python scripts/run_phase1.py`."
        )
    connection = sqlite3.connect(sqlite_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT restaurant_id, name, city, area, cuisines, avg_cost_for_two,
                   budget_band, rating, rating_count
            FROM restaurants
            """
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def _city_matches(pref: CanonicalPreferences, row: dict[str, Any]) -> bool:
    city = str(row.get("city") or "").strip().lower()
    area = str(row.get("area") or "").strip().lower()
    if pref.city != "Unknown" and city == pref.city.strip().lower():
        return True
    if pref.area and area == pref.area.strip().lower():
        return True
    return False


def _rating_filter(row: dict[str, Any], min_rating: float) -> bool:
    rating = row.get("rating")
    if rating is None:
        return False
    try:
        return float(rating) >= min_rating
    except (TypeError, ValueError):
        return False


def _budget_filter(row: dict[str, Any], cost_range: dict[str, int | None]) -> bool:
    cost = row.get("avg_cost_for_two")
    if cost is None:
        return False
    try:
        cost = float(cost)
    except (TypeError, ValueError):
        return False
    min_cost = float(cost_range["min"]) if cost_range.get("min") is not None else None
    max_cost = float(cost_range["max"]) if cost_range.get("max") is not None else None
    if min_cost is not None and cost < min_cost:
        return False
    if max_cost is not None and cost > max_cost:
        return False
    return True


def _cuisine_overlap_count(requested: list[str], offered: list[str]) -> int:
    req = {item.strip().lower() for item in requested if item.strip()}
    off = {item.strip().lower() for item in offered if item.strip()}
    return len(req.intersection(off))


def _budget_fit_component(cost: float | None, range_min: int | None, range_max: int | None) -> float:
    if cost is None:
        return 0.0
    if range_min is not None and cost < range_min:
        return 0.0
    if range_max is not None and cost > range_max:
        return 0.0
    return 1.0


def _score_row(
    row: dict[str, Any],
    pref: CanonicalPreferences,
    weights: dict[str, float],
    max_rating_count: int,
) -> tuple[float, dict[str, float]]:
    offered_cuisines = _parse_cuisines(row.get("cuisines"))
    overlap_count = _cuisine_overlap_count(pref.cuisines, offered_cuisines)
    cuisine_match = 0.0 if not pref.cuisines else overlap_count / len(pref.cuisines)

    rating = float(row.get("rating")) if row.get("rating") is not None else 0.0
    rating_norm = max(0.0, min(1.0, rating / 5.0))

    avg_cost_for_two = float(row.get("avg_cost_for_two")) if row.get("avg_cost_for_two") is not None else None
    budget_fit = _budget_fit_component(
        avg_cost_for_two,
        pref.cost_range.get("min"),
        pref.cost_range.get("max"),
    )

    rating_count = int(row.get("rating_count") or 0)
    popularity_norm = rating_count / max_rating_count if max_rating_count > 0 else 0.0

    breakdown = {
        "cuisine_match": round(cuisine_match, 4),
        "rating_norm": round(rating_norm, 4),
        "budget_fit": round(budget_fit, 4),
        "popularity_norm": round(popularity_norm, 4),
    }

    fit_score = (
        weights["cuisine_match"] * cuisine_match
        + weights["rating_norm"] * rating_norm
        + weights["budget_fit"] * budget_fit
        + weights["popularity_norm"] * popularity_norm
    )
    return round(fit_score, 4), breakdown


def _apply_strict_filters(rows: list[dict[str, Any]], pref: CanonicalPreferences) -> list[dict[str, Any]]:
    filtered = [row for row in rows if _city_matches(pref, row)]
    filtered = [row for row in filtered if _rating_filter(row, pref.min_rating)]
    filtered = [row for row in filtered if _budget_filter(row, pref.cost_range)]
    filtered = [
        row
        for row in filtered
        if _cuisine_overlap_count(pref.cuisines, _parse_cuisines(row.get("cuisines"))) > 0
    ]
    return filtered


def _fallback_expand_location(rows: list[dict[str, Any]], pref: CanonicalPreferences) -> list[dict[str, Any]]:
    if pref.city == "Unknown":
        return rows
    city_lower = pref.city.strip().lower()
    matched = [row for row in rows if city_lower in str(row.get("city") or "").strip().lower()]
    if matched:
        return matched
    # Some datasets store only localities in the city column; use full catalog as a safe fallback.
    return rows


def _fallback_lower_rating(rows: list[dict[str, Any]], min_rating: float) -> list[dict[str, Any]]:
    lower = max(0.0, min_rating - 0.2)
    return [row for row in rows if _rating_filter(row, lower)]


CUISINE_RELATED_MAP = {
    "North Indian": ["Mughlai", "Biryani"],
    "Chinese": ["Asian", "Thai"],
    "Italian": ["Pizza", "Continental"],
}


def _fallback_expand_cuisines(pref_cuisines: list[str]) -> list[str]:
    expanded = list(pref_cuisines)
    existing = {item.lower() for item in expanded}
    for cuisine in pref_cuisines:
        for related in CUISINE_RELATED_MAP.get(cuisine, []):
            if related.lower() not in existing:
                existing.add(related.lower())
                expanded.append(related)
    return expanded


def generate_candidate_shortlist(
    request: PreferenceValidationRequest,
    shortlist_size: int = FIXED_SHORTLIST_SIZE,
    sqlite_path: Path = Path("data/catalog.db"),
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> CandidateShortlistResponse:
    validation = validate_preferences(request, sqlite_path=sqlite_path)
    pref = validation.canonical_preferences
    warnings = list(validation.warnings)
    config = _load_phase3_config(config_path)
    weights = config["weights"]
    shortlist_size = int(config.get("default_shortlist_size", FIXED_SHORTLIST_SIZE))
    min_desired = int(config.get("min_desired_candidates", shortlist_size))
    dedup_strategy = str(config.get("dedup_strategy", "name_area")).strip().lower()
    if dedup_strategy not in {"name", "name_area", "restaurant_id"}:
        dedup_strategy = "name_area"
        warnings.append("Invalid dedup strategy in config; defaulted to name_area.")

    rows = _fetch_catalog_rows(sqlite_path)

    current = _apply_strict_filters(rows, pref)
    relaxation_steps: list[str] = []

    if len(current) < min_desired:
        location_relaxed = _fallback_expand_location(rows, pref)
        location_relaxed = [row for row in location_relaxed if _budget_filter(row, pref.cost_range)]
        location_relaxed = [row for row in location_relaxed if _rating_filter(row, pref.min_rating)]
        location_relaxed = [
            row
            for row in location_relaxed
            if _cuisine_overlap_count(pref.cuisines, _parse_cuisines(row.get("cuisines"))) > 0
        ]
        if len(location_relaxed) > len(current):
            current = location_relaxed
            relaxation_steps.append("Expanded nearby areas within city.")

    if len(current) < min_desired:
        city_filtered = [row for row in rows if _city_matches(pref, row)]
        rating_relaxed = _fallback_lower_rating(city_filtered, pref.min_rating)
        rating_relaxed = [row for row in rating_relaxed if _budget_filter(row, pref.cost_range)]
        rating_relaxed = [
            row
            for row in rating_relaxed
            if _cuisine_overlap_count(pref.cuisines, _parse_cuisines(row.get("cuisines"))) > 0
        ]
        if len(rating_relaxed) > len(current):
            current = rating_relaxed
            relaxation_steps.append("Lowered minimum rating threshold by 0.2.")

    if len(current) < min_desired:
        expanded_cuisines = _fallback_expand_cuisines(pref.cuisines)
        cuisine_relaxed = [row for row in rows if _city_matches(pref, row)]
        cuisine_relaxed = [row for row in cuisine_relaxed if _budget_filter(row, pref.cost_range)]
        cuisine_relaxed = [row for row in cuisine_relaxed if _rating_filter(row, pref.min_rating - 0.2)]
        cuisine_relaxed = [
            row
            for row in cuisine_relaxed
            if _cuisine_overlap_count(expanded_cuisines, _parse_cuisines(row.get("cuisines"))) > 0
        ]
        if len(cuisine_relaxed) > len(current):
            current = cuisine_relaxed
            relaxation_steps.append("Expanded cuisines to related options.")

    max_rating_count = max((int(row.get("rating_count") or 0) for row in current), default=1)
    candidates: list[CandidateItem] = []
    for row in current:
        fit_score, breakdown = _score_row(row, pref, weights, max_rating_count)
        candidates.append(
            CandidateItem(
                restaurant_id=str(row.get("restaurant_id")),
                name=str(row.get("name") or ""),
                city=str(row.get("city") or ""),
                area=str(row.get("area") or ""),
                cuisines=_parse_cuisines(row.get("cuisines")),
                avg_cost_for_two=float(row.get("avg_cost_for_two")) if row.get("avg_cost_for_two") is not None else None,
                budget_band=str(row.get("budget_band")) if row.get("budget_band") is not None else None,
                rating=float(row.get("rating")) if row.get("rating") is not None else None,
                rating_count=int(row.get("rating_count") or 0),
                fit_score=fit_score,
                score_breakdown=breakdown,
            )
        )

    candidates.sort(key=lambda item: (item.fit_score, item.rating or 0.0, item.rating_count), reverse=True)

    # Deduplicate using configurable strategy from phase3_scoring.json.
    unique_candidates: list[CandidateItem] = []
    seen_keys: set[str] = set()
    for candidate in candidates:
        name_key = candidate.name.strip().lower()
        if not name_key:
            continue
        key = _candidate_dedup_key(candidate, dedup_strategy)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        unique_candidates.append(candidate)

    shortlisted = unique_candidates[:shortlist_size]

    if len(shortlisted) == 0:
        warnings.append("No candidates found for the provided constraints even after fallback.")

    return CandidateShortlistResponse(
        canonical_preferences=pref,
        warnings=warnings,
        relaxation_steps_applied=relaxation_steps,
        total_candidates_considered=len(current),
        shortlisted_candidates=shortlisted,
    )

