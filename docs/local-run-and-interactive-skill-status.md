# Local Run and Interactive Skill Status

Date: 2026-05-23

This note records the current verification result and the target shape for turning the UI workflow into an interactive `openevolve-coding-agent` skill.

## Summary

The public UI repo can be installed, built, started, and smoke-tested locally. The backend API, frontend dev server, project upload, file tree API, and the backend-to-skill-runner launch path are working.

The OpenEvolve core path is also working when launched directly with `openevolve-run` and the local provider environment.

The remaining blocker for a full UI-triggered evolution run is the `opencode` agent layer: the UI currently asks `opencode` to run agent `openevolve-unified-primary`, but that agent is not registered in the local public setup. Because of that, the UI `START` endpoint creates a run and starts `opencode`, but no `best_program.py` or best metrics are produced through that route yet.

## Verified Components

- Public UI repository
- `openevolve-coding-agent` skill repository
- AI4Math wrapper skill entry

## Environment Observed

- `opencode --version`: `1.4.11`
- Backend test Python: `/usr/bin/python3` (`3.9.6`)
- OpenEvolve runtime Python: Python `3.13.5` in the local OpenEvolve environment
- OpenEvolve executable: `openevolve-run`
- Node.js used for build: `v22.22.0`
- npm used for build: `10.9.4`

Notes:

- The project recommends Node.js 20 for public users. Node.js 22 built successfully in this local verification.
- The system has HTTP proxy variables configured, so local smoke tests use `curl --noproxy '*'`.
- The backend Python and OpenEvolve Python may be different interpreters. Make sure `openevolve-run` is available in the environment that launches runs.

## Verification Results

Passed:

- Python unit tests in the public UI repo: `5` tests passed.
- Backend syntax check for `backend/server.py`, `backend/llm_client.py`, and `backend/skill_runner.py`.
- Skill repo unit tests: `6` tests passed.
- Skill quick validation passed.
- Frontend install and production build passed.
- Backend HTTP smoke passed at `http://127.0.0.1:8001/api/projects`.
- Frontend HTTP smoke passed at `http://localhost:5173/`.
- Project ZIP upload passed through `POST /api/projects/upload`.
- Project tree API passed through `GET /api/projects/<name>/tree`.
- Direct `openevolve-run` completed a one-iteration function-minimization run.
- Skill summarizer found the direct run's best program and metrics.

Warnings:

- `npm ci` reported `4` audit findings: `2` moderate and `2` high.
- `npm run build` emitted a Vite chunk-size warning for the main bundle.

Blocked:

- UI `POST /api/runs/start` launches `opencode` through the skill runner, but the configured `opencode` agent `openevolve-unified-primary` is missing locally.
- The UI-triggered route therefore starts a run directory and monitor log, but does not yet produce final OpenEvolve best artifacts.

## Direct OpenEvolve Smoke Result

The direct one-iteration run completed and produced best artifacts under the configured OpenEvolve output directory.

Observed best metrics:

```text
avg_delay: 1.8279
delay_score: 0.9163
reliability_score: 1.0
combined_score: 0.9330
```

This confirms that the provider configuration and OpenEvolve runtime can work locally. The unresolved part is not the model endpoint itself; it is the `opencode` custom-agent bridge used by the UI `START` button.

## Current Skill Effect

The current `openevolve-coding-agent` skill is an MVP with deterministic helper scripts:

- `validate_project.py`: checks that an OpenEvolve project has the expected files and can be prepared for a run.
- `run_openevolve.py`: builds an `opencode run` command with UI-provided parameters, Chinese-language prompting, output directory, and extra OpenEvolve settings.
- `summarize_run.py`: reads OpenEvolve output and summarizes best metrics/artifacts.

In other words, the skill is already useful as a stable adapter between the UI backend and an agent-driven OpenEvolve run. It is not yet a complete interactive replacement for the original UI platform.

## Target: Interactive Skill Equivalent To The UI

The desired target is a stateful, interactive skill that can guide a coding agent through the same workflow that the UI currently exposes.

Suggested command surface:

```text
init                 create or select a workspace
import               import a project from a folder or zip
validate             validate config.yaml, evaluator.py, and initial_program.py
configure            set iterations, population size, islands, timeout, mutation rate, archive size, etc.
run                  start an evolution run through direct OpenEvolve or opencode mode
tail                 stream or summarize current logs/events
stop                 stop the active run
tree                 inspect project files and output files
read                 read selected project or output files
summarize            report best metrics and best program path
next                 recommend the next action based on current state
```

The skill should keep a small JSON session state file, for example:

```text
.openevolve-agent/session.json
```

That state should track:

- selected project directory
- selected run mode: `direct` or `opencode`
- current run id
- output directory
- last validated files
- selected parameter set
- process id, if a run is active
- last summary and best metrics

## UI-To-Skill Mapping

| Existing UI capability | Interactive skill equivalent |
| --- | --- |
| Upload ZIP / create project | `import` |
| Project list / selection | `init` or `select` |
| File browser | `tree` and `read` |
| Parameter panel | `configure` |
| START button | `run` |
| STOP button | `stop` |
| Run Monitor | `tail` |
| Results Analysis | `summarize` |
| Download output | report output directory and selected artifacts |
| Backend validation | `validate` |

## Recommended Next Implementation Step

There are two viable ways to remove the current blocker:

1. Register and publish the `openevolve-unified-primary` opencode agent as part of the public setup.
2. Add a direct-run mode to the skill runner and backend so the UI can call `openevolve-run` without requiring a custom opencode agent.

For a lighter open-source architecture, option 2 is the better default. It makes the UI repo runnable with OpenEvolve plus provider credentials, while keeping the opencode-agent path as an advanced mode.

After that, the interactive skill can become the shared core:

```text
UI frontend
  -> backend API
    -> interactive/direct skill runner
      -> OpenEvolve

Coding agent
  -> same interactive skill
    -> OpenEvolve
```

This would let the project ship as two related open-source entry points:

- UI version: visual project management, run monitor, and result browser.
- Coding-agent skill version: conversational project setup, validation, execution, and result analysis.

Both should share the same project format and runner scripts.

## Local Run Commands

Start backend:

```bash
export OPENEVOLVE_SKILL_REPO=/path/to/openevolve-coding-agent-skill
python3 backend/server.py
```

Start frontend:

```bash
npm run dev
```

Smoke check:

```bash
./scripts/smoke_ui_repo.sh
```

Direct OpenEvolve check, using a private local `.env` without printing secrets:

```bash
set -a
source /path/to/private/.env
set +a

openevolve-run \
  examples/function-minimization/initial_program.py \
  examples/function-minimization/evaluator.py \
  --config examples/function-minimization/config.yaml \
  --output /tmp/openevolve-direct-smoke \
  --iterations 1 \
  --api-base "$LLM_BASE_URL" \
  --primary-model "$LLM_MODEL_ID" \
  --secondary-model "$LLM_MODEL_ID" \
  --log-level INFO
```
