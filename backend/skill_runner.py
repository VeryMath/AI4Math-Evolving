from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SKILL_REPO = ROOT_DIR.parent / "openevolve-coding-agent-skill"


class SkillRunnerError(RuntimeError):
    pass


def skill_repo_root() -> Path:
    configured = os.environ.get("OPENEVOLVE_SKILL_REPO", "").strip()
    return Path(configured).expanduser().resolve() if configured else DEFAULT_SKILL_REPO.resolve()


def script_path(script_name: str, repo_root: Path | None = None) -> Path:
    root = repo_root or skill_repo_root()
    path = root / "openevolve-coding-agent" / "scripts" / script_name
    if not path.is_file():
        raise SkillRunnerError(
            f"missing OpenEvolve skill runner script: {path}. "
            "Set OPENEVOLVE_SKILL_REPO to the openevolve-coding-agent-skill repository."
        )
    return path


def _run_json(script: Path, args: list[str], timeout_sec: int = 30) -> dict[str, Any]:
    cmd = [sys.executable, str(script), *args]
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        raise SkillRunnerError(f"skill runner timed out: {script}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise SkillRunnerError(f"skill runner failed: {detail[:500]}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SkillRunnerError(f"skill runner returned non-JSON output: {proc.stdout[:500]}") from exc
    if not isinstance(payload, dict):
        raise SkillRunnerError("skill runner JSON output must be an object")
    return payload


def _extra_args(extras: dict[str, Any] | None) -> list[str]:
    args: list[str] = []
    for key, value in (extras or {}).items():
        args.extend(["--extra", f"{key}={value}"])
    return args


def build_run_payload(
    project_dir: Path,
    *,
    iterations: int,
    checkpoint_interval: int,
    output_dir: Path,
    agent: str = "openevolve-unified-primary",
    language: str = "zh-CN",
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    script = script_path("run_openevolve.py")
    args = [
        str(Path(project_dir).resolve()),
        "--mode",
        "opencode",
        "--agent",
        agent,
        "--iterations",
        str(iterations),
        "--checkpoint-interval",
        str(checkpoint_interval),
        "--output-dir",
        str(Path(output_dir).resolve()),
        "--language",
        language,
        "--dry-run",
        "--json",
        *_extra_args(extras),
    ]
    return _run_json(script, args)


def build_run_command(
    project_dir: Path,
    *,
    iterations: int,
    checkpoint_interval: int,
    output_dir: Path,
    agent: str = "openevolve-unified-primary",
    language: str = "zh-CN",
    extras: dict[str, Any] | None = None,
) -> list[str]:
    payload = build_run_payload(
        project_dir,
        iterations=iterations,
        checkpoint_interval=checkpoint_interval,
        output_dir=output_dir,
        agent=agent,
        language=language,
        extras=extras,
    )
    command = payload.get("command")
    if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
        raise SkillRunnerError("skill runner payload missing string-list command")
    return command
