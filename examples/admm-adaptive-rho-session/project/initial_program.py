"""Starter adaptive-rho strategy for LASSO ADMM.

OpenEvolve should modify only the code between the EVOLVE block markers.
The evaluator supplies scalar residual norms and a short history list.
"""

import math


# EVOLVE-BLOCK-START
def update_rho(rho, primal_residual, dual_residual, iteration, history):
    """Return the next positive ADMM penalty parameter.

    This starter uses the classic residual-balancing heuristic: increase rho
    when the primal residual dominates, decrease rho when the dual residual
    dominates, otherwise keep rho unchanged.
    """
    rho_value = float(rho)
    primal = max(float(primal_residual), 0.0)
    dual = max(float(dual_residual), 0.0)

    if not math.isfinite(rho_value) or rho_value <= 0.0:
        return 1.0
    if not math.isfinite(primal) or not math.isfinite(dual):
        return rho_value

    mu = 10.0
    tau = 2.0

    if primal > mu * max(dual, 1e-12):
        return rho_value * tau
    if dual > mu * max(primal, 1e-12):
        return rho_value / tau
    return rho_value
# EVOLVE-BLOCK-END


def run_search():
    """Return the evolvable strategy for lightweight project validators."""
    return update_rho
