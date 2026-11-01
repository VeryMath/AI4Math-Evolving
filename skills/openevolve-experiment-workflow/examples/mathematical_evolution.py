from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
from itertools import permutations
import json
from pathlib import Path


@dataclass(frozen=True)
class Candidate:
    kind: str
    value: tuple


def algorithm_evaluate(candidate):
    step = candidate.value[0]
    spectra = ((1, 2, 4), (1, 3, 9))
    if step <= 0 or step >= Fraction(2, 9):
        return {
            "valid": False,
            "reason": "The step violates 0 < step < 2/9 for the declared spectrum.",
            "violations": ["step_outside_spectral_interval"],
            "metrics": {"step": step},
        }
    residuals = []
    for spectrum in spectra:
        x = [Fraction(1) for _ in spectrum]
        for _ in range(12):
            x = [xi - step * eigenvalue * xi for xi, eigenvalue in zip(x, spectrum)]
        residuals.append(sum(xi * xi for xi in x) / len(x))
    worst = max(residuals)
    contraction = max(abs(1 - step * eigenvalue) for eigenvalue in (1, 9))
    return {
        "valid": True,
        "rank": (-worst,),
        "reason": "Exact rational gradient iterations completed on both diagonal quadratics.",
        "metrics": {"worst_squared_error": worst, "worst_squared_error_decimal": float(worst),
                    "step": step, "iterations": 12},
        "mathematical_check": {
            "status": "spectral_bound_checked",
            "contraction_bound": contraction,
            "scope": "For a symmetric positive definite quadratic with spectrum in [1, 9], "
            "the gradient error contracts by at most max(|1-step|, |1-9*step|).",
        },
    }


def algorithm_mutate(candidate, evaluation, history):
    step = candidate.value[0]
    proposals = [
        ("double step", step * 2, {"source": "current_step", "step": evaluation["metrics"]["step"]}),
        ("increase step by 1/64", step + Fraction(1, 64), {"source": "local_neighbor"}),
        ("decrease step by 1/64", step - Fraction(1, 64), {"source": "local_neighbor"}),
    ]
    unstable = []
    for previous in history:
        for proposal in previous["proposals"]:
            result = proposal["evaluation"]
            if "step_outside_spectral_interval" in result.get("violations", []) and result["metrics"]["step"] > step:
                unstable.append((result["metrics"]["step"], previous["round"], result["reason"]))
    if unstable:
        rejected_step, previous_round, reason = min(unstable)
        proposals.insert(0, (
            "bisect toward a previously rejected unstable step", (step + rejected_step) / 2,
            {"source": "failed_candidate", "round": previous_round, "rejected_step": rejected_step, "reason": reason},
        ))
    seen = set()
    for label, value, feedback_used in proposals:
        if value not in seen:
            seen.add(value)
            yield label, Candidate(candidate.kind, (value,)), feedback_used


# 系数按 x^4、x^3*y、x^2*y^2、x*y^3、y^4 排列。
TARGET = (1, -1, 0, -1, 1)
SQUARE_BASES = ((1, -4, 6, -4, 1), (1, 0, -2, 0, 1))


def proof_evaluate(candidate):
    a, b = candidate.value
    if a < 0 or b < 0:
        return {"valid": False, "reason": "A negative square coefficient cannot prove nonnegativity.",
                "metrics": {"coefficients": candidate.value}}
    expanded = tuple(a * u + b * v for u, v in zip(*SQUARE_BASES))
    difference = tuple(actual - target for actual, target in zip(expanded, TARGET))
    error = sum(abs(value) for value in difference)
    exact = error == 0
    return {
        "valid": True,
        "rank": (-error,),
        "reason": "Exact polynomial identity established." if exact else "The proposed identity has unmatched coefficients.",
        "metrics": {"coefficient_error": error, "coefficient_difference": difference, "a": a, "b": b},
        "mathematical_check": {
            "status": "exact_sos_identity" if exact else "unproved",
            "scope": "All real x and y; rational polynomial expansion, no proof assistant.",
            "identity": "x^4 + y^4 - x^3*y - x*y^3 = a*(x-y)^4 + b*(x^2-y^2)^2",
        },
    }


