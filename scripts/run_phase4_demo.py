from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.phase2.schemas import PreferenceValidationRequest
from src.phase4.service import generate_recommendations


def main() -> None:
    demo_request = PreferenceValidationRequest(
        location="Bangalore",
        budget=2000,
        cuisine=["Italian", "Chinese"],
        min_rating=4.0,
        additional_preferences="family friendly with quick service",
    )
    result = generate_recommendations(request=demo_request, top_k=5)
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()

