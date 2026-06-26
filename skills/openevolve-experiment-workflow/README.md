# OpenEvolve Experiment Workflow

Chinese guide: [README.zh-CN.md](README.zh-CN.md)

`openevolve-experiment-workflow` helps a coding agent run controlled OpenEvolve experiment sessions for code or prompt search.

## When To Use It

Use this skill when you have:

- code or prompts that can be scored by a metric;
- an existing OpenEvolve project that needs inspection, repair, or a bounded run;
- a research goal that can be turned into a starter project and evaluator;
- API or runtime risk that should be checked before expensive search.

## What It Produces

The agent should produce workspace state, dry-run plans, short-probe logs, metrics, checkpoints, best-program artifacts, and next-step recommendations.

## Installation

Copy this to your coding agent:

```text
Please install the `openevolve-experiment-workflow` skill from https://github.com/VeryMath/AI4Math-Evolving.git. Read the package `SKILL.md`, install the declared Skill entrypoint, verify that `$openevolve-experiment-workflow` is discoverable, and tell me whether I need to restart the agent.
```

If you already have this skill repository locally, replace the repository URL
with the local folder path. The coding agent should handle cloning, linking,
configuration, reload/restart checks, and verification.

## Quick Start

Give the goal to your coding agent:

```text
Use this repository's OpenEvolve experiment workflow.

My goal is: <describe the optimization problem, algorithm idea, benchmark, or research objective>.

Inspect the workspace first, configure a runnable OpenEvolve environment, keep the first run small, and ask before any long or expensive search.
```

For an existing OpenEvolve project, also give the project path and the metric or behavior you care about. For a new project, just describe the target; the coding agent should create or select the workspace and starter project.

## How To Interact

Use a checkpoint loop:

```text
goal -> workspace inspection -> dry-run plan -> approve / revise / reject / skip
     -> approved probe -> evidence summary -> next checkpoint
```

Use `approve` to run a proposed step, `revise` to update the plan, `reject` to
stop the path, and `skip` to move past a phase. The agent should ask before API
spend, long runs, source edits, dependency changes, or final claims.

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

- `skills/openevolve-experiment-workflow/SKILL.md`: the interaction contract for goal-driven AI4Math-Evolving sessions.
- `skills/openevolve-experiment-workflow/scripts/`: internal helper scripts for validation, dry runs, run summaries, and session state.
- `skills/openevolve-experiment-workflow/references/`: focused references for project format and troubleshooting.
- `examples/`: package-level runnable examples, including the main project files needed to understand and rerun each case.

## Smoke Check

The scripts are internal helpers for agents, but the repository can be checked directly:

```bash
python3 skills/openevolve-experiment-workflow/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json init
python3 skills/openevolve-experiment-workflow/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json next
python3 -m unittest discover -s tests -v
```
