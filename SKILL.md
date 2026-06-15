---
name: ai4math-evolving-skill
description: Use when running coding-agent-guided AI4Math/OpenEvolve experiment sessions, including workspace setup, dry-run validation, short probes, run summaries, and approval-gated longer evolution searches.
---

# AI4Math Evolving Skill

This root `SKILL.md` is a compatibility entrypoint for platforms that expect one
top-level Skill file. The shared Skill layer lives at:

```text
openevolve-coding-agent/SKILL.md
```

Read that concrete Skill before running an OpenEvolve session. Keep platform
adapters thin and improve the shared Skill layer first.

## Operating Boundary

- Inspect the workspace before asking broad project questions.
- Keep API keys in environment variables or ignored local files.
- Run dry-run validation before spending API budget.
- Ask before long or expensive evolution searches.
- Report from logs, checkpoints, metrics, and best-program artifacts.