def proof_mutate(candidate, evaluation, history):
    difference = evaluation["metrics"]["coefficient_difference"]
    monomials = ("x^4", "x^3*y", "x^2*y^2", "x*y^3", "y^4")
    # 先通过混合单项式确定 a，再修正其他系数。
    for index, (name, order) in enumerate((("a", (1, 3, 2, 0, 4)), ("b", (2, 0, 4)))):
        for coordinate in order:
            basis_coefficient = SQUARE_BASES[index][coordinate]
            if difference[coordinate] and basis_coefficient:
                correction = -difference[coordinate] / basis_coefficient
                change = min(abs(correction), Fraction(1, 8)) * (1 if correction > 0 else -1)
                values = list(candidate.value)
                values[index] += change
                yield f"change {name} by {change} to reduce the {monomials[coordinate]} mismatch", Candidate(candidate.kind, tuple(values)), {
                    "source": "coefficient_difference", "monomial": monomials[coordinate],
                    "difference": difference[coordinate], "basis_coefficient": basis_coefficient,
                    "reason": evaluation["reason"],
                }
                break


def connected(vertices, edges):
    reached = {0}
    while True:
        new = reached | {v for edge in edges if reached.intersection(edge) for v in edge}
        if new == reached:
            return len(reached) == vertices
        reached = new


def normalize_graph(candidate):
    if candidate.kind != "graph" or not isinstance(candidate.value, (tuple, list)) or len(candidate.value) != 2:
        raise ValueError("A graph Candidate must contain a vertex count and an edge list.")
    vertices, edge_list = candidate.value
    if type(vertices) is not int or vertices < 3:
        raise ValueError("The conjecture requires an integer vertex count n >= 3.")
    if not isinstance(edge_list, (tuple, list)):
        raise ValueError("Graph edges must be a list or tuple of endpoint pairs.")
    normalized = set()
    for edge in edge_list:
        if not isinstance(edge, (tuple, list)) or len(edge) != 2:
            raise ValueError(f"An edge must have two endpoints: {edge!r}.")
        if any(type(vertex) is not int or not 0 <= vertex < vertices for vertex in edge):
            raise ValueError(f"Edge endpoints must be integer vertices in [0, {vertices}): {edge!r}.")
        if edge[0] == edge[1]:
            raise ValueError(f"A simple graph cannot contain a self-loop: {edge!r}.")
        pair = tuple(sorted(edge))
        if pair in normalized:
            raise ValueError(f"A simple graph cannot repeat the undirected edge {pair!r}.")
        normalized.add(pair)
    return vertices, tuple(sorted(normalized))


def counterexample_evaluate(candidate):
    vertices, edge_tuple = normalize_graph(candidate)
    edges = set(edge_tuple)
    degrees = tuple(sum(vertex in edge for edge in edges) for vertex in range(vertices))
    violations = []
    if len(edges) < vertices:
        violations.append("too_few_edges")
    if not connected(vertices, edges):
        violations.append("disconnected")
    if violations:
        return {
            "valid": False,
            "reason": "The graph fails the conjecture assumptions: " + "; ".join(
                "the graph is disconnected" if violation == "disconnected" else "there are fewer than n edges"
                for violation in violations
            ) + ".",
            "violations": violations,
            "metrics": {"vertices": vertices, "edges": len(edges), "degrees": degrees},
        }
    cycles = 0
    # 固定顶点 0，排除反向重复，枚举全部环路。
    for order in permutations(range(1, vertices)):
        if order[0] > order[-1]:
            continue
        route = (0,) + order + (0,)
        if all(tuple(sorted((u, v))) in edges for u, v in zip(route, route[1:])):
            cycles += 1
    leaf = next((v for v, degree in enumerate(degrees) if degree == 1), None)
    found = cycles == 0
    return {
        "valid": True,
        "rank": (-cycles, -len(edges)),
        "reason": "Connected graph with m >= n and no Hamiltonian cycle." if found else "A Hamiltonian cycle still exists.",
        "metrics": {"vertices": vertices, "edges": len(edges), "hamiltonian_cycles": cycles, "degrees": degrees},
        "mathematical_check": {
            "status": "counterexample_verified" if found else "not_a_counterexample",
            "exhaustive_cycle_enumeration": True,
            "independent_witness": f"Vertex {leaf} has degree 1, but every vertex on a cycle has degree at least 2."
            if leaf is not None else None,
            "scope": f"The concrete simple undirected graph on {vertices} vertices.",
        },
    }


