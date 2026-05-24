# AI4Math-Evolving Skill

An agent-native skill for turning a user's AI4Math/OpenEvolve goal into an interactive coding-agent session.

This repository is the skill-first counterpart to the AI4Math-Evolving UI bridge. Its public experience is not a command checklist: a coding agent should understand the goal, inspect project state, ask for feedback when it matters, run or repair experiments, and adapt from observed metrics and logs.

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
