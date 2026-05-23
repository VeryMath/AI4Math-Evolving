# AI4Math-Evolving Skill

An agent-native workflow for interactively creating, validating, running, inspecting, and summarizing OpenEvolve projects.

This repository is the skill-first counterpart to the AI4Math-Evolving UI bridge. It is intended for coding agents such as Codex, OpenCode, or similar tools that can read project files, execute scripts, repair errors, and report results.

## Contents

- `openevolve-coding-agent/SKILL.md`: agent workflow.
- `openevolve-coding-agent/scripts/interactive_session.py`: stateful session CLI for import/select/validate/configure/run/tail/stop/tree/read/summarize/next.
- `openevolve-coding-agent/scripts/validate_project.py`: validates OpenEvolve project files.
- `openevolve-coding-agent/scripts/run_openevolve.py`: runs or dry-runs OpenEvolve through direct or opencode mode.
- `openevolve-coding-agent/scripts/summarize_run.py`: extracts best metrics and artifacts from a run directory.

## Test

```bash
python3 -m unittest discover -s tests -v
```

## Runner Contract

Interactive session:

```bash
python3 openevolve-coding-agent/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json init
python3 openevolve-coding-agent/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json import /path/to/project --name demo
python3 openevolve-coding-agent/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json validate
python3 openevolve-coding-agent/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json configure --mode direct --iterations 10
python3 openevolve-coding-agent/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json run --dry-run
```

Stateless runner:

```bash
python3 openevolve-coding-agent/scripts/run_openevolve.py /path/to/project \
  --mode opencode \
  --iterations 10 \
  --checkpoint-interval 5 \
  --output-dir /path/to/output \
  --language zh-CN \
  --extra num_islands=2 \
  --dry-run \
  --json
```
