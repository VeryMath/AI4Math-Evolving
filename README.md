# AI4Math-Evolving Skill

An agent-native, coding-agent skill for turning an AI4Math/OpenEvolve goal into an interactive experiment session.

The skill helps a coding agent inspect an OpenEvolve project, validate its files, propose a small next experiment, run or monitor the search, summarize best metrics, and adapt from observed logs and artifacts.

## Contents

- `openevolve-coding-agent/SKILL.md`: interaction contract for goal-driven AI4Math-Evolving sessions.
- `openevolve-coding-agent/scripts/interactive_session.py`: internal session primitive for project state, validation, runs, logs, reads, and summaries.
- `openevolve-coding-agent/scripts/validate_project.py`: validates OpenEvolve project files.
- `openevolve-coding-agent/scripts/run_openevolve.py`: runs or dry-runs OpenEvolve directly.
- `openevolve-coding-agent/scripts/summarize_run.py`: extracts best metrics and artifacts from a run directory.
- `examples/`: repository-level examples. Each example should be a self-contained case package with a narrative README and the main runnable project files.

## New User Onboarding Path

Use the skill conversationally:

> Use `$openevolve-coding-agent` to turn my optimization goal into a runnable OpenEvolve project. Start small, keep API keys out of files, and ask me before running anything long.

For a user who starts with only a goal, the expected agent behavior is:

- turn the goal into an objective metric, run budget, and expected artifact;
- configure the runnable environment first: workspace, Python/OpenEvolve CLI, API environment variable, model, and base URL;
- create or select a visible workspace, defaulting to `~/Desktop/AI4Math-Evolving` when no better project path is known;
- create or select a starter OpenEvolve project when needed;
- validate and repair only relevant project issues;
- build a dry-run command before spending runtime;
- run, inspect logs, summarize best metrics, and recommend the next move;
- incorporate user feedback into the next experiment.

## Examples

Examples live at the repository root under `examples/`, not inside the skill runtime directory. A useful example should include the main project files needed to understand and rerun the case, such as `initial_program.py`, `evaluator.py`, `config.yaml`, tests, and a README. Generated run directories and plaintext API keys should not be committed.

## Internal Tooling

The scripts are deliberately kept as internal primitives for agents and tests. For manual smoke checks, use JSON output:

```bash
python3 openevolve-coding-agent/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json init
python3 openevolve-coding-agent/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json next
```

## Test

```bash
python3 -m unittest discover -s tests -v
```
