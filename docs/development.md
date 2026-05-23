# Development

## Backend syntax check

```bash
python3 -m py_compile backend/server.py backend/llm_client.py backend/skill_runner.py
```

## Frontend build

```bash
npm run build
```

## Public export test

```bash
python3 -m unittest tests/test_export_public_ui.py -v
```

## Smoke check

Start the backend and frontend, then run:

```bash
./scripts/smoke_ui_repo.sh
```

See [local-run-and-interactive-skill-status.md](local-run-and-interactive-skill-status.md) for the latest local verification notes and the interactive skill roadmap.

## Skill-runner integration

`/api/runs/start` constructs the run command through the `openevolve-coding-agent` interactive session runner. The backend still owns deterministic Web/API work such as upload, auth, SSE, file browsing, process tracking, and downloads.

```bash
python3 ../AI4Math-Evolving-Skill/openevolve-coding-agent/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json init --project /path/to/project --name demo
python3 ../AI4Math-Evolving-Skill/openevolve-coding-agent/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json configure --mode direct --iterations 10
python3 ../AI4Math-Evolving-Skill/openevolve-coding-agent/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json run --dry-run
```

Set `OPENEVOLVE_SKILL_REPO` if the skill repo is not a sibling of the UI repo.
