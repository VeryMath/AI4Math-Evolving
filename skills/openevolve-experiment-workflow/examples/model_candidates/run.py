import argparse
import asyncio
from datetime import datetime, timezone
import getpass
from importlib.metadata import version
import logging
import os
from pathlib import Path
import tempfile

import orjson
from openevolve.config import Config
from openevolve.controller import OpenEvolve

from candidate_evaluator import EVALUATORS, encode, evaluate_candidate, load_candidate, parse_candidate


HERE = Path(__file__).resolve().parent
TASKS = {
    "algorithm": (
        "Improve a constant rational gradient step for 12 iterations from all-ones vectors "
        "on diagonal quadratic objectives with spectra (1,2,4) and (1,3,9). "
        "Minimize the worst mean squared error. The step must satisfy 0 < step < 2/9. "
        'Keep kind="gradient_step" and value=["rational step"].'
    ),
    "proof": (
        "Prove x^4+y^4-x^3*y-x*y^3 >= 0 for all real x,y using "
        "a*(x-y)^4+b*(x^2-y^2)^2 with nonnegative rational a,b. "
        "Minimize the exact coefficient mismatch; only a zero mismatch proves the identity. "
        'Keep kind="sos_proof" and value=["rational a","rational b"].'
    ),
    "counterexample": (
        "Refute the statement that every connected simple undirected graph with n>=3 "
        "and m>=n has a Hamiltonian cycle. This task fixes n=5 and vertices 0,1,2,3,4. "
        "Find a connected graph with at least five edges and no Hamiltonian cycle; "
        "then prefer fewer edges. Edges are unique unordered integer endpoint pairs. "
        'Keep kind="graph" and value=[5,[[u,v],...]].'
    ),
}
TARGET_SCORES = {"algorithm": 0.995, "proof": 1.0, "counterexample": 1 / 1.05}


def make_config(case, model, base_url, api_key, iterations, output):
    return Config.from_dict({
        "max_iterations": iterations,
        "checkpoint_interval": 1,
        "random_seed": None,
        "language": "json",
        "file_suffix": ".json",
        "diff_based_evolution": False,
        "max_code_length": 8000,
        "llm": {
            "api_base": base_url, "api_key": api_key,
            "models": [{"name": model, "weight": 1.0}],
            "temperature": 0.2, "max_tokens": 4096, "timeout": 120, "retries": 0,
        },
        "prompt": {
            "system_message": TASKS[case] + " Read the fixed evaluator feedback. "
                "Return only one complete JSON object in a fenced json block. "
                "Keep its fields and kind unchanged. All fractions are strings. "
                "The candidate is data; do not return executable code or alter the evaluator.",
            "include_artifacts": True, "use_template_stochasticity": False,
            "num_top_programs": 1, "num_diverse_programs": 0,
        },
        "database": {"num_islands": 1, "population_size": 16, "archive_size": 16,
                     "random_seed": None, "log_prompts": True},
        "evaluator": {"cascade_evaluation": False, "parallel_evaluations": 1,
                      "max_retries": 0, "use_llm_feedback": False, "timeout": 10},
        "evolution_trace": {"enabled": True, "include_code": True,
                            "include_prompts": True, "buffer_size": 1,
                            "output_path": str(output / "evolution_trace.jsonl")},
    })


def proposal_feedback(programs, case):
    feedback = []
    for program in programs:
        if program.parent_id is not None:
            candidate = orjson.loads(program.code)
            result = EVALUATORS[case](parse_candidate(candidate, case))
            feedback.append({"candidate": candidate, "evaluation": encode(result)})
    return feedback


