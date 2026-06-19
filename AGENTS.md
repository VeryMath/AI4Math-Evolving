# AGENTS.md

This repository is an AI4Math Skill adapter package for interactive
OpenEvolve experiment sessions. The shared Skill layer is:

```text
openevolve-experiment-workflow/SKILL.md
```

## Contract

- Use the shared Skill layer as the workflow source of truth.
- Keep platform-specific files thin; do not fork OpenEvolve workflow behavior.
- Inspect the target workspace before asking broad setup questions.
- Keep API keys out of repository files.
- Run small probes and dry-run checks before long or expensive searches.
- Ask before dependency changes, source edits outside the active workspace, API
  calls that spend budget, long runs, or final research claims.
