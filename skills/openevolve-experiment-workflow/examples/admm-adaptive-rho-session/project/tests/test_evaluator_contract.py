import importlib.util
import math
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
INITIAL_FILE = PROJECT_DIR / "initial_program.py"
EVALUATOR_FILE = PROJECT_DIR / "evaluator.py"


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_initial_program_contract_and_evolve_block():
    text = INITIAL_FILE.read_text()
    assert "EVOLVE-BLOCK-START" in text
    assert "EVOLVE-BLOCK-END" in text

    module = load_module(INITIAL_FILE, "candidate_initial_program")
    assert callable(module.update_rho)
    assert callable(module.run_search)
    assert module.run_search() is module.update_rho

    new_rho = module.update_rho(
        rho=1.0,
        primal_residual=10.0,
        dual_residual=0.01,
        iteration=3,
        history=[],
    )

    assert isinstance(new_rho, (int, float))
    assert math.isfinite(float(new_rho))
    assert float(new_rho) > 0.0


def test_evaluator_returns_numeric_metrics_for_starter_program():
    evaluator = load_module(EVALUATOR_FILE, "admm_evaluator")
    metrics = evaluator.evaluate(str(INITIAL_FILE))

    required_keys = {
        "combined_score",
        "candidate_convergence_rate",
        "candidate_mean_iterations",
        "candidate_failure_rate",
        "candidate_clip_rate",
        "candidate_mean_relative_objective_gap",
        "baseline_fixed_mean_iterations",
        "baseline_boyd_mean_iterations",
        "case_count",
    }

    assert required_keys.issubset(metrics.keys())

    for key, value in metrics.items():
        assert isinstance(value, (int, float)), key
        assert math.isfinite(float(value)), key

    assert metrics["combined_score"] > 0.0
    assert 0.0 <= metrics["candidate_convergence_rate"] <= 1.0
    assert 0.0 <= metrics["candidate_failure_rate"] <= 1.0
    assert metrics["case_count"] >= 4


def test_starter_strategy_leaves_search_headroom():
    evaluator = load_module(EVALUATOR_FILE, "admm_evaluator_headroom")
    metrics = evaluator.evaluate(str(INITIAL_FILE))

    assert metrics["combined_score"] > 50.0
    assert metrics["combined_score"] < 95.0


def test_bad_strategy_is_penalized_not_crashed(tmp_path):
    evaluator = load_module(EVALUATOR_FILE, "admm_evaluator_bad_case")
    bad_program = tmp_path / "bad_program.py"
    bad_program.write_text(
        "def update_rho(rho, primal_residual, dual_residual, iteration, history):\n"
        "    return float('nan')\n"
    )

    good_metrics = evaluator.evaluate(str(INITIAL_FILE))
    bad_metrics = evaluator.evaluate(str(bad_program))

    assert bad_metrics["combined_score"] < good_metrics["combined_score"]
    assert bad_metrics["candidate_failure_rate"] >= good_metrics["candidate_failure_rate"]
    assert bad_metrics["candidate_clip_rate"] >= good_metrics["candidate_clip_rate"]
