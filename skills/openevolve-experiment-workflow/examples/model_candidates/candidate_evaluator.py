from fractions import Fraction
from pathlib import Path
import sys

import orjson
from openevolve.evaluation_result import EvaluationResult


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mathematical_evolution import (
    Candidate, algorithm_evaluate, counterexample_evaluate, encode, proof_evaluate,
)


KINDS = {"algorithm": "gradient_step", "proof": "sos_proof", "counterexample": "graph"}
EVALUATORS = {
    "algorithm": algorithm_evaluate,
    "proof": proof_evaluate,
    "counterexample": counterexample_evaluate,
}


def load_candidate(path, case):
    return parse_candidate(orjson.loads(Path(path).read_bytes()), case)


def parse_candidate(document, case):
    if not isinstance(document, dict) or set(document) != {"kind", "value"}:
        raise ValueError("A candidate must have exactly the kind and value fields.")
    if document["kind"] != KINDS[case]:
        raise ValueError(f"The evaluator fixes candidate kind to {KINDS[case]}.")
    values = document["value"]
    if not isinstance(values, list):
        raise ValueError("Candidate value must be a JSON array.")
    if case == "counterexample":
        if len(values) != 2 or type(values[0]) is not int or values[0] != 5:
            raise ValueError("This finite graph task fixes the vertex count to five.")
        if not isinstance(values[1], list) or len(values[1]) > 10:
            raise ValueError("The five-vertex graph must have at most ten edges.")
        return Candidate(document["kind"], (values[0], values[1]))
    expected = 1 if case == "algorithm" else 2
    if len(values) != expected or any(not isinstance(v, str) or len(v) > 64 for v in values):
        raise ValueError(f"This case requires {expected} rational strings, each at most 64 characters.")
    return Candidate(document["kind"], tuple(Fraction(v) for v in values))


def evaluate_candidate(path, case):
    candidate = load_candidate(path, case)
    result = EVALUATORS[case](candidate)
    target = False
    score = -1.0
    if result["valid"]:
        metrics = result["metrics"]
        if case == "algorithm":
            score = 1.0 / (1.0 + float(metrics["worst_squared_error"]))
            baseline = algorithm_evaluate(Candidate("gradient_step", (Fraction(1, 64),)))
            target = result["rank"] > baseline["rank"]
        elif case == "proof":
            score = 1.0 / (1.0 + float(metrics["coefficient_error"]))
            target = result["mathematical_check"]["status"] == "exact_sos_identity"
        else:
            score = 1.0 / (1.0 + metrics["hamiltonian_cycles"] + metrics["edges"] / 100)
            target = result["mathematical_check"]["status"] == "counterexample_verified"
    return EvaluationResult(
        metrics={"combined_score": score, "admissible": float(result["valid"]),
                 "target_reached": float(target)},
        artifacts={"mathematical_feedback": orjson.dumps(encode(result)).decode("utf-8")},
    )
