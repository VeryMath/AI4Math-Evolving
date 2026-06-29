<div align="center">

# AI4Math · Evolving

Agent-led workflows for iterative mathematical experiments, OpenEvolve runs,
evaluation loops, and skill refinement.

[中文说明](README.zh-CN.md) · [Contributors](CONTRIBUTORS.md) · [Skill packages](#skill-packages) · [Quick start](#quick-start) · [Security model](#security-and-scope)

![version](https://img.shields.io/badge/version-0.1.0-blue)
![skills](https://img.shields.io/badge/skills-1-2ea44f)
![license](https://img.shields.io/badge/license-MIT-green)

</div>

## What This Repository Is

This repository is the AI4Math home for evolving-agent workflows. It currently
focuses on bounded OpenEvolve experiment sessions: environment readiness,
project inspection, short probes, metric review, and next-step iteration.

Use the root page as the public map, then open the package for the concrete
workflow.

## Skill Packages

| Package | Use it for | Start here |
| --- | --- | --- |
| [`openevolve-experiment-workflow`](skills/openevolve-experiment-workflow/) | Inspect or create OpenEvolve projects, validate runtime configuration, run bounded probes, summarize metrics, and guide iterative improvement. | [`README`](skills/openevolve-experiment-workflow/README.md) · [`SKILL`](skills/openevolve-experiment-workflow/SKILL.md) |

## Quick Start

Clone the repository and open the package:

```bash
git clone https://github.com/VeryMath/AI4Math-Evolving.git
cd AI4Math-Evolving
```

Start with:

```text
skills/openevolve-experiment-workflow/SKILL.md
```

## Repository Layout

```text
AI4Math-Evolving/
├── README.md
├── README.zh-CN.md
├── SKILL.md
└── skills/
    └── openevolve-experiment-workflow/
```

Experiment logs, checkpoints, provider settings, and generated outputs belong in
task-local output directories, not in the public root.

## Validation

There is no root build step. When changing the package, validate its `SKILL.md`,
README links, scripts, and references. If you use Codex's local skill validator,
run it against `skills/openevolve-experiment-workflow/`.

## Security and Scope

Do not commit provider API keys, plaintext model credentials, `.env` files,
OpenEvolve run logs with secrets, generated checkpoints, or private experiment
outputs. Public examples should be sanitized and safe to redistribute.
