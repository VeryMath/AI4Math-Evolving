#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from run_openevolve import build_direct_command, build_opencode_command, build_prompt, parse_extra  # noqa: E402
from summarize_run import summarize  # noqa: E402
from validate_project import validate_project  # noqa: E402


REQUIRED_FILES = ("initial_program.py", "evaluator.py")
CONFIG_NAMES = ("config.yaml", "config.yml", "config_default.yaml")
DEFAULT_CONFIG: dict[str, Any] = {
    "mode": "direct",
    "iterations": 10,
    "checkpoint_interval": 5,
    "language": "zh-CN",
    "agent": "openevolve-unified-primary",
    "extras": {},
}


def now_id() -> str:
    return time.strftime("run_%Y%m%d_%H%M%S")


def timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def safe_name(raw: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw.strip()).strip("._-")
    return name or "project"


def state_dir(workspace: Path) -> Path:
    return workspace / ".openevolve-agent"


def state_path(workspace: Path) -> Path:
    return state_dir(workspace) / "session.json"


def default_state(workspace: Path) -> dict[str, Any]:
    root = state_dir(workspace)
    return {
        "schemaVersion": 1,
        "workspace": str(workspace),
        "stateFile": str(state_path(workspace)),
        "currentProject": "",
        "currentRun": "",
        "projects": {},
        "runs": {},
        "config": dict(DEFAULT_CONFIG),
        "updatedAt": timestamp(),
    }


def load_state(workspace: Path) -> dict[str, Any]:
    path = state_path(workspace)
    if not path.is_file():
        return default_state(workspace)
    data = json.loads(path.read_text(encoding="utf-8"))
    state = default_state(workspace)
    state.update(data)
    state.setdefault("projects", {})
    state.setdefault("runs", {})
    state.setdefault("config", dict(DEFAULT_CONFIG))
    merged_config = dict(DEFAULT_CONFIG)
    merged_config.update(state["config"])
    merged_config.setdefault("extras", {})
    state["config"] = merged_config
    return state


def save_state(workspace: Path, state: dict[str, Any]) -> None:
    root = state_dir(workspace)
    root.mkdir(parents=True, exist_ok=True)
    state["workspace"] = str(workspace)
    state["stateFile"] = str(state_path(workspace))
    state["updatedAt"] = timestamp()
    state_path(workspace).write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    status = payload.get("status") or ("ok" if payload.get("ok", True) else "error")
    print(status)
    for key in ("message", "next", "projectName", "runId", "projectPath", "outputDir", "logPath"):
        if payload.get(key):
            print(f"{key}: {payload[key]}")


def has_project_contract(path: Path) -> bool:
    return all((path / name).is_file() for name in REQUIRED_FILES) and any((path / name).is_file() for name in CONFIG_NAMES)


def find_project_root(path: Path) -> Path | None:
    if has_project_contract(path):
        return path
    for initial in path.rglob("initial_program.py"):
        candidate = initial.parent
        if has_project_contract(candidate):
            return candidate
    return None


def normalize_config(project: Path) -> None:
    config_yaml = project / "config.yaml"
    if config_yaml.is_file():
        return
    for name in ("config.yml", "config_default.yaml"):
        candidate = project / name
        if candidate.is_file():
            shutil.copy2(candidate, config_yaml)
            return


def copy_project(source_root: Path, target: Path, overwrite: bool) -> None:
    if target.exists():
        if not overwrite:
            raise SystemExit(f"target project already exists: {target}")
        shutil.rmtree(target)
    shutil.copytree(source_root, target, ignore=shutil.ignore_patterns("__pycache__", ".git", ".DS_Store"))
    normalize_config(target)


def selected_project(state: dict[str, Any], explicit: str = "") -> tuple[str, Path]:
    name = explicit or state.get("currentProject") or ""
    projects = state.get("projects", {})
    if name in projects:
        return name, Path(projects[name]["path"]).resolve()
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if path.is_dir():
            return safe_name(path.name), path
    raise SystemExit("no project selected; run init --project, import, or select first")


