from fractions import Fraction
from itertools import combinations
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import orjson
import sympy


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "skills" / "openevolve-experiment-workflow" / "examples"
sys.path.insert(0, str(EXAMPLES))
sys.path.insert(0, str(EXAMPLES / "model_candidates"))

from mathematical_evolution import (
    Candidate, algorithm_evaluate, algorithm_mutate, counterexample_evaluate,
    counterexample_mutate, evolve, proof_evaluate, proof_mutate,
)
from candidate_evaluator import evaluate_candidate, load_candidate


class MathematicalCandidateTests(unittest.TestCase):
    def test_gradient_search_improves_exact_objective_and_stays_stable(self):
        result = evolve(Candidate("gradient_step", (Fraction(1, 64),)),
                        algorithm_mutate, algorithm_evaluate, 10)
        best = result["best"]
        self.assertGreater(best["evaluation"]["rank"], result["baseline"]["evaluation"]["rank"])
        step = best["candidate"].value[0]
        self.assertGreater(step, 0)
        self.assertLess(step, Fraction(2, 9))
        self.assertLess(best["evaluation"]["mathematical_check"]["contraction_bound"], 1)
        repaired = [p for r in result["rounds"] for p in r["proposals"]
                    if p["feedback_used"]["source"] == "failed_candidate"]
        self.assertTrue(repaired)
        for proposal in repaired:
            feedback = proposal["feedback_used"]
            self.assertGreaterEqual(feedback["rejected_step"], Fraction(2, 9))

    def test_spectral_boundary_is_rejected(self):
        for step in (Fraction(0), Fraction(-1), Fraction(2, 9), Fraction(1)):
            self.assertFalse(algorithm_evaluate(Candidate("gradient_step", (step,)))["valid"])

    def test_proof_search_is_independently_verified_by_sympy(self):
        result = evolve(Candidate("sos_proof", (Fraction(0), Fraction(0))),
                        proof_mutate, proof_evaluate, 10)
        a, b = result["best"]["candidate"].value
        self.assertGreaterEqual(a, 0)
        self.assertGreaterEqual(b, 0)
        x, y = sympy.symbols("x y", real=True)
        expression = x**4 + y**4 - x**3*y - x*y**3
        squares = sympy.Rational(a.numerator, a.denominator)*(x-y)**4
        squares += sympy.Rational(b.numerator, b.denominator)*(x*x-y*y)**2
        self.assertEqual(sympy.Poly(sympy.expand(expression-squares), x, y), sympy.Poly(0, x, y))
        self.assertEqual(result["best"]["evaluation"]["mathematical_check"]["status"], "exact_sos_identity")

    def test_partial_and_negative_coefficients_do_not_certify_a_proof(self):
        partial = proof_evaluate(Candidate("sos_proof", (Fraction(1, 4), Fraction(0))))
        self.assertEqual(partial["mathematical_check"]["status"], "unproved")
        self.assertFalse(proof_evaluate(Candidate("sos_proof", (Fraction(-1), Fraction(1))))["valid"])

    def test_graph_search_has_independent_degree_witness(self):
        result = evolve(Candidate("graph", (5, tuple(combinations(range(5), 2)))),
                        counterexample_mutate, counterexample_evaluate, 10)
        vertices, edges = result["best"]["candidate"].value
        degrees = [sum(v in edge for edge in edges) for v in range(vertices)]
        self.assertIn(1, degrees)
        self.assertGreaterEqual(len(edges), vertices)
        self.assertEqual(result["best"]["evaluation"]["metrics"]["hamiltonian_cycles"], 0)
        reached = {0}
        for _ in range(vertices):
            reached |= {v for edge in edges if reached.intersection(edge) for v in edge}
        self.assertEqual(len(reached), vertices)

    def test_cycle_is_not_a_counterexample_and_disconnected_graph_is_inadmissible(self):
        cycle = Candidate("graph", (5, ((0, 1), (1, 2), (2, 3), (3, 4), (0, 4))))
        result = counterexample_evaluate(cycle)
        self.assertTrue(result["valid"])
        self.assertEqual(result["metrics"]["hamiltonian_cycles"], 1)
        self.assertEqual(result["mathematical_check"]["status"], "not_a_counterexample")
        disconnected = Candidate("graph", (5, tuple(combinations(range(4), 2))))
        self.assertIn("disconnected", counterexample_evaluate(disconnected)["violations"])

    def test_malformed_graph_fails_at_input_validation(self):
        for edge_list in (((0, 0),), ((0, 1), (1, 0)), ((0, 5),), ((True, 1),)):
            with self.assertRaises(ValueError):
                counterexample_evaluate(Candidate("graph", (5, edge_list)))

    def test_short_proof_budget_exits_with_partial_result(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "partial.json"
            completed = subprocess.run(
                [sys.executable, str(EXAMPLES / "mathematical_evolution.py"),
                 "--case", "proof", "--rounds", "1", "--output", str(output)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            report = orjson.loads(output.read_bytes())
            self.assertFalse(report["target_reached"])
            self.assertEqual(report["cases"]["proof"]["best"]["evaluation"]["mathematical_check"]["status"], "unproved")

    def test_json_evaluator_keeps_case_and_graph_size_fixed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_bytes(orjson.dumps({"kind": "sos_proof", "value": ["1/4", "3/4"]}))
            result = evaluate_candidate(path, "proof")
            self.assertEqual(result.metrics["combined_score"], 1.0)
            self.assertEqual(result.metrics["target_reached"], 1.0)
            self.assertIn("exact_sos_identity", result.artifacts["mathematical_feedback"])
            with self.assertRaises(ValueError):
                evaluate_candidate(path, "algorithm")
            path.write_bytes(orjson.dumps({"kind": "graph", "value": [12, []]}))
            with self.assertRaises(ValueError):
                load_candidate(path, "counterexample")

    def test_json_is_data_and_cannot_execute_generated_python(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_text("__import__('os').getcwd()", encoding="utf-8")
            with self.assertRaises(orjson.JSONDecodeError):
                load_candidate(path, "algorithm")
            path.write_bytes(orjson.dumps({"kind": "gradient_step", "value": [0.2]}))
            with self.assertRaises(ValueError):
                load_candidate(path, "algorithm")


if __name__ == "__main__":
    unittest.main()
