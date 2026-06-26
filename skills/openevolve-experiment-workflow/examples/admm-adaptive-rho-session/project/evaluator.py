"""OpenEvolve evaluator entrypoint for ADMM adaptive-rho strategies."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Dict


PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from admm_benchmark import evaluate_program


PRIMARY_METRIC = "combined_score"


def evaluate(program_path: str) -> Dict[str, float]:
    """Evaluate a candidate program and return numeric metrics."""
    return evaluate_program(program_path)


if __name__ == "__main__":
    candidate_path = PROJECT_DIR / "initial_program.py"
    print(json.dumps(evaluate(str(candidate_path)), indent=2, sort_keys=True))
