<div align="center">

# AI4Math · Evolving

Agent-led workflows for iterative mathematical experiments, OpenEvolve runs,
evaluation loops, and skill refinement.

[中文说明](README.zh-CN.md) · [Contributors](CONTRIBUTORS.md) · [Skill packages](#skill-packages) · [Installation](#installation) · [Quick start](#quick-start) · [Security model](#security-and-scope)

![version](https://img.shields.io/badge/version-0.2.0-blue)
![skills](https://img.shields.io/badge/skills-1-2ea44f)
![license](https://img.shields.io/badge/license-MIT-green)

</div>

<p align="center">
  If this project helps your work, please consider giving the repository a Star ⭐
  <a href="https://github.com/VeryMath/AI4Math-Evolving"><img alt="GitHub stars" src="https://img.shields.io/github/stars/VeryMath/AI4Math-Evolving?style=social"></a>
</p>

## What This Repository Is

This repository is the AI4Math home for evolving-agent workflows. It currently
focuses on bounded OpenEvolve experiment sessions: environment readiness,
algorithm, proof-candidate, and counterexample evolution with mathematical verification and failure feedback.

Use the root page as the public map, then open the package for the concrete
workflow.

## Skill Packages

| Package | Use it for | Start here |
| --- | --- | --- |
| [`openevolve-experiment-workflow`](skills/openevolve-experiment-workflow/) | Evolve algorithms, proof candidates, and counterexamples; evaluate each change and record mathematical verification and failures. | [`README`](skills/openevolve-experiment-workflow/README.md) · [`SKILL`](skills/openevolve-experiment-workflow/SKILL.md) |

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

- `README.md` and `README.zh-CN.md`: repository map and installation.
- `SKILL.md`: route tasks to the package.
- `skills/openevolve-experiment-workflow/`: workflow, examples, and references.
- `tests/`: script behavior, metadata, links, and mathematical verification.

Experiment logs, checkpoints, provider settings, and generated outputs belong in
task-local output directories, not in the public root.

## Validation

Install validation dependencies and run the checks from the repository root:

```bash
python -m pip install '.[test]'
mkdir -p .verification/temporary
TMPDIR="$PWD/.verification/temporary" python -m pytest -q
python skills/openevolve-experiment-workflow/examples/mathematical_evolution.py --case all --rounds 10 --output .verification/mathematical-evolution.json
```

The [real-model examples](skills/openevolve-experiment-workflow/examples/model_candidates/README.md)
use JSON candidates with fixed evaluators. A verified `ecnu-max` run is recorded in
[model validation](skills/openevolve-experiment-workflow/references/model-validation.md).
CI runs local mathematical checks without provider credentials.

## Security and Scope

Do not commit provider API keys, plaintext model credentials, `.env` files,
OpenEvolve run logs with secrets, generated checkpoints, or private experiment
outputs. Public examples should be sanitized and safe to redistribute.
