from __future__ import annotations

from pydantic import BaseModel, Field

from src.phase2.schemas import CanonicalPreferences, PreferenceValidationRequest
from src.phase3.schemas import CandidateItem


class RecommendationGenerateRequest(BaseModel):
    preferences: PreferenceValidationRequest
    top_k: int = Field(default=5, ge=1, le=20)


class RankedRecommendation(BaseModel):
    restaurant_id: str
    rank: int
    reason: str
    match_tags: list[str]
    candidate: CandidateItem


class RecommendationGenerateResponse(BaseModel):
    canonical_preferences: CanonicalPreferences
    warnings: list[str]
    llm_used: bool
    fallback_reason: str | None
    prompt_version: str
    recommendations: list[RankedRecommendation]

