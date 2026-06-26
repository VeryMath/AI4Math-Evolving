#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import os
import re
from pathlib import Path
from typing import Any


CONFIG_NAMES = ("config.yaml", "config.yml", "config_default.yaml")


def error(code: str, message: str, path: str = "") -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def has_function(source: str, name: str) -> bool:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    return any(isinstance(node, ast.FunctionDef) and node.name == name for node in ast.walk(tree))


def config_api_key_value(text: str) -> str:
    match = re.search(r"(?im)^\s*api_key\s*:\s*['\"]?([^'\"\s#]+)", text)
    if not match:
        return ""
    return match.group(1).strip()


def env_var_name(value: str) -> str:
    match = re.fullmatch(r"\$\{([^}]+)\}", value)
    return match.group(1) if match else ""


def validate_project(project: Path) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    initial = project / "initial_program.py"
    evaluator = project / "evaluator.py"
    config = next((project / name for name in CONFIG_NAMES if (project / name).is_file()), project / "config.yaml")
    if not initial.is_file():
        errors.append(error("missing_file", "missing initial_program.py", "initial_program.py"))
    if not evaluator.is_file():
        errors.append(error("missing_file", "missing evaluator.py", "evaluator.py"))
    if not config.is_file():
        errors.append(error("missing_file", "missing config.yaml, config.yml, or config_default.yaml", "config.yaml"))

    if initial.is_file():
        text = initial.read_text(encoding="utf-8", errors="replace")
        if "EVOLVE-BLOCK-START" not in text or "EVOLVE-BLOCK-END" not in text:
            errors.append(
                error(
                    "missing_evolve_block",
                    "initial_program.py must contain EVOLVE-BLOCK markers",
                    "initial_program.py",
                )
            )
        if not has_function(text, "run_search"):
            errors.append(error("missing_entrypoint", "initial_program.py must define run_search()", "initial_program.py"))

    if evaluator.is_file():
        text = evaluator.read_text(encoding="utf-8", errors="replace")
        if not has_function(text, "evaluate"):
            errors.append(error("missing_evaluator_entrypoint", "evaluator.py must define evaluate(program_path)", "evaluator.py"))
        if "combined_score" not in text:
            warnings.append(error("missing_metric_hint", "evaluator.py should return a combined_score metric", "evaluator.py"))

    if config.is_file():
        text = config.read_text(encoding="utf-8", errors="replace")
        for required in ("max_iterations", "checkpoint_interval"):
            if not re.search(rf"(?m)^\s*{required}\s*:", text):
                errors.append(error("missing_config_key", f"{config.name} missing {required}", config.name))
        if re.search(r"(?im)api_key\s*:\s*['\"]?(?!\$\{)[A-Za-z0-9_\-]{12,}", text):
            errors.append(error("plaintext_secret", f"{config.name} contains a plaintext api_key", config.name))
        api_key = config_api_key_value(text)
        if not api_key or api_key.lower() in {"null", "none"}:
            warnings.append(
                error(
                    "missing_llm_api_key_config",
                    f"{config.name} should set llm.api_key to an environment placeholder such as ${{LLM_API_KEY}} before real runs",
                    config.name,
                )
            )
        else:
            var_name = env_var_name(api_key)
            if var_name and not os.environ.get(var_name):
                warnings.append(
                    error(
                        "missing_api_key_env",
                        f"{config.name} references ${{{var_name}}}, but environment variable {var_name} is not set",
                        config.name,
                    )
                )

    return {
        "ok": not errors,
        "projectDir": str(project),
        "configPath": str(config) if config.is_file() else "",
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = validate_project(Path(args.project).resolve())
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("ok" if payload["ok"] else "failed")
        for item in payload["errors"]:
            print(f"ERROR {item['path']}: {item['message']}")
        for item in payload["warnings"]:
            print(f"WARN {item['path']}: {item['message']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
