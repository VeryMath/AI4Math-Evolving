---
name: openevolve-experiment-workflow
description: Use when a coding agent is asked to pursue an interactive AI4Math-Evolving/OpenEvolve goal involving initial_program.py, evaluator.py, config.yaml, metrics, logs, checkpoints, best-program artifacts, or iterative user feedback.
---

# OpenEvolve Experiment Workflow

## Overview

Turn a user's evolving goal into an agent-led OpenEvolve session. The user should experience a collaborative coding agent that understands intent, asks only necessary questions, edits project files when useful, runs experiments, observes results, and proposes the next move.

Use the bundled scripts as private tool primitives. Do not present the skill as a command menu unless the user explicitly asks for commands.

## Interaction Contract

- Start from the user's goal, not from a fixed sequence of commands. Restate the target metric, constraints, budget, and expected artifact when they are clear.
- Establish the runnable environment before deep project design. Inspect or configure the workspace, Python/OpenEvolve package, `openevolve-run`, provider API variable, model, and base URL before asking domain-shaping questions.
- Inspect the project before asking project questions. Infer entry points, evaluator shape, config path, current results, and likely blockers from files and logs.
- Ask the user for feedback only when it changes a decision: objective tradeoffs, runtime budget, model/provider choice, acceptance threshold, or risky code changes.
- Make the next action explicit before starting a costly run: baseline, repair, short probe, full run, log inspection, result comparison, or stop.
- After each observation, decide what changed and what should happen next. Prefer "I found X, so I will do Y" over generic status updates.
- Keep secrets out of artifacts. Provider keys must stay in environment variables or placeholders, never plaintext config, logs, examples, or summaries.

## Capabilities

Use the skill to guide these agent-led tasks:

- Goal intake: turn a loose optimization or research request into an objective metric, run budget, and expected artifact.
- First-run onboarding: help a new user move from an open-ended goal to a visible workspace, starter OpenEvolve project, validation result, dry-run command, and small first run.
- Project readiness: inspect, validate, and minimally repair `initial_program.py`, `evaluator.py`, and config files.
- Baseline run: start with a short probe or baseline before spending a larger search budget.
- Evolution search: launch direct OpenEvolve runs, track status, tail logs, stop runs, and preserve output directories.
- Result analysis: summarize best metrics, best-program artifacts, evaluator failures, and likely reasons a run stalled.
- Visualization data: extract metric series, checkpoint timelines, best-artifact paths, and log highlights for a UI or report without rendering the UI here.
- Iteration planning: use user feedback and observed metrics to decide whether to adjust code, evaluator, config, budget, or acceptance criteria.

## User Guidance

Reply in Chinese by default unless the user asks for another language or the surrounding project explicitly requires English.

Guide the user through one decision at a time. Do not ask the user to choose from a command list; choose the next useful action yourself, explain why it is the right signal, and ask only for the decision that changes that action.

When a user gives an open-ended goal, guide them toward one crisp next experiment. Prefer short prompts such as:

- "I can run a short baseline first; what metric should count as success if the evaluator exposes several?"
- "This may spend API budget. Should I cap the first search to a small probe?"
- "The best score improved but the logs show evaluator noise. I can inspect the best program or tighten the evaluator next."

Do not ask for information already present in project files. When the user is unsure, choose conservative defaults, explain the assumption, and keep the first run small.

During first-run onboarding, avoid assuming the user already has an OpenEvolve project. First establish the environment snapshot, then create or guide creation of the smallest project that can be validated and dry-run before asking about a longer evolution run.

Before asking domain-shaping questions, confirm the workspace, Python interpreter, `openevolve` package, `openevolve-run`, provider API variable, model, and base URL. Do not start with a multi-option algorithm or benchmark questionnaire; ask at most one blocking question when the environment or objective cannot be inferred.

If the current location is an empty or temporary workspace and the user did not provide a project path, the default action is to initialize a visible workspace at `~/Desktop/AI4Math-Evolving` and report its absolute path. Do not force a single workspace path: use an existing project path, an explicit user location, or the current directory when it is clearly intended.

## Runtime/API Configuration

