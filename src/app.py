from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from src.phase2.schemas import PreferenceValidationRequest, PreferenceValidationResponse
from src.phase2.service import get_supported_cuisines, get_supported_locations, validate_preferences
from src.phase3.schemas import CandidateShortlistRequest, CandidateShortlistResponse
from src.phase3.service import generate_candidate_shortlist
from src.phase4.schemas import RecommendationGenerateRequest, RecommendationGenerateResponse
from src.phase4.service import generate_recommendations


app = FastAPI(title="Restaurant Recommendation API", version="0.1.0")
UI_PATH = Path("ui/index.html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def ui_home() -> FileResponse:
    if not UI_PATH.exists():
        raise HTTPException(status_code=404, detail="UI file not found.")
    return FileResponse(UI_PATH)


@app.get("/api/locations")
def get_locations() -> dict[str, list[str]]:
    try:
        return {"locations": get_supported_locations()}
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/cuisines")
def get_cuisines() -> dict[str, list[str]]:
    try:
        return {"cuisines": get_supported_cuisines()}
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/preferences/validate", response_model=PreferenceValidationResponse)
def validate_user_preferences(payload: PreferenceValidationRequest) -> PreferenceValidationResponse:
    try:
        return validate_preferences(payload)
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/candidates/shortlist", response_model=CandidateShortlistResponse)
def shortlist_candidates(payload: CandidateShortlistRequest) -> CandidateShortlistResponse:
    try:
        return generate_candidate_shortlist(payload.preferences)
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/recommendations/generate", response_model=RecommendationGenerateResponse)
def generate_ranked_recommendations(payload: RecommendationGenerateRequest) -> RecommendationGenerateResponse:
    try:
        return generate_recommendations(
            request=payload.preferences,
            top_k=payload.top_k,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

