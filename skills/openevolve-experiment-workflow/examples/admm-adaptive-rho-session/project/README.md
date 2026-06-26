# ADMM Adaptive Rho OpenEvolve Project

This project evolves `update_rho(...)`, an adaptive penalty update rule for two-block LASSO ADMM.

## Local Validation

Use a Python environment with `numpy`, `pytest`, and `openevolve` installed.

Run the contract tests:

```bash
cd examples/admm-adaptive-rho-session/project
PYTHONPATH=. python3 -m pytest tests/test_evaluator_contract.py -q
```

Run the evaluator without using the LLM API:

```bash
cd examples/admm-adaptive-rho-session/project
python3 evaluator.py
```

## Short OpenEvolve Probe

The API key must be provided through the `LLM_API_KEY` environment variable. The key is not stored in this project.

```bash
cd examples/admm-adaptive-rho-session/project
openevolve-run \
  initial_program.py \
  evaluator.py \
  --config config.yaml \
  --output runs/probe-001 \
  --iterations 10 \
  --log-level INFO
```
