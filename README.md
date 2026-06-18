# AI4Math-Evolving Skill

Chinese guide: [README.zh-CN.md](README.zh-CN.md)

`openevolve-coding-agent` is a coding-agent skill for interactive AI4Math/OpenEvolve experiment sessions. It is meant to be installed and operated by a coding agent: the agent reads the project, sets up the runnable environment, asks only decision-changing questions, runs small probes before expensive searches, and keeps API keys out of files.

## AI4Math Role

This skill is the experiment-improvement loop in the AI4Math stack. Use it when
a conjecture, proof strategy, optimization formulation, evaluator, or scientific
computing workflow needs controlled search over code or prompts with measurable
feedback. It is strongest after another skill has already produced a concrete
artifact to improve.

## Handoff

Typical upstream inputs come from `paper-to-skill`, `discover-math-problems`,
`agentic-rethlas-proving`, optimization Skills, or computational reproduction
runs. Handoff artifacts should name the target metric, budget, evaluator,
starter files, and acceptance threshold. Return best-program artifacts, logs,
metrics, and next-iteration recommendations to the originating skill.
Best-program artifacts and improved metrics are search evidence, not proof. If
an evolved result suggests a theorem or proof obligation, route it to
`agentic-rethlas-proving` or `AI4Math-Lean-Agents`.

## Installation / Loading

Use the repository checkout first. Ask your coding agent to read:

```text
AGENTS.md
SKILL.md
openevolve-coding-agent/SKILL.md
```

If your agent supports local Skill discovery, install or link
`openevolve-coding-agent/` into that agent's Skill path and reload the agent if
needed. Platform-specific notes live in `CLAUDE.md`, `GEMINI.md`,
`.codex/INSTALL.md`, and `.opencode/INSTALL.md`.

To install from a remote repository, give your coding agent this prompt:

```text
Install the `openevolve-coding-agent` skill from https://github.com/VeryMath/AI4Math-Evolving into the coding agent environment I am using.

Please detect the target agent and its skill/config location, preserve existing configuration, install or link only what is needed, keep API keys out of files, verify that `openevolve-coding-agent/SKILL.md` is discoverable, and tell me whether I need to restart the target agent.
```

The installing agent should own the mechanics. If the target is OpenCode or another skill-aware agent, it should use that agent's native skill discovery path and verification command instead of asking you to edit config by hand.

## Quick Start

```text
Use this repository's AI4Math-Evolving workflow.

Read:
- AGENTS.md
- SKILL.md
- openevolve-coding-agent/SKILL.md

Goal:
<describe the optimization problem, algorithm idea, benchmark, or research objective>

Constraints:
- inspect first;
- keep the first run small;
- ask before long or expensive searches.
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
