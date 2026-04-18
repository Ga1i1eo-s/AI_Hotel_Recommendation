from __future__ import annotations

import re
import sqlite3
import json
from dataclasses import dataclass
from pathlib import Path

from .schemas import CanonicalPreferences, PreferenceValidationRequest, PreferenceValidationResponse


ADDITIONAL_TAG_KEYWORDS = {
    "family_friendly": ["family", "kids", "child", "children"],
    "quick_service": ["quick", "fast service", "speedy"],
    "romantic": ["romantic", "date night", "couple"],
    "outdoor_seating": ["outdoor", "open air", "terrace"],
    "pet_friendly": ["pet friendly", "pets allowed", "dog friendly"],
    "veg_friendly": ["veg", "vegetarian", "vegan"],
}

CITY_ALIASES = {
    "bangalore": "Bangalore",
    "bengaluru": "Bangalore",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "ncr": "Delhi NCR",
    "mumbai": "Mumbai",
    "pune": "Pune",
    "hyderabad": "Hyderabad",
    "chennai": "Chennai",
    "kolkata": "Kolkata",
}


@dataclass
class LocationCatalog:
    cities: set[str]
    areas: set[str]
    city_by_lower: dict[str, str]
    area_by_lower: dict[str, str]


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _normalize_title(text: str) -> str:
    return _normalize_whitespace(text).title()


def _cost_range_from_budget_amount(budget_max_for_two: float) -> dict[str, int | None]:
    return {"min": 0, "max": int(round(budget_max_for_two))}


def _normalize_cuisines(value: str | list[str]) -> list[str]:
    raw_items: list[str]
    if isinstance(value, str):
        raw_items = re.split(r"[,/|]", value)
    else:
        raw_items = value

    cuisines: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        cleaned = _normalize_title(str(item))
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            cuisines.append(cleaned)
    return cuisines


def _extract_additional_tags(additional_text: str) -> list[str]:
    normalized = additional_text.lower()
    tags: list[str] = []
    for tag, keywords in ADDITIONAL_TAG_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            tags.append(tag)
    return tags


def load_location_catalog(sqlite_path: Path = Path("data/catalog.db")) -> LocationCatalog:
    if not sqlite_path.exists():
        raise FileNotFoundError(
            "Catalog DB not found. Run Phase 1 first using `python scripts/run_phase1.py`."
        )

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute("SELECT city, area FROM restaurants").fetchall()
    finally:
        connection.close()

    cities = {_normalize_title(row[0]) for row in rows if row[0]}
    areas = {_normalize_title(row[1]) for row in rows if row[1]}
    return LocationCatalog(
        cities=cities,
        areas=areas,
        city_by_lower={city.lower(): city for city in cities},
        area_by_lower={area.lower(): area for area in areas},
    )


def get_supported_locations(sqlite_path: Path = Path("data/catalog.db")) -> list[str]:
    catalog = load_location_catalog(sqlite_path=sqlite_path)
    return sorted(catalog.cities)


def get_supported_cuisines(sqlite_path: Path = Path("data/catalog.db")) -> list[str]:
    if not sqlite_path.exists():
        raise FileNotFoundError(
            "Catalog DB not found. Run Phase 1 first using `python scripts/run_phase1.py`."
        )

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute("SELECT cuisines FROM restaurants WHERE cuisines IS NOT NULL").fetchall()
    finally:
        connection.close()

    unique: set[str] = set()
    for (raw_value,) in rows:
        if not raw_value:
            continue
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                for item in parsed:
                    normalized = _normalize_title(str(item))
                    if normalized:
                        unique.add(normalized)
        except json.JSONDecodeError:
            continue

    return sorted(unique)


def _resolve_location(location_input: str, catalog: LocationCatalog) -> tuple[str, str | None, list[str]]:
    warnings: list[str] = []
    normalized_input = _normalize_title(location_input)
    lower_input = normalized_input.lower()

    if lower_input in CITY_ALIASES:
        warnings.append("Location matched using supported metro-city alias mapping.")
        return CITY_ALIASES[lower_input], None, warnings

    if lower_input in catalog.city_by_lower:
        return catalog.city_by_lower[lower_input], None, warnings

    if lower_input in catalog.area_by_lower:
        area = catalog.area_by_lower[lower_input]
        warnings.append("Location matched as area/locality. City could not be uniquely inferred.")
        return "Unknown", area, warnings

    city_match = next((city for city in catalog.cities if lower_input in city.lower()), None)
    if city_match:
        warnings.append("Location was matched approximately to nearest supported city.")
        return city_match, None, warnings

    area_match = next((area for area in catalog.areas if lower_input in area.lower()), None)
    if area_match:
        warnings.append("Location was matched approximately to nearest supported area.")
        return "Unknown", area_match, warnings

    raise ValueError(f"Unsupported location: {location_input}")


def validate_preferences(
    request: PreferenceValidationRequest, sqlite_path: Path = Path("data/catalog.db")
) -> PreferenceValidationResponse:
    catalog = load_location_catalog(sqlite_path=sqlite_path)

    city, area, location_warnings = _resolve_location(request.location, catalog)
    cuisines = _normalize_cuisines(request.cuisine)
    warnings = list(location_warnings)
    if not cuisines:
        warnings.append("No valid cuisine values were provided after normalization.")

    additional_text = _normalize_whitespace(request.additional_preferences)
    additional_tags = _extract_additional_tags(additional_text)
    if additional_text and not additional_tags:
        warnings.append("Additional preferences captured as free text; no standard tags matched.")

    budget_max_for_two = round(float(request.budget), 2)

    canonical = CanonicalPreferences(
        location_input=request.location,
        city=city,
        area=area,
        budget_max_for_two=budget_max_for_two,
        cost_range=_cost_range_from_budget_amount(budget_max_for_two),
        cuisines=cuisines,
        min_rating=round(request.min_rating, 2),
        additional_preference_text=additional_text,
        additional_preference_tags=additional_tags,
    )
    return PreferenceValidationResponse(canonical_preferences=canonical, warnings=warnings)

