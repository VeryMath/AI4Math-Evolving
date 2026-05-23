# Troubleshooting

## Missing Files

Run `scripts/validate_project.py` and repair only the reported files.

## Missing Metrics

Check that `evaluator.py` returns a numeric `combined_score` metric.

## API Key Errors

Confirm the provider key is in the environment. Use `${LLM_API_KEY}` or `${DEEPSEEK_API_KEY}` in `config.yaml`; do not paste plaintext keys.

## No Best Result

Inspect `logs/`, `checkpoints/`, and `best/`. A failed evaluator often prevents best artifacts from being written.
