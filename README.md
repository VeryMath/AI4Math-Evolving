# OpenEvolve Coding Agent Skill

An agent-native workflow for creating, validating, running, and summarizing OpenEvolve projects.

This repository is the skill-first counterpart to the OpenEvolve UI bridge. It is intended for coding agents such as Codex, OpenCode, or similar tools that can read project files, execute scripts, repair errors, and report results.

## Contents

- `openevolve-coding-agent/SKILL.md`: agent workflow.
- `openevolve-coding-agent/scripts/validate_project.py`: validates OpenEvolve project files.
- `openevolve-coding-agent/scripts/run_openevolve.py`: runs or dry-runs OpenEvolve through direct or opencode mode.
- `openevolve-coding-agent/scripts/summarize_run.py`: extracts best metrics and artifacts from a run directory.

## Test

```bash
python3 -m unittest discover -s tests -v
```
