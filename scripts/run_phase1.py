from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from phase1.pipeline import IngestionConfig, run_phase1


def main() -> None:
    result = run_phase1(IngestionConfig())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

