from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from src.phase2.schemas import PreferenceValidationRequest
from src.phase3.schemas import CandidateItem
from src.phase3.service import generate_candidate_shortlist
from src.phase4.schemas import (
    RankedRecommendation,
    RecommendationGenerateResponse,
)


PHASE4_CONFIG_PATH = Path("config/phase4_prompt.json")
load_dotenv()


def _load_phase4_config(config_path: Path = PHASE4_CONFIG_PATH) -> dict[str, Any]:
    if not config_path.exists():
        return {
            "prompt_version": "v1",
            "max_reason_words": 50,
            "default_top_k": 5,
            "llm": {
                "provider": "groq",
                "api_url": "https://api.groq.com/openai/v1/chat/completions",
                "model": "llama-3.1-70b-versatile",
                "temperature": 0.2,
                "timeout_seconds": 30,
                "max_retries": 2,
            },
        }
    with config_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(".") + "."


def _build_prompt(preferences: dict[str, Any], candidates: list[CandidateItem], top_k: int, max_reason_words: int) -> list[dict[str, str]]:
    candidate_rows = []
    for item in candidates:
        candidate_rows.append(
            {
                "restaurant_id": item.restaurant_id,
                "name": item.name,
                "city": item.city,
                "area": item.area,
                "cuisines": item.cuisines,
                "avg_cost_for_two": item.avg_cost_for_two,
                "rating": item.rating,
                "rating_count": item.rating_count,
                "fit_score": item.fit_score,
            }
        )

    system_message = (
        "You are a restaurant recommendation ranker. "
        "Use ONLY the provided candidate restaurants. "
        "Do not invent restaurants. "
        "Return strict JSON only."
    )
    user_message = json.dumps(
        {
            "task": "Rank restaurants and explain why they match user preferences.",
            "constraints": {
                "top_k": top_k,
                "max_reason_words": max_reason_words,
                "budget_guidance": "Treat user_preferences.budget_max_for_two as the strict maximum budget for two people.",
                "output_schema": {
                    "recommendations": [
                        {
                            "restaurant_id": "string from candidates",
                            "rank": "integer starting at 1",
                            "reason": "short text grounded in provided candidate attributes only",
                            "match_tags": ["short tags like budget_fit, rating_fit, cuisine_fit"],
                        }
                    ]
                },
            },
            "user_preferences": preferences,
            "candidates": candidate_rows,
        },
        ensure_ascii=True,
    )
    return [{"role": "system", "content": system_message}, {"role": "user", "content": user_message}]


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("LLM output is not valid JSON.")
        return json.loads(text[start : end + 1])


