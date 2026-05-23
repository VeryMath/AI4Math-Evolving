#!/usr/bin/env bash
# ./stop_all.sh
# ENABLE_PUBLIC_TUNNEL=1 TUNNEL_PROVIDER=localhost.run DETACH=1 ./start_all.sh
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_CMD=(python3 backend/server.py)
FRONTEND_CMD=(npm run dev)
REQUIRED_NODE_MAJOR=20
ENABLE_PUBLIC_TUNNEL="${ENABLE_PUBLIC_TUNNEL:-0}"
TUNNEL_PORT="${TUNNEL_PORT:-8001}"
CLOUDFLARED_BIN="${CLOUDFLARED_BIN:-$PROJECT_ROOT/.tools/cloudflared}"
CLOUDFLARED_PROTOCOL="${CLOUDFLARED_PROTOCOL:-http2}"
TUNNEL_PROVIDER="${TUNNEL_PROVIDER:-auto}"
USE_VITE_DEV="${USE_VITE_DEV:-1}"
VITE_PORT="${VITE_PORT:-5173}"
DETACH="${DETACH:-0}"
LOG_DIR="${LOG_DIR:-$PROJECT_ROOT/.run_logs}"
PID_DIR="${PID_DIR:-$PROJECT_ROOT/.run_pids}"

cd "$PROJECT_ROOT"

load_nvm() {
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    # shellcheck source=/dev/null
    . "$NVM_DIR/nvm.sh"
  fi
}

ensure_node_version() {
  if command -v nvm >/dev/null 2>&1; then
    nvm use "$REQUIRED_NODE_MAJOR" >/dev/null
    return
  fi

  if ! command -v node >/dev/null 2>&1; then
    echo "错误：未找到 node。请先安装 Node.js 或 nvm。"
    exit 1
  fi

  local current_major
  current_major="$(node -p "process.versions.node.split('.')[0]")"
  if [[ "$current_major" != "$REQUIRED_NODE_MAJOR" ]]; then
    echo "警告：当前 Node 主版本是 $current_major，建议使用 $REQUIRED_NODE_MAJOR。"
    echo "如果你有 nvm，请安装后重试，本脚本会自动执行 nvm use $REQUIRED_NODE_MAJOR。"
  fi
}

ensure_frontend_deps() {
  if [[ ! -d node_modules ]]; then
    echo "未检测到 node_modules，正在安装前端依赖..."
    npm install
  fi
}

start_process() {
  local name="$1"
  shift

  if [[ "$DETACH" == "1" ]]; then
    mkdir -p "$LOG_DIR" "$PID_DIR"
    local logfile="$LOG_DIR/${name}.log"
    echo "后台启动 ${name}: $*"
    nohup "$@" >"$logfile" 2>&1 &
    local pid=$!
    echo "$pid" >"$PID_DIR/${name}.pid"
    sleep 1
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "错误：${name} 启动失败，请查看日志 $logfile"
      exit 1
    fi
    echo "${name} 已后台运行，PID=$pid，日志: $logfile"
  else
    "$@" &
  fi
}

print_public_url_hint() {
  local logfile="$1"
  local tries=20
  local url=""

  if [[ ! -f "$logfile" ]]; then
    return 0
  fi

  while (( tries > 0 )); do
    url="$(python3 - <<'PY' "$logfile"
import re
import sys

logfile = sys.argv[1]
try:
    text = open(logfile, "r", encoding="utf-8", errors="ignore").read()
except OSError:
    print("")
    raise SystemExit(0)

matches = re.findall(r"https://[a-zA-Z0-9./:_-]+", text)
good = []
for item in matches:
    if "trycloudflare.com" in item:
        good.append(item)
        continue
    if "localhost.run" in item:
        # 排除文档/后台链接，只保留实际映射域名
        if "/docs" in item or "admin.localhost.run" in item or "twitter.com/localhost_run" in item:
            continue
        if item.rstrip("/").endswith("localhost.run"):
            continue
    if ".lhr.life" in item or ".localhost.run" in item:
        good.append(item)

print(good[-1] if good else "")
PY
)"
    if [[ -n "$url" ]]; then
      echo "公网访问地址: $url"
      return 0
    fi
    sleep 1
    tries=$((tries - 1))
  done

  echo "暂未自动解析到公网地址，可手动查看日志: $logfile"
}

is_bridge_ready() {
  local url="http://127.0.0.1:${EVOLVE_BRIDGE_PORT}/api/projects"
  curl -fsS --max-time 2 "$url" >/dev/null 2>&1
}

can_bind_bridge_port() {
  python3 - <<'PY' "$EVOLVE_BRIDGE_HOST" "$EVOLVE_BRIDGE_PORT"
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind((host, port))
except OSError:
    sys.exit(1)
finally:
    s.close()
PY
}

cleanup() {
  echo
  echo "正在停止进程..."
  if [[ -n "${TUNNEL_PID:-}" ]] && kill -0 "$TUNNEL_PID" 2>/dev/null; then
    kill "$TUNNEL_PID" 2>/dev/null || true
  fi
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  wait || true
  echo "已退出。"
}

if [[ "$DETACH" != "1" ]]; then
  trap cleanup INT TERM EXIT
fi

load_nvm
ensure_node_version
ensure_frontend_deps