def selected_run(state: dict[str, Any], explicit: str = "") -> tuple[str, dict[str, Any]]:
    run_id = explicit or state.get("currentRun") or ""
    runs = state.get("runs", {})
    if run_id and run_id in runs:
        return run_id, runs[run_id]
    raise SystemExit("no run selected; run the project first or pass --run-id")


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def refresh_runs(state: dict[str, Any]) -> None:
    for run in state.get("runs", {}).values():
        if run.get("status") == "running" and not process_alive(int(run.get("pid") or 0)):
            run["status"] = "exited"
            run["endedAt"] = run.get("endedAt") or timestamp()


def build_command(state: dict[str, Any], project: Path, output_dir: Path) -> tuple[list[str], str]:
    config = state["config"]
    extras_dict = config.get("extras") or {}
    extra = [(str(key), str(value)) for key, value in extras_dict.items()]
    mode = config.get("mode", "direct")
    if mode == "direct":
        return build_direct_command(project, int(config["iterations"]), output_dir, extra=extra), ""
    prompt = build_prompt(
        project,
        int(config["iterations"]),
        int(config["checkpoint_interval"]),
        output_dir,
        language=str(config.get("language") or ""),
        extra=extra,
    )
    return build_opencode_command(str(config.get("agent") or DEFAULT_CONFIG["agent"]), project, prompt), prompt


def cmd_init(args: argparse.Namespace, workspace: Path, state: dict[str, Any]) -> dict[str, Any]:
    state_dir(workspace).mkdir(parents=True, exist_ok=True)
    (state_dir(workspace) / "projects").mkdir(parents=True, exist_ok=True)
    (state_dir(workspace) / "runs").mkdir(parents=True, exist_ok=True)
    if args.project:
        path = Path(args.project).expanduser().resolve()
        if not path.is_dir():
            raise SystemExit(f"project does not exist: {path}")
        name = safe_name(args.name or path.name)
        state["projects"][name] = {"path": str(path), "imported": False, "updatedAt": timestamp()}
        state["currentProject"] = name
    save_state(workspace, state)
    return {"ok": True, "status": "initialized", "workspace": str(workspace), "stateFile": str(state_path(workspace)), "currentProject": state.get("currentProject", "")}


def cmd_import(args: argparse.Namespace, workspace: Path, state: dict[str, Any]) -> dict[str, Any]:
    source = Path(args.source).expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"source does not exist: {source}")
    with tempfile.TemporaryDirectory() as td:
        source_root = source
        if source.is_file():
            if not zipfile.is_zipfile(source):
                raise SystemExit(f"only zip files are supported for file import: {source}")
            with zipfile.ZipFile(source) as zf:
                zf.extractall(td)
            source_root = Path(td)
        project_root = find_project_root(source_root)
        if not project_root:
            raise SystemExit("could not find initial_program.py, evaluator.py, and config file in source")
        name = safe_name(args.name or project_root.name or source.stem)
        target = state_dir(workspace) / "projects" / name
        copy_project(project_root, target, overwrite=args.overwrite)
    state["projects"][name] = {"path": str(target.resolve()), "imported": True, "source": str(source), "updatedAt": timestamp()}
    state["currentProject"] = name
    save_state(workspace, state)
    return {"ok": True, "status": "imported", "projectName": name, "projectPath": str(target.resolve()), "next": "validate"}


def cmd_select(args: argparse.Namespace, workspace: Path, state: dict[str, Any]) -> dict[str, Any]:
    name, path = selected_project(state, args.project)
    state["projects"].setdefault(name, {"path": str(path), "imported": False, "updatedAt": timestamp()})
    state["currentProject"] = name
    save_state(workspace, state)
    return {"ok": True, "status": "selected", "projectName": name, "projectPath": str(path), "next": "validate"}


def cmd_validate(args: argparse.Namespace, workspace: Path, state: dict[str, Any]) -> dict[str, Any]:
    name, path = selected_project(state, args.project)
    payload = validate_project(path)
    state.setdefault("projects", {}).setdefault(name, {"path": str(path)})
    state["projects"][name]["lastValidation"] = payload
    state["currentProject"] = name
    save_state(workspace, state)
    payload.update({"projectName": name, "next": "configure" if payload["ok"] else "repair files listed in errors"})
    return payload