async def run_case(case, args, api_key):
    initial = HERE / f"{case}.json"
    baseline = evaluate_candidate(initial, case)
    checkpoint = None
    feedback = []
    for round_number in range(1, args.iterations + 1):
        output = args.output / case / f"round-{round_number}"
        config = make_config(case, args.model, args.base_url, api_key, 1, output)
        if feedback:
            config.prompt.system_message += "\nPreviously evaluated proposals and fixed mathematical feedback:\n"
            config.prompt.system_message += orjson.dumps(feedback).decode("utf-8")
        controller = OpenEvolve(str(initial), str(HERE / f"{case}_evaluator.py"),
                                config=config, output_dir=str(output))
        best = await controller.run(iterations=1, checkpoint_path=checkpoint)
        if best is None:
            raise RuntimeError(f"OpenEvolve returned no candidate for {case}.")
        programs = sorted(controller.database.programs.values(), key=lambda p: p.iteration_found)
        children = [p for p in programs if p.parent_id is not None]
        if len(children) != round_number:
            raise RuntimeError(f"A generation failed for {case}; inspect the local run logs.")
        if any("combined_score" not in p.metrics or "error" in p.metrics for p in programs):
            raise RuntimeError(f"An evaluator failed for {case}; inspect the local run logs.")
        checkpoint = str(output / "checkpoints" / f"checkpoint_{round_number}")
        if not Path(checkpoint).is_dir():
            raise RuntimeError(f"The OpenEvolve checkpoint is missing for round {round_number}.")
        feedback = proposal_feedback(programs, case)
        # 每次只生成一个候选，确保下一次生成能够读取当前评估和失败信息。
        for handler in list(logging.getLogger().handlers):
            handler.close()
            logging.getLogger().removeHandler(handler)
        if best.metrics["combined_score"] >= TARGET_SCORES[case]:
            break
    best_path = output / "best" / "best_program.json"
    checked = evaluate_candidate(best_path, case)
    if checked.metrics != best.metrics:
        raise RuntimeError(f"Independent re-evaluation disagrees with stored metrics for {case}.")
    candidate = load_candidate(best_path, case)
    result = {
        "target_reached": bool(checked.metrics["target_reached"]),
        "model_candidates_evaluated": len(children),
        "baseline": baseline.metrics,
        "best_candidate": encode(candidate),
        "best_metrics": checked.metrics,
        "mathematical_evaluation": encode(EVALUATORS[case](candidate)),
        "proposals": [{"iteration": p.iteration_found, "id": p.id,
                       "parent_id": p.parent_id, "candidate": orjson.loads(p.code),
                       "metrics": p.metrics, "token_usage": p.metadata.get("token_usage")}
                      for p in children],
    }
    return result


async def run(args, api_key):
    cases = list(TASKS) if args.case == "all" else [args.case]
    report = {"search_backend": "openevolve_model_generated_json",
              "model": args.model, "openevolve_version": version("openevolve"),
              "timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "iteration_limit_per_case": args.iterations,
              "requested_cases": cases, "cases": {}, "target_reached": False}
    args.output.mkdir(parents=True, exist_ok=True)
    temporary = args.output / "temporary"
    temporary.mkdir(exist_ok=True)
    os.environ["TMPDIR"] = str(temporary.resolve())
    tempfile.tempdir = str(temporary.resolve())
    for case in cases:
        report["cases"][case] = await run_case(case, args, api_key)
        report["target_reached"] = (len(report["cases"]) == len(cases)
                                    and all(v["target_reached"] for v in report["cases"].values()))
        (args.output / "verification.json").write_bytes(orjson.dumps(report, option=orjson.OPT_INDENT_2) + b"\n")
    print(orjson.dumps(report, option=orjson.OPT_INDENT_2).decode("utf-8"))
    return 0 if report["target_reached"] else 1


def main():
    parser = argparse.ArgumentParser(description="Evolve mathematical JSON candidates with a real model.")
    parser.add_argument("--case", choices=(*TASKS, "all"), default="all")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=os.environ.get("LLM_MODEL_ID"))
    parser.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL"))
    args = parser.parse_args()
    if args.iterations < 1 or not args.model or not args.base_url:
        parser.error("Positive iterations, a model, and a base URL are required.")
    args.output = args.output.resolve()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Use a new output directory so earlier run evidence is preserved.")
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        api_key = getpass.getpass("LLM_API_KEY (hidden input): ")
    if not api_key:
        parser.error("A provider API key is required.")
    return asyncio.run(run(args, api_key))


if __name__ == "__main__":
    raise SystemExit(main())
