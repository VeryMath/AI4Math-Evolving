#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="${PID_DIR:-$PROJECT_ROOT/.run_pids}"

stop_one() {
  local name="$1"
  local pid_file="$PID_DIR/${name}.pid"

  if [[ ! -f "$pid_file" ]]; then
    echo "${name}: 未找到 pid 文件，跳过"
    return 0
  fi

  local pid
  pid="$(tr -d '[:space:]' <"$pid_file")"
  if [[ -z "$pid" ]]; then
    echo "${name}: pid 文件为空，已清理"
    rm -f "$pid_file"
    return 0
  fi

  if kill -0 "$pid" 2>/dev/null; then
    echo "${name}: 正在停止 PID=$pid"
    kill "$pid" 2>/dev/null || true

    for _ in {1..20}; do
      if ! kill -0 "$pid" 2>/dev/null; then
        break
      fi
      sleep 0.2
    done

    if kill -0 "$pid" 2>/dev/null; then
      echo "${name}: 进程仍在运行，发送 SIGKILL"
      kill -9 "$pid" 2>/dev/null || true
    fi

    echo "${name}: 已停止"
  else
    echo "${name}: 进程不存在，清理 pid 文件"
  fi

  rm -f "$pid_file"
}

echo "停止后台服务..."
stop_one "tunnel"
stop_one "frontend"
stop_one "backend"
echo "完成。"
#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

stop_by_pattern() {
  local pattern="$1"
  local name="$2"
  local pids

  pids="$(pgrep -f "$pattern" || true)"
  if [[ -z "$pids" ]]; then
    echo "$name: 未发现运行中的进程"
    return
  fi

  echo "$name: 正在停止 -> $pids"
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
}

stop_by_port() {
  local port="$1"
  local name="$2"
  local pids=""

  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ' | xargs || true)"
  elif command -v ss >/dev/null 2>&1; then
    pids="$(ss -ltnp 2>/dev/null | awk -v p=":$port" '$4 ~ p {print $NF}' | sed -E 's/.*pid=([0-9]+).*/\1/' | tr '\n' ' ' | xargs || true)"
  fi

  if [[ -z "$pids" ]]; then
    echo "$name: 端口 $port 未发现监听进程"
    return
  fi

  echo "$name: 按端口 $port 停止 -> $pids"
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
}

cd "$PROJECT_ROOT"

# 仅匹配当前项目路径，避免误杀其他目录同名进程
BACKEND_PATTERN="$PROJECT_ROOT/backend/server.py"
FRONTEND_PATTERN="$PROJECT_ROOT/node_modules/.bin/vite"

stop_by_pattern "$BACKEND_PATTERN" "后端"
stop_by_pattern "$FRONTEND_PATTERN" "前端"
stop_by_port "8001" "后端端口清理"

echo "停止命令已执行。可用 ps/pgrep 再确认进程状态。"
