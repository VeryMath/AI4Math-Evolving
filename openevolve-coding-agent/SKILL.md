---
name: openevolve-coding-agent
description: Use when a coding agent is asked to pursue an interactive AI4Math-Evolving/OpenEvolve goal involving initial_program.py, evaluator.py, config.yaml, metrics, logs, checkpoints, best-program artifacts, or iterative user feedback.
---

# AI4Math-Evolving Coding Agent

## Overview

Turn a user's evolving goal into an agent-led OpenEvolve session. The user should experience a collaborative coding agent that understands intent, asks only necessary questions, edits project files when useful, runs experiments, observes results, and proposes the next move.

Use the bundled scripts as private tool primitives. Do not present the skill as a command menu unless the user explicitly asks for commands.

## Interaction Contract

- Start from the user's goal, not from a fixed sequence of commands. Restate the target metric, constraints, budget, and expected artifact when they are clear.
- Inspect the project before asking setup questions. Infer entry points, evaluator shape, config path, current results, and likely blockers from files and logs.
- Ask the user for feedback only when it changes a decision: objective tradeoffs, runtime budget, model/provider choice, acceptance threshold, or risky code changes.
- Make the next action explicit before starting a costly run: baseline, repair, short probe, full run, log inspection, result comparison, or stop.
- After each observation, decide what changed and what should happen next. Prefer "I found X, so I will do Y" over generic status updates.
- Keep secrets out of artifacts. Provider keys must stay in environment variables or placeholders, never plaintext config, logs, examples, or summaries.

## Capabilities

Use the skill to guide these agent-led tasks:

- Goal intake: turn a loose optimization or research request into an objective metric, run budget, and expected artifact.
- Project readiness: inspect, validate, and minimally repair `initial_program.py`, `evaluator.py`, and config files.
- Baseline run: start with a short probe or baseline before spending a larger search budget.
- Evolution search: launch direct OpenEvolve runs, track status, tail logs, stop runs, and preserve output directories.
- Result analysis: summarize best metrics, best-program artifacts, evaluator failures, and likely reasons a run stalled.
- Visualization data: extract metric series, checkpoint timelines, best-artifact paths, and log highlights for a UI or report without rendering the UI here.
- Iteration planning: use user feedback and observed metrics to decide whether to adjust code, evaluator, config, budget, or acceptance criteria.

## User Guidance

Guide the user through one decision at a time. Do not ask the user to choose from a command list; choose the next useful action yourself, explain why it is the right signal, and ask only for the decision that changes that action.

When a user gives an open-ended goal, guide them toward one crisp next experiment. Prefer short prompts such as:

- "I can run a short baseline first; what metric should count as success if the evaluator exposes several?"
- "This may spend API budget. Should I cap the first search to a small probe?"
- "The best score improved but the logs show evaluator noise. I can inspect the best program or tighten the evaluator next."

Do not ask for information already present in project files. When the user is unsure, choose conservative defaults, explain the assumption, and keep the first run small.

## Runtime/API Configuration

Before a real evolution run, inspect the config and environment together:

- If config already has `llm.api_key: "${VAR_NAME}"` and `VAR_NAME` is set in the environment, do not ask for the key again.
- If config has model and base URL but no `api_key`, propose adding an environment placeholder such as `${LLM_API_KEY}`.
- If config references `${VAR_NAME}` but the environment variable is missing, ask the user to export it or provide a local env setup. Do not ask them to paste secrets into tracked files.
- For ChatECNU-style OpenAI-compatible endpoints, a typical config is `api_base: "https://chat.ecnu.edu.cn/open/api/v1"`, `primary_model: "ecnu-plus"`, and `api_key: "${LLM_API_KEY}"`.

Do not write plaintext API keys into config, examples, logs, summaries, tests, or docs. It is fine to write placeholder names.

## Agent Decision Loop

1. **Understand**: identify the evolving goal, objective metric, constraints, and what the user considers success.
2. **Inspect**: read the project files and prior run artifacts before proposing changes.
3. **Prepare**: validate project shape, repair only relevant files, and keep edits scoped to the goal.
4. **Propose**: choose the smallest useful experiment and explain the expected signal.
5. **Run**: execute a dry run or real run when the command, budget, and output path are clear.
6. **Observe**: inspect logs, checkpoints, metrics, and best-program artifacts.
7. **Adapt**: summarize the result, compare it with the goal, and choose whether to refine code, tune config, rerun, or ask the user.

## Tool Primitives

Use these scripts behind the scenes when deterministic state, validation, execution, or summarization is useful:

- `scripts/interactive_session.py`: session state, project import/selection, validation, run records, log tails, file reads, summaries, and next-action hints.
- `scripts/validate_project.py`: direct validation for OpenEvolve project shape and plaintext key checks.
- `scripts/run_openevolve.py`: direct OpenEvolve execution, including dry-run command construction.
- `scripts/summarize_run.py`: extraction of best metrics and best-program metadata from an output directory.

Prefer JSON output from scripts so you can reason over structured state. Load command help or script source only when a decision requires exact flags.

## Project Contract

An OpenEvolve project should contain:

- `initial_program.py` with `EVOLVE-BLOCK-START` and `EVOLVE-BLOCK-END`.
- `evaluator.py` with `evaluate(program_path)`.
- `config.yaml`, `config.yml`, or `config_default.yaml` with `max_iterations` and `checkpoint_interval`.

If the project differs from this shape, first inspect the files and decide whether to adapt, repair, or ask the user before forcing the default contract.

## Operating Rules

- Favor short probe runs before long searches unless the user already gave a runtime budget.
- Treat UI-originated requests and conversational requests the same way: the agent owns interpretation and next-step selection.
- Do not overwrite user changes. Read current files, patch narrowly, and explain meaningful edits.
- When validation fails, repair only the files named by the report or directly implicated by inspection.
- When a run is active, inspect status/logs before starting another run.
- When results are available, report the best metric, artifact path, and one concrete recommendation.

## References

- Read `references/project-format.md` when creating or repairing project files.
- Read `references/troubleshooting.md` when validation, execution, metrics, or artifact discovery fail.