def cmd_configure(args: argparse.Namespace, workspace: Path, state: dict[str, Any]) -> dict[str, Any]:
    config = state["config"]
    for key in ("mode", "iterations", "checkpoint_interval", "language", "agent"):
        value = getattr(args, key)
        if value is not None:
            config[key] = value
    if args.clear_extras:
        config["extras"] = {}
    for key, value in parse_extra(args.extra or []):
        config.setdefault("extras", {})[key] = value
    save_state(workspace, state)
    return {"ok": True, "status": "configured", "config": config, "next": "run --dry-run"}


def cmd_run(args: argparse.Namespace, workspace: Path, state: dict[str, Any]) -> dict[str, Any]:
    name, project = selected_project(state, args.project)
    validation = validate_project(project)
    if not validation["ok"] and not args.skip_validate:
        return {"ok": False, "status": "validation_failed", "projectName": name, "validation": validation, "next": "fix validation errors"}

    run_id = args.run_id or now_id()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else state_dir(workspace) / "runs" / run_id
    command, prompt = build_command(state, project, output_dir)
    payload = {
        "ok": True,
        "status": "planned" if args.dry_run else "running",
        "projectName": name,
        "projectPath": str(project),
        "runId": run_id,
        "outputDir": str(output_dir),
        "command": command,
        "prompt": prompt,
        "mode": state["config"].get("mode"),
    }
    if args.dry_run:
        state["lastPlan"] = payload
        save_state(workspace, state)
        return payload

    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "run.log"
    log = log_path.open("ab")
    proc = subprocess.Popen(command, cwd=str(project), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    log.close()
    run = {
        "id": run_id,
        "projectName": name,
        "projectPath": str(project),
        "outputDir": str(output_dir),
        "logPath": str(log_path),
        "pid": proc.pid,
        "status": "running",
        "mode": state["config"].get("mode"),
        "command": command,
        "prompt": prompt,
        "startedAt": timestamp(),
    }
    state["runs"][run_id] = run
    state["currentRun"] = run_id
    save_state(workspace, state)
    payload.update({"pid": proc.pid, "logPath": str(log_path), "next": "tail"})
    if args.foreground:
        code = proc.wait()
        run["returnCode"] = code
        run["status"] = "exited"
        run["endedAt"] = timestamp()
        save_state(workspace, state)
        payload.update({"status": "exited", "returnCode": code, "next": "summarize"})
    return payload


def cmd_record_run(args: argparse.Namespace, workspace: Path, state: dict[str, Any]) -> dict[str, Any]:
    name, project = selected_project(state, args.project)
    output_dir = Path(args.output_dir).expanduser().resolve()
    log_path = Path(args.log_path).expanduser().resolve() if args.log_path else output_dir / "run.log"
    try:
        command = json.loads(args.command_json) if args.command_json else []
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid --command-json: {exc}") from exc
    if command and (not isinstance(command, list) or not all(isinstance(item, str) for item in command)):
        raise SystemExit("--command-json must be a JSON string list")
    run = {
        "id": args.run_id,
        "projectName": name,
        "projectPath": str(project),
        "outputDir": str(output_dir),
        "logPath": str(log_path),
        "pid": int(args.pid or 0),
        "status": args.status,
        "mode": args.mode,
        "command": command,
        "startedAt": timestamp(),
        "external": True,
    }
    state["runs"][args.run_id] = run
    state["currentRun"] = args.run_id
    save_state(workspace, state)
    return {"ok": True, "status": "recorded", "runId": args.run_id, "projectName": name, "outputDir": str(output_dir), "logPath": str(log_path)}


def cmd_status(args: argparse.Namespace, workspace: Path, state: dict[str, Any]) -> dict[str, Any]:
    refresh_runs(state)
    save_state(workspace, state)
    current_run = state.get("currentRun", "")
    run = state.get("runs", {}).get(current_run, {}) if current_run else {}
    return {
        "ok": True,
        "status": "status",
        "workspace": str(workspace),
        "currentProject": state.get("currentProject", ""),
        "currentRun": current_run,
        "runStatus": run.get("status", ""),
        "config": state.get("config", {}),
        "projects": sorted(state.get("projects", {}).keys()),
        "runs": sorted(state.get("runs", {}).keys()),
    }


def cmd_tail(args: argparse.Namespace, workspace: Path, state: dict[str, Any]) -> dict[str, Any]:
    run_id, run = selected_run(state, args.run_id)
    log_path = Path(run.get("logPath") or Path(run["outputDir"]) / "run.log")
    lines: list[str] = []
    if log_path.is_file():
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-args.lines :]
    return {"ok": True, "status": "tail", "runId": run_id, "logPath": str(log_path), "lines": lines}


