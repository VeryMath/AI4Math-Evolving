#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


CONFIG_NAMES = ("config.yaml", "config.yml", "config_default.yaml")


def parse_extra(values: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"--extra must use key=value format: {raw}")
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"--extra key must not be empty: {raw}")
        pairs.append((key, value.strip()))
    return pairs


def build_prompt(
    project_dir: Path,
    iterations: int,
    checkpoint_interval: int,
    output_dir: Path | None,
    *,
    language: str = "",
    extra: list[tuple[str, str]] | None = None,
) -> str:
    lines = [
        "Please run one OpenEvolve task now. Do not only write a plan.",
        f"project_dir: {project_dir}",
        f"iterations: {iterations}",
        f"checkpoint_interval: {checkpoint_interval}",
    ]
    if language.strip().lower() in {"zh", "zh-cn", "chinese", "simplified-chinese"}:
        lines.insert(0, "语言要求（强制）：所有自然语言回复必须使用简体中文；不要输出 <think>。")
    for key, value in extra or []:
        lines.append(f"{key}: {value}")
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


def project_config(project_dir: Path) -> Path:
    for name in CONFIG_NAMES:
        candidate = project_dir / name
        if candidate.is_file():
            return candidate
    return project_dir / "config.yaml"


def build_direct_command(
    project_dir: Path,
    iterations: int,
    output_dir: Path | None,
    *,
    extra: list[tuple[str, str]] | None = None,
) -> list[str]:
    command = [
        "openevolve-run",
        str(project_dir / "initial_program.py"),
        str(project_dir / "evaluator.py"),
        "--config",
        str(project_config(project_dir)),
        "--iterations",
        str(iterations),
    ]
    if output_dir:
        command.extend(["--output", str(output_dir)])

    option_map = {
        "api_base": "--api-base",
        "api-base": "--api-base",
        "primary_model": "--primary-model",
        "primary-model": "--primary-model",
        "secondary_model": "--secondary-model",
        "secondary-model": "--secondary-model",
        "target_score": "--target-score",
        "target-score": "--target-score",
        "log_level": "--log-level",
        "log-level": "--log-level",
        "checkpoint": "--checkpoint",
    }
    for key, value in extra or []:
        option = option_map.get(key)
        if option and value:
            command.extend([option, value])
    return command


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("--mode", choices=["opencode", "direct"], default="opencode")
    parser.add_argument("--agent", default="openevolve-unified-primary")
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--checkpoint-interval", type=int, default=5)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--language", default="")
    parser.add_argument("--extra", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    project_dir = Path(args.project).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else None
    try:
        extra = parse_extra(args.extra)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    prompt = build_prompt(
        project_dir,
        args.iterations,
        args.checkpoint_interval,
        output_dir,
        language=args.language,
        extra=extra,
    )

    if args.mode == "direct":
        command = build_direct_command(project_dir, args.iterations, output_dir, extra=extra)
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
