#!/usr/bin/env python3
"""
AI4Math-Evolving <-> Frontend Bridge (标准库无依赖版)

功能：
  - 文件管理（zip 上传、项目列表、输出列表、文件浏览）
  - opencode CLI 桥接（通过 opencode 子代理调用 OpenEvolve）

接口：
  文件管理：
    GET  /api/projects
    GET  /api/outputs
    POST /api/projects/upload     (multipart/form-data: zip, projectName)
    GET  /api/projects/{name}/tree
    GET  /api/projects/{name}/file
    GET  /api/projects/{name}/download
    GET  /api/projects/{name}/metrics-schema
    POST /api/projects/{name}/file
    DELETE /api/projects/{name}
    GET  /api/outputs/{project}/{runId}/tree
    GET  /api/outputs/{project}/{runId}/file
    GET  /api/outputs/{project}/{runId}/download
    GET  /api/outputs/{project}/{runId}/archive
    GET  /api/outputs/{project}/{runId}/trend
    GET  /api/outputs/{project}/{runId}/artifacts
    DELETE /api/outputs/{project}/{runId}
    GET  /api/outputs/{project}/{runId}/analyses
    GET  /api/outputs/{project}/{runId}/analyses/{id}
    GET  /api/outputs/{project}/{runId}/analyses/{id}/download
    POST /api/outputs/{project}/{runId}/analyze
    DELETE /api/outputs/{project}/{runId}/analyses/{id}

  opencode 演化桥接：
    POST /api/runs/start            (json: projectName, iterations)
    POST /api/runs/{runId}/stop
    GET  /api/runs/{runId}/events  (SSE: 实时推送 opencode stdout 解析结果)
"""

from __future__ import annotations

import ast
import io
import hashlib
import json
import mimetypes
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
import select
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.error import URLError
from urllib.request import urlopen
from email.parser import BytesParser
from email.policy import default as email_default_policy

try:
    from llm_client import LLMClientError, analyze_with_deepseek

    HAS_LLM = True
except ImportError:
    HAS_LLM = False

try:
    from services.ops_guard import append_audit_log, require_write_auth
except Exception:

    def append_audit_log(*a, **k) -> None:
        pass

    def require_write_auth(h, *a, **k):
        return True, ""

    class LLMClientError(Exception):
        pass

try:
    from skill_runner import (
        SkillRunnerError,
        build_run_command,
        provider_extras_from_env,
        record_external_run,
    )
except ImportError:
    try:
        from backend.skill_runner import (
            SkillRunnerError,
            build_run_command,
            provider_extras_from_env,
            record_external_run,
        )
    except ImportError:
        build_run_command = None
        provider_extras_from_env = None
        record_external_run = None

        class SkillRunnerError(Exception):
            pass


ROOT_DIR = Path(__file__).resolve().parents[1]
SERVER_DATA_DIR = ROOT_DIR / "server_data"
SERVER_DATA_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = ROOT_DIR / ".env"
MAX_JSON_BODY_BYTES = 1024 * 1024
MAX_UPLOAD_BODY_BYTES = 200 * 1024 * 1024
AUDIT_LOG_FILE = ROOT_DIR / "server_data" / "_audit.log"
VISUALIZER_SCRIPT_DEFAULT = ROOT_DIR.parent / "openevolve" / "scripts" / "visualizer.py"


class PayloadTooLargeError(ValueError):
    pass


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("export "):
            s = s[7:].strip()
        if "=" not in s:
            continue
        key, _, value = s.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not key:
            continue
        if key not in os.environ:
            os.environ[key] = value


REQUIRED_FILES = ["initial_program.py", "evaluator.py"]
CONFIG_FILES = ["config.yaml", "config_default.yaml", "config.yml"]


def _json_response(
    handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]
) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


def _read_json_body(
    handler: BaseHTTPRequestHandler, max_bytes: int = MAX_JSON_BODY_BYTES
) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length > max_bytes:
        raise PayloadTooLargeError(f"json body too large (>{max_bytes} bytes)")
    raw = handler.rfile.read(length) if length > 0 else b""
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _safe_extract_zip(zip_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            member_name = member.filename
            if member_name.startswith("/") or member_name.startswith("\\"):
                raise ValueError(f"zip member has absolute path: {member_name}")
            parts = Path(member_name).parts
            if any(p == ".." for p in parts):
                raise ValueError(f"zip member has path traversal: {member_name}")
        zf.extractall(dest_dir)


def _find_first_recursive(project_dir: Path, filename: str) -> Path | None:
    for p in project_dir.rglob(filename):
        if p.is_file():
            return p
    return None


def _ensure_required_files_at_root(project_dir: Path) -> tuple[Path, Path, Path]:
    required_paths: dict[str, Path] = {}
    for name in REQUIRED_FILES:
        root_p = project_dir / name
        if root_p.exists():
            required_paths[name] = root_p
            continue
        found = _find_first_recursive(project_dir, name)
        if not found:
            raise FileNotFoundError(f"missing required file: {name}")
        root_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(found), str(root_p))
        required_paths[name] = root_p

    config_path: Path | None = None
    for cfg in CONFIG_FILES:
        root_cfg = project_dir / cfg
        if root_cfg.exists():
            config_path = root_cfg
            break
    if not config_path:
        for cfg in CONFIG_FILES:
            found = _find_first_recursive(project_dir, cfg)
            if found:
                root_cfg = project_dir / cfg
                shutil.move(str(found), str(root_cfg))
                config_path = root_cfg
                break
    if not config_path:
        raise FileNotFoundError(
            "missing config file (config.yaml or config_default.yaml)"
        )

    return (
        required_paths["initial_program.py"],
        required_paths["evaluator.py"],
        config_path,
    )


def _override_checkpoint_interval(project_dir: Path, checkpoint_interval: int) -> None:
    """Persist checkpoint_interval into project config before run starts."""
    cfg_path: Path | None = None
    for name in CONFIG_FILES:
        p = project_dir / name
        if p.exists() and p.is_file():
            cfg_path = p
            break
    if cfg_path is None:
        raise FileNotFoundError("missing config file for checkpoint override")

    raw = cfg_path.read_text(encoding="utf-8")
    line = f"checkpoint_interval: {checkpoint_interval}"
    if re.search(r"(?m)^\s*checkpoint_interval\s*:", raw):
        patched = re.sub(
            r"(?m)^(\s*checkpoint_interval\s*:\s*).*$",
            rf"\g<1>{checkpoint_interval}",
            raw,
            count=1,
        )
    else:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        patched = raw + line + "\n"
    if patched != raw:
        cfg_path.write_text(patched, encoding="utf-8")


def _override_num_islands(project_dir: Path, num_islands: int) -> None:
    """Persist num_islands into project config before run starts."""
    cfg_path: Path | None = None
    for name in CONFIG_FILES:
        p = project_dir / name
        if p.exists() and p.is_file():
            cfg_path = p
            break
    if cfg_path is None:
        raise FileNotFoundError("missing config file for num_islands override")

    raw = cfg_path.read_text(encoding="utf-8")
    line = f"  num_islands: {num_islands}"
    if re.search(r"(?m)^\s*num_islands\s*:", raw):
        patched = re.sub(
            r"(?m)^(\s*num_islands\s*:\s*).*$",
            rf"\g<1>{num_islands}",
            raw,
            count=1,
        )
    else:
        if re.search(r"(?m)^\s*database\s*:\s*$", raw):
            patched = re.sub(
                r"(?m)^(\s*database\s*:\s*$)",
                rf"\1\n{line}",
                raw,
                count=1,
            )
        else:
            if raw and not raw.endswith("\n"):
                raw += "\n"
            patched = raw + "database:\n" + line + "\n"
    if patched != raw:
        cfg_path.write_text(patched, encoding="utf-8")


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value)
    if s == "":
        return '""'
    return s


def _override_config_value(project_dir: Path, key_path: str, value: Any) -> None:
    """Persist a scalar config value by dotted path, e.g. database.population_size."""
    cfg_path: Path | None = None
    for name in CONFIG_FILES:
        p = project_dir / name
        if p.exists() and p.is_file():
            cfg_path = p
            break
    if cfg_path is None:
        raise FileNotFoundError("missing config file for settings override")

    raw = cfg_path.read_text(encoding="utf-8")
    yaml_value = _yaml_scalar(value)
    parts = [x.strip() for x in key_path.split(".") if x.strip()]
    if not parts:
        return

    if len(parts) == 1:
        key = parts[0]
        line = f"{key}: {yaml_value}"
        if re.search(rf"(?m)^\s*{re.escape(key)}\s*:", raw):
            patched = re.sub(
                rf"(?m)^(\s*{re.escape(key)}\s*:\s*).*$",
                rf"\g<1>{yaml_value}",
                raw,
                count=1,
            )
        else:
            if raw and not raw.endswith("\n"):
                raw += "\n"
            patched = raw + line + "\n"
        if patched != raw:
            cfg_path.write_text(patched, encoding="utf-8")
        return

    section = parts[0]
    sub_key = parts[1]
    section_pat = rf"(?m)^\s*{re.escape(section)}\s*:\s*$"
    sub_line = f"  {sub_key}: {yaml_value}"
    if re.search(section_pat, raw):
        lines = raw.splitlines()
        out: list[str] = []
        in_section = False
        inserted_or_replaced = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            is_section_line = bool(re.match(section_pat, line))
            if is_section_line:
                in_section = True
                out.append(line)
                continue

            if in_section:
                is_top_level = bool(re.match(r"^\S", line))
                if is_top_level:
                    if not inserted_or_replaced:
                        out.append(sub_line)
                        inserted_or_replaced = True
                    in_section = False
                else:
                    if re.match(rf"^\s+{re.escape(sub_key)}\s*:", line):
                        prefix = re.sub(rf"^(\s*{re.escape(sub_key)}\s*:\s*).*$", r"\1", line)
                        out.append(f"{prefix}{yaml_value}")
                        inserted_or_replaced = True
                        continue
            out.append(line)

        if in_section and not inserted_or_replaced:
            out.append(sub_line)
            inserted_or_replaced = True
        patched = "\n".join(out)
        if raw.endswith("\n"):
            patched += "\n"
    else:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        patched = raw + f"{section}:\n{sub_line}\n"

    if patched != raw:
        cfg_path.write_text(patched, encoding="utf-8")