def cmd_stop(args: argparse.Namespace, workspace: Path, state: dict[str, Any]) -> dict[str, Any]:
    run_id, run = selected_run(state, args.run_id)
    pid = int(run.get("pid") or 0)
    if not process_alive(pid):
        run["status"] = "exited"
        save_state(workspace, state)
        return {"ok": True, "status": "not_running", "runId": run_id}
    try:
        os.killpg(pid, signal.SIGTERM)
    except Exception:
        os.kill(pid, signal.SIGTERM)
    run["status"] = "stopped"
    run["endedAt"] = timestamp()
    save_state(workspace, state)
    return {"ok": True, "status": "stopped", "runId": run_id, "pid": pid}


def list_tree(base: Path, max_depth: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base = base.resolve()
    for path in sorted(base.rglob("*")):
        rel = path.relative_to(base)
        if any(part in {".git", "__pycache__"} for part in rel.parts):
            continue
        if len(rel.parts) > max_depth:
            continue
        rows.append({"path": str(rel), "type": "dir" if path.is_dir() else "file", "size": path.stat().st_size if path.is_file() else 0})
    return rows


def base_for_target(state: dict[str, Any], target: str) -> Path:
    if target == "workspace":
        return Path(state["workspace"]).resolve()
    if target == "output":
        _, run = selected_run(state)
        return Path(run["outputDir"]).resolve()
    _, project = selected_project(state)
    return project


def cmd_tree(args: argparse.Namespace, workspace: Path, state: dict[str, Any]) -> dict[str, Any]:
    base = base_for_target(state, args.target)
    if not base.exists():
        return {"ok": False, "status": "missing", "base": str(base), "entries": []}
    return {"ok": True, "status": "tree", "target": args.target, "base": str(base), "entries": list_tree(base, args.max_depth)}


def cmd_read(args: argparse.Namespace, workspace: Path, state: dict[str, Any]) -> dict[str, Any]:
    base = base_for_target(state, args.target)
    path = (base / args.path).resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError as exc:
        raise SystemExit("path escapes selected target") from exc
    if not path.is_file():
        raise SystemExit(f"file does not exist: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")[: args.max_bytes]
    return {"ok": True, "status": "read", "target": args.target, "path": str(path), "content": text}


def cmd_summarize(args: argparse.Namespace, workspace: Path, state: dict[str, Any]) -> dict[str, Any]:
    if args.run_dir:
        run_dir = Path(args.run_dir).expanduser().resolve()
        run_id = ""
    else:
        run_id, run = selected_run(state, args.run_id)
        run_dir = Path(run["outputDir"]).resolve()
    payload = summarize(run_dir)
    payload.update({"ok": True, "status": "summary", "runId": run_id, "next": "inspect best program" if payload.get("hasBest") else "tail logs or rerun"})
    return payload


def cmd_next(args: argparse.Namespace, workspace: Path, state: dict[str, Any]) -> dict[str, Any]:
    refresh_runs(state)
    if not state.get("currentProject"):
        return {"ok": True, "status": "next", "next": "import a project or select an existing project"}
    name, project = selected_project(state)
    validation = validate_project(project)
    if not validation["ok"]:
        return {"ok": True, "status": "next", "projectName": name, "next": "fix validation errors", "validation": validation}
    if not state.get("currentRun"):
        plan = state.get("lastPlan") or {}
        if plan.get("projectName") == name:
            return {"ok": True, "status": "next", "projectName": name, "next": "run to start the planned command", "plan": plan}
        return {"ok": True, "status": "next", "projectName": name, "next": "configure parameters, then run --dry-run"}
    run_id, run = selected_run(state)
    if run.get("status") == "running":
        return {"ok": True, "status": "next", "runId": run_id, "next": "tail logs or stop the run"}
    summary = summarize(Path(run["outputDir"]))
    return {"ok": True, "status": "next", "runId": run_id, "next": "summarize results" if summary.get("hasBest") else "inspect logs, then rerun or adjust config", "summary": summary}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Interactive AI4Math-Evolving skill session CLI")
    p.add_argument("--workspace", default=".", help="workspace that stores .openevolve-agent/session.json")
    p.add_argument("--json", action="store_true", help="emit JSON")
    sub = p.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--project", default="")
    init.add_argument("--name", default="")
    init.set_defaults(func=cmd_init)

    imp = sub.add_parser("import")
    imp.add_argument("source")
    imp.add_argument("--name", default="")
    imp.add_argument("--overwrite", action="store_true")
    imp.set_defaults(func=cmd_import)

    select = sub.add_parser("select")
    select.add_argument("project")
    select.set_defaults(func=cmd_select)

    validate = sub.add_parser("validate")
    validate.add_argument("--project", default="")
    validate.set_defaults(func=cmd_validate)

    configure = sub.add_parser("configure")
    configure.add_argument("--mode", choices=["direct", "opencode"])
    configure.add_argument("--iterations", type=int)
    configure.add_argument("--checkpoint-interval", dest="checkpoint_interval", type=int)
    configure.add_argument("--language")
    configure.add_argument("--agent")
    configure.add_argument("--extra", action="append", default=[])
    configure.add_argument("--clear-extras", action="store_true")
    configure.set_defaults(func=cmd_configure)

    run = sub.add_parser("run")
    run.add_argument("--project", default="")
    run.add_argument("--run-id", default="")
    run.add_argument("--output-dir", default="")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--foreground", action="store_true")
    run.add_argument("--skip-validate", action="store_true")
    run.set_defaults(func=cmd_run)

    record = sub.add_parser("record-run")
    record.add_argument("--project", default="")
    record.add_argument("--run-id", required=True)
    record.add_argument("--output-dir", required=True)
    record.add_argument("--log-path", default="")
    record.add_argument("--pid", type=int, default=0)
    record.add_argument("--status", default="running")
    record.add_argument("--mode", choices=["direct", "opencode"], default="direct")
    record.add_argument("--command-json", default="")
    record.set_defaults(func=cmd_record_run)

    status = sub.add_parser("status")
    status.set_defaults(func=cmd_status)

    tail = sub.add_parser("tail")
    tail.add_argument("--run-id", default="")
    tail.add_argument("--lines", type=int, default=40)
    tail.set_defaults(func=cmd_tail)

    stop = sub.add_parser("stop")
    stop.add_argument("--run-id", default="")
    stop.set_defaults(func=cmd_stop)

    tree = sub.add_parser("tree")
    tree.add_argument("--target", choices=["project", "output", "workspace"], default="project")
    tree.add_argument("--max-depth", type=int, default=3)
    tree.set_defaults(func=cmd_tree)

    read = sub.add_parser("read")
    read.add_argument("path")
    read.add_argument("--target", choices=["project", "output", "workspace"], default="project")
    read.add_argument("--max-bytes", type=int, default=20000)
    read.set_defaults(func=cmd_read)

    summary = sub.add_parser("summarize")
    summary.add_argument("--run-id", default="")
    summary.add_argument("--run-dir", default="")
    summary.set_defaults(func=cmd_summarize)

    nxt = sub.add_parser("next")
    nxt.set_defaults(func=cmd_next)

    return p


def main() -> int:
    p = parser()
    args = p.parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    state = load_state(workspace)
    payload = args.func(args, workspace, state)
    emit(payload, args.json)
    return 0 if payload.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
