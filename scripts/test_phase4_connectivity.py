from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.phase2.schemas import PreferenceValidationRequest
from src.phase4.service import generate_recommendations


TEST_CASES = [
    {
        "name": "Bangalore 2000 Italian Chinese",
        "request": PreferenceValidationRequest(
            location="Bangalore",
            budget=2000,
            cuisine=["Italian", "Chinese"],
            min_rating=4.0,
            additional_preferences="family friendly with quick service",
        ),
        "top_k": 5,
    },
    {
        "name": "Delhi 800 North Indian",
        "request": PreferenceValidationRequest(
            location="Delhi",
            budget=800,
            cuisine="North Indian",
            min_rating=3.8,
            additional_preferences="quick service",
        ),
        "top_k": 5,
    },
    {
        "name": "Mumbai 3500 Asian",
        "request": PreferenceValidationRequest(
            location="Mumbai",
            budget=3500,
            cuisine=["Asian"],
            min_rating=4.0,
            additional_preferences="romantic",
        ),
        "top_k": 5,
    },
    {
        "name": "Pune 1800 Cafe",
        "request": PreferenceValidationRequest(
            location="Pune",
            budget=1800,
            cuisine="Cafe",
            min_rating=4.1,
            additional_preferences="outdoor seating",
        ),
        "top_k": 5,
    },
]


def run_case(case: dict) -> dict:
    response = generate_recommendations(
        request=case["request"],
        top_k=case["top_k"],
    )
    return {
        "case": case["name"],
        "llm_used": response.llm_used,
        "fallback_reason": response.fallback_reason,
        "warnings": response.warnings,
        "recommendation_count": len(response.recommendations),
        "top_restaurants": [item.candidate.name for item in response.recommendations[:3]],
    }


def main() -> None:
    results = [run_case(case) for case in TEST_CASES]
    llm_success_count = sum(1 for result in results if result["llm_used"])
    summary = {
        "total_tests": len(results),
        "llm_success_count": llm_success_count,
        "llm_failure_count": len(results) - llm_success_count,
        "results": results,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

