---
name: openevolve-coding-agent
description: Use when a coding agent needs an interactive AI4Math-Evolving/OpenEvolve workflow to import, select, validate, configure, run, stop, inspect, repair, or summarize evolution projects with initial_program.py, evaluator.py, config.yaml, checkpoints, metrics, logs, or best-program artifacts.
---

# AI4Math-Evolving Coding Agent

## Overview

Operate OpenEvolve projects from a coding-agent environment. Prefer the interactive session CLI for multi-step work so project selection, run configuration, logs, outputs, and next actions stay in `.openevolve-agent/session.json`.

Keep orchestration in scripts, repair only reported project files, and never put plaintext provider keys in project artifacts.

## Workflow

1. Start or resume an interactive workspace:

```bash
python openevolve-coding-agent/scripts/interactive_session.py --workspace /path/to/workspace --json init
```

2. Import or select a project:

```bash
python openevolve-coding-agent/scripts/interactive_session.py --workspace /path/to/workspace --json import /path/to/project-or.zip --name my-project
```

3. Validate, repair only files named in the validation report, then validate again:

```bash
python openevolve-coding-agent/scripts/interactive_session.py --workspace /path/to/workspace --json validate
```

4. Configure and dry-run before starting a real run:

```bash
python openevolve-coding-agent/scripts/interactive_session.py --workspace /path/to/workspace --json configure --mode direct --iterations 10
python openevolve-coding-agent/scripts/interactive_session.py --workspace /path/to/workspace --json run --dry-run
```

5. Run, inspect logs, stop if needed, and summarize:

```bash
python openevolve-coding-agent/scripts/interactive_session.py --workspace /path/to/workspace --json run
python openevolve-coding-agent/scripts/interactive_session.py --workspace /path/to/workspace --json tail --lines 80
python openevolve-coding-agent/scripts/interactive_session.py --workspace /path/to/workspace --json summarize
```

6. Ask for the next recommended action at any point:

```bash
python openevolve-coding-agent/scripts/interactive_session.py --workspace /path/to/workspace --json next
```

## Project Contract

An OpenEvolve project must contain:

- `initial_program.py` with `EVOLVE-BLOCK-START` and `EVOLVE-BLOCK-END`.
- `evaluator.py` with `evaluate(program_path)`.
- `config.yaml`, `config.yml`, or `config_default.yaml` with `max_iterations` and `checkpoint_interval`.

Provider credentials must come from environment placeholders such as `${LLM_API_KEY}` or `${DEEPSEEK_API_KEY}`. Do not write plaintext API keys into `config.yaml`, logs, generated examples, or summaries.

## Script Surface

- `interactive_session.py`: stateful workflow commands: `init`, `import`, `select`, `validate`, `configure`, `run`, `status`, `tail`, `stop`, `tree`, `read`, `summarize`, `next`.
- `validate_project.py`: stateless project validation.
- `run_openevolve.py`: stateless direct/opencode command construction and execution.
- `summarize_run.py`: stateless best-artifact summarization.

## References

- Read `references/project-format.md` when creating or repairing project files.
- Read `references/opencode-adapter.md` when using `--mode opencode`.
- Read `references/troubleshooting.md` when validation, execution, or metrics fail.
