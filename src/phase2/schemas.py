from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class PreferenceValidationRequest(BaseModel):
    location: str = Field(..., min_length=1)
    budget: float = Field(..., gt=0.0, le=20000.0)
    cuisine: str | list[str]
    min_rating: float = Field(..., ge=0.0, le=5.0)
    additional_preferences: str = ""

    @field_validator("location")
    @classmethod
    def location_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("location must not be blank")
        return value


class CanonicalPreferences(BaseModel):
    location_input: str
    city: str
    area: str | None
    budget_max_for_two: float
    cost_range: dict[str, int | None]
    cuisines: list[str]
    min_rating: float
    additional_preference_text: str
    additional_preference_tags: list[str]


class PreferenceValidationResponse(BaseModel):
    canonical_preferences: CanonicalPreferences
    warnings: list[str]

