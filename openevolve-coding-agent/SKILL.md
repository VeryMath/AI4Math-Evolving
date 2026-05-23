---
name: openevolve-coding-agent
description: Use when a coding agent needs to create, validate, run, repair, or summarize OpenEvolve projects with initial_program.py, evaluator.py, config.yaml, opencode adapters, checkpoints, metrics, or best-program artifacts.
---

# OpenEvolve Coding Agent

## Overview

Operate OpenEvolve projects from a coding-agent environment. Keep orchestration in scripts, repair only reported project files, and never put plaintext provider keys in project artifacts.

## Workflow

1. Inspect the project directory and identify `initial_program.py`, `evaluator.py`, and `config.yaml`.
2. Validate before running:

```bash
python openevolve-coding-agent/scripts/validate_project.py /path/to/project --json
```

3. If validation fails, repair only the files named in the validation report and validate again.
4. Run through the selected adapter. Use dry-run first when wiring a new UI or automation:

```bash
python openevolve-coding-agent/scripts/run_openevolve.py /path/to/project --mode opencode --iterations 10 --dry-run --json
```

5. Summarize the output directory after a run:

```bash
python openevolve-coding-agent/scripts/summarize_run.py /path/to/output --json
```

## Project Contract

An OpenEvolve project must contain:

- `initial_program.py` with `EVOLVE-BLOCK-START` and `EVOLVE-BLOCK-END`.
- `evaluator.py` with `evaluate(program_path)`.
- `config.yaml` with `max_iterations` and `checkpoint_interval`.

Provider credentials must come from environment placeholders such as `${LLM_API_KEY}` or `${DEEPSEEK_API_KEY}`. Do not write plaintext API keys into `config.yaml`, logs, generated examples, or summaries.

## References

- Read `references/project-format.md` when creating or repairing project files.
- Read `references/opencode-adapter.md` when using `--mode opencode`.
- Read `references/troubleshooting.md` when validation, execution, or metrics fail.
