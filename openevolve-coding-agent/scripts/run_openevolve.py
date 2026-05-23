#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def build_prompt(project_dir: Path, iterations: int, checkpoint_interval: int, output_dir: Path | None) -> str:
    lines = [
        "Please run one OpenEvolve task now. Do not only write a plan.",
        f"project_dir: {project_dir}",
        f"iterations: {iterations}",
        f"checkpoint_interval: {checkpoint_interval}",
    ]
    if output_dir:
        lines.append(f"output_dir: {output_dir}")
    lines.append("When finished, emit a concise summary and then a final line: DONE")
    return "\n".join(lines)


def build_opencode_command(agent: str, project_dir: Path, prompt: str) -> list[str]:
    return [
        "opencode",
        "run",
        "--format",
        "json",
        "--agent",
        agent,
        "--dir",
        str(project_dir),
        prompt,
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("--mode", choices=["opencode", "direct"], default="opencode")
    parser.add_argument("--agent", default="openevolve-unified-primary")
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--checkpoint-interval", type=int, default=5)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    project_dir = Path(args.project).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else None
    prompt = build_prompt(project_dir, args.iterations, args.checkpoint_interval, output_dir)

    if args.mode == "direct":
        command = ["openevolve-run", str(project_dir), "--iterations", str(args.iterations)]
    else:
        command = build_opencode_command(args.agent, project_dir, prompt)

    payload = {
        "mode": args.mode,
        "projectDir": str(project_dir),
        "outputDir": str(output_dir) if output_dir else "",
        "command": command,
        "prompt": prompt,
    }
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else " ".join(command))
        return 0

    proc = subprocess.run(command, cwd=str(project_dir), text=True)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