def counterexample_mutate(candidate, evaluation, history):
    vertices, edges = normalize_graph(candidate)
    if evaluation["metrics"]["edges"] <= vertices:
        return
    preserve = {}
    for previous in history:
        for proposal in previous["proposals"]:
            result = proposal["evaluation"]
            if "disconnected" in result.get("violations", []):
                removed = set(normalize_graph(previous["parent"])[1]) - set(normalize_graph(proposal["candidate"])[1])
                for edge in removed:
                    preserve[edge] = {"edge": edge, "round": previous["round"], "reason": result["reason"]}
    degrees = evaluation["metrics"]["degrees"]
    for edge in sorted(edges, key=lambda edge: (min(degrees[v] for v in edge), edge)):
        if edge not in preserve:
            yield f"remove edge {edge}", Candidate(candidate.kind, (vertices, tuple(e for e in edges if e != edge))), {
                "source": "current_degrees_and_failed_candidates", "endpoint_degrees": tuple(degrees[v] for v in edge),
                "preserved_edges": list(preserve.values()), "reason": evaluation["reason"],
            }


def encode(value):
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, Candidate):
        return {"kind": value.kind, "value": encode(value.value)}
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [encode(item) for item in value]
    return value


def evolve(initial, mutate, evaluate, rounds):
    current = initial
    evaluation = evaluate(current)
    baseline = {"candidate": current, "evaluation": evaluation}
    history = []
    for round_number in range(1, rounds + 1):
        best, best_evaluation = current, evaluation
        proposals = []
        best_proposal = None
        for mutation, candidate, feedback_used in mutate(current, evaluation, history):
            result = evaluate(candidate)
            proposals.append({"mutation": mutation, "feedback_used": feedback_used, "candidate": candidate, "evaluation": result})
            if result["valid"] and result["rank"] > best_evaluation["rank"]:
                best, best_evaluation = candidate, result
                best_proposal = len(proposals) - 1
        for index, proposal in enumerate(proposals):
            result = proposal["evaluation"]
            proposal["feedback"] = (
                "Selected for the next round." if index == best_proposal else
                result["reason"] if not result["valid"] else
                "No strict improvement over the selected candidate; use the metric details to refine the next proposal."
            )
        history.append({"round": round_number, "parent": current, "proposals": proposals,
                        "selected_proposal": best_proposal, "improved": best != current})
        if best == current:
            break
        current, evaluation = best, best_evaluation
    return {"baseline": baseline, "rounds": history, "best": {"candidate": current, "evaluation": evaluate(current)}}


def main():
    parser = argparse.ArgumentParser(description="Run three exact finite mathematical searches.")
    parser.add_argument("--case", choices=("algorithm", "proof", "counterexample", "all"), default="all")
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--output", type=Path, help="Write the computed candidates and feedback as JSON.")
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("--rounds must be positive")
    cases = {
        "algorithm": (Candidate("gradient_step", (Fraction(1, 64),)), algorithm_mutate, algorithm_evaluate),
        "proof": (Candidate("sos_proof", (Fraction(0), Fraction(0))), proof_mutate, proof_evaluate),
        "counterexample": (Candidate("graph", (5, tuple((u, v) for u in range(5) for v in range(u + 1, 5)))),
                           counterexample_mutate, counterexample_evaluate),
    }
    selected = cases if args.case == "all" else {args.case: cases[args.case]}
    results = {name: evolve(*parameters, args.rounds) for name, parameters in selected.items()}
    for name, result in results.items():
        best = result["best"]["evaluation"]
        status = best.get("mathematical_check", {}).get("status")
        if name == "algorithm":
            reached = best["valid"] and status == "spectral_bound_checked" and best["rank"] > result["baseline"]["evaluation"]["rank"]
        elif name == "proof":
            reached = best["valid"] and status == "exact_sos_identity"
        else:
            reached = best["valid"] and status == "counterexample_verified"
        result["target_reached"] = reached
    report = {"search_backend": "deterministic_local_search", "llm_or_openevolve_run": False,
              "target_reached": all(result["target_reached"] for result in results.values()), "cases": results}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(encode(report), indent=2) + "\n")
    summary = {"search_backend": report["search_backend"], "llm_or_openevolve_run": False,
               "target_reached": report["target_reached"], "cases": {
        name: {"target_reached": result["target_reached"], "rounds_evaluated": len(result["rounds"]),
               "improving_rounds": sum(item["improved"] for item in result["rounds"]),
               "baseline_metrics": result["baseline"]["evaluation"]["metrics"],
               "best": result["best"]} for name, result in results.items()}}
    print(json.dumps(encode(summary if report["target_reached"] else report), indent=2))
    return 0 if report["target_reached"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