def _list_project_files(project_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    key_files = [
        "initial_program.py",
        "evaluator.py",
        "config.yaml",
        "config_default.yaml",
        "README.md",
        "USAGE.md",
        "run_evolution.py",
        "run_evolution.sh",
    ]
    for name in key_files:
        p = project_dir / name
        if p.exists() and p.is_file():
            out.append(
                {"name": name, "type": "file", "extension": p.suffix.lstrip(".")}
            )
    if not out:
        for p in project_dir.rglob("*"):
            if p.is_file():
                out.append(
                    {
                        "name": p.relative_to(project_dir).as_posix(),
                        "type": "file",
                        "extension": p.suffix.lstrip("."),
                    }
                )
                if len(out) >= 12:
                    break
    return out


def _extract_numeric_metrics(raw_metrics: Any) -> dict[str, float]:
    out: dict[str, float] = {}
    if not isinstance(raw_metrics, dict):
        return out
    for k, v in raw_metrics.items():
        if isinstance(v, (int, float)):
            out[str(k)] = float(v)
    return out


def _pick_fitness_metric(metrics: dict[str, float]) -> tuple[str | None, float | None]:
    if "combined_score" in metrics:
        return "combined_score", float(metrics["combined_score"])
    for k, v in metrics.items():
        return k, float(v)
    return None, None


def _collect_output_runs() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for proj in sorted(SERVER_DATA_DIR.iterdir(), key=lambda x: x.name):
        if not proj.is_dir():
            continue
        od = proj / "openevolve_output"
        if not od.is_dir():
            continue
        for run in od.iterdir():
            if not run.is_dir():
                continue
            run_id = run.name
            best_info = run / "best" / "best_program_info.json"
            combined: float | None = None
            primary_metric_name: str | None = None
            primary_metric_value: float | None = None
            all_metrics: dict[str, float] = {}
            fitness_key: str | None = None
            if best_info.exists():
                try:
                    j = json.loads(best_info.read_text(encoding="utf-8"))
                    metrics = _extract_numeric_metrics(j.get("metrics") or {})
                    all_metrics = metrics
                    fitness_key, fitness_value = _pick_fitness_metric(metrics)
                    primary_metric_name = fitness_key
                    primary_metric_value = fitness_value
                    if "combined_score" in metrics:
                        combined = float(metrics["combined_score"])
                except Exception:
                    pass
            try:
                mtime = run.stat().st_mtime
            except OSError:
                mtime = 0.0
            runs.append(
                {
                    "projectName": proj.name,
                    "runId": run_id,
                    "outputDir": str(run),
                    "mtime": mtime,
                    "bestCombined": combined,
                    "primaryMetricName": primary_metric_name,
                    "primaryMetricValue": primary_metric_value,
                    "fitnessKey": fitness_key,
                    "allMetrics": all_metrics,
                }
            )
    runs.sort(key=lambda x: -float(x["mtime"]))
    return runs


def _list_tree(
    root: Path,
    max_depth: int = 5,
    max_entries: int = 1200,
    exclude_top_dirs: set[str] | None = None,
) -> list[dict[str, Any]]:
    max_depth = max(1, min(max_depth, 8))
    entries: list[dict[str, Any]] = []
    root_resolved = root.resolve()
    excluded = exclude_top_dirs or set()
    for p in root_resolved.rglob("*"):
        if len(entries) >= max_entries:
            break
        try:
            rel = p.relative_to(root_resolved)
        except ValueError:
            continue
        if rel.parts and rel.parts[0] in excluded:
            continue
        if len(rel.parts) > max_depth:
            continue
        is_dir = p.is_dir()
        size = 0 if is_dir else p.stat().st_size
        entries.append({"path": rel.as_posix(), "isDir": is_dir, "size": size})
    entries.sort(key=lambda x: (x["isDir"] is False, x["path"]))
    return entries


def _safe_rooted_path(root: Path, rel_path: str) -> Path:
    if not rel_path:
        raise ValueError("missing file path")
    if Path(rel_path).is_absolute():
        raise ValueError("absolute path is not allowed")
    cleaned = rel_path.strip().lstrip("/").lstrip("\\")
    if not cleaned:
        raise ValueError("invalid file path")
    resolved = (root / cleaned).resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("path traversal is not allowed") from exc
    return resolved


def _send_file_download(handler: BaseHTTPRequestHandler, file_path: Path) -> None:
    data = file_path.read_bytes()
    ctype, _ = mimetypes.guess_type(file_path.name)
    if not ctype:
        ctype = "application/octet-stream"
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header(
        "Content-Disposition", f'attachment; filename="{file_path.name}"'
    )
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(data)


def _send_directory_zip_download(
    handler: BaseHTTPRequestHandler, dir_path: Path, zip_name: str
) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in dir_path.rglob("*"):
            if not p.is_file():
                continue
            arcname = p.relative_to(dir_path).as_posix()
            zf.write(p, arcname=arcname)
    data = buf.getvalue()
    handler.send_response(200)
    handler.send_header("Content-Type", "application/zip")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Content-Disposition", f'attachment; filename="{zip_name}"')
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(data)


def _to_positive_int(raw: str | None, default: int) -> int:
    try:
        parsed = int(str(raw or "").strip())
        return parsed if parsed > 0 else default
    except Exception:
        return default


def _kill_processes_listening_on_port(port: int) -> None:
    pids: set[int] = set()
    if port <= 0:
        return
    try:
        out = subprocess.check_output(
            ["lsof", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        for line in out.splitlines():
            s = line.strip()
            if not s:
                continue
            try:
                pids.add(int(s))
            except Exception:
                continue
    except Exception:
        pass
    if not pids:
        return
    for pid in sorted(pids):
        if pid <= 1 or pid == os.getpid():
            continue
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            continue
    time.sleep(0.25)
    for pid in sorted(pids):
        if pid <= 1 or pid == os.getpid():
            continue
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            continue


# ── opencode CLI 桥接：Run State ─────────────────────────────────────────────
_RUN_LOCK = threading.Lock()
_RUNS: dict[str, dict] = {}
_SCENARIO_LOCK = threading.Lock()
_SCENARIO_SESSIONS: dict[str, dict[str, Any]] = {}
_SCENARIO_DRAFT_ROOT = SERVER_DATA_DIR / "_scenario_drafts"
_SCENARIO_DRAFT_ROOT.mkdir(parents=True, exist_ok=True)
_VISUALIZER_LOCK = threading.Lock()
_VISUALIZER_STATE: dict[str, Any] = {
    "proc": None,
    "host": "127.0.0.1",
    "port": 8088,
    "project_name": "",
    "run_id": "",
    "run_output_dir": "",
    "started_at": 0.0,
}


def _default_run_id() -> str:
    ts = time.strftime("%Y%m%d_%H%M")
    suffix = uuid.uuid4().hex[:4]
    return f"run_{ts}_{suffix}"


def _default_scenario_session_id() -> str:
    ts = time.strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"sess_{ts}_{suffix}"


def _scenario_persist_draft_files(session: dict[str, Any], files: dict[str, str]) -> dict[str, str]:
    session_id = str(session.get("id") or _default_scenario_session_id())
    draft_dir = _SCENARIO_DRAFT_ROOT / session_id
    draft_dir.mkdir(parents=True, exist_ok=True)
    initial_path = draft_dir / "initial_program.py"
    evaluator_path = draft_dir / "evaluator.py"
    config_path = draft_dir / "config.yaml"
    initial_path.write_text(str(files.get("initialProgram") or ""), encoding="utf-8")
    evaluator_path.write_text(str(files.get("evaluator") or ""), encoding="utf-8")
    config_path.write_text(str(files.get("configYaml") or ""), encoding="utf-8")
    rel_dir = draft_dir.relative_to(ROOT_DIR).as_posix()
    persisted = {
        "draftDir": rel_dir,
        "initialProgramPath": initial_path.relative_to(ROOT_DIR).as_posix(),
        "evaluatorPath": evaluator_path.relative_to(ROOT_DIR).as_posix(),
        "configYamlPath": config_path.relative_to(ROOT_DIR).as_posix(),
    }
    session["result"]["draftStorage"] = persisted
    return persisted


def _scenario_publish(session: dict[str, Any], event_type: str, payload: dict[str, Any]) -> None:
    with session["lock"]:
        session["seq"] = int(session.get("seq") or 0) + 1
        ev = {
            "eventType": event_type,
            "sessionId": session["id"],
            "timestamp": int(time.time() * 1000),
            "seq": session["seq"],
            "payload": payload,
        }
        session["events"].append(ev)
        dead: list[queue.Queue] = []
        for q in session["subs"]:
            try:
                q.put_nowait(ev)
            except Exception:
                dead.append(q)
        if dead:
            session["subs"] = [q for q in session["subs"] if q not in dead]


def _assess_scenario_gate(payload: dict[str, Any]) -> dict[str, Any]:
    problem = str(payload.get("problemDescription") or "").strip()
    objective = str(payload.get("objectiveType") or "").strip().lower()
    has_auto_eval = bool(payload.get("hasAutoEvaluation") is True)
    constraints = str(payload.get("constraints") or "").strip()
    io_contract = str(payload.get("ioContract") or "").strip()
    missing: list[str] = []
    reasons: list[str] = []
    fallback: list[str] = []
    if not problem:
        missing.append("problemDescription")
    if objective not in {"maximize", "minimize"}:
        missing.append("objectiveType(maximize|minimize)")
    if not has_auto_eval:
        missing.append("hasAutoEvaluation=true")
        fallback.append("当前任务缺少自动评测，不建议直接用 evolve。")
    if not io_contract:
        missing.append("ioContract")
    if not constraints:
        reasons.append("建议补充约束（超时、内存、依赖）以提高生成质量。")
    fit = len(missing) == 0
    score = 1.0 if fit else max(0.0, 1.0 - len(missing) * 0.2)
    if fit:
        reasons.insert(0, "任务具备可执行、可评分和契约约束，适合进入 OpenCode 生成流程。")
    else:
        reasons.insert(0, "当前信息不足以稳定驱动演化流程。")
        fallback.extend(
            [
                "可先用固定算法实现可运行版本，再补充评测指标。",
                "也可以先拆分为可评测子任务，再接入 evolve。",
            ]
        )
    return {
        "fit": fit,
        "score": round(score, 2),
        "reasons": reasons,
        "missingInfo": missing,
        "fallbackAdvice": fallback,
    }


def _scenario_default_files(intake: dict[str, Any]) -> dict[str, str]:
    objective = str(intake.get("objectiveType") or "minimize").strip().lower()
    objective_comment = "minimize score" if objective != "maximize" else "maximize score"
    task = str(intake.get("problemDescription") or "Custom optimization task").strip()
    contract = str(intake.get("ioContract") or "run_search() -> tuple").strip()
    primary_metric = str(intake.get("primaryMetric") or "combined_score").strip() or "combined_score"
    baseline_code = str(intake.get("baselineCode") or "").strip()
    initial_program = baseline_code or (
        "# EVOLVE-BLOCK-START\n"
        f'"""Auto-generated baseline for: {task}"""\n\n'
        "import random\n\n"
        "def run_search(iterations: int = 100):\n"
        "    best = None\n"
        "    for _ in range(max(1, iterations)):\n"
        "        candidate = random.random()\n"
        "        if best is None or candidate < best:\n"
        "            best = candidate\n"
        "    return best\n"
        "# EVOLVE-BLOCK-END\n\n"
        f"# Contract: {contract}\n"
    )
    evaluator = (
        '"""Auto-generated evaluator for OpenEvolve scenario."""\n\n'
        "import importlib.util\n"
        "from openevolve.evaluation_result import EvaluationResult\n\n"
        "def evaluate(program_path):\n"
        '    spec = importlib.util.spec_from_file_location("program", program_path)\n'
        "    program = importlib.util.module_from_spec(spec)\n"
        "    spec.loader.exec_module(program)\n"
        '    if not hasattr(program, "run_search"):\n'
        '        return EvaluationResult(metrics={"combined_score": 0.0, "error": "missing run_search"})\n'
        "    result = program.run_search()\n"
        "    try:\n"
        "        score = float(result if not isinstance(result, tuple) else result[-1])\n"
        "    except Exception:\n"
        "        score = 0.0\n"
        f"    # Objective: {objective_comment}\n"
        f'    return EvaluationResult(metrics={{"{primary_metric}": score, "combined_score": score}})\n'
    )
    config = (
        "max_iterations: 20\n"
        "checkpoint_interval: 2\n\n"
        "llm:\n"
        '  primary_model: "deepseek-chat"\n'
        '  secondary_model: "deepseek-chat"\n'
        "  secondary_model_weight: 0.0\n"
        '  api_base: "https://api.deepseek.com"\n'
        "  api_key: \"${DEEPSEEK_API_KEY}\"\n"
        "  temperature: 0.7\n"
        "  max_tokens: 8000\n"
        "  timeout: 300\n\n"
        "prompt:\n"
        f'  system_message: "{task.replace(chr(34), chr(39))}"\n\n'
        "database:\n"
        "  population_size: 30\n"
        "  archive_size: 10\n"
        "  num_islands: 2\n"
        "  elite_selection_ratio: 0.2\n"
        "  exploitation_ratio: 0.7\n"
        "  similarity_threshold: 0.99\n"
        "  mutation_rate: 0.1\n\n"
        "evaluator:\n"
        "  timeout: 30\n"
        "  parallel_evaluations: 2\n\n"
        "diff_based_evolution: false\n"
    )
    return {
        "initialProgram": initial_program,
        "evaluator": evaluator,
        "configYaml": config,
    }


def _scenario_extract_file_block(text: str, filename: str) -> str:
    def _strip_fence(s: str) -> str:
        val = (s or "").strip()
        m = re.match(r"^```[a-zA-Z0-9_-]*\n(.*)\n```$", val, re.DOTALL)
        if m:
            return m.group(1).strip()
        return val

    # 1) Legacy protocol: ===FILE:name=== ... ===FILE:next=== / ===END===
    pattern_legacy = rf"===FILE:{re.escape(filename)}===\n(.*?)(?=\n===FILE:|\n===END===|\Z)"
    m_legacy = re.search(pattern_legacy, text, re.DOTALL)
    if m_legacy:
        return _strip_fence(m_legacy.group(1))

    # 2) XML-like protocol: <file path="name"> ... </file>
    pattern_xml = rf"<file\s+path=[\"']{re.escape(filename)}[\"']>\s*(.*?)\s*</file>"
    m_xml = re.search(pattern_xml, text, re.DOTALL | re.IGNORECASE)
    if m_xml:
        return _strip_fence(m_xml.group(1))

    # 3) Fenced blocks annotated with filename:
    #    ```python
    #    # FILE: initial_program.py
    #    ...
    #    ```
    pattern_annotated = (
        rf"```[a-zA-Z0-9_-]*\n"
        rf"(?:#|//)\s*FILE:\s*{re.escape(filename)}\s*\n"
        rf"(.*?)\n```"
    )
    m_annotated = re.search(pattern_annotated, text, re.DOTALL | re.IGNORECASE)
    if m_annotated:
        return (m_annotated.group(1) or "").strip()

    return ""


def _scenario_load_skill_text(skill_name: str) -> tuple[str, str]:
    normalized = re.sub(r"[^a-z0-9\-]", "", str(skill_name or "").strip().lower())
    if not normalized:
        normalized = "opencode-scenario-builder"
    skill_path = ROOT_DIR / ".cursor" / "skills" / normalized / "SKILL.md"
    try:
        if skill_path.exists() and skill_path.is_file():
            return normalized, skill_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass
    return normalized, ""


def _scenario_build_opencode_prompt(
    intake: dict[str, Any],
    skill_name: str,
    skill_text: str,
    seed_files: dict[str, str] | None = None,
    validation_report: dict[str, Any] | None = None,
    user_feedback: str = "",
) -> str:
    problem = str(intake.get("problemDescription") or "").strip()
    objective = str(intake.get("objectiveType") or "minimize").strip()
    contract = str(intake.get("ioContract") or "run_search()").strip()
    metric = str(intake.get("primaryMetric") or "combined_score").strip() or "combined_score"
    constraints = str(intake.get("constraints") or "").strip()
    baseline = str(intake.get("baselineCode") or "").strip()
    report_json = json.dumps(validation_report or {}, ensure_ascii=False)
    seed_initial = str((seed_files or {}).get("initialProgram") or "").strip()
    seed_eval = str((seed_files or {}).get("evaluator") or "").strip()
    seed_cfg = str((seed_files or {}).get("configYaml") or "").strip()
    return (
        "Language requirement (strict): All natural-language responses MUST be in Simplified Chinese (zh-CN) only.\n"
        "你是 OpenEvolve 场景项目生成助手。请根据需求创建可运行的三件套：initial_program.py / evaluator.py / config.yaml。\n"
        f"必须优先遵循技能规范 skill={skill_name}。\n"
        "必须遵循：\n"
        "1) initial_program.py 提供 run_search 入口；包含 EVOLVE-BLOCK-START/END。\n"
        "2) evaluator.py 提供 evaluate(program_path)，返回 EvaluationResult(metrics={...})，包含 combined_score。\n"
        "3) config.yaml 必须含 max_iterations 与 checkpoint_interval，且 api_key 使用 ${DEEPSEEK_API_KEY} 占位，不得明文。\n"
        f"\n[任务描述]\n{problem or '(空)'}\n"
        f"\n[目标类型]\n{objective}\n"
        f"\n[运行契约]\n{contract}\n"
        f"\n[主指标]\n{metric}\n"
        f"\n[约束]\n{constraints or '(空)'}\n"
        f"\n[baselineCode]\n{baseline or '(无)'}\n"
        f"\n[已有草案-initial]\n{seed_initial or '(无)'}\n"
        f"\n[已有草案-evaluator]\n{seed_eval or '(无)'}\n"
        f"\n[已有草案-config]\n{seed_cfg or '(无)'}\n"
        f"\n[上轮校验报告]\n{report_json}\n"
        f"\n[用户反馈]\n{user_feedback or '(无)'}\n"
        f"\n[技能文本]\n{skill_text or '(未找到技能文本，回退到内置规范)'}\n"
        "\n输出格式（必须严格遵守；不要输出额外解释）：\n"
        "<file path=\"initial_program.py\">\n```python\n# FILE: initial_program.py\n<内容>\n```\n</file>\n"
        "<file path=\"evaluator.py\">\n```python\n# FILE: evaluator.py\n<内容>\n```\n</file>\n"
        "<file path=\"config.yaml\">\n```yaml\n# FILE: config.yaml\n<内容>\n```\n</file>\n"
        "===END===\n"
        "\n重要：每个 file block 都必须完整闭合，且文件内容放在代码块内。"
    )


def _scenario_generate_with_opencode(
    intake: dict[str, Any],
    skill_name: str,
    seed_files: dict[str, str] | None = None,
    validation_report: dict[str, Any] | None = None,
    user_feedback: str = "",
    session: dict[str, Any] | None = None,
) -> tuple[dict[str, str], str, dict[str, Any]]:
    normalized_skill, skill_text = _scenario_load_skill_text(skill_name)
    prompt = _scenario_build_opencode_prompt(
        intake=intake,
        skill_name=normalized_skill,
        skill_text=skill_text,
        seed_files=seed_files,
        validation_report=validation_report,
        user_feedback=user_feedback,
    )
    agent = (
        os.environ.get("OPENCODE_SCENARIO_AGENT", "").strip()
        or os.environ.get("OPENCODE_EVOLVE_AGENT", "").strip()
        or "openevolve-unified-primary"
    )
    cmd = ["opencode", "run", "--agent", agent, "--dir", str(ROOT_DIR), prompt]
    timeout_sec = max(30, min(int(os.environ.get("OPENCODE_SCENARIO_TIMEOUT", "180")), 600))
    heartbeat_interval = 5.0
    max_log_len = 500
    if session is not None:
        _scenario_publish(
            session,
            "log",
            {
                "level": "info",
                "source": "opencode-stream",
                "message": f"OpenCode 已启动（agent={agent}），正在流式生成...",
            },
        )
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(ROOT_DIR),
        )
        start_ts = time.monotonic()
        last_heartbeat = start_ts
        timed_out = False
        raw_lines: list[str] = []
        line_q: queue.Queue[str] = queue.Queue(maxsize=1024)

        def _reader() -> None:
            try:
                stdout = proc.stdout
                if stdout is None:
                    return
                for ln in stdout:
                    try:
                        line_q.put_nowait(ln)
                    except Exception:
                        # queue full: drop oldest by draining one item first
                        try:
                            _ = line_q.get_nowait()
                            line_q.put_nowait(ln)
                        except Exception:
                            pass
            except Exception:
                pass

        reader_thread = threading.Thread(target=_reader, daemon=True)
        reader_thread.start()

        while True:
            now = time.monotonic()
            if proc.poll() is None and now - start_ts > float(timeout_sec):
                timed_out = True
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                ln = line_q.get(timeout=0.3)
                txt = str(ln or "")
                if txt:
                    raw_lines.append(txt)
                    if session is not None:
                        msg = txt.strip()
                        if msg:
                            if len(msg) > max_log_len:
                                msg = msg[:max_log_len] + "...(truncated)"
                            _scenario_publish(
                                session,
                                "log",
                                {"level": "info", "source": "opencode-stream", "message": msg},
                            )
                continue
            except Exception:
                pass

            now = time.monotonic()
            if session is not None and proc.poll() is None and now - last_heartbeat >= heartbeat_interval:
                last_heartbeat = now
                _scenario_publish(
                    session,
                    "log",
                    {"level": "info", "source": "opencode-stream", "message": "OpenCode 仍在生成中，请稍候..."},
                )

            if proc.poll() is not None and line_q.empty():
                break

        try:
            if proc.stdout is not None:
                proc.stdout.close()
        except Exception:
            pass
        reader_thread.join(timeout=0.5)
        raw = "".join(raw_lines)
        exit_code = int(proc.returncode or 0)
        if timed_out:
            if session is not None:
                _scenario_publish(
                    session,
                    "log",
                    {
                        "level": "error",
                        "source": "opencode-stream",
                        "message": f"OpenCode 生成超时（>{timeout_sec}s），已终止并回退模板。",
                    },
                )
            return (
                _scenario_default_files(intake),
                f"fallback_template(opencode_timeout,skill={normalized_skill})",
                {
                    "generationSource": "fallback",
                    "generationError": f"opencode_timeout: exceeded {timeout_sec}s",
                    "rawPreview": raw[:1200],
                    "exitCode": exit_code,
                },
            )
        initial_program = _scenario_extract_file_block(raw, "initial_program.py")
        evaluator = _scenario_extract_file_block(raw, "evaluator.py")
        config_yaml = _scenario_extract_file_block(raw, "config.yaml")
        if initial_program and evaluator and config_yaml:
            if session is not None:
                _scenario_publish(
                    session,
                    "log",
                    {"level": "info", "source": "opencode-stream", "message": "OpenCode 输出解析成功，三件套已生成。"},
                )
            return (
                {
                    "initialProgram": initial_program,
                    "evaluator": evaluator,
                    "configYaml": config_yaml,
                },
                f"generated_by_opencode(skill={normalized_skill})",
                {
                    "generationSource": "opencode",
                    "generationError": "",
                    "rawPreview": raw[:1200],
                    "exitCode": exit_code,
                },
            )
        if session is not None:
            _scenario_publish(
                session,
                "log",
                {"level": "warn", "source": "opencode-stream", "message": "OpenCode 输出无法完整解析，已回退模板。"},
            )
        return (
            _scenario_default_files(intake),
            f"fallback_template(parse_failed,skill={normalized_skill})",
            {
                "generationSource": "fallback",
                "generationError": (
                    f"parse_failed: missing file blocks, exit={exit_code}"
                ),
                "rawPreview": raw[:1200],
                "exitCode": exit_code,
            },
        )
    except Exception as e:
        return (
            _scenario_default_files(intake),
            f"fallback_template(opencode_failed,skill={normalized_skill})",
            {
                "generationSource": "fallback",
                "generationError": f"opencode_failed: {e}",
                "rawPreview": "",
                "exitCode": None,
            },
        )


def _validate_scenario_files(files: dict[str, str]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    suggestions: list[str] = []

    initial = str(files.get("initialProgram") or "")
    evaluator = str(files.get("evaluator") or "")
    config = str(files.get("configYaml") or "")

    if not initial.strip():
        errors.append({"code": "missing_initial", "message": "initialProgram 为空", "path": "initial_program.py"})
    if not evaluator.strip():
        errors.append({"code": "missing_evaluator", "message": "evaluator 为空", "path": "evaluator.py"})
    if not config.strip():
        errors.append({"code": "missing_config", "message": "configYaml 为空", "path": "config.yaml"})

    if initial.strip():
        try:
            ast.parse(initial, filename="initial_program.py")
        except SyntaxError as e:
            errors.append(
                {
                    "code": "initial_syntax",
                    "message": f"initial_program.py 语法错误: {e.msg}",
                    "path": "initial_program.py",
                    "line": int(e.lineno or 0),
                }
            )
        if "def run_search" not in initial:
            errors.append(
                {
                    "code": "missing_run_search",
                    "message": "initial_program.py 缺少 run_search 入口",
                    "path": "initial_program.py",
                }
            )
        if ("EVOLVE-BLOCK-START" not in initial) or ("EVOLVE-BLOCK-END" not in initial):
            errors.append(
                {
                    "code": "missing_evolve_block_markers",
                    "message": "initial_program.py 缺少 EVOLVE-BLOCK-START/END 标记",
                    "path": "initial_program.py",
                }
            )
    if evaluator.strip():
        try:
            ast.parse(evaluator, filename="evaluator.py")
        except SyntaxError as e:
            errors.append(
                {
                    "code": "evaluator_syntax",
                    "message": f"evaluator.py 语法错误: {e.msg}",
                    "path": "evaluator.py",
                    "line": int(e.lineno or 0),
                }
            )
        if "def evaluate" not in evaluator:
            errors.append(
                {
                    "code": "missing_evaluate",
                    "message": "evaluator.py 缺少 evaluate 入口",
                    "path": "evaluator.py",
                }
            )
        if "combined_score" not in evaluator:
            errors.append(
                {
                    "code": "missing_combined_score",
                    "message": "evaluator.py 未体现 combined_score 指标",
                    "path": "evaluator.py",
                }
            )
    if config.strip():
        if "max_iterations:" not in config:
            errors.append({"code": "missing_max_iterations", "message": "config 缺少 max_iterations", "path": "config.yaml"})
        if "checkpoint_interval:" not in config:
            errors.append({"code": "missing_checkpoint_interval", "message": "config 缺少 checkpoint_interval", "path": "config.yaml"})
        if "llm:" not in config:
            errors.append({"code": "missing_llm_section", "message": "config 缺少 llm 配置段", "path": "config.yaml"})
        if "database:" not in config:
            errors.append({"code": "missing_database_section", "message": "config 缺少 database 配置段", "path": "config.yaml"})
        if "evaluator:" not in config:
            errors.append({"code": "missing_evaluator_section", "message": "config 缺少 evaluator 配置段", "path": "config.yaml"})
        if re.search(r"(?im)^\s*api_key\s*:\s*['\"]?\s*(?!\$\{)[A-Za-z0-9_\-]{16,}", config):
            warnings.append({"code": "plaintext_secret", "message": "检测到疑似明文 api_key，建议改用 ${DEEPSEEK_API_KEY}", "path": "config.yaml"})
            suggestions.append("请将 config 中的 api_key 替换为环境变量占位符 ${DEEPSEEK_API_KEY}。")

    if not errors:
        suggestions.append("结构校验通过，可进行人工 diff 审核后创建项目。")
    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "suggestions": suggestions,
    }


def _attempt_fix_scenario_files(
    files: dict[str, str], report: dict[str, Any]
) -> tuple[dict[str, str], str]:
    fixed = dict(files)
    changed = False
    error_codes = {str(e.get("code") or "") for e in (report.get("errors") or [])}
    if "missing_run_search" in error_codes:
        fixed["initialProgram"] = (
            (fixed.get("initialProgram") or "").rstrip()
            + "\n\n"
            + "def run_search(iterations: int = 100):\n"
            + "    return float(iterations)\n"
        )
        changed = True
    if "missing_evaluate" in error_codes:
        fixed["evaluator"] = (
            (fixed.get("evaluator") or "").rstrip()
            + "\n\n"
            + "from openevolve.evaluation_result import EvaluationResult\n"
            + "def evaluate(program_path):\n"
            + "    return EvaluationResult(metrics={\"combined_score\": 0.0})\n"
        )
        changed = True
    if "missing_max_iterations" in error_codes:
        fixed["configYaml"] = (
            (fixed.get("configYaml") or "").rstrip() + "\nmax_iterations: 20\n"
        )
        changed = True
    if "missing_checkpoint_interval" in error_codes:
        fixed["configYaml"] = (
            (fixed.get("configYaml") or "").rstrip() + "\ncheckpoint_interval: 2\n"
        )
        changed = True
    return fixed, ("improved" if changed else "no_change")


def _run_scenario_session_worker(session_id: str) -> None:
    with _SCENARIO_LOCK:
        session = _SCENARIO_SESSIONS.get(session_id)
    if session is None:
        return
    try:
        session["status"] = "running"
        session["result"]["usedSkill"] = session.get("skillName") or "opencode-scenario-builder"
        _scenario_publish(session, "session_started", {"status": "running"})
        _scenario_publish(session, "phase_changed", {"phase": "draft", "message": "OpenCode 正在根据描述生成三件套草案"})
        _scenario_publish(
            session,
            "log",
            {"level": "info", "source": "opencode-skill", "message": f"开始生成 initial/evaluator/config（skill={session.get('skillName') or 'opencode-scenario-builder'}）"},
        )
        files, summary_flag, generation_meta = _scenario_generate_with_opencode(
            intake=session.get("intake") or {},
            skill_name=str(session.get("skillName") or "opencode-scenario-builder"),
            seed_files=session.get("seedFiles") or {},
            validation_report=session["result"].get("validationReport") or {},
            user_feedback=str(session.get("userFeedback") or ""),
            session=session,
        )
        session["result"]["draftFiles"] = files
        draft_storage = _scenario_persist_draft_files(session, files)
        session["result"]["changeSummary"] = summary_flag
        session["result"]["generationSource"] = str(generation_meta.get("generationSource") or "")
        session["result"]["generationError"] = str(generation_meta.get("generationError") or "")
        session["result"]["rawPreview"] = str(generation_meta.get("rawPreview") or "")
        _scenario_publish(
            session,
            "draft_files",
            {
                "files": files,
                "summary": f"已生成三件套草案（{summary_flag}）",
                "generationSource": str(generation_meta.get("generationSource") or ""),
                "generationError": str(generation_meta.get("generationError") or ""),
                "draftStorage": draft_storage,
            },
        )
        _scenario_publish(
            session,
            "phase_changed",
            {"phase": "validate", "message": "正在执行结构校验"},
        )
        report = _validate_scenario_files(files)
        session["result"]["validationReport"] = report
        _scenario_publish(session, "validation_report", report)
        max_attempts = max(1, min(int(session.get("maxAttempts") or 2), 5))
        attempt = 0
        while (not report.get("ok")) and attempt < max_attempts:
            attempt += 1
            _scenario_publish(
                session,
                "phase_changed",
                {"phase": "fix", "message": f"OpenCode 修复中（第 {attempt} 轮）"},
            )
            _scenario_publish(
                session,
                "fix_attempt",
                {
                    "attempt": attempt,
                    "maxAttempts": max_attempts,
                    "status": "started",
                    "result": "no_change",
                },
            )
            files, gen_flag, gen_meta = _scenario_generate_with_opencode(
                intake=session.get("intake") or {},
                skill_name=str(session.get("skillName") or "opencode-scenario-builder"),
                seed_files=files,
                validation_report=report,
                user_feedback=str(session.get("userFeedback") or ""),
                session=session,
            )
            fallback_files, fallback_flag = _attempt_fix_scenario_files(files, report)
            if gen_flag.startswith("fallback_template"):
                files = fallback_files
                result_flag = fallback_flag
            else:
                result_flag = "improved"
            session["result"]["draftFiles"] = files
            draft_storage = _scenario_persist_draft_files(session, files)
            session["result"]["changeSummary"] = f"{gen_flag}; fix={result_flag}"
            session["result"]["generationSource"] = str(gen_meta.get("generationSource") or "")
            session["result"]["generationError"] = str(gen_meta.get("generationError") or "")
            session["result"]["rawPreview"] = str(gen_meta.get("rawPreview") or "")
            _scenario_publish(
                session,
                "draft_files",
                {
                    "files": files,
                    "summary": f"修复后草案（第 {attempt} 轮，{gen_flag}）",
                    "generationSource": str(gen_meta.get("generationSource") or ""),
                    "generationError": str(gen_meta.get("generationError") or ""),
                    "draftStorage": draft_storage,
                },
            )
            report = _validate_scenario_files(files)
            session["result"]["validationReport"] = report
            _scenario_publish(session, "validation_report", report)
            _scenario_publish(
                session,
                "fix_attempt",
                {
                    "attempt": attempt,
                    "maxAttempts": max_attempts,
                    "status": "finished",
                    "result": result_flag,
                },
            )
        if report.get("ok"):
            session["status"] = "await_user_confirm"
            _scenario_publish(
                session,
                "phase_changed",
                {"phase": "await_user_confirm", "message": "校验通过，等待用户确认创建"},
            )
            _scenario_publish(
                session,
                "session_completed",
                {
                    "resultRef": {"sessionId": session_id},
                    "requiresUserConfirm": True,
                    "changeSummary": session["result"].get("changeSummary") or "",
                    "usedSkill": session["result"].get("usedSkill") or session.get("skillName") or "opencode-scenario-builder",
                    "generationSource": session["result"].get("generationSource") or "",
                    "generationError": session["result"].get("generationError") or "",
                    "draftStorage": session["result"].get("draftStorage") or {},
                },
            )
        else:
            session["status"] = "failed"
            _scenario_publish(
                session,
                "session_failed",
                {
                    "errorCode": "validation_failed",
                    "errorMessage": "修复次数达到上限，仍未通过校验",
                    "retryable": True,
                },
            )
    except Exception as e:
        session["status"] = "failed"
        _scenario_publish(
            session,
            "session_failed",
            {
                "errorCode": "session_exception",
                "errorMessage": str(e),
                "retryable": True,
            },
        )


def _stop_visualizer_locked() -> None:
    proc = _VISUALIZER_STATE.get("proc")
    if proc is not None and proc.poll() is None:
        try:
            os.killpg(int(proc.pid), signal.SIGTERM)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        try:
            proc.wait(timeout=2.5)
        except Exception:
            pass
        if proc.poll() is None:
            try:
                os.killpg(int(proc.pid), signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
    _VISUALIZER_STATE["proc"] = None


def _visualizer_status_payload() -> dict[str, Any]:
    with _VISUALIZER_LOCK:
        proc = _VISUALIZER_STATE.get("proc")
        running = proc is not None and proc.poll() is None
        if not running:
            _VISUALIZER_STATE["proc"] = None
        host = str(_VISUALIZER_STATE.get("host") or "127.0.0.1")
        port = int(_VISUALIZER_STATE.get("port") or 8088)
        url = f"http://{host}:{port}" if running else ""
        return {
            "ok": True,
            "running": running,
            "mode": "single",
            "host": host,
            "port": port,
            "url": url,
            "projectName": str(_VISUALIZER_STATE.get("project_name") or ""),
            "runId": str(_VISUALIZER_STATE.get("run_id") or ""),
            "outputDir": str(_VISUALIZER_STATE.get("run_output_dir") or ""),
            "startedAt": float(_VISUALIZER_STATE.get("started_at") or 0.0),
        }


def _wait_visualizer_ready(
    host: str, port: int, proc: subprocess.Popen, timeout_sec: float
) -> bool:
    deadline = time.time() + max(1.0, timeout_sec)
    health_url = f"http://{host}:{port}/api/data"
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urlopen(health_url, timeout=1.0) as resp:
                if int(getattr(resp, "status", 0) or 0) == 200:
                    return True
        except URLError:
            pass
        except Exception:
            pass
        time.sleep(0.25)
    return False


def _start_visualizer_for_run(
    project_name: str, run_id: str, run_output_dir: Path
) -> dict[str, Any]:
    script_path = Path(
        os.environ.get("EVOLVE_VISUALIZER_SCRIPT", str(VISUALIZER_SCRIPT_DEFAULT))
    ).expanduser()
    if not script_path.exists() or not script_path.is_file():
        raise FileNotFoundError(f"visualizer script not found: {script_path}")

    host = os.environ.get("EVOLVE_VISUALIZER_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = _to_positive_int(os.environ.get("EVOLVE_VISUALIZER_PORT"), 8088)
    python_bin = os.environ.get("EVOLVE_VISUALIZER_PYTHON", "python3").strip() or "python3"
    startup_timeout = float(os.environ.get("EVOLVE_VISUALIZER_START_TIMEOUT", "8.0"))

    cmd = [
        python_bin,
        str(script_path),
        "--path",
        str(run_output_dir),
        "--host",
        host,
        "--port",
        str(port),
    ]

    with _VISUALIZER_LOCK:
        _VISUALIZER_STATE["host"] = host
        _VISUALIZER_STATE["port"] = port
        _stop_visualizer_locked()
        # Clear any externally-started visualizer still occupying the target port.
        _kill_processes_listening_on_port(port)
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            text=False,
        )
        _VISUALIZER_STATE.update(
            {
                "proc": proc,
                "project_name": project_name,
                "run_id": run_id,
                "run_output_dir": str(run_output_dir),
                "started_at": time.time(),
            }
        )

    if not _wait_visualizer_ready(host, port, proc, timeout_sec=startup_timeout):
        with _VISUALIZER_LOCK:
            _stop_visualizer_locked()
        raise RuntimeError("visualization service failed to start or become ready")
    return _visualizer_status_payload()


def _kill_run_processes_by_signature(run_id: str, output_dir: Path | str) -> None:
    """Best-effort cleanup for detached child processes."""
    sigs: list[str] = []
    if run_id:
        sigs.append(run_id)
    if output_dir:
        sigs.append(str(output_dir))
    for sig in sigs:
        # Use pkill as a fallback for detached process trees not in current pgid.
        subprocess.run(
            ["pkill", "-f", sig],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _collect_descendant_pids(root_pid: int) -> set[int]:
    """Collect all descendants for a process pid (best-effort)."""
    descendants: set[int] = set()
    frontier: list[int] = [root_pid]
    while frontier:
        parent = frontier.pop()
        try:
            out = subprocess.check_output(
                ["pgrep", "-P", str(parent)],
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            continue
        for raw in out.splitlines():
            s = raw.strip()
            if not s:
                continue
            try:
                child = int(s)
            except Exception:
                continue
            if child <= 0 or child in descendants:
                continue
            descendants.add(child)
            frontier.append(child)
    return descendants


def _terminate_run_processes(proc: subprocess.Popen, run_id: str, output_dir: Path | str) -> None:
    """Terminate run process tree with escalating signals."""
    pid = int(getattr(proc, "pid", 0) or 0)
    if pid <= 0:
        _kill_run_processes_by_signature(run_id, output_dir)
        return

    # Snapshot descendants early in case they detach quickly.
    descendants = _collect_descendant_pids(pid)
    targets = {pid, *descendants}
    my_pid = os.getpid()
    targets = {p for p in targets if p > 1 and p != my_pid}

    # 1) Graceful termination: process group first.
    try:
        os.killpg(pid, signal.SIGTERM)
    except Exception:
        pass
    for p in sorted(targets):
        try:
            os.kill(p, signal.SIGTERM)
        except Exception:
            pass

    # 2) Wait briefly for the leader to exit.
    try:
        proc.wait(timeout=2.5)
    except Exception:
        pass

    # 3) Force kill leftovers.
    for p in sorted(targets):
        try:
            os.kill(p, signal.SIGKILL)
        except Exception:
            pass
    try:
        os.killpg(pid, signal.SIGKILL)
    except Exception:
        pass

    # 4) Extra fallback for detached descendants.
    _kill_run_processes_by_signature(run_id, output_dir)


def _stop_run_if_orphaned(run_id: str, grace_seconds: float = 3.0) -> None:
    """Stop run when no SSE subscribers remain after a short grace period."""
    if grace_seconds > 0:
        time.sleep(grace_seconds)
    with _RUN_LOCK:
        runsrv = _RUNS.get(run_id)
    if not runsrv or runsrv.get("done"):
        return
    with runsrv["lock"]:
        has_subscribers = bool(runsrv.get("subs"))
    if has_subscribers:
        return
    proc = runsrv.get("proc")
    if proc is None or proc.poll() is not None:
        runsrv["done"] = True
        return
    output_dir = Path(str(runsrv.get("output_dir") or ""))
    _terminate_run_processes(proc, run_id, output_dir)
    runsrv["done"] = True
    _broadcast(
        runsrv,
        {
            "type": "done",
            "code": -15,
            "orphanStopped": True,
            "channel": "system_log",
            "origin": "backend",
            "confidence": "high",
        },
    )


def _find_active_run_locked() -> tuple[str, dict[str, Any]] | None:
    """Return the first active run under _RUN_LOCK."""
    # Prune finished processes opportunistically to avoid stale state.
    stale: list[str] = []
    for rid, rs in _RUNS.items():
        proc = rs.get("proc")
        if proc is None:
            continue
        if proc.poll() is None:
            return rid, rs
        stale.append(rid)
    for rid in stale:
        rs = _RUNS.get(rid)
        if rs is not None:
            rs["done"] = True
    return None


def _broadcast(runsrv: dict, ev: dict) -> None:
    log_path: Path | None = runsrv.get("monitor_log_path")
    log_lock: threading.Lock | None = runsrv.get("monitor_log_lock")
    if log_path is not None and log_lock is not None:
        try:
            rec = {
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "event": ev,
            }
            with log_lock:
                with open(log_path, "a", encoding="utf-8") as wf:
                    wf.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[DEBUG] failed to write monitor log: {e}", file=sys.stderr)

    dead = []
    with runsrv["lock"]:
        for q in runsrv["subs"]:
            try:
                q.put_nowait(ev)
            except Exception:
                dead.append(q)
        if dead:
            runsrv["subs"] = [q for q in runsrv["subs"] if q not in dead]


def _poll_loop(runsrv: dict) -> None:
    """Tail opencode stdout/stderr and OpenEvolve logs, then emit hybrid SSE events."""
    proc = runsrv["proc"]
    output_dir = Path(runsrv["output_dir"])
    run_id = str(runsrv.get("run_id") or "")
    log_dir = output_dir / "logs"
    last_log_check = 0.0
    file_offsets: dict[str, int] = {}
    current_iteration = 0
    emitted_keys: set[str] = set()
    last_raw_line = ""
    agent_md_buffer: list[str] = []
    agent_md_last_append = 0.0
    ansi_re = re.compile(r"\x1b\[[0-9;]*m")

    metric_kv_re = re.compile(
        r"([A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(?![A-Za-z0-9_])"
    )
    iteration_completed_re = re.compile(
        r"Iteration\s+(\d+):\s*Program\s+([0-9a-f-]+).*completed in\s+([0-9.]+)s",
        re.IGNORECASE,
    )
    metrics_re = re.compile(r"Metrics\s*:\s*(.+)$", re.IGNORECASE)
    new_best_re = re.compile(
        r"New best solution found at iteration\s+(\d+)\s*:\s*([0-9a-f-]+)",
        re.IGNORECASE,
    )
    checkpoint_re = re.compile(
        r"Saved checkpoint at iteration\s+(\d+)\s+to\s+(.+)$", re.IGNORECASE
    )
    run_summary_re = re.compile(
        r"(Evolution complete\. Best program has metrics:|Evolution completed - Maximum iterations reached)",
        re.IGNORECASE,
    )
    openevolve_log_line_re = re.compile(
        r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d+\s+-\s+openevolve\.",
        re.IGNORECASE,
    )
    stdout_noise_patterns = [
        re.compile(r"^<think>", re.IGNORECASE),
        re.compile(r"^</think>$", re.IGNORECASE),
        re.compile(r"^\$ ", re.IGNORECASE),
        re.compile(r"^>\s*openevolve-unified", re.IGNORECASE),
        re.compile(r"^→\s*Read\s+", re.IGNORECASE),
        re.compile(r"^\*\*OpenEvolve .*完成\*\*", re.IGNORECASE),
        re.compile(r"^\*\*关键日志摘要", re.IGNORECASE),
        re.compile(r"^\*\*最终最佳程序指标", re.IGNORECASE),
        re.compile(r"^\*\*输出文件", re.IGNORECASE),
        re.compile(r"^\|\s*指标\s*\|\s*值\s*\|$"),
        re.compile(r"^DONE$", re.IGNORECASE),
        re.compile(r"^total\s+\d+$", re.IGNORECASE),
        re.compile(r"^[d-]rw[-rwx]{7,}", re.IGNORECASE),
        re.compile(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d+\s+-\s+INFO\s+-", re.IGNORECASE),
    ]
    noise_prefixes = (
        "The user wants me",
        "Let me check",
        "Now I have all the information",
        "Now I'll execute",
    )

    def _now() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def _normalize_line(raw: str) -> str:
        return ansi_re.sub("", raw).strip()

    def _metrics_from_text(text: str) -> dict[str, float]:
        out: dict[str, float] = {}
        for mk, mv in metric_kv_re.findall(text):
            try:
                out[mk] = float(mv)
            except Exception:
                continue
        return out

    def _best_fitness_from_metrics(metrics: dict[str, float]) -> float | None:
        for k in ("combined_score", "bestFitness", "fitness", "score"):
            if k in metrics:
                return metrics[k]
        return None

    agent_stdout_patterns = (
        # English agent narration patterns
        re.compile(r"^let me\b", re.IGNORECASE),
        re.compile(r"^i need to\b", re.IGNORECASE),
        re.compile(r"^now i need to\b", re.IGNORECASE),
        re.compile(r"^now i(?:'| a)m\b", re.IGNORECASE),
        re.compile(r"^the user\b", re.IGNORECASE),
        re.compile(r"^according to\b", re.IGNORECASE),
        re.compile(r"^based on\b", re.IGNORECASE),
        re.compile(r"^i('ll| will)\b", re.IGNORECASE),
        re.compile(r"^first,?\s", re.IGNORECASE),
        re.compile(r"^next,?\s", re.IGNORECASE),
        re.compile(r"^finally,?\s", re.IGNORECASE),
        re.compile(r"^this (should|will|is)\b", re.IGNORECASE),
        re.compile(r"^here('s| is)\b", re.IGNORECASE),
        re.compile(r"^looking at\b", re.IGNORECASE),
        re.compile(r"^checking\b", re.IGNORECASE),
        re.compile(r"^running\b", re.IGNORECASE),
        # Chinese agent narration patterns - common openings
        re.compile(r"^openEvolve 任务"),
        re.compile(r"^执行摘要"),
        re.compile(r"^关键日志"),
        re.compile(r"^最佳程序指标"),
        re.compile(r"^输出位置"),
        re.compile(r"^根据规则"),
        re.compile(r"^根据要求"),
        re.compile(r"^命令启动后"),
        re.compile(r"^结束时"),
        re.compile(r"^让我"),
        re.compile(r"^我需要"),
        re.compile(r"^现在执行"),
        re.compile(r"^现在我需要"),
        re.compile(r"^现在"),
        re.compile(r"^这应该"),
        re.compile(r"^这是"),
        re.compile(r"^这表明"),
        re.compile(r"^这说明"),
        re.compile(r"^可以看到"),
        re.compile(r"^看起来"),
        re.compile(r"^接下来"),
        re.compile(r"^首先"),
        re.compile(r"^然后"),
        re.compile(r"^最后"),
        re.compile(r"^任务"),
        re.compile(r"^运行"),
        re.compile(r"^已经"),
        re.compile(r"^正在"),
        re.compile(r"^开始"),
        re.compile(r"^完成"),
        re.compile(r"^成功"),
        re.compile(r"^失败"),
        re.compile(r"^检查"),
        re.compile(r"^查看"),
        re.compile(r"^分析"),
        re.compile(r"^发现"),
        re.compile(r"^结果"),
        re.compile(r"^总结"),
        re.compile(r"^综上"),
        re.compile(r"^因此"),
        re.compile(r"^所以"),
        re.compile(r"^由于"),
        re.compile(r"^目前"),
        re.compile(r"^当前"),
        re.compile(r"^下面"),
        re.compile(r"^以下"),
        re.compile(r"^以上"),
        re.compile(r"^如[上下]"),
        re.compile(r"^请注意"),
        re.compile(r"^注意"),
        re.compile(r"^提示"),
        re.compile(r"^备注"),
        re.compile(r"^说明"),
        # Markdown formatting patterns
        re.compile(r"^\d+\.\s"),
        re.compile(r"^\|.*\|$"),
        re.compile(r"^\*\*.*\*\*$"),
        re.compile(r"^-\s"),
        re.compile(r"^✱\s"),
        re.compile(r"^#+\s"),
        re.compile(r"^>\s"),
        re.compile(r"^```"),
    )

    def _classify_raw_channel(text: str, source: str) -> tuple[str, str]:
        src = (source or "").strip().lower()
        if src == "openevolve_log":
            return ("system_log", "high")
        if src == "opencode_stdout":
            s = (text or "").strip()
            if s and any(p.search(s) for p in agent_stdout_patterns):
                return ("agent_response", "high")
            return ("system_log", "medium")
        return ("system_log", "low")

    def _emit_raw(text: str, source: str = "raw") -> None:
        nonlocal last_raw_line
        if not text:
            return
        if last_raw_line == text:
            return
        last_raw_line = text
        channel, confidence = _classify_raw_channel(text, source)
        _broadcast(
            runsrv,
            {
                "type": "raw",
                "timestamp": _now(),
                "runId": run_id,
                "text": text,
                "source": source,
                "channel": channel,
                "origin": source or "backend",
                "confidence": confidence,
            },
        )

    def _flush_agent_md_buffer(force: bool = False) -> None:
        nonlocal agent_md_buffer, agent_md_last_append
        if not agent_md_buffer:
            return
        now_mono = time.monotonic()
        # Keep collecting nearby lines into one markdown segment unless forced.
        if not force and (now_mono - agent_md_last_append) < 0.75:
            return
        merged = "\n".join(agent_md_buffer).strip()
        agent_md_buffer = []
        agent_md_last_append = 0.0
        if merged:
            # Agent text from --format json is directly classified as agent_response
            _broadcast(
                runsrv,
                {
                    "type": "raw",
                    "timestamp": _now(),
                    "runId": run_id,
                    "text": merged,
                    "source": "opencode_agent",
                    "channel": "agent_response",
                    "origin": "opencode_json",
                    "confidence": "high",
                },
            )

    def _emit_structured(
        *,
        event_type: str,
        source_line: str,
        generation: int | None = None,
        message: str = "",
        metrics: dict[str, float] | None = None,
        phase: str = "",
        extra: dict[str, Any] | None = None,
    ) -> None:
        effective_gen = generation if isinstance(generation, int) and generation > 0 else 0
        sig_src = f"{run_id}|{effective_gen}|{event_type}|{source_line}".encode("utf-8")
        dedupe_key = hashlib.sha1(sig_src).hexdigest()[:16]
        if dedupe_key in emitted_keys:
            return
        emitted_keys.add(dedupe_key)
        payload: dict[str, Any] = {
            "type": event_type,
            "timestamp": _now(),
            "runId": run_id,
            "generation": effective_gen,
            "phase": phase,
            "message": message or source_line,
            "metrics": metrics or {},
            "sourceLine": source_line,
            "dedupeKey": dedupe_key,
            "outputFile": str(runsrv["output_dir"]),
            "channel": "system_log",
            "origin": "openevolve_log",
            "confidence": "high",
        }
        best_fit = _best_fitness_from_metrics(payload["metrics"])
        if best_fit is not None:
            payload["bestFitness"] = float(best_fit)
        if extra:
            payload.update(extra)
        _broadcast(runsrv, payload)

    def _handle_log_line(txt: str) -> None:
        nonlocal current_iteration
        _emit_raw(txt, source="openevolve_log")

        m_iter = iteration_completed_re.search(txt)
        if m_iter:
            gen = int(m_iter.group(1))
            current_iteration = gen
            _emit_structured(
                event_type="iteration_completed",
                generation=gen,
                phase="evolution",
                source_line=txt,
                message=f"Iteration {gen} completed",
                extra={
                    "programId": m_iter.group(2),
                    "durationSec": float(m_iter.group(3)),
                },
            )
            return

        m_new_best = new_best_re.search(txt)
        if m_new_best:
            gen = int(m_new_best.group(1))
            current_iteration = gen
            _emit_structured(
                event_type="new_best",
                generation=gen,
                phase="selection",
                source_line=txt,
                message=f"New best at iteration {gen}",
                extra={"programId": m_new_best.group(2)},
            )
            return

        m_checkpoint = checkpoint_re.search(txt)
        if m_checkpoint:
            gen = int(m_checkpoint.group(1))
            current_iteration = gen
            _emit_structured(
                event_type="checkpoint_saved",
                generation=gen,
                phase="checkpoint",
                source_line=txt,
                message=f"Checkpoint saved at iteration {gen}",
                extra={"checkpointPath": m_checkpoint.group(2).strip()},
            )
            return

        if "Checkpoint interval reached at iteration" in txt:
            m_gen = re.search(r"iteration\s+(\d+)", txt, re.IGNORECASE)
            gen = int(m_gen.group(1)) if m_gen else current_iteration
            current_iteration = gen
            _emit_structured(
                event_type="checkpoint_saved",
                generation=gen,
                phase="checkpoint",
                source_line=txt,
                message=txt,
            )
            return

        m_metrics = metrics_re.search(txt)
        if m_metrics:
            metrics = _metrics_from_text(m_metrics.group(1))
            if metrics:
                _emit_structured(
                    event_type="metrics",
                    generation=current_iteration,
                    phase="evaluation",
                    source_line=txt,
                    metrics=metrics,
                    message=f"Metrics updated at iteration {current_iteration or 0}",
                )
            return

        if run_summary_re.search(txt):
            _emit_structured(
                event_type="run_summary",
                generation=current_iteration,
                phase="summary",
                source_line=txt,
                message=txt,
            )

    def _should_drop_stdout_line(txt: str) -> bool:
        if not txt:
            return True
        if openevolve_log_line_re.search(txt):
            # Authoritative lines are tailed from openevolve_*.log to avoid duplication.
            return True
        if txt.startswith(noise_prefixes):
            return True
        for p in stdout_noise_patterns:
            if p.search(txt):
                return True
        return False

    def check_log_files():
        nonlocal last_log_check, file_offsets
        now = time.time()
        if now - last_log_check < 2.0:  # 每2秒检查一次
            return
        last_log_check = now

        if not log_dir.exists():
            return

        for log_file in log_dir.glob("openevolve_*.log"):
            key = str(log_file)
            offset = file_offsets.get(key, 0)
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    f.seek(offset)
                    lines = f.readlines()
                    file_offsets[key] = f.tell()
                    for line in lines:
                        txt = _normalize_line(line)
                        if not txt:
                            continue
                        _handle_log_line(txt)
            except Exception as e:
                print(
                    f"[DEBUG] Error reading log file {log_file}: {e}", file=sys.stderr
                )

    stdout = proc.stdout
    line_buffer = ""
    fd = None
    if stdout is not None:
        try:
            fd = stdout.fileno()
            os.set_blocking(fd, False)
        except Exception:
            fd = None

    def _process_opencode_json_line(line: str) -> None:
        """Process a single JSON line from opencode --format json output."""
        nonlocal agent_md_buffer, agent_md_last_append
        if not line.strip():
            return
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            # Fallback: treat as plain text (legacy mode)
            txt = _normalize_line(line)
            if txt and not _should_drop_stdout_line(txt):
                channel, _confidence = _classify_raw_channel(txt, "opencode_stdout")
                if channel == "agent_response":
                    agent_md_buffer.append(txt)
                    agent_md_last_append = time.monotonic()
                    if len(agent_md_buffer) >= 12:
                        _flush_agent_md_buffer(force=True)
                else:
                    _flush_agent_md_buffer(force=True)
                    _emit_raw(txt, source="opencode_stdout")
            return

        event_type = event.get("type", "")

        # Event type "text" = agent's text response (high confidence)
        if event_type == "text":
            part = event.get("part", {})
            text_content = part.get("text", "")
            if text_content:
                for txt_line in text_content.split("\n"):
                    txt_line = txt_line.strip()
                    if txt_line and not _should_drop_stdout_line(txt_line):
                        agent_md_buffer.append(txt_line)
                        agent_md_last_append = time.monotonic()
                if len(agent_md_buffer) >= 12:
                    _flush_agent_md_buffer(force=True)
            return

        # Event type "tool_use" = tool execution output (system_log)
        if event_type == "tool_use":
            _flush_agent_md_buffer(force=True)
            tool_name = event.get("name", event.get("tool", ""))
            tool_title = event.get("title", "")
            tool_output = event.get("output", "")
            # Format tool output for display
            if tool_title:
                display_text = f"✱ {tool_title}"
            elif tool_name:
                display_text = f"✱ {tool_name}"
            else:
                display_text = str(tool_output)[:200] if tool_output else ""
            if display_text:
                _broadcast(
                    runsrv,
                    {
                        "type": "raw",
                        "timestamp": _now(),
                        "runId": run_id,
                        "text": display_text,
                        "source": "opencode_tool",
                        "channel": "system_log",
                        "origin": "opencode_json",
                        "confidence": "high",
                    },
                )
            return

        # Event type "step_start" / "step_finish" - can be logged as system events
        if event_type in ("step_start", "step_finish"):
            _flush_agent_md_buffer(force=True)
            reason = event.get("reason", "")
            if event_type == "step_finish" and reason:
                _broadcast(
                    runsrv,
                    {
                        "type": "raw",
                        "timestamp": _now(),
                        "runId": run_id,
                        "text": f"[step_finish: {reason}]",
                        "source": "opencode_step",
                        "channel": "system_log",
                        "origin": "opencode_json",
                        "confidence": "high",
                    },
                )
            return

        # Other event types - emit as system log
        _flush_agent_md_buffer(force=True)
        raw_text = json.dumps(event, ensure_ascii=False)[:300]
        _emit_raw(raw_text, source="opencode_stdout")

    def flush_stdout_lines(force: bool = False) -> None:
        nonlocal line_buffer
        if fd is None:
            return
        while True:
            has_data = False
            try:
                ready, _, _ = select.select([fd], [], [], 0)
                has_data = bool(ready)
            except Exception:
                has_data = False
            if not has_data:
                break
            try:
                chunk = os.read(fd, 8192)
            except BlockingIOError:
                break
            except Exception:
                break
            if not chunk:
                break
            line_buffer += chunk.decode("utf-8", errors="replace")
            while "\n" in line_buffer:
                line, line_buffer = line_buffer.split("\n", 1)
                _process_opencode_json_line(line)
        _flush_agent_md_buffer(force=False)
        if force:
            if line_buffer.strip():
                _process_opencode_json_line(line_buffer)
            _flush_agent_md_buffer(force=True)
            line_buffer = ""

    try:
        while proc.poll() is None:
            flush_stdout_lines(force=False)
            check_log_files()
            time.sleep(0.2)
        flush_stdout_lines(force=True)
        check_log_files()

    finally:
        runsrv["done"] = True
        _broadcast(
            runsrv,
            {
                "type": "done",
                "timestamp": _now(),
                "runId": run_id,
                "outputDir": str(runsrv["output_dir"]),
                "channel": "system_log",
                "origin": "backend",
                "confidence": "high",
            },
        )


# ── HTTP Handler ──────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return

    def _maybe_send_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,X-API-Token")

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self._maybe_send_cors()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path.startswith("/api/scenarios/opencode/session/"):
            parts = path.split("/")
            if len(parts) >= 7 and parts[6] == "events":
                return self._handle_scenario_session_events(parts[5])
            if len(parts) >= 7 and parts[6] == "result":
                return self._handle_scenario_session_result(parts[5])

        if path == "/api/projects":
            return self._handle_get_projects()
        if path == "/api/outputs":
            return self._handle_get_outputs()
        if path == "/api/outputs/visualization/status":
            return self._handle_visualization_status()
        if path.startswith("/api/projects/"):
            parts = path.split("/")
            if len(parts) >= 5 and parts[4] in {"tree", "file", "download", "metrics-schema"}:
                project_name = parts[3]
                if parts[4] == "tree":
                    return self._handle_project_tree(project_name, query)
                if parts[4] == "file":
                    return self._handle_project_file(project_name, query)
                if parts[4] == "metrics-schema":
                    return self._handle_project_metrics_schema(project_name)
                return self._handle_project_download(project_name, query)
        if path.startswith("/api/outputs/"):
            parts = path.split("/")
            if len(parts) == 7 and parts[5] == "analyses" and parts[6]:
                project_name, run_id, analysis_id = parts[3], parts[4], parts[6]
                raw_flag = query.get("raw", ["0"])[0] in {"1", "true", "yes"}
                if raw_flag:
                    return self._handle_output_analysis_get(
                        project_name, run_id, analysis_id
                    )
                return self._handle_output_analysis_download(
                    project_name, run_id, analysis_id
                )
            if len(parts) == 6 and parts[5] == "analyses":
                return self._handle_output_analyses_list(parts[3], parts[4])
            if len(parts) >= 6 and parts[5] in {"tree", "file", "download", "archive", "trend", "artifacts"}:
                project_name, run_id = parts[3], parts[4]
                if parts[5] == "tree":
                    return self._handle_output_tree(project_name, run_id, query)
                if parts[5] == "file":
                    return self._handle_output_file(project_name, run_id, query)
                if parts[5] == "archive":
                    return self._handle_output_archive(project_name, run_id)
                if parts[5] == "trend":
                    return self._handle_output_trend(project_name, run_id)
                if parts[5] == "artifacts":
                    return self._handle_output_artifacts(project_name, run_id)
                return self._handle_output_download(project_name, run_id, query)
        if path.startswith("/api/runs/") and path.endswith("/events"):
            parts = path.split("/")
            run_id = parts[3] if len(parts) >= 5 else ""
            return self._handle_sse_events(run_id)

        return _json_response(self, HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path not in {"/api/scenarios/gate", "/api/scenarios/opencode/session"}:
            ok, err = require_write_auth(self.headers)
            if not ok:
                return _json_response(self, HTTPStatus.UNAUTHORIZED, {"error": err})

        if path == "/api/scenarios/gate":
            return self._handle_scenario_gate()
        if path == "/api/scenarios/opencode/session":
            return self._handle_scenario_session_start()
        if path == "/api/scenarios/create":
            return self._handle_scenario_create()

        if path.startswith("/api/outputs/") and path.endswith("/analyze"):
            parts = path.split("/")
            return self._handle_output_analyze(parts[3], parts[4])
        if path.startswith("/api/outputs/") and path.endswith("/visualization/start"):
            parts = path.split("/")
            if len(parts) >= 7:
                return self._handle_output_visualization_start(parts[3], parts[4])
        if path.startswith("/api/projects/") and path.endswith("/file"):
            return self._handle_project_file_save(path.split("/")[3])
        if path.startswith("/api/outputs/") and path.endswith("/file"):
            parts = path.split("/")
            return self._handle_output_file_save(parts[3], parts[4])
        if path == "/api/projects/upload":
            return self._handle_upload(query)
        if path == "/api/runs/start":
            return self._handle_start()
        if path.startswith("/api/runs/") and path.endswith("/stop"):
            parts = path.split("/")
            return self._handle_stop(parts[3] if len(parts) >= 5 else "")

        return _json_response(self, HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        ok, err = require_write_auth(self.headers)
        if not ok:
            return _json_response(self, HTTPStatus.UNAUTHORIZED, {"error": err})
        parts = path.split("/")
        if len(parts) == 4 and parts[3]:
            return self._handle_delete_project(parts[3])
        if len(parts) == 7 and parts[5] == "analyses" and parts[6]:
            return self._handle_delete_analysis(parts[3], parts[4], parts[6])
        if len(parts) == 5 and parts[3] and parts[4]:
            return self._handle_delete_output(parts[3], parts[4])
        return _json_response(self, HTTPStatus.NOT_FOUND, {"error": "not found"})

    # ── 文件管理 handler ────────────────────────────────────────────────────

    def _handle_get_projects(self) -> None:
        projects: list[dict[str, Any]] = []
        for d in sorted(SERVER_DATA_DIR.iterdir(), key=lambda x: x.name):
            if not d.is_dir():
                continue
            try:
                _ensure_required_files_at_root(d)
            except Exception:
                continue
            files = _list_project_files(d)
            projects.append({"name": d.name, "files": files})
        _json_response(self, 200, {"projects": projects})

    def _handle_get_outputs(self) -> None:
        try:
            runs = _collect_output_runs()
            _json_response(self, 200, {"runs": runs})
        except PayloadTooLargeError as e:
            _json_response(self, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _iter_project_runs(self, project_root: Path) -> list[Path]:
        out_root = project_root / "openevolve_output"
        if not out_root.exists() or not out_root.is_dir():
            return []
        runs: list[Path] = []
        for p in out_root.iterdir():
            if p.is_dir():
                runs.append(p)
        runs.sort(
            key=lambda x: x.stat().st_mtime if x.exists() else 0.0,
            reverse=True,
        )
        return runs

    def _find_artifacts_in_program_json(
        self, program_json_path: Path, max_items: int = 24
    ) -> dict[str, Any]:
        raw = json.loads(program_json_path.read_text(encoding="utf-8"))
        artifacts: dict[str, Any] = {}
        artifacts_json = raw.get("artifacts_json")
        if isinstance(artifacts_json, str) and artifacts_json.strip():
            try:
                parsed = json.loads(artifacts_json)
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        artifacts[str(k)] = v
            except Exception:
                pass
        artifact_dir = raw.get("artifact_dir")
        files: list[dict[str, Any]] = []
        if isinstance(artifact_dir, str) and artifact_dir.strip():
            ad = Path(artifact_dir)
            if ad.exists() and ad.is_dir():
                for f in sorted(ad.rglob("*")):
                    if not f.is_file():
                        continue
                    rel = f.relative_to(ad).as_posix()
                    size = f.stat().st_size
                    item: dict[str, Any] = {
                        "name": rel,
                        "size": size,
                        "isText": False,
                    }
                    try:
                        text = f.read_bytes()[:65536].decode("utf-8")
                        item["isText"] = True
                        item["truncated"] = size > 65536
                        item["content"] = text
                    except Exception:
                        pass
                    files.append(item)
                    if len(files) >= max_items:
                        break
        return {
            "programId": str(raw.get("id") or program_json_path.stem),
            "artifacts": artifacts,
            "artifactFiles": files,
        }

    def _handle_project_metrics_schema(self, project_name: str) -> None:
        try:
            root = self._get_project_root(project_name)
            runs = self._iter_project_runs(root)
            if not runs:
                return _json_response(
                    self,
                    200,
                    {
                        "projectName": project_name,
                        "sourceRunId": None,
                        "fitnessKey": None,
                        "metrics": [],
                        "hasArtifacts": False,
                    },
                )
            for run in runs:
                best_info = run / "best" / "best_program_info.json"
                if not best_info.exists():
                    continue
                try:
                    raw = json.loads(best_info.read_text(encoding="utf-8"))
                except Exception:
                    continue
                metrics = _extract_numeric_metrics(raw.get("metrics") or {})
                fitness_key, _ = _pick_fitness_metric(metrics)
                has_artifacts = False
                ckpt_dir = run / "checkpoints"
                if ckpt_dir.exists() and ckpt_dir.is_dir():
                    for program_json in ckpt_dir.glob("checkpoint_*/programs/*.json"):
                        try:
                            p_raw = json.loads(program_json.read_text(encoding="utf-8"))
                            if p_raw.get("artifacts_json") or p_raw.get("artifact_dir"):
                                has_artifacts = True
                                break
                        except Exception:
                            continue
                return _json_response(
                    self,
                    200,
                    {
                        "projectName": project_name,
                        "sourceRunId": run.name,
                        "fitnessKey": fitness_key,
                        "metrics": list(metrics.keys()),
                        "hasArtifacts": has_artifacts,
                    },
                )
            _json_response(
                self,
                200,
                {
                    "projectName": project_name,
                    "sourceRunId": runs[0].name if runs else None,
                    "fitnessKey": None,
                    "metrics": [],
                    "hasArtifacts": False,
                },
            )
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_output_trend(self, project_name: str, run_id: str) -> None:
        try:
            run_root = self._get_output_root(project_name, run_id)
            points_by_iter: dict[int, dict[str, Any]] = {}
            ckpt_root = run_root / "checkpoints"
            if ckpt_root.exists() and ckpt_root.is_dir():
                for ckpt in ckpt_root.iterdir():
                    if not ckpt.is_dir():
                        continue
                    m = re.match(r"checkpoint_(\d+)", ckpt.name)
                    if not m:
                        continue
                    info = ckpt / "best_program_info.json"
                    if not info.exists():
                        continue
                    try:
                        raw = json.loads(info.read_text(encoding="utf-8"))
                        metrics = _extract_numeric_metrics(raw.get("metrics") or {})
                        if not metrics:
                            continue
                        fitness_key, fitness_value = _pick_fitness_metric(metrics)
                        iteration = int(m.group(1))
                        points_by_iter[iteration] = {
                            "iteration": iteration,
                            "metrics": metrics,
                            "fitnessKey": fitness_key,
                            "fitnessValue": fitness_value,
                        }
                    except Exception:
                        continue

            # Supplement checkpoint points with per-iteration metrics from monitor logs.
            # This avoids sparse trends when checkpoint_interval > 1.
            monitor_path = run_root / "logs" / "monitor_realtime.jsonl"
            if monitor_path.exists() and monitor_path.is_file():
                try:
                    for line in monitor_path.read_text(
                        encoding="utf-8", errors="replace"
                    ).splitlines():
                        if not line.strip():
                            continue
                        row = json.loads(line)
                        event = row.get("event") or {}
                        if str(event.get("type") or "") != "metrics":
                            continue
                        iteration = int(event.get("generation") or 0)
                        if iteration <= 0:
                            continue
                        metrics = _extract_numeric_metrics(event.get("metrics") or {})
                        if not metrics:
                            continue
                        # Keep checkpoint-derived point if present; otherwise fill from monitor.
                        if iteration in points_by_iter:
                            continue
                        fitness_key, fitness_value = _pick_fitness_metric(metrics)
                        points_by_iter[iteration] = {
                            "iteration": iteration,
                            "metrics": metrics,
                            "fitnessKey": fitness_key,
                            "fitnessValue": fitness_value,
                        }
                except Exception:
                    pass

            points = sorted(
                points_by_iter.values(), key=lambda x: int(x.get("iteration") or 0)
            )
            _json_response(
                self,
                200,
                {
                    "projectName": project_name,
                    "runId": run_id,
                    "points": points,
                },
            )
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_output_artifacts(self, project_name: str, run_id: str) -> None:
        try:
            run_root = self._get_output_root(project_name, run_id)
            best_program = run_root / "best" / "best_program.py"
            project_root = self._get_project_root(project_name)
            initial_program = project_root / "initial_program.py"
            initial_content = (
                initial_program.read_text(encoding="utf-8", errors="replace")
                if initial_program.exists()
                else ""
            )
            best_content = (
                best_program.read_text(encoding="utf-8", errors="replace")
                if best_program.exists()
                else ""
            )
            selected_program: dict[str, Any] | None = None
            ckpt_root = run_root / "checkpoints"
            latest_checkpoint_num = -1
            if ckpt_root.exists() and ckpt_root.is_dir():
                for ckpt in ckpt_root.iterdir():
                    if not ckpt.is_dir():
                        continue
                    m = re.match(r"checkpoint_(\d+)", ckpt.name)
                    if not m:
                        continue
                    n = int(m.group(1))
                    if n <= latest_checkpoint_num:
                        continue
                    programs_dir = ckpt / "programs"
                    if not programs_dir.exists() or not programs_dir.is_dir():
                        continue
                    candidate: dict[str, Any] | None = None
                    for p in programs_dir.glob("*.json"):
                        try:
                            found = self._find_artifacts_in_program_json(p)
                            if found["artifacts"] or found["artifactFiles"]:
                                candidate = found
                                break
                        except Exception:
                            continue
                    if candidate is not None:
                        selected_program = candidate
                        latest_checkpoint_num = n
            _json_response(
                self,
                200,
                {
                    "projectName": project_name,
                    "runId": run_id,
                    "checkpoint": latest_checkpoint_num if latest_checkpoint_num >= 0 else None,
                    "programId": (selected_program or {}).get("programId"),
                    "artifacts": (selected_program or {}).get("artifacts", {}),
                    "artifactFiles": (selected_program or {}).get("artifactFiles", []),
                    "initialProgram": initial_content,
                    "bestProgram": best_content,
                },
            )
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_visualization_status(self) -> None:
        try:
            _json_response(self, 200, _visualizer_status_payload())
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_output_visualization_start(self, project_name: str, run_id: str) -> None:
        try:
            run_root = self._get_output_root(project_name, run_id)
            payload = _start_visualizer_for_run(project_name, run_id, run_root)
            append_audit_log(
                AUDIT_LOG_FILE,
                "visualization_start",
                {
                    "project": project_name,
                    "runId": run_id,
                    "port": payload.get("port"),
                    "url": payload.get("url"),
                    "mode": payload.get("mode"),
                },
            )
            _json_response(self, 200, payload)
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _get_project_root(self, project_name: str) -> Path:
        root = (SERVER_DATA_DIR / project_name).resolve()
        if not root.exists() or not root.is_dir():
            raise FileNotFoundError("project not found")
        return root

    def _get_output_root(self, project_name: str, run_id: str) -> Path:
        root = (SERVER_DATA_DIR / project_name / "openevolve_output" / run_id).resolve()
        if not root.exists() or not root.is_dir():
            raise FileNotFoundError("output run not found")
        return root

    def _pick_query_param(
        self, query: dict[str, list[str]], key: str, default: str = ""
    ) -> str:
        val = query.get(key, [])
        return str(val[0] or default) if val else default

    def _handle_project_tree(
        self, project_name: str, query: dict[str, list[str]]
    ) -> None:
        try:
            root = self._get_project_root(project_name)
            max_depth = int(self._pick_query_param(query, "maxDepth", "5"))
            include_outputs = self._pick_query_param(query, "includeOutputs", "0") in {
                "1",
                "true",
                "yes",
            }
            excluded = set() if include_outputs else {"openevolve_output"}
            files = _list_tree(root, max_depth=max_depth, exclude_top_dirs=excluded)
            _json_response(self, 200, {"projectName": project_name, "files": files})
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_output_tree(
        self, project_name: str, run_id: str, query: dict[str, list[str]]
    ) -> None:
        try:
            root = self._get_output_root(project_name, run_id)
            max_depth = int(self._pick_query_param(query, "maxDepth", "6"))
            files = _list_tree(root, max_depth=max_depth)
            _json_response(
                self,
                200,
                {"projectName": project_name, "runId": run_id, "files": files},
            )
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_project_file(
        self, project_name: str, query: dict[str, list[str]]
    ) -> None:
        try:
            root = self._get_project_root(project_name)
            rel_path = self._pick_query_param(query, "path")
            max_bytes = int(self._pick_query_param(query, "maxBytes", "65536"))
            target = _safe_rooted_path(root, rel_path)
            if not target.exists() or not target.is_file():
                raise FileNotFoundError("file not found")
            raw = target.read_bytes()
            truncated = len(raw) > max_bytes
            payload = raw[:max_bytes].decode("utf-8", errors="replace")
            _json_response(
                self,
                200,
                {
                    "path": rel_path,
                    "size": len(raw),
                    "truncated": truncated,
                    "content": payload,
                },
            )
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_output_file(
        self, project_name: str, run_id: str, query: dict[str, list[str]]
    ) -> None:
        try:
            root = self._get_output_root(project_name, run_id)
            rel_path = self._pick_query_param(query, "path")
            max_bytes = int(self._pick_query_param(query, "maxBytes", "65536"))
            target = _safe_rooted_path(root, rel_path)
            if not target.exists() or not target.is_file():
                raise FileNotFoundError("file not found")
            raw = target.read_bytes()
            truncated = len(raw) > max_bytes
            payload = raw[:max_bytes].decode("utf-8", errors="replace")
            _json_response(
                self,
                200,
                {
                    "path": rel_path,
                    "size": len(raw),
                    "truncated": truncated,
                    "content": payload,
                },
            )
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_project_download(
        self, project_name: str, query: dict[str, list[str]]
    ) -> None:
        try:
            root = self._get_project_root(project_name)
            rel_path = self._pick_query_param(query, "path")
            target = _safe_rooted_path(root, rel_path)
            if not target.exists() or not target.is_file():
                raise FileNotFoundError("file not found")
            _send_file_download(self, target)
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_output_download(
        self, project_name: str, run_id: str, query: dict[str, list[str]]
    ) -> None:
        try:
            root = self._get_output_root(project_name, run_id)
            rel_path = self._pick_query_param(query, "path")
            target = _safe_rooted_path(root, rel_path)
            if not target.exists() or not target.is_file():
                raise FileNotFoundError("file not found")
            _send_file_download(self, target)
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_output_archive(self, project_name: str, run_id: str) -> None:
        try:
            root = self._get_output_root(project_name, run_id)
            _send_directory_zip_download(
                self, root, f"{project_name}_{run_id}_output.zip"
            )
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_project_file_save(self, project_name: str) -> None:
        try:
            root = self._get_project_root(project_name)
            data = _read_json_body(self)
            rel_path = str(data.get("path") or "")
            content = data.get("content")
            if not isinstance(content, str):
                raise ValueError("content must be string")
            target = _safe_rooted_path(root, rel_path)
            if not target.exists() or not target.is_file():
                raise FileNotFoundError("file not found")
            target.write_text(content, encoding="utf-8")
            append_audit_log(
                AUDIT_LOG_FILE,
                "project_file_save",
                {"project": project_name, "path": rel_path},
            )
            _json_response(self, 200, {"ok": True, "path": rel_path})
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_output_file_save(self, project_name: str, run_id: str) -> None:
        try:
            root = self._get_output_root(project_name, run_id)
            data = _read_json_body(self)
            rel_path = str(data.get("path") or "")
            content = data.get("content")
            if not isinstance(content, str):
                raise ValueError("content must be string")
            target = _safe_rooted_path(root, rel_path)
            if not target.exists() or not target.is_file():
                raise FileNotFoundError("file not found")
            target.write_text(content, encoding="utf-8")
            append_audit_log(
                AUDIT_LOG_FILE,
                "output_file_save",
                {"project": project_name, "runId": run_id, "path": rel_path},
            )
            _json_response(self, 200, {"ok": True, "path": rel_path, "runId": run_id})
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_upload(self, query: dict[str, list[str]] | None = None) -> None:
        try:
            ctype = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in ctype:
                return _json_response(
                    self,
                    HTTPStatus.BAD_REQUEST,
                    {"error": "expected multipart/form-data"},
                )
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_UPLOAD_BODY_BYTES:
                return _json_response(
                    self,
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    {"error": "upload too large"},
                )
            raw_body = self.rfile.read(length) if length > 0 else b""
            if not raw_body:
                return _json_response(
                    self, HTTPStatus.BAD_REQUEST, {"error": "empty upload body"}
                )
            pseudo_headers = (
                f"Content-Type: {ctype}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
            )
            msg = BytesParser(policy=email_default_policy).parsebytes(
                pseudo_headers + raw_body
            )
            zip_bytes: bytes | None = None
            zip_filename: str | None = None
            project_name: str | None = None
            for part in msg.iter_parts():
                cd = part.get("Content-Disposition", "")
                name = part.get_param("name", header="Content-Disposition")
                filename = part.get_param("filename", header="Content-Disposition")
                if name == "projectName":
                    payload = part.get_payload(decode=True) or b""
                    project_name = payload.decode("utf-8", errors="ignore").strip()
                elif name == "zip":
                    zip_bytes = part.get_payload(decode=True)
                    zip_filename = filename
            if not zip_bytes or not zip_filename:
                return _json_response(
                    self,
                    HTTPStatus.BAD_REQUEST,
                    {"error": "missing zip file field `zip`"},
                )
            if not project_name:
                project_name = Path(zip_filename).stem
            project_dir = SERVER_DATA_DIR / project_name
            q = query or {}
            allow_overwrite = str(
                (q.get("allowOverwrite", ["0"])[0] or "0")
            ).lower() in {"1", "true", "yes"}
            if project_dir.exists():
                if not allow_overwrite:
                    return _json_response(
                        self,
                        HTTPStatus.CONFLICT,
                        {
                            "error": f"project already exists: {project_name}. pass allowOverwrite=1 to replace"
                        },
                    )
                shutil.rmtree(project_dir)
                append_audit_log(
                    AUDIT_LOG_FILE, "project_overwrite", {"project": project_name}
                )
            project_dir.mkdir(parents=True, exist_ok=True)
            tmp_zip_dir = Path(tempfile.mkdtemp(prefix="openevolve_upload_"))
            tmp_zip = tmp_zip_dir / "upload.zip"
            tmp_zip.write_bytes(zip_bytes)
            try:
                _safe_extract_zip(tmp_zip, project_dir)
                _ensure_required_files_at_root(project_dir)
            except Exception:
                shutil.rmtree(project_dir, ignore_errors=True)
                raise
            finally:
                try:
                    tmp_zip.unlink(missing_ok=True)
                except Exception:
                    pass
            append_audit_log(
                AUDIT_LOG_FILE,
                "project_upload",
                {"project": project_name, "overwrite": allow_overwrite},
            )
            _json_response(self, 200, {"ok": True, "projectName": project_name})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_delete_project(self, project_name: str) -> None:
        try:
            target = (SERVER_DATA_DIR / project_name).resolve()
            if not target.exists() or not target.is_dir():
                return _json_response(
                    self, HTTPStatus.NOT_FOUND, {"error": "project not found"}
                )
            target.relative_to(SERVER_DATA_DIR.resolve())
            shutil.rmtree(target)
            append_audit_log(
                AUDIT_LOG_FILE, "project_delete", {"project": project_name}
            )
            _json_response(self, 200, {"ok": True, "projectName": project_name})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_delete_output(self, project_name: str, run_id: str) -> None:
        try:
            target = (
                SERVER_DATA_DIR / project_name / "openevolve_output" / run_id
            ).resolve()
            if not target.exists() or not target.is_dir():
                return _json_response(
                    self, HTTPStatus.NOT_FOUND, {"error": "output run not found"}
                )
            target.relative_to(SERVER_DATA_DIR.resolve())
            shutil.rmtree(target)
            append_audit_log(
                AUDIT_LOG_FILE,
                "output_delete",
                {"project": project_name, "runId": run_id},
            )
            _json_response(
                self, 200, {"ok": True, "projectName": project_name, "runId": run_id}
            )
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    # ── 分析 handler ─────────────────────────────────────────────────────────

    def _build_analysis_payload(self, run_root: Path, max_bytes: int) -> dict[str, Any]:
        samples: list[dict[str, Any]] = []

        def add_sample(label: str, rel: str) -> None:
            p = _safe_rooted_path(run_root, rel)
            if not p.exists() or not p.is_file():
                return
            raw = p.read_bytes()
            truncated = len(raw) > max_bytes
            text = raw[:max_bytes].decode("utf-8", errors="replace")
            samples.append(
                {"label": label, "path": rel, "truncated": truncated, "content": text}
            )

        add_sample("best_program_info", "best/best_program_info.json")
        add_sample("best_program", "best/best_program.py")
        checkpoints_dir = run_root / "checkpoints"
        latest_info: Path | None = None
        latest_num = -1
        if checkpoints_dir.exists() and checkpoints_dir.is_dir():
            for p in checkpoints_dir.iterdir():
                if not p.is_dir():
                    continue
                m = re.match(r"checkpoint_(\d+)", p.name)
                if not m:
                    continue
                n = int(m.group(1))
                cand = p / "best_program_info.json"
                if n > latest_num and cand.exists():
                    latest_num = n
                    latest_info = cand
        if latest_info:
            add_sample(
                "latest_checkpoint_info", latest_info.relative_to(run_root).as_posix()
            )
        if not samples:
            raise FileNotFoundError("no analyzable files found under this run")
        return {"runRoot": str(run_root), "fileCount": len(samples), "samples": samples}

    def _build_analysis_prompt(
        self, project_name: str, run_id: str, focus: str, payload: dict[str, Any]
    ) -> str:
        files_desc = [
            f"- {s['label']}: {s['path']}"
            + (" (truncated)" if s.get("truncated") else "")
            for s in payload.get("samples", [])
        ]
        sections = [
            f"### {s['label']} [{s['path']}]\n{s['content']}"
            for s in payload.get("samples", [])
        ]
        return (
            "请始终使用简体中文输出。\n"
            f"项目: {project_name}\n运行ID: {run_id}\n"
            f"分析关注点: {focus or '整体质量、潜在风险、下一轮改进建议'}\n\n"
            "可用文件:\n" + "\n".join(files_desc) + "\n\n"
            "请分析本次运行结果，并按以下结构输出:\n"
            "1) 总结\n2) 关键发现\n3) 风险与失败模式\n"
            "4) 下一步行动（3-5条可执行建议）\n\n运行产物:\n" + "\n\n".join(sections)
        )

    def _analysis_history_dir(self, run_root: Path, create: bool = True) -> Path:
        d = run_root / "analysis_history"
        if create:
            d.mkdir(parents=True, exist_ok=True)
        return d

    def _new_analysis_id(self) -> str:
        return f"analysis_{time.strftime('%Y%m%d_%H%M')}_{uuid.uuid4().hex[:4]}"

    def _handle_output_analyze(self, project_name: str, run_id: str) -> None:
        if not HAS_LLM:
            _json_response(
                self,
                HTTPStatus.BAD_REQUEST,
                {"error": "LLM analysis not available (llm_client.py not found)"},
            )
            return
        try:
            root = self._get_output_root(project_name, run_id)
            data = _read_json_body(self)
            focus = str(data.get("focus") or "").strip()
            max_bytes = max(4096, min(int(data.get("maxBytes") or 65536), 262144))
            ap = self._build_analysis_payload(root, max_bytes=max_bytes)
            prompt = self._build_analysis_prompt(project_name, run_id, focus, ap)
            llm_result = analyze_with_deepseek(prompt, timeout_sec=60)
            aid = self._new_analysis_id()
            hist_dir = self._analysis_history_dir(root, create=True)
            record = {
                "id": aid,
                "projectName": project_name,
                "runId": run_id,
                "createdAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                "model": llm_result["model"],
                "focus": focus,
                "analysis": llm_result["analysis"],
                "inputsSummary": {
                    "fileCount": ap["fileCount"],
                    "files": [
                        {
                            "label": s["label"],
                            "path": s["path"],
                            "truncated": s["truncated"],
                        }
                        for s in ap["samples"]
                    ],
                },
            }
            (hist_dir / f"{aid}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "analysisId": aid,
                    "analysis": llm_result["analysis"],
                    "model": llm_result["model"],
                    "projectName": project_name,
                    "runId": run_id,
                    "inputsSummary": record["inputsSummary"],
                },
            )
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except PayloadTooLargeError as e:
            _json_response(self, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": str(e)})
        except LLMClientError as e:
            msg = str(e)
            status = (
                HTTPStatus.BAD_REQUEST
                if "missing DEEPSEEK_API_KEY" in msg or "missing LLM_API_KEY" in msg
                else HTTPStatus.BAD_GATEWAY
            )
            _json_response(self, status, {"error": msg})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_output_analyses_list(self, project_name: str, run_id: str) -> None:
        try:
            root = self._get_output_root(project_name, run_id)
            hist_dir = self._analysis_history_dir(root, create=False)
            if not hist_dir.exists():
                return _json_response(
                    self,
                    200,
                    {"projectName": project_name, "runId": run_id, "items": []},
                )
            items: list[dict[str, Any]] = []
            for p in sorted(
                hist_dir.glob("analysis_*.json"), key=lambda x: x.name, reverse=True
            ):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    analysis = str(data.get("analysis") or "")
                    lines = [ln.strip() for ln in analysis.splitlines() if ln.strip()]
                    items.append(
                        {
                            "id": str(data.get("id") or p.stem),
                            "createdAt": str(data.get("createdAt", "")),
                            "model": str(data.get("model", "")),
                            "focus": str(data.get("focus", "")),
                            "preview": lines[0][:180] if lines else "",
                            "downloadUrl": f"/api/outputs/{project_name}/{run_id}/analyses/{p.stem}",
                        }
                    )
                except Exception:
                    continue
            _json_response(
                self,
                200,
                {"projectName": project_name, "runId": run_id, "items": items},
            )
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_output_analysis_download(
        self, project_name: str, run_id: str, analysis_id: str
    ) -> None:
        try:
            root = self._get_output_root(project_name, run_id)
            hist_dir = self._analysis_history_dir(root, create=False)
            target = _safe_rooted_path(hist_dir, f"{analysis_id}.json")
            if not target.exists() or not target.is_file():
                raise FileNotFoundError("analysis not found")
            data = json.loads(target.read_text(encoding="utf-8"))
            md = (
                f"# Analysis {analysis_id}\n\n"
                f"- Project: {project_name}\n- Run: {run_id}\n"
                f"- Model: {data.get('model', '')}\n- Created: {data.get('createdAt', '')}\n"
                f"- Focus: {data.get('focus', '')}\n\n## Output\n\n{data.get('analysis', '')}"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.send_header("Content-Length", str(len(md)))
            self.send_header(
                "Content-Disposition", f'attachment; filename="{analysis_id}.md"'
            )
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(md)
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_output_analysis_get(
        self, project_name: str, run_id: str, analysis_id: str
    ) -> None:
        try:
            root = self._get_output_root(project_name, run_id)
            hist_dir = self._analysis_history_dir(root, create=False)
            target = _safe_rooted_path(hist_dir, f"{analysis_id}.json")
            if not target.exists() or not target.is_file():
                raise FileNotFoundError("analysis not found")
            data = json.loads(target.read_text(encoding="utf-8"))
            _json_response(
                self,
                200,
                {
                    "id": str(data.get("id") or analysis_id),
                    "projectName": str(data.get("projectName") or project_name),
                    "runId": str(data.get("runId") or run_id),
                    "createdAt": str(data.get("createdAt", "")),
                    "model": str(data.get("model", "")),
                    "focus": str(data.get("focus", "")),
                    "analysis": str(data.get("analysis", "")),
                    "inputsSummary": data.get("inputsSummary") or {},
                },
            )
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_delete_analysis(
        self, project_name: str, run_id: str, analysis_id: str
    ) -> None:
        try:
            root = self._get_output_root(project_name, run_id)
            hist_dir = self._analysis_history_dir(root, create=False)
            target = _safe_rooted_path(hist_dir, f"{analysis_id}.json")
            if not target.exists() or not target.is_file():
                raise FileNotFoundError("analysis not found")
            target.unlink(missing_ok=True)
            append_audit_log(
                AUDIT_LOG_FILE,
                "analysis_delete",
                {"project": project_name, "runId": run_id, "analysisId": analysis_id},
            )
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "projectName": project_name,
                    "runId": run_id,
                    "analysisId": analysis_id,
                },
            )
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    # ── Scenario Builder / OpenCode session handler ──────────────────────────

    def _handle_scenario_gate(self) -> None:
        try:
            data = _read_json_body(self)
            result = _assess_scenario_gate(data)
            _json_response(self, 200, result)
        except PayloadTooLargeError as e:
            _json_response(self, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_scenario_session_start(self) -> None:
        try:
            data = _read_json_body(self)
            intake = data.get("intake") or {}
            if not isinstance(intake, dict):
                return _json_response(
                    self, HTTPStatus.BAD_REQUEST, {"error": "intake must be object"}
                )
            gate_payload = {
                "problemDescription": intake.get("problemDescription"),
                "objectiveType": intake.get("objectiveType"),
                "hasAutoEvaluation": intake.get("hasAutoEvaluation"),
                "constraints": intake.get("constraints"),
                "ioContract": intake.get("ioContract"),
            }
            gate = _assess_scenario_gate(gate_payload)
            if not gate.get("fit"):
                return _json_response(
                    self,
                    HTTPStatus.BAD_REQUEST,
                    {"error": "gate rejected", "gate": gate},
                )
            session_id = _default_scenario_session_id()
            skill_name = re.sub(r"[^a-z0-9\-]", "", str(data.get("skillName") or "opencode-scenario-builder").strip().lower()) or "opencode-scenario-builder"
            session: dict[str, Any] = {
                "id": session_id,
                "status": "created",
                "createdAt": int(time.time() * 1000),
                "seq": 0,
                "intake": intake,
                "skillName": skill_name,
                "maxAttempts": int(data.get("maxAttempts") or 2),
                "seedFiles": data.get("seedFiles") if isinstance(data.get("seedFiles"), dict) else {},
                "userFeedback": str(data.get("userFeedback") or ""),
                "events": [],
                "subs": [],
                "lock": threading.Lock(),
                "result": {
                    "draftFiles": {
                        "initialProgram": "",
                        "evaluator": "",
                        "configYaml": "",
                    },
                    "validationReport": {
                        "ok": False,
                        "errors": [],
                        "warnings": [],
                        "suggestions": [],
                    },
                    "changeSummary": "OpenCode 会话已启动",
                    "usedSkill": skill_name,
                    "draftStorage": {
                        "draftDir": f"server_data/_scenario_drafts/{session_id}",
                        "initialProgramPath": f"server_data/_scenario_drafts/{session_id}/initial_program.py",
                        "evaluatorPath": f"server_data/_scenario_drafts/{session_id}/evaluator.py",
                        "configYamlPath": f"server_data/_scenario_drafts/{session_id}/config.yaml",
                    },
                },
            }
            with _SCENARIO_LOCK:
                _SCENARIO_SESSIONS[session_id] = session
            threading.Thread(
                target=_run_scenario_session_worker,
                args=(session_id,),
                daemon=True,
            ).start()
            _json_response(
                self,
                200,
                {
                    "sessionId": session_id,
                    "status": "created",
                    "gate": gate,
                    "usedSkill": skill_name,
                    "draftStorage": session["result"].get("draftStorage") or {},
                },
            )
        except PayloadTooLargeError as e:
            _json_response(self, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _get_scenario_session(self, session_id: str) -> dict[str, Any]:
        with _SCENARIO_LOCK:
            session = _SCENARIO_SESSIONS.get(session_id)
        if not session:
            raise FileNotFoundError("scenario session not found")
        return session

    def _handle_scenario_session_events(self, session_id: str) -> None:
        try:
            session = self._get_scenario_session(session_id)
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
            return
        sub_q: queue.Queue = queue.Queue(maxsize=512)
        with session["lock"]:
            for ev in session["events"]:
                try:
                    sub_q.put_nowait(ev)
                except Exception:
                    break
            session["subs"].append(sub_q)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            while True:
                msg = sub_q.get()
                payload = json.dumps(msg, ensure_ascii=False)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
                if msg.get("eventType") in {"session_completed", "session_failed"}:
                    break
        except Exception:
            pass
        finally:
            with session["lock"]:
                session["subs"] = [q for q in session["subs"] if q is not sub_q]

    def _handle_scenario_session_result(self, session_id: str) -> None:
        try:
            session = self._get_scenario_session(session_id)
            _json_response(
                self,
                200,
                {
                    "sessionId": session_id,
                    "status": session.get("status"),
                    "result": session.get("result") or {},
                },
            )
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_scenario_create(self) -> None:
        try:
            data = _read_json_body(self)
            project_name = str(data.get("projectName") or "").strip()
            session_id = str(data.get("sessionId") or "").strip()
            used_skill = re.sub(r"[^a-z0-9\-]", "", str(data.get("usedSkill") or "opencode-scenario-builder").strip().lower()) or "opencode-scenario-builder"
            files = data.get("files") or {}
            if not project_name:
                raise ValueError("missing projectName")
            if not isinstance(files, dict):
                raise ValueError("files must be object")
            initial_program = str(files.get("initialProgram") or "")
            evaluator = str(files.get("evaluator") or "")
            config_yaml = str(files.get("configYaml") or "")
            report = _validate_scenario_files(
                {
                    "initialProgram": initial_program,
                    "evaluator": evaluator,
                    "configYaml": config_yaml,
                }
            )
            if not report.get("ok"):
                return _json_response(
                    self,
                    HTTPStatus.BAD_REQUEST,
                    {"error": "validation failed", "validationReport": report},
                )
            if re.search(r"(?im)^\s*api_key\s*:\s*['\"]?\s*(?!\$\{)[A-Za-z0-9_\-]{16,}", config_yaml):
                return _json_response(
                    self,
                    HTTPStatus.BAD_REQUEST,
                    {
                        "error": "config contains plaintext api_key, use ${DEEPSEEK_API_KEY}",
                    },
                )
            allow_overwrite = bool(data.get("allowOverwrite") is True)
            project_dir = SERVER_DATA_DIR / project_name
            if project_dir.exists():
                if not allow_overwrite:
                    return _json_response(
                        self,
                        HTTPStatus.CONFLICT,
                        {
                            "error": f"project already exists: {project_name}. pass allowOverwrite=true to replace"
                        },
                    )
                shutil.rmtree(project_dir, ignore_errors=True)
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "initial_program.py").write_text(initial_program, encoding="utf-8")
            (project_dir / "evaluator.py").write_text(evaluator, encoding="utf-8")
            (project_dir / "config.yaml").write_text(config_yaml, encoding="utf-8")
            cleaned_draft_dir = ""
            if session_id:
                draft_dir = _SCENARIO_DRAFT_ROOT / session_id
                try:
                    if draft_dir.exists():
                        shutil.rmtree(draft_dir, ignore_errors=True)
                        cleaned_draft_dir = draft_dir.relative_to(ROOT_DIR).as_posix()
                except Exception:
                    cleaned_draft_dir = ""
            append_audit_log(
                AUDIT_LOG_FILE,
                "scenario_create_project",
                {
                    "project": project_name,
                    "overwrite": allow_overwrite,
                    "usedSkill": used_skill,
                    "sessionId": session_id,
                    "cleanedDraftDir": cleaned_draft_dir,
                },
            )
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "projectName": project_name,
                    "usedSkill": used_skill,
                    "createdPaths": [
                        f"server_data/{project_name}/initial_program.py",
                        f"server_data/{project_name}/evaluator.py",
                        f"server_data/{project_name}/config.yaml",
                    ],
                    "cleanedDraftDir": cleaned_draft_dir,
                },
            )
        except FileNotFoundError as e:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": str(e)})
        except PayloadTooLargeError as e:
            _json_response(self, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": str(e)})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    # ── opencode CLI 桥接 handler ────────────────────────────────────────────

    def _handle_start(self) -> None:
        try:
            data = _read_json_body(self)
            project_name = str(data.get("projectName") or "")
            iterations = int(data.get("iterations") or 10)
            if iterations <= 0:
                iterations = 10
            checkpoint_interval = int(data.get("checkpointInterval") or 3)
            if checkpoint_interval <= 0:
                checkpoint_interval = 3
            num_islands = int(data.get("numIslands") or 2)
            if num_islands <= 0:
                num_islands = 2
            population_size = int(data.get("populationSize") or 30)
            if population_size <= 0:
                population_size = 30
            evaluator_timeout = int(data.get("evaluatorTimeout") or 30)
            if evaluator_timeout <= 0:
                evaluator_timeout = 30
            parallel_evaluations = int(data.get("parallelEvaluations") or 2)
            if parallel_evaluations <= 0:
                parallel_evaluations = 2
            mutation_rate = float(data.get("mutationRate") or 0.1)
            if mutation_rate < 0 or mutation_rate > 1:
                mutation_rate = 0.1
            diff_based_evolution = bool(data.get("diffBasedEvolution") is True)
            archive_size = int(data.get("archiveSize") or 10)
            if archive_size <= 0:
                archive_size = 10
            elite_selection_ratio = float(data.get("eliteSelectionRatio") or 0.2)
            if elite_selection_ratio < 0 or elite_selection_ratio > 1:
                elite_selection_ratio = 0.2
            exploitation_ratio = float(data.get("exploitationRatio") or 0.7)
            if exploitation_ratio < 0 or exploitation_ratio > 1:
                exploitation_ratio = 0.7
            similarity_threshold = float(data.get("similarityThreshold") or 0.99)
            if similarity_threshold < 0 or similarity_threshold > 1:
                similarity_threshold = 0.99
            with _RUN_LOCK:
                active = _find_active_run_locked()
            if active is not None:
                active_run_id, _ = active
                return _json_response(
                    self,
                    HTTPStatus.CONFLICT,
                    {
                        "error": f"another run is already active: {active_run_id}. stop it before starting a new run"
                    },
                )
            if not project_name:
                return _json_response(
                    self, HTTPStatus.BAD_REQUEST, {"error": "missing projectName"}
                )
            project_dir = SERVER_DATA_DIR / project_name
            if not project_dir.exists():
                return _json_response(
                    self, HTTPStatus.NOT_FOUND, {"error": "project not found"}
                )
            _override_checkpoint_interval(project_dir, checkpoint_interval)
            _override_num_islands(project_dir, num_islands)
            _override_config_value(project_dir, "database.population_size", population_size)
            _override_config_value(project_dir, "evaluator.timeout", evaluator_timeout)
            _override_config_value(
                project_dir, "evaluator.parallel_evaluations", parallel_evaluations
            )
            _override_config_value(project_dir, "database.mutation_rate", mutation_rate)
            _override_config_value(
                project_dir, "diff_based_evolution", diff_based_evolution
            )
            _override_config_value(project_dir, "database.archive_size", archive_size)
            _override_config_value(
                project_dir, "database.elite_selection_ratio", elite_selection_ratio
            )
            _override_config_value(project_dir, "database.exploitation_ratio", exploitation_ratio)
            _override_config_value(
                project_dir, "database.similarity_threshold", similarity_threshold
            )

            run_id = str(data.get("runId") or "").strip() or _default_run_id()
            output_dir = project_dir / "openevolve_output" / run_id
            output_dir.mkdir(parents=True, exist_ok=True)
            logs_dir = output_dir / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            monitor_log_path = logs_dir / "monitor_realtime.jsonl"

            # 通过交互式 skill runner 构造 OpenEvolve 调用；后端只保留 Web/API 与进程管理职责。
            opencode_agent = os.environ.get(
                "OPENCODE_EVOLVE_AGENT", "openevolve-unified-primary"
            ).strip() or "openevolve-unified-primary"
            run_mode = str(
                data.get("runMode")
                or os.environ.get("AI4MATH_EVOLVE_RUN_MODE")
                or os.environ.get("EVOLVE_RUN_MODE")
                or "direct"
            ).strip().lower()
            if run_mode not in {"direct", "opencode"}:
                run_mode = "direct"
            if build_run_command is None:
                return _json_response(
                    self,
                    HTTPStatus.BAD_GATEWAY,
                    {"error": "OpenEvolve skill runner adapter is unavailable"},
                )
            runner_extras = provider_extras_from_env() if provider_extras_from_env else {}
            runner_extras.update(
                {
                    "num_islands": num_islands,
                    "population_size": population_size,
                    "evaluator_timeout": evaluator_timeout,
                    "parallel_evaluations": parallel_evaluations,
                    "mutation_rate": mutation_rate,
                    "diff_based_evolution": diff_based_evolution,
                    "archive_size": archive_size,
                    "elite_selection_ratio": elite_selection_ratio,
                    "exploitation_ratio": exploitation_ratio,
                    "similarity_threshold": similarity_threshold,
                }
            )
            try:
                cmd = build_run_command(
                    project_dir,
                    iterations=iterations,
                    checkpoint_interval=checkpoint_interval,
                    output_dir=output_dir,
                    mode=run_mode,
                    workspace=project_dir,
                    project_name=project_name,
                    agent=opencode_agent,
                    language="zh-CN",
                    extras=runner_extras,
                )
            except SkillRunnerError as e:
                return _json_response(self, HTTPStatus.BAD_GATEWAY, {"error": str(e)})
            print(f"[DEBUG] Starting evolution ({run_mode}): {' '.join(cmd)}", file=sys.stderr)
            print(f"[DEBUG] Working dir: {project_dir}", file=sys.stderr)

            proc = subprocess.Popen(
                cmd,
                cwd=str(project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                text=True,
            )
            print(f"[DEBUG] Process started with PID: {proc.pid}", file=sys.stderr)
            if record_external_run is not None:
                try:
                    record_external_run(
                        project_dir,
                        run_id=run_id,
                        output_dir=output_dir,
                        log_path=monitor_log_path,
                        pid=proc.pid,
                        mode=run_mode,
                        command=cmd,
                        workspace=project_dir,
                        project_name=project_name,
                    )
                except SkillRunnerError as e:
                    print(f"[DEBUG] failed to record interactive session run: {e}", file=sys.stderr)

            runsrv: dict[str, Any] = {
                "proc": proc,
                "output_dir": output_dir,
                "project_name": project_name,
                "run_id": run_id,
                "iterations": iterations,
                "checkpoint_interval": checkpoint_interval,
                "num_islands": num_islands,
                "population_size": population_size,
                "evaluator_timeout": evaluator_timeout,
                "parallel_evaluations": parallel_evaluations,
                "mutation_rate": mutation_rate,
                "diff_based_evolution": diff_based_evolution,
                "archive_size": archive_size,
                "elite_selection_ratio": elite_selection_ratio,
                "exploitation_ratio": exploitation_ratio,
                "similarity_threshold": similarity_threshold,
                "runner_mode": run_mode,
                "subs": [],
                "lock": threading.Lock(),
                "monitor_log_path": monitor_log_path,
                "monitor_log_lock": threading.Lock(),
                "done": False,
            }
            with _RUN_LOCK:
                _RUNS[run_id] = runsrv

            t = threading.Thread(target=_poll_loop, args=(runsrv,), daemon=True)
            t.start()

            _broadcast(
                runsrv,
                {
                    "type": "started",
                    "runId": run_id,
                    "outputDir": str(output_dir),
                    "iterations": iterations,
                    "checkpointInterval": checkpoint_interval,
                    "numIslands": num_islands,
                    "populationSize": population_size,
                    "evaluatorTimeout": evaluator_timeout,
                    "parallelEvaluations": parallel_evaluations,
                    "mutationRate": mutation_rate,
                    "diffBasedEvolution": diff_based_evolution,
                    "archiveSize": archive_size,
                    "eliteSelectionRatio": elite_selection_ratio,
                    "exploitationRatio": exploitation_ratio,
                    "similarityThreshold": similarity_threshold,
                    "runMode": run_mode,
                    "channel": "system_log",
                    "origin": "backend",
                    "confidence": "high",
                },
            )
            _json_response(
                self,
                200,
                {
                    "runId": run_id,
                    "outputDir": str(output_dir),
                    "iterationsApplied": iterations,
                    "checkpointIntervalApplied": checkpoint_interval,
                    "numIslandsApplied": num_islands,
                    "populationSizeApplied": population_size,
                    "evaluatorTimeoutApplied": evaluator_timeout,
                    "parallelEvaluationsApplied": parallel_evaluations,
                    "mutationRateApplied": mutation_rate,
                    "diffBasedEvolutionApplied": diff_based_evolution,
                    "archiveSizeApplied": archive_size,
                    "eliteSelectionRatioApplied": elite_selection_ratio,
                    "exploitationRatioApplied": exploitation_ratio,
                    "similarityThresholdApplied": similarity_threshold,
                    "runMode": run_mode,
                },
            )
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_stop(self, run_id: str) -> None:
        try:
            if not run_id:
                return _json_response(
                    self, HTTPStatus.BAD_REQUEST, {"error": "missing runId"}
                )
            with _RUN_LOCK:
                runsrv = _RUNS.get(run_id)
            if not runsrv:
                return _json_response(
                    self, HTTPStatus.NOT_FOUND, {"error": "run not found"}
                )
            proc = runsrv["proc"]
            output_dir = Path(str(runsrv.get("output_dir") or ""))
            _terminate_run_processes(proc, run_id, output_dir)
            runsrv["done"] = True
            _json_response(self, 200, {"ok": True, "runId": run_id})
        except Exception as e:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(e)})

    def _handle_sse_events(self, run_id: str) -> None:
        with _RUN_LOCK:
            runsrv = _RUNS.get(run_id)
        if not runsrv:
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": "run not found"})
            return
        sub_q: queue.Queue = queue.Queue(maxsize=256)
        with runsrv["lock"]:
            runsrv["subs"].append(sub_q)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            while True:
                msg = sub_q.get()
                payload = json.dumps(msg, ensure_ascii=False)
                data = f"data: {payload}\n\n".encode("utf-8")
                self.wfile.write(data)
                self.wfile.flush()
                if msg.get("type") in ("done", "error"):
                    break
        except Exception:
            pass
        finally:
            with runsrv["lock"]:
                runsrv["subs"] = [q for q in runsrv["subs"] if q is not sub_q]
            # If page/tab is closed and no subscribers remain, stop the run.
            with runsrv["lock"]:
                should_orphan_stop = (not runsrv.get("done")) and (len(runsrv["subs"]) == 0)
            if should_orphan_stop:
                threading.Thread(
                    target=_stop_run_if_orphaned,
                    args=(run_id, 3.0),
                    daemon=True,
                ).start()


def main() -> None:
    _load_env_file(ENV_FILE)
    host = os.environ.get("EVOLVE_BRIDGE_HOST", "127.0.0.1")
    port = int(os.environ.get("EVOLVE_BRIDGE_PORT", "8001"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"AI4Math-Evolving Bridge listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
