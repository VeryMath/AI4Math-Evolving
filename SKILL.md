---
name: ai4math-evolving
description: Route AI4Math evolving-agent and iterative skill-improvement tasks to normalized skill packages in this repository.
---

# AI4Math Evolving

Use this repository as a routing layer for AI4Math evolving-agent workflows.

Concrete skills belong under `skills/<skill-name>/`. Before running a concrete
workflow, open that package and follow its package-local `SKILL.md`, README,
scripts, and references.

## Packages

- `skills/openevolve-experiment-workflow/`: inspect or create an OpenEvolve
  project, validate runtime configuration, run bounded probes, summarize
  metrics, and guide iterative improvement sessions.

## Repository Boundary

- Keep root documentation concise and focused on routing.
- Add new skill packages under `skills/` using kebab-case names.
- Keep generated outputs, private notes, and local staging material out of
  release content.
