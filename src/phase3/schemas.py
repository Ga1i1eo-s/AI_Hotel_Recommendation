from __future__ import annotations

from pydantic import BaseModel

from src.phase2.schemas import CanonicalPreferences, PreferenceValidationRequest


class CandidateShortlistRequest(BaseModel):
    preferences: PreferenceValidationRequest


class CandidateItem(BaseModel):
    restaurant_id: str
    name: str
    city: str
    area: str
    cuisines: list[str]
    avg_cost_for_two: float | None
    budget_band: str | None
    rating: float | None
    rating_count: int
    fit_score: float
    score_breakdown: dict[str, float]


class CandidateShortlistResponse(BaseModel):
    canonical_preferences: CanonicalPreferences
    warnings: list[str]
    relaxation_steps_applied: list[str]
    total_candidates_considered: int
    shortlisted_candidates: list[CandidateItem]

