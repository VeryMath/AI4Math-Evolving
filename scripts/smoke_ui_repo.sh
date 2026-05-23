#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8001}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:5173}"

curl --noproxy '*' -fsS --max-time 3 "$BACKEND_URL/api/projects" >/tmp/openevolve_ui_projects.json
python3 - <<'PY'
import json

payload = json.load(open("/tmp/openevolve_ui_projects.json"))
assert "projects" in payload and isinstance(payload["projects"], list), payload
print("backend ok")
PY

curl --noproxy '*' -fsS --max-time 3 -I "$FRONTEND_URL/" | grep -E '^HTTP/.* 200' >/dev/null
echo "frontend ok"
