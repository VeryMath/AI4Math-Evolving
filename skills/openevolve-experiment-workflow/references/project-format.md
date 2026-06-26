# OpenEvolve Project Format

Required files:

- `initial_program.py`: contains evolved code inside `EVOLVE-BLOCK-START` and `EVOLVE-BLOCK-END`.
- `evaluator.py`: defines `evaluate(program_path)` and returns numeric metrics.
- `config.yaml`: includes `max_iterations`, `checkpoint_interval`, model settings, database settings, and evaluator settings.

Recommended primary metric:

```yaml
combined_score: higher is better
```

Secrets must use environment placeholders:

```yaml
api_key: "${LLM_API_KEY}"
```

Legacy projects may use:

```yaml
api_key: "${DEEPSEEK_API_KEY}"
```
