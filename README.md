# AI4Math-Evolving Skill

An agent-native, coding-agent skill for turning an AI4Math/OpenEvolve goal into an interactive experiment session.

The skill helps a coding agent inspect an OpenEvolve project, validate its files, propose a small next experiment, run or monitor the search, summarize best metrics, and adapt from observed logs and artifacts.

## Contents

- `openevolve-coding-agent/SKILL.md`: interaction contract for goal-driven AI4Math-Evolving sessions.
- `openevolve-coding-agent/scripts/interactive_session.py`: internal session primitive for project state, validation, runs, logs, reads, and summaries.
- `openevolve-coding-agent/scripts/validate_project.py`: validates OpenEvolve project files.
- `openevolve-coding-agent/scripts/run_openevolve.py`: runs or dry-runs OpenEvolve directly.
- `openevolve-coding-agent/scripts/summarize_run.py`: extracts best metrics and artifacts from a run directory.

## Goal-Driven Usage

Use the skill conversationally:

> Use `$openevolve-coding-agent` to improve this project's search strategy. Start with a short baseline, keep API keys out of files, and ask me before running anything long.

The expected agent behavior is:

- infer the OpenEvolve project shape from files;
- validate and repair only relevant project issues;
- propose a small next experiment before spending runtime;
- run, inspect logs, summarize best metrics, and recommend the next move;
- incorporate user feedback into the next experiment.

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
