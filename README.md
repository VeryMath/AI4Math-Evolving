<div align="center">

# AI4Math · Evolving

Agent-led workflows for iterative mathematical experiments, OpenEvolve runs,
evaluation loops, and skill refinement.

[中文说明](README.zh-CN.md) · [Contributors](CONTRIBUTORS.md) · [Skill packages](#skill-packages) · [Installation](#installation) · [Quick start](#quick-start) · [Security model](#security-and-scope)

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

## Installation

The recommended path is AI-assisted installation: ask your coding agent to clone or update this repository, read the Skill instructions, install the entrypoints, and verify discovery.

```text
Please install these AI4Math Skills for me.

Repository: https://github.com/VeryMath/AI4Math-Evolving.git
Branch: main
Skill paths:
- skills/openevolve-experiment-workflow

Steps:
1. Clone or update the repository locally.
2. Read README.md, SKILL.md, AGENTS.md if present, and each target Skill entrypoint.
3. If this environment supports local Skill discovery, link each directory that contains SKILL.md into the local skills directory.
4. Keep shared sibling support directories in place when a Skill depends on them.
5. Verify that the installed Skills are discoverable.
6. Tell me the installed paths, whether a restart is needed, and give me one test prompt.
```

Manual fallback for Codex-style local discovery:

```bash
git clone https://github.com/VeryMath/AI4Math-Evolving.git
cd AI4Math-Evolving
mkdir -p ~/.codex/skills
ln -s "$PWD/skills/openevolve-experiment-workflow" ~/.codex/skills/openevolve-experiment-workflow
```

If your agent uses a different local Skill directory, replace `~/.codex/skills` with that configured path.

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
