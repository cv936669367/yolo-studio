#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
# YOLO Studio 一键启动/停止脚本
#   后端 FastAPI  : http://localhost:8000  (/docs 接口文档)
#   前端 Vite     : http://localhost:3000
# 用法:
#   ./start.sh         启动前后端
#   ./start.sh start   启动前后端
#   ./start.sh stop    停止前后端
#   ./start.sh status  查看运行状态
#   ./start.sh restart 重启
# ═══════════════════════════════════════════════════════════
set -u

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT/logs"
BACKEND_PORT=8000
FRONTEND_PORT=3000

mkdir -p "$LOG_DIR"

log() { echo -e "\033[1;34m[YOLO]\033[0m $*"; }
ok()   { echo -e "\033[1;32m  ✓\033[0m $*"; }
err()  { echo -e "\033[1;31m  ✗\033[0m $*"; }

port_in_use() { lsof -i :"$1" -sTCP:LISTEN >/dev/null 2>&1; }

# ── 启动后端 ─────────────────────────────────────────────
start_backend() {
  if port_in_use $BACKEND_PORT; then
    ok "后端已在运行 (端口 $BACKEND_PORT)"
    return 0
  fi
  if [ ! -x "$ROOT/backend/venv/bin/python" ]; then
    err "backend/venv 不存在 → 请先: cd backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt"
    return 1
  fi
  log "启动后端..."
  ( cd "$ROOT/backend" && nohup ./venv/bin/python main.py \
      > "$LOG_DIR/backend.log" 2>&1 &
    echo $! > "$LOG_DIR/backend.pid" )
  # 等待就绪
  for i in $(seq 1 30); do
    sleep 1
    if curl -sf http://127.0.0.1:$BACKEND_PORT/health >/dev/null 2>&1; then
      ok "后端就绪 → http://localhost:$BACKEND_PORT  (接口文档 /docs)"
      return 0
    fi
    [ $((i % 5)) -eq 0 ] && log "  等待后端启动中... (${i}s)"
  done
  err "后端启动超时，查看 $LOG_DIR/backend.log"
  return 1
}

# ── 启动前端 ─────────────────────────────────────────────
start_frontend() {
  if port_in_use $FRONTEND_PORT; then
    ok "前端已在运行 (端口 $FRONTEND_PORT)"
    return 0
  fi
  if [ ! -d "$ROOT/frontend/node_modules" ]; then
    err "frontend/node_modules 不存在 → 请先: cd frontend && npm install"
    return 1
  fi
  log "启动前端..."
  ( cd "$ROOT/frontend" && nohup npm run dev \
      > "$LOG_DIR/frontend.log" 2>&1 &
    echo $! > "$LOG_DIR/frontend.pid" )
  for i in $(seq 1 30); do
    sleep 1
    if curl -sf -o /dev/null http://127.0.0.1:$FRONTEND_PORT/ 2>/dev/null; then
      ok "前端就绪 → http://localhost:$FRONTEND_PORT"
      return 0
    fi
    [ $((i % 5)) -eq 0 ] && log "  等待前端启动中... (${i}s)"
  done
  err "前端启动超时，查看 $LOG_DIR/frontend.log"
  return 1
}

# ── 停止 ─────────────────────────────────────────────────
stop_all() {
  log "停止服务..."
  [ -f "$LOG_DIR/frontend.pid" ] && kill "$(cat "$LOG_DIR/frontend.pid")" 2>/dev/null && ok "前端已停止"
  [ -f "$LOG_DIR/backend.pid" ] && kill "$(cat "$LOG_DIR/backend.pid")" 2>/dev/null && ok "后端已停止"
  # 兜底：清理残留进程
  pkill -f "vite" >/dev/null 2>&1 && true
  pkill -f "backend/.*main.py" >/dev/null 2>&1 && true
  sleep 1
  rm -f "$LOG_DIR"/*.pid
  log "全部停止完成"
}

status_all() {
  echo ""
  echo "── YOLO Studio 状态 ──────────────────────────"
  if port_in_use $BACKEND_PORT; then
    ok "后端  http://localhost:$BACKEND_PORT  (PID: $(lsof -ti :$BACKEND_PORT -sTCP:LISTEN))"
  else
    err "后端  未运行 (端口 $BACKEND_PORT)"
  fi
  if port_in_use $FRONTEND_PORT; then
    ok "前端  http://localhost:$FRONTEND_PORT  (PID: $(lsof -ti :$FRONTEND_PORT -sTCP:LISTEN))"
  else
    err "前端  未运行 (端口 $FRONTEND_PORT)"
  fi
  echo "──────────────────────────────────────────────"
}

case "${1:-start}" in
  start)
    start_backend
    start_frontend
    status_all
    log "启动完成！浏览器打开  http://localhost:$FRONTEND_PORT"
    log "日志目录: $LOG_DIR/   (tail -f logs/backend.log 查看后端)"
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    sleep 1
    start_backend
    start_frontend
    status_all
    ;;
  status)
    status_all
    ;;
  *)
    echo "用法: $0 {start|stop|restart|status}"
    ;;
esac
