# Advanced AI Platform Interface

A local web UI for running OpenEvolve workflows through coding-agent orchestration.

This repository is the UI half of a two-repo design:

```text
advanced_ai_platform_interface/      # browser UI and deterministic backend
openevolve-coding-agent-skill/       # canonical agent workflow and runner scripts
```

The UI backend handles predictable web work: upload, auth, run state, SSE, file browsing, downloads, and result analysis. Evolution orchestration is delegated through the sibling `openevolve-coding-agent-skill` runner, which constructs the `opencode run --agent openevolve-unified-primary` command that drives OpenEvolve.

## Architecture

```text
Browser UI
  -> Python stdlib backend
  -> backend/skill_runner.py
  -> openevolve-coding-agent-skill
  -> opencode / coding agent
  -> OpenEvolve
```

This keeps the backend thin without asking a coding agent to serve HTTP, manage files, or stream events.

## Requirements

- Node.js 20
- Python 3.10+
- `opencode` CLI configured locally
- OpenEvolve available to the coding-agent runtime
- A provider API key in `.env` or your shell
- The sibling `openevolve-coding-agent-skill` repository, or `OPENEVOLVE_SKILL_REPO` pointing to it

## Quick Start

Install frontend dependencies:

```bash
npm install
```

Create local configuration:

```bash
cp .env.example .env
```

Edit `.env` with your provider settings:

```bash
LLM_API_KEY=
LLM_BASE_URL=https://chat.ecnu.edu.cn/open/api/v1
LLM_MODEL_ID=ecnu-plus

# Optional compatibility names for existing OpenEvolve configs.
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=
DEEPSEEK_MODEL=

# Optional when the skill repo is not a sibling of this repo.
OPENEVOLVE_SKILL_REPO=
```

Start backend and frontend:

```bash
./start_all.sh
```

Or run them separately:

```bash
python3 backend/server.py
npm run dev
```

By default, the backend listens on `127.0.0.1:8001` and Vite listens on `127.0.0.1:5173`.

## Using The UI

Upload a zip containing an OpenEvolve project. The backend accepts either a zip whose root directly contains the required files, or a zip with one nested project folder.

Required project files:

- `initial_program.py`
- `evaluator.py`
- `config.yaml`, `config.yml`, or `config_default.yaml`

The UI can then start and stop runs, stream logs, browse outputs, preview files, download artifacts, and request LLM analysis of a finished run.

## Configuration

See:

- [docs/installation.md](docs/installation.md)
- [docs/configuration.md](docs/configuration.md)
- [docs/security.md](docs/security.md)
- [docs/development.md](docs/development.md)

## Public Safety

- Do not commit `.env`.
- Do not commit `opencode.json` with real provider keys; use `opencode.example.json`.
- Treat uploaded evolution objects as executable code.
- Keep runtime data, logs, archives, and migration bundles out of the public repository.

## Development Checks

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile backend/server.py backend/llm_client.py backend/skill_runner.py
npm run build
```
