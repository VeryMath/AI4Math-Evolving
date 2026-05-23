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

`/api/runs/start` constructs the opencode command through the `openevolve-coding-agent` skill runner. The backend still owns deterministic Web/API work such as upload, auth, SSE, file browsing, process tracking, and downloads.

```bash
python3 ../openevolve-coding-agent-skill/openevolve-coding-agent/scripts/run_openevolve.py /path/to/project --mode opencode --iterations 10 --dry-run --json
```

Set `OPENEVOLVE_SKILL_REPO` if the skill repo is not a sibling of the UI repo.