Treat API/provider settings as readiness information, not as a mandatory first gate for every request. Before a real evolution run, inspect the config and environment together:

- If config already has `llm.api_key: "${VAR_NAME}"` and `VAR_NAME` is set in the environment, do not ask for the key again.
- If config has model and base URL but no `api_key`, propose adding an environment placeholder such as `${LLM_API_KEY}`.
- If config references `${VAR_NAME}` but the environment variable is missing, ask the user to export it or provide a local env setup. Do not ask them to paste secrets into tracked files.
- If the user provides API settings in chat, acknowledge receipt without repeating the secret value. Convert the project config to environment-variable placeholders and, if a real key was exposed, recommend rotating it after setup.
- For ChatECNU-style OpenAI-compatible endpoints, a typical config is `api_base: "https://chat.ecnu.edu.cn/open/api/v1"`, `primary_model: "ecnu-plus"`, and `api_key: "${LLM_API_KEY}"`.

Do not write plaintext API keys into config, examples, logs, summaries, tests, or docs. It is fine to write placeholder names.

## Goal-Directed Environment Setup

For new-user onboarding, establish a runnable environment before project design or domain-shaping questions. The environment snapshot should cover workspace, Python interpreter, `openevolve` package, `openevolve-run`, provider API variable, model, and base URL.

Let the user's goal shape defaults: workspace name, model choice, first-run budget, project complexity, and the smallest useful evaluator. Do not turn readiness into a fixed checklist; once the environment pieces needed for the user's goal are known or configured, move on to the minimal project and dry run.

OpenEvolve is used as a Python package and CLI. Do not describe this as deploying a local service; the local requirement is an installed `openevolve` package exposing `openevolve-run`, plus project files and API configuration. Prefer installing or importing the package and calling the CLI; do not clone or deploy OpenEvolve itself unless the user asks.

For a real evolution run, verify the relevant API key placeholder, model settings, Python availability, `openevolve-run`, and project files. For inspection, repair, dry-run command construction, or scaffolding, check only the pieces needed for that step and explain what can wait.

When a new workspace is useful and the user did not choose a location, use the visible default `~/Desktop/AI4Math-Evolving`. If an existing project path or current workspace is clearly the user's intended project, use it instead of enforcing a location rule.

## Agent Decision Loop

1. **Understand**: identify the evolving goal, objective metric, constraints, and what the user considers success.
2. **Set Up Environment**: establish or repair the workspace, Python/OpenEvolve CLI, API environment variable, model, and base URL needed for the goal.
3. **Observe State**: inspect available project files, config hints, and prior artifacts enough to choose a useful next action.
4. **Prepare Project**: create, validate, or minimally repair project files scoped to the goal.
5. **Dry Run**: build the OpenEvolve command and confirm paths/config before spending API budget.
6. **Propose**: choose the smallest useful experiment and explain the expected signal.
7. **Run**: execute a dry run or real run when the command, budget, and output path are clear.
8. **Observe**: inspect logs, checkpoints, metrics, and best-program artifacts.
9. **Adapt**: summarize the result, compare it with the goal, and choose whether to refine code, tune config, rerun, or ask the user.

Best-program artifacts, improved metrics, and evaluator wins are search
evidence, not proof. If an evolved result creates a theorem claim or proof
obligation, route it to `proof-blueprint-review` or `lean-formalization`.

## Tool Primitives

Use these scripts behind the scenes when deterministic state, validation, execution, or summarization is useful:

- `scripts/interactive_session.py`: session state, project import/selection, validation, run records, log tails, file reads, summaries, and next-action hints.
- `scripts/validate_project.py`: direct validation for OpenEvolve project shape and plaintext key checks.
- `scripts/run_openevolve.py`: direct OpenEvolve execution, including dry-run command construction.
- `scripts/summarize_run.py`: extraction of best metrics and best-program metadata from an output directory.

Prefer JSON output from scripts so you can reason over structured state. Load command help or script source only when a decision requires exact flags.

For an empty first-run workspace, initialize the visible workspace with:

```bash
python3 scripts/interactive_session.py --workspace ~/Desktop/AI4Math-Evolving --json init
```

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
