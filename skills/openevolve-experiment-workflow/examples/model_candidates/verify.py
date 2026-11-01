import argparse
from pathlib import Path

import networkx
import orjson
import sympy


def verify_case(case, result):
    candidate = result["best_candidate"]
    kinds = {"algorithm": "gradient_step", "proof": "sos_proof", "counterexample": "graph"}
    if candidate["kind"] != kinds[case]:
        raise ValueError("The candidate kind disagrees with the fixed mathematical case.")
    if case == "algorithm":
        step = sympy.Rational(candidate["value"][0])
        if not 0 < step < sympy.Rational(2, 9):
            raise ValueError("The gradient step violates the spectral interval.")
        errors = []
        for spectrum in ((1, 2, 4), (1, 3, 9)):
            matrix = sympy.diag(*spectrum)
            state = (sympy.eye(3) - step*matrix)**12 * sympy.ones(3, 1)
            errors.append((state.T*state)[0] / 3)
        error = max(errors)
        recorded = sympy.Rational(result["mathematical_evaluation"]["metrics"]["worst_squared_error"])
        if error != recorded:
            raise ValueError("Independent matrix arithmetic disagrees with the recorded error.")
        baseline = max(sum((1-sympy.Rational(1, 64)*v)**24 for v in spectrum)/3
                       for spectrum in ((1, 2, 4), (1, 3, 9)))
        target = error < baseline
        check = {"worst_squared_error": str(error),
                 "contraction_bound": str(max(abs(1-step), abs(1-9*step)))}
    elif case == "proof":
        a, b = map(sympy.Rational, candidate["value"])
        x, y = sympy.symbols("x y", real=True)
        polynomial = x**4+y**4-x**3*y-x*y**3-a*(x-y)**4-b*(x*x-y*y)**2
        target = a >= 0 and b >= 0 and sympy.expand(polynomial) == 0
        check = {"exact_identity": bool(target), "weights": [str(a), str(b)]}
    elif case == "counterexample":
        count, edges = candidate["value"]
        graph = networkx.Graph()
        graph.add_nodes_from(range(count))
        graph.add_edges_from(edges)
        if (count != 5 or set(graph.nodes) != set(range(5))
                or graph.number_of_edges() != len(edges) or networkx.number_of_selfloops(graph)):
            raise ValueError("The graph representation is invalid.")
        cycles = sum(len(cycle) == count for cycle in networkx.simple_cycles(graph, length_bound=count))
        target = networkx.is_connected(graph) and len(edges) >= count and cycles == 0
        check = {"connected": networkx.is_connected(graph), "hamiltonian_cycles": cycles,
                 "edges": len(edges), "degrees": dict(graph.degree())}
    else:
        raise ValueError(f"Unknown mathematical case: {case}.")
    if bool(target) != result["target_reached"]:
        raise ValueError(f"Independent mathematical verification disagrees for {case}.")
    return check


def verify_run(directory):
    report = orjson.loads((directory / "verification.json").read_bytes())
    output = {"cases": {}, "model_calls": 0, "total_tokens": 0}
    for case, result in report["cases"].items():
        traces = []
        for path in sorted((directory / case).glob("round-*/evolution_trace.jsonl")):
            traces.extend(orjson.loads(line) for line in path.read_bytes().splitlines())
        traces.sort(key=lambda trace: trace["iteration"])
        if len(traces) != result["model_candidates_evaluated"]:
            raise ValueError(f"The actual trace count disagrees for {case}.")
        if not 1 <= len(traces) <= report["iteration_limit_per_case"]:
            raise ValueError(f"The model budget is invalid for {case}.")
        for index, (trace, proposal) in enumerate(zip(traces, result["proposals"], strict=True)):
            if trace["child_id"] != proposal["id"] or orjson.loads(trace["child_code"]) != proposal["candidate"]:
                raise ValueError(f"The model trace and reported candidate disagree for {case}.")
            for previous in traces[:index]:
                previous_object = orjson.dumps(orjson.loads(previous["child_code"])).decode("utf-8")
                if previous_object not in trace["prompt"]["system"]:
                    raise ValueError(f"Prior candidate feedback is missing from the next prompt for {case}.")
            usage = trace["metadata"]["token_usage"]
            if usage != proposal["token_usage"] or usage["total_tokens"] <= 0:
                raise ValueError(f"Recorded API token usage disagrees for {case}.")
            output["total_tokens"] += usage["total_tokens"]
        output["model_calls"] += len(traces)
        output["cases"][case] = verify_case(case, result)
    requested = report.get("requested_cases", list(report["cases"]))
    complete = (set(report["cases"]) == set(requested)
                and all(v["target_reached"] for v in report["cases"].values()))
    if report["target_reached"] != complete:
        raise ValueError("The overall mathematical status is inconsistent.")
    output["target_reached"] = report["target_reached"]
    return output


def main():
    parser = argparse.ArgumentParser(description="Independently verify actual model run artifacts.")
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    print(orjson.dumps(verify_run(args.run_directory), option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS).decode("utf-8"))


if __name__ == "__main__":
    main()
