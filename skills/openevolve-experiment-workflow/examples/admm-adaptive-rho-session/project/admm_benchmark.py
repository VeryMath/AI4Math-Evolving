"""Deterministic LASSO ADMM benchmark for evolving adaptive rho rules."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import math
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

import numpy as np


RHO_MIN = 1e-4
RHO_MAX = 1e4
ABS_TOL = 1e-4
REL_TOL = 1e-3
MAX_ITERS = 180
REFERENCE_ITERS = 700


UpdateFn = Callable[[float, float, float, int, List[Dict[str, float]]], float]


@dataclass(frozen=True)
class LassoInstance:
    name: str
    a_matrix: np.ndarray
    b_vector: np.ndarray
    lam: float


@dataclass
class RunResult:
    converged: bool
    iterations: int
    objective: float
    final_primal: float
    final_dual: float
    rho_min: float
    rho_max: float
    clipped_updates: int
    update_errors: int
    max_iters: int


def soft_threshold(values: np.ndarray, threshold: float) -> np.ndarray:
    return np.sign(values) * np.maximum(np.abs(values) - threshold, 0.0)


def lasso_objective(instance: LassoInstance, x_vector: np.ndarray) -> float:
    residual = instance.a_matrix @ x_vector - instance.b_vector
    return float(0.5 * np.dot(residual, residual) + instance.lam * np.linalg.norm(x_vector, 1))


def _make_matrix(rng: np.random.Generator, rows: int, cols: int, condition: float) -> np.ndarray:
    left, _ = np.linalg.qr(rng.normal(size=(rows, cols)))
    right, _ = np.linalg.qr(rng.normal(size=(cols, cols)))
    singular_values = np.geomspace(condition, 1.0, cols)
    return ((left * singular_values) @ right.T) / math.sqrt(rows)


def _make_instance(
    seed: int,
    rows: int,
    cols: int,
    condition: float,
    sparsity: float,
    noise: float,
    lam_scale: float,
) -> LassoInstance:
    rng = np.random.default_rng(seed)
    a_matrix = _make_matrix(rng, rows, cols, condition)

    x_true = np.zeros(cols)
    support_size = max(1, int(round(cols * sparsity)))
    support = rng.choice(cols, size=support_size, replace=False)
    x_true[support] = rng.normal(loc=0.0, scale=1.0, size=support_size)

    clean_b = a_matrix @ x_true
    clean_norm = max(float(np.linalg.norm(clean_b)), 1.0)
    b_vector = clean_b + noise * clean_norm / math.sqrt(rows) * rng.normal(size=rows)

    lam = lam_scale * max(float(np.max(np.abs(a_matrix.T @ b_vector))), 1e-8)
    name = f"seed{seed}_cond{condition:g}_s{sparsity:g}_n{noise:g}_l{lam_scale:g}"
    return LassoInstance(name=name, a_matrix=a_matrix, b_vector=b_vector, lam=lam)


def generate_lasso_instances() -> List[LassoInstance]:
    configs = [
        (11, 36, 24, 3.0, 0.18, 0.00, 0.055),
        (17, 40, 26, 12.0, 0.15, 0.01, 0.065),
        (23, 44, 28, 45.0, 0.12, 0.02, 0.075),
        (31, 48, 30, 90.0, 0.20, 0.01, 0.060),
        (43, 42, 24, 25.0, 0.25, 0.03, 0.080),
        (59, 50, 32, 120.0, 0.16, 0.02, 0.070),
    ]
    return [_make_instance(*config) for config in configs]


def load_update_function(program_path: str | Path) -> UpdateFn:
    path = Path(program_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"candidate program not found: {path}")

    module_name = f"candidate_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load candidate module from {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    update_fn = getattr(module, "update_rho", None)
    if not callable(update_fn):
        raise AttributeError("candidate program must define callable update_rho")
    return update_fn


def fixed_update_rho(
    rho: float,
    primal_residual: float,
    dual_residual: float,
    iteration: int,
    history: List[Dict[str, float]],
) -> float:
    return rho


def boyd_update_rho(
    rho: float,
    primal_residual: float,
    dual_residual: float,
    iteration: int,
    history: List[Dict[str, float]],
) -> float:
    mu = 10.0
    tau = 2.0
    primal = max(float(primal_residual), 0.0)
    dual = max(float(dual_residual), 0.0)
    if primal > mu * max(dual, 1e-12):
        return rho * tau
    if dual > mu * max(primal, 1e-12):
        return rho / tau
    return rho


def _safe_update(
    update_fn: UpdateFn,
    rho: float,
    primal_residual: float,
    dual_residual: float,
    iteration: int,
    history: List[Dict[str, float]],
) -> Tuple[float, bool, bool]:
    try:
        raw_value = update_fn(
            float(rho),
            float(primal_residual),
            float(dual_residual),
            int(iteration),
            list(history[-20:]),
        )
        proposed = float(raw_value)
    except Exception:
        return rho, True, True

    if not math.isfinite(proposed) or proposed <= 0.0:
        return rho, True, True

    clipped = min(max(proposed, RHO_MIN), RHO_MAX)
    was_clipped = clipped != proposed
    return clipped, was_clipped, False


def run_admm(
    instance: LassoInstance,
    update_fn: UpdateFn,
    max_iters: int = MAX_ITERS,
    rho0: float = 1.0,
) -> RunResult:
    a_matrix = instance.a_matrix
    b_vector = instance.b_vector
    lam = instance.lam
    _, cols = a_matrix.shape
    ata = a_matrix.T @ a_matrix
    atb = a_matrix.T @ b_vector
    identity = np.eye(cols)

    x_vector = np.zeros(cols)
    z_vector = np.zeros(cols)
    u_vector = np.zeros(cols)
    rho = float(rho0)
    rho_low = rho
    rho_high = rho
    clipped_updates = 0
    update_errors = 0
    history: List[Dict[str, float]] = []
    objective = lasso_objective(instance, z_vector)
    primal_norm = math.inf
    dual_norm = math.inf

    for iteration in range(1, max_iters + 1):
        z_previous = z_vector.copy()

        system_matrix = ata + rho * identity
        rhs = atb + rho * (z_vector - u_vector)
        try:
            x_vector = np.linalg.solve(system_matrix, rhs)
        except np.linalg.LinAlgError:
            x_vector = np.linalg.lstsq(system_matrix, rhs, rcond=None)[0]

        z_vector = soft_threshold(x_vector + u_vector, lam / rho)
        u_vector = u_vector + x_vector - z_vector

        primal_norm = float(np.linalg.norm(x_vector - z_vector))
        dual_norm = float(np.linalg.norm(rho * (z_vector - z_previous)))
        objective = lasso_objective(instance, z_vector)

        eps_primal = math.sqrt(cols) * ABS_TOL + REL_TOL * max(
            float(np.linalg.norm(x_vector)),
            float(np.linalg.norm(z_vector)),
        )
        eps_dual = math.sqrt(cols) * ABS_TOL + REL_TOL * float(np.linalg.norm(rho * u_vector))

        history.append(
            {
                "iteration": float(iteration),
                "rho": float(rho),
                "primal_residual": primal_norm,
                "dual_residual": dual_norm,
                "objective": objective,
            }
        )

        if not all(math.isfinite(value) for value in (primal_norm, dual_norm, objective, rho)):
            return RunResult(
                converged=False,
                iterations=iteration,
                objective=float("inf"),
                final_primal=float("inf"),
                final_dual=float("inf"),
                rho_min=rho_low,
                rho_max=rho_high,
                clipped_updates=clipped_updates + 1,
                update_errors=update_errors + 1,
                max_iters=max_iters,
            )

        if primal_norm <= eps_primal and dual_norm <= eps_dual:
            return RunResult(
                converged=True,
                iterations=iteration,
                objective=objective,
                final_primal=primal_norm,
                final_dual=dual_norm,
                rho_min=rho_low,
                rho_max=rho_high,
                clipped_updates=clipped_updates,
                update_errors=update_errors,
                max_iters=max_iters,
            )

        new_rho, was_clipped, had_error = _safe_update(
            update_fn,
            rho,
            primal_norm,
            dual_norm,
            iteration,
            history,
        )
        if was_clipped:
            clipped_updates += 1
        if had_error:
            update_errors += 1

        if new_rho != rho:
            u_vector = (rho / new_rho) * u_vector
            rho = new_rho
            rho_low = min(rho_low, rho)
            rho_high = max(rho_high, rho)

    return RunResult(
        converged=False,
        iterations=max_iters,
        objective=objective,
        final_primal=primal_norm,
        final_dual=dual_norm,
        rho_min=rho_low,
        rho_max=rho_high,
        clipped_updates=clipped_updates,
        update_errors=update_errors,
        max_iters=max_iters,
    )


def _effective_iterations(result: RunResult) -> float:
    if result.converged:
        return float(result.iterations)
    return float(result.max_iters) * 1.5


def _relative_objective_gap(objective: float, reference_objective: float) -> float:
    if not math.isfinite(objective):
        return 10.0
    denominator = max(abs(reference_objective), 1e-8)
    return max(0.0, (objective - reference_objective) / denominator)


def _score_case(
    candidate: RunResult,
    fixed: RunResult,
    boyd: RunResult,
    reference_objective: float,
) -> Tuple[float, float]:
    baseline_effort = min(_effective_iterations(fixed), _effective_iterations(boyd))
    candidate_effort = _effective_iterations(candidate)
    speed_ratio = baseline_effort / max(candidate_effort, 1.0)
    speed_score = 0.5 + 0.5 * math.tanh(math.log(max(speed_ratio, 1e-9)))

    objective_gap = _relative_objective_gap(candidate.objective, reference_objective)
    accuracy_score = max(0.0, 1.0 - min(objective_gap * 20.0, 1.0))

    residual_scale = max(candidate.final_primal, candidate.final_dual, 0.0)
    residual_score = 1.0 / (1.0 + min(residual_scale, 100.0))

    convergence_score = 1.0 if candidate.converged else 0.25 * residual_score
    update_count = max(candidate.iterations, 1)
    clip_rate = candidate.clipped_updates / update_count
    error_rate = candidate.update_errors / update_count
    stability_score = max(0.0, 1.0 - 4.0 * clip_rate - 8.0 * error_rate)

    case_score = 100.0 * (
        0.45 * convergence_score
        + 0.25 * speed_score
        + 0.20 * accuracy_score
        + 0.10 * stability_score
    )
    return max(0.0, case_score), objective_gap


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def failure_metrics() -> Dict[str, float]:
    return {
        "combined_score": 0.0,
        "candidate_convergence_rate": 0.0,
        "candidate_mean_iterations": float(MAX_ITERS),
        "candidate_failure_rate": 1.0,
        "candidate_clip_rate": 1.0,
        "candidate_mean_relative_objective_gap": 10.0,
        "baseline_fixed_mean_iterations": float(MAX_ITERS),
        "baseline_boyd_mean_iterations": float(MAX_ITERS),
        "case_count": 0.0,
    }


def evaluate_update_function(update_fn: UpdateFn) -> Dict[str, float]:
    instances = generate_lasso_instances()
    case_scores: List[float] = []
    objective_gaps: List[float] = []
    candidate_results: List[RunResult] = []
    fixed_results: List[RunResult] = []
    boyd_results: List[RunResult] = []

    for instance in instances:
        fixed = run_admm(instance, fixed_update_rho)
        boyd = run_admm(instance, boyd_update_rho)
        reference = run_admm(instance, boyd_update_rho, max_iters=REFERENCE_ITERS)
        reference_objective = min(fixed.objective, boyd.objective, reference.objective)

        candidate = run_admm(instance, update_fn)
        score, objective_gap = _score_case(candidate, fixed, boyd, reference_objective)

        case_scores.append(score)
        objective_gaps.append(objective_gap)
        candidate_results.append(candidate)
        fixed_results.append(fixed)
        boyd_results.append(boyd)

    total_updates = max(sum(result.iterations for result in candidate_results), 1)
    total_clips = sum(result.clipped_updates for result in candidate_results)
    total_errors = sum(result.update_errors for result in candidate_results)
    failed_cases = sum(
        1
        for result in candidate_results
        if (not result.converged) or result.update_errors > 0 or not math.isfinite(result.objective)
    )

    combined_score = _mean(case_scores)
    error_penalty = 20.0 * (total_errors / total_updates)
    combined_score = max(0.0, combined_score - error_penalty)

    return {
        "combined_score": combined_score,
        "candidate_convergence_rate": _mean(
            1.0 if result.converged else 0.0 for result in candidate_results
        ),
        "candidate_mean_iterations": _mean(float(result.iterations) for result in candidate_results),
        "candidate_failure_rate": failed_cases / len(candidate_results),
        "candidate_clip_rate": total_clips / total_updates,
        "candidate_mean_relative_objective_gap": _mean(objective_gaps),
        "baseline_fixed_mean_iterations": _mean(float(result.iterations) for result in fixed_results),
        "baseline_boyd_mean_iterations": _mean(float(result.iterations) for result in boyd_results),
        "case_count": float(len(instances)),
    }


def evaluate_program(program_path: str | Path) -> Dict[str, float]:
    try:
        update_fn = load_update_function(program_path)
        return evaluate_update_function(update_fn)
    except Exception:
        return failure_metrics()