if [[ "${EVOLVE_BRIDGE_HOST:-}" == "" ]]; then
  export EVOLVE_BRIDGE_HOST=127.0.0.1
fi
if [[ "${EVOLVE_BRIDGE_PORT:-}" == "" ]]; then
  export EVOLVE_BRIDGE_PORT="$TUNNEL_PORT"
fi

if can_bind_bridge_port; then
  echo "启动后端: ${BACKEND_CMD[*]}"
  start_process "backend" "${BACKEND_CMD[@]}"
  if [[ "$DETACH" != "1" ]]; then
    BACKEND_PID=$!
    sleep 1
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
      echo "错误：后端启动失败，请检查端口或日志。"
      exit 1
    fi
  fi
else
  if is_bridge_ready; then
    echo "检测到已有后端在 ${EVOLVE_BRIDGE_HOST}:${EVOLVE_BRIDGE_PORT}，将复用该实例。"
  else
    echo "错误：端口 ${EVOLVE_BRIDGE_PORT} 已被占用，且现有服务不是可用的 OpenEvolve 后端。"
    echo "请先释放端口，或设置其他端口后重试：EVOLVE_BRIDGE_PORT=8002 ./start_all.sh"
    exit 1
  fi
fi

if [[ "$USE_VITE_DEV" == "1" ]]; then
  if [[ "$ENABLE_PUBLIC_TUNNEL" == "1" ]]; then
    export VITE_ALLOWED_HOSTS=all
  fi
  echo "启动前端: ${FRONTEND_CMD[*]}"
  start_process "frontend" "${FRONTEND_CMD[@]}"
  if [[ "$DETACH" != "1" ]]; then
    FRONTEND_PID=$!
  fi
else
  echo "未启动 Vite dev（USE_VITE_DEV=0）。注意：当前后端未提供静态前端托管时，公网只会暴露 API。"
fi

if [[ "$ENABLE_PUBLIC_TUNNEL" == "1" ]]; then
  tunnel_port="$EVOLVE_BRIDGE_PORT"
  if [[ "$USE_VITE_DEV" == "1" ]]; then
    tunnel_port="$VITE_PORT"
  fi

  if [[ "$TUNNEL_PROVIDER" != "auto" && "$TUNNEL_PROVIDER" != "cloudflared" && "$TUNNEL_PROVIDER" != "localhost.run" ]]; then
    echo "错误：TUNNEL_PROVIDER 仅支持 auto / cloudflared / localhost.run"
    exit 1
  fi

  use_cloudflared=0
  use_localhost_run=0
  if [[ "$TUNNEL_PROVIDER" == "cloudflared" ]]; then
    use_cloudflared=1
  elif [[ "$TUNNEL_PROVIDER" == "localhost.run" ]]; then
    use_localhost_run=1
  else
    if [[ -x "$CLOUDFLARED_BIN" ]]; then
      use_cloudflared=1
    else
      use_localhost_run=1
    fi
  fi

  if [[ "$use_cloudflared" == "1" ]]; then
    if [[ ! -x "$CLOUDFLARED_BIN" ]]; then
      echo "错误：未找到可执行 cloudflared: $CLOUDFLARED_BIN"
      exit 1
    fi
    echo "启动公网隧道: $CLOUDFLARED_BIN tunnel --protocol ${CLOUDFLARED_PROTOCOL} --url http://127.0.0.1:${tunnel_port}"
    start_process "tunnel" "$CLOUDFLARED_BIN" tunnel --protocol "${CLOUDFLARED_PROTOCOL}" --url "http://127.0.0.1:${tunnel_port}"
    if [[ "$DETACH" != "1" ]]; then
      TUNNEL_PID=$!
    fi
    echo "已启用 cloudflared 公网隧道，稍等终端输出 https 链接。"
  elif [[ "$use_localhost_run" == "1" ]] && command -v ssh >/dev/null 2>&1; then
    echo "未检测到 cloudflared，回退到 localhost.run 隧道..."
    start_process "tunnel" ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -R 80:127.0.0.1:"${tunnel_port}" nokey@localhost.run
    if [[ "$DETACH" != "1" ]]; then
      TUNNEL_PID=$!
    fi
    echo "已启用 localhost.run 公网隧道，稍等终端输出 https 链接。"
  else
    echo "警告：无法启动公网隧道（ssh 不可用，无法使用 localhost.run）。"
  fi
fi

if [[ "$ENABLE_PUBLIC_TUNNEL" == "1" ]]; then
  echo "前后端+隧道已启动。按 Ctrl+C 可一键停止。"
else
  echo "前后端已启动。按 Ctrl+C 可一键停止。"
  echo "如需公网访问：ENABLE_PUBLIC_TUNNEL=1 ./start_all.sh"
fi

if [[ "$DETACH" == "1" ]]; then
  echo "当前为后台模式（DETACH=1），退出终端后服务会继续运行。"
  echo "查看日志: ls \"$LOG_DIR\""
  echo "停止服务示例: kill \$(cat \"$PID_DIR/backend.pid\") \$(cat \"$PID_DIR/frontend.pid\")"
  if [[ "$ENABLE_PUBLIC_TUNNEL" == "1" ]]; then
    print_public_url_hint "$LOG_DIR/tunnel.log"
  fi
  exit 0
fi

wait
