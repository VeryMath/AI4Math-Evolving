# AI4Math-Evolving Skill

Chinese guide: [README.zh-CN.md](README.zh-CN.md)

GitHub: <https://github.com/VeryMath/AI4Math-Evolving>

`openevolve-coding-agent` is a coding-agent skill for interactive AI4Math/OpenEvolve experiment sessions. It is meant to be installed and operated by a coding agent: the agent reads the project, sets up the runnable environment, asks only decision-changing questions, runs small probes before expensive searches, and keeps API keys out of files.

## 1. Install With Your Coding Agent

Give your coding agent this repository URL or this local checkout, then ask:

```text
Install the `openevolve-coding-agent` skill from https://github.com/VeryMath/AI4Math-Evolving into the coding agent environment I am using.

Please detect the target agent and its skill/config location, preserve existing configuration, install or link only what is needed, keep API keys out of files, verify that `openevolve-coding-agent/SKILL.md` is discoverable, and tell me whether I need to restart the target agent.
```

The installing agent should own the mechanics. If the target is OpenCode or another skill-aware agent, it should use that agent's native skill discovery path and verification command instead of asking you to edit config by hand.

## 2. Start An Interactive OpenEvolve Session

After installation, start by giving the coding agent your goal:

```text
Use $openevolve-coding-agent.

My goal is: <describe the optimization problem, algorithm idea, benchmark, or research objective>.

Please inspect the workspace first, set up the runnable OpenEvolve environment, keep the first run small, and ask me before any long or expensive run.
```

For an existing OpenEvolve project, also give the project path and the metric or behavior you care about. For a new project, just describe the target; the coding agent should create or select the workspace and starter project.

## What The Coding Agent Should Do

During a session, the agent should:

- inspect the workspace before asking project questions;
- check Python, the `openevolve` package, `openevolve-run`, API environment variables, model, and base URL;
- create or select a visible workspace, defaulting to `~/Desktop/AI4Math-Evolving` when no better path is known;
- inspect or create `initial_program.py`, `evaluator.py`, and `config.yaml`;
- validate the project and repair only directly relevant issues;
- build a dry-run command before spending API budget;
- run a short probe before a longer evolution search;
- inspect logs, metrics, checkpoints, and best-program artifacts;
- summarize what changed and propose the next concrete step.

## Project Contract

An OpenEvolve project usually contains:

- `initial_program.py` with `EVOLVE-BLOCK-START` and `EVOLVE-BLOCK-END`;
- `evaluator.py` with `evaluate(program_path)`;
- `config.yaml`, `config.yml`, or `config_default.yaml` with `max_iterations` and `checkpoint_interval`.

The skill should inspect nonstandard projects before forcing this shape.

## Repository Layout

- `openevolve-coding-agent/SKILL.md`: the interaction contract for goal-driven AI4Math-Evolving sessions.
- `openevolve-coding-agent/scripts/`: internal helper scripts for validation, dry runs, run summaries, and session state.
- `openevolve-coding-agent/references/`: focused references for project format and troubleshooting.
- `examples/`: repository-level runnable examples, including the main project files needed to understand and rerun each case.

## Smoke Check

The scripts are internal helpers for agents, but the repository can be checked directly:

```bash
python3 openevolve-coding-agent/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json init
python3 openevolve-coding-agent/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json next
python3 -m unittest discover -s tests -v
```
