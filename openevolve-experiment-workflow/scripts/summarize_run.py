#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def find_best_info(run_dir: Path) -> Path | None:
    direct = run_dir / "best" / "best_program_info.json"
    if direct.is_file():
        return direct
    candidates = sorted(run_dir.glob("checkpoints/**/best_program_info.json"))
    return candidates[-1] if candidates else None


def summarize(run_dir: Path) -> dict[str, Any]:
    best_info = find_best_info(run_dir)
    data = read_json(best_info) if best_info else {}
    metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
    return {
        "runDir": str(run_dir),
        "bestProgramInfoPath": str(best_info) if best_info else "",
        "bestMetrics": metrics,
        "bestProgramId": str(data.get("id") or data.get("program_id") or ""),
        "hasBest": bool(best_info),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = summarize(Path(args.run_dir).absolute())
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"run: {payload['runDir']}")
        print(f"best: {payload['bestProgramInfoPath']}")
        print(f"metrics: {payload['bestMetrics']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
