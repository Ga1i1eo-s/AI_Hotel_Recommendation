from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.phase2.schemas import PreferenceValidationRequest
from src.phase3.service import generate_candidate_shortlist


def main() -> None:
    demo_request = PreferenceValidationRequest(
        location="Bangalore",
        budget=2000,
        cuisine=["Italian", "Chinese"],
        min_rating=4.0,
        additional_preferences="family friendly and quick service",
    )
    result = generate_candidate_shortlist(demo_request)
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()

