from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
import re


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SKILL_REPO = ROOT_DIR.parent / "AI4Math-Evolving-Skill"


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
            "Set OPENEVOLVE_SKILL_REPO to the AI4Math-Evolving-Skill repository."
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


def _safe_name(raw: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw.strip()).strip("._-")
    return name or "project"


def _runner_mode(mode: str | None = None) -> str:
    raw = (
        mode
        or os.environ.get("AI4MATH_EVOLVE_RUN_MODE")
        or os.environ.get("EVOLVE_RUN_MODE")
        or "direct"
    )
    value = str(raw).strip().lower()
    return value if value in {"direct", "opencode"} else "direct"


def _env_first(env: dict[str, str], *names: str) -> str:
    for name in names:
        value = str(env.get(name) or "").strip()
        if value:
            return value
    return ""


def provider_extras_from_env(env: dict[str, str] | None = None) -> dict[str, str]:
    source = env or os.environ
    base_url = _env_first(source, "LLM_BASE_URL", "DEEPSEEK_BASE_URL")
    model = _env_first(source, "LLM_MODEL_ID", "DEEPSEEK_MODEL")
    extras: dict[str, str] = {}
    if base_url:
        extras["api_base"] = base_url
    if model:
        extras["primary_model"] = model
        extras["secondary_model"] = model
    return extras


def build_run_payload(
    project_dir: Path,
    *,
    iterations: int,
    checkpoint_interval: int,
    output_dir: Path,
    mode: str | None = None,
    workspace: Path | None = None,
    project_name: str | None = None,
    agent: str = "openevolve-unified-primary",
    language: str = "zh-CN",
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    script = script_path("interactive_session.py")
    project = Path(project_dir).resolve()
    output = Path(output_dir).resolve()
    session_workspace = Path(workspace).resolve() if workspace else project
    selected_project = _safe_name(project_name or project.name)
    selected_mode = _runner_mode(mode)

    init_args = [
        "--workspace",
        str(session_workspace),
        "--json",
        "init",
        "--project",
        str(project),
        "--name",
        selected_project,
    ]
    _run_json(script, init_args)

    configure_args = [
        "--workspace",
        str(session_workspace),
        "--json",
        "configure",
        "--mode",
        selected_mode,
        "--agent",
        agent,
        "--iterations",
        str(iterations),
        "--checkpoint-interval",
        str(checkpoint_interval),
        "--language",
        language,
        *_extra_args(extras),
    ]
    _run_json(script, configure_args)

    run_args = [
        "--workspace",
        str(session_workspace),
        "--json",
        "run",
        "--project",
        selected_project,
        "--run-id",
        output.name,
        "--output-dir",
        str(output),
        "--dry-run",
    ]
    payload = _run_json(script, run_args)
    payload["mode"] = selected_mode
    payload["workspace"] = str(session_workspace)
    payload["initArgv"] = init_args
    payload["configureArgv"] = configure_args
    payload["argv"] = run_args
    return payload


def build_run_command(
    project_dir: Path,
    *,
    iterations: int,
    checkpoint_interval: int,
    output_dir: Path,
    mode: str | None = None,
    workspace: Path | None = None,
    project_name: str | None = None,
    agent: str = "openevolve-unified-primary",
    language: str = "zh-CN",
    extras: dict[str, Any] | None = None,
) -> list[str]:
    payload = build_run_payload(
        project_dir,
        iterations=iterations,
        checkpoint_interval=checkpoint_interval,
        output_dir=output_dir,
        mode=mode,
        workspace=workspace,
        project_name=project_name,
        agent=agent,
        language=language,
        extras=extras,
    )
    command = payload.get("command")
    if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
        raise SkillRunnerError("skill runner payload missing string-list command")
    return command


def record_external_run(
    project_dir: Path,
    *,
    run_id: str,
    output_dir: Path,
    log_path: Path,
    pid: int,
    mode: str,
    command: list[str],
    workspace: Path | None = None,
    project_name: str | None = None,
) -> dict[str, Any]:
    script = script_path("interactive_session.py")
    project = Path(project_dir).resolve()
    session_workspace = Path(workspace).resolve() if workspace else project
    selected_project = _safe_name(project_name or project.name)

    init_args = [
        "--workspace",
        str(session_workspace),
        "--json",
        "init",
        "--project",
        str(project),
        "--name",
        selected_project,
    ]
    _run_json(script, init_args)

    args = [
        "--workspace",
        str(session_workspace),
        "--json",
        "record-run",
        "--project",
        selected_project,
        "--run-id",
        run_id,
        "--output-dir",
        str(Path(output_dir).resolve()),
        "--log-path",
        str(Path(log_path).resolve()),
        "--pid",
        str(int(pid)),
        "--status",
        "running",
        "--mode",
        _runner_mode(mode),
        "--command-json",
        json.dumps(command),
    ]
    payload = _run_json(script, args)
    payload["argv"] = args
    return payload