def _call_llm(messages: list[dict[str, str]], config: dict[str, Any]) -> dict[str, Any]:
    llm_cfg = config["llm"]
    api_url = os.getenv("LLM_API_URL", llm_cfg["api_url"])
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Missing GROQ_API_KEY/LLM_API_KEY/OPENAI_API_KEY for LLM call.")

    primary_model = os.getenv("LLM_MODEL", llm_cfg["model"])
    fallback_models = [
        llm_cfg.get("fallback_model", "llama-3.3-70b-versatile"),
        "llama-3.3-70b-versatile",
    ]
    model_candidates = [primary_model] + [model for model in fallback_models if model and model != primary_model]

    payload = {
        "model": primary_model,
        "messages": messages,
        "temperature": llm_cfg.get("temperature", 0.2),
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    retries = int(llm_cfg.get("max_retries", 2))
    timeout_seconds = int(llm_cfg.get("timeout_seconds", 30))
    last_error: Exception | None = None
    for model_name in model_candidates:
        payload["model"] = model_name
        for _ in range(retries + 1):
            try:
                response = requests.post(api_url, headers=headers, json=payload, timeout=timeout_seconds)
                if not response.ok:
                    error_detail = response.text
                    if "model_decommissioned" in error_detail and model_name != model_candidates[-1]:
                        break
                    raise ValueError(f"HTTP {response.status_code} from LLM provider: {error_detail}")
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return _extract_json_object(content)
            except (requests.RequestException, ValueError, KeyError, json.JSONDecodeError) as error:
                last_error = error
    raise ValueError(f"LLM call failed after retries: {last_error}")


def _fallback_rank(
    candidates: list[CandidateItem], top_k: int, max_reason_words: int
) -> list[RankedRecommendation]:
    fallback_items = candidates[:top_k]
    recommendations: list[RankedRecommendation] = []
    for index, item in enumerate(fallback_items, start=1):
        reason = (
            f"Strong deterministic fit with rating {item.rating}, budget {item.budget_band}, "
            f"and cuisine overlap score {item.score_breakdown.get('cuisine_match', 0.0):.2f}."
        )
        reason = _truncate_words(reason, max_reason_words)
        tags = []
        if item.score_breakdown.get("budget_fit", 0) > 0:
            tags.append("budget_fit")
        if (item.score_breakdown.get("rating_norm", 0) or 0) >= 0.8:
            tags.append("rating_fit")
        if (item.score_breakdown.get("cuisine_match", 0) or 0) > 0:
            tags.append("cuisine_fit")
        recommendations.append(
            RankedRecommendation(
                restaurant_id=item.restaurant_id,
                rank=index,
                reason=reason,
                match_tags=tags,
                candidate=item,
            )
        )
    return recommendations


def _validate_llm_recommendations(
    llm_output: dict[str, Any],
    candidate_map: dict[str, CandidateItem],
    top_k: int,
    max_reason_words: int,
) -> list[RankedRecommendation]:
    raw_items = llm_output.get("recommendations")
    if not isinstance(raw_items, list):
        raise ValueError("LLM output missing recommendations list.")

    validated: list[RankedRecommendation] = []
    seen_ids: set[str] = set()
    for raw in raw_items:
        restaurant_id = str(raw.get("restaurant_id", "")).strip()
        if not restaurant_id or restaurant_id in seen_ids or restaurant_id not in candidate_map:
            continue
        seen_ids.add(restaurant_id)
        rank = int(raw.get("rank", len(validated) + 1))
        reason = _truncate_words(str(raw.get("reason", "")).strip(), max_reason_words)
        match_tags = raw.get("match_tags", [])
        if not isinstance(match_tags, list):
            match_tags = []
        match_tags = [str(item) for item in match_tags if str(item).strip()]
        if not reason:
            reason = "Recommended due to strong match with your preferences."

        validated.append(
            RankedRecommendation(
                restaurant_id=restaurant_id,
                rank=max(1, rank),
                reason=reason,
                match_tags=match_tags,
                candidate=candidate_map[restaurant_id],
            )
        )
        if len(validated) >= top_k:
            break

    validated.sort(key=lambda item: item.rank)
    for index, item in enumerate(validated, start=1):
        item.rank = index
    return validated


def generate_recommendations(
    request: PreferenceValidationRequest,
    top_k: int = 5,
) -> RecommendationGenerateResponse:
    config = _load_phase4_config()
    prompt_version = str(config.get("prompt_version", "v1"))
    max_reason_words = int(config.get("max_reason_words", 50))
    shortlist = generate_candidate_shortlist(request=request)
    warnings = list(shortlist.warnings)
    candidates = shortlist.shortlisted_candidates
    top_k = min(top_k, len(candidates)) if candidates else top_k
    if not candidates:
        return RecommendationGenerateResponse(
            canonical_preferences=shortlist.canonical_preferences,
            warnings=warnings,
            llm_used=False,
            fallback_reason="No candidate restaurants available from Phase 3.",
            prompt_version=prompt_version,
            recommendations=[],
        )

    candidate_map = {item.restaurant_id: item for item in candidates}
    messages = _build_prompt(
        preferences=shortlist.canonical_preferences.model_dump(),
        candidates=candidates,
        top_k=top_k,
        max_reason_words=max_reason_words,
    )

    try:
        llm_output = _call_llm(messages=messages, config=config)
        recommendations = _validate_llm_recommendations(
            llm_output=llm_output,
            candidate_map=candidate_map,
            top_k=top_k,
            max_reason_words=max_reason_words,
        )
        if not recommendations:
            raise ValueError("Validated LLM output contained no usable recommendations.")
        return RecommendationGenerateResponse(
            canonical_preferences=shortlist.canonical_preferences,
            warnings=warnings,
            llm_used=True,
            fallback_reason=None,
            prompt_version=prompt_version,
            recommendations=recommendations,
        )
    except ValueError as error:
        warnings.append("LLM ranking unavailable; deterministic fallback applied.")
        fallback = _fallback_rank(candidates=candidates, top_k=top_k, max_reason_words=max_reason_words)
        return RecommendationGenerateResponse(
            canonical_preferences=shortlist.canonical_preferences,
            warnings=warnings,
            llm_used=False,
            fallback_reason=str(error),
            prompt_version=prompt_version,
            recommendations=fallback,
        )

