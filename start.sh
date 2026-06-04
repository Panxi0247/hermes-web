#!/bin/bash
# hermes-web 啟動腳本
# 啟動所有必要服務：FastAPI後端 + Vite前端 + Hermes API Server + WebSocket Bridge

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_BRIDGE="$SCRIPT_DIR/ws_chat_bridge.py"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

# hermes CLI 完整路徑
HERMES_BIN="/home/fu/.local/bin/hermes"

echo "=== hermes-web 啟動腳本 ==="

# ── 1. FastAPI 後端 (port 8000) ──────────────────────────────────────
if ss -tlnp | grep -q ":8000 "; then
    echo "[OK] FastAPI 後端已在運行 (port 8000)"
else
    echo "[啟動] FastAPI 後端 (port 8000)..."
    cd "$SCRIPT_DIR"
    nohup python3 -m uvicorn main:app --reload --port 8000 --host 0.0.0.0 > "$LOG_DIR/fastapi.log" 2>&1 &
    sleep 3
    if ss -tlnp | grep -q ":8000 "; then
        echo "[OK] FastAPI 後端啟動成功 (port 8000)"
    else
        echo "[錯誤] FastAPI 後端啟動失敗"
    fi
fi

# ── 2. Vite 前端 (port 5173) ─────────────────────────────────────────
if ss -tlnp | grep -q ":5173 "; then
    echo "[OK] Vite 前端已在運行 (port 5173)"
else
    echo "[啟動] Vite 前端 (port 5173)..."
    cd "$SCRIPT_DIR/frontend"
    nohup npm run dev > "$LOG_DIR/vite.log" 2>&1 &
    sleep 5
    if ss -tlnp | grep -q ":5173 "; then
        echo "[OK] Vite 前端啟動成功 (port 5173)"
    else
        echo "[錯誤] Vite 前端啟動失敗"
    fi
fi

# ── 3. Hermes Gateway / API Server (port 8642) ──────────────────────
if ss -tlnp | grep -q ":8642 "; then
    echo "[OK] Hermes API Server 已在運行 (port 8642)"
else
    echo "[啟動] Hermes API Server (port 8642)..."
    cd "$SCRIPT_DIR"
    setsid "$HERMES_BIN" gateway run --quiet > "$LOG_DIR/hermes.log" 2>&1 &
    # 等待啟動（最多20秒）
    for i in $(seq 1 20); do
        if ss -tlnp | grep -q ":8642 "; then
            echo "[OK] Hermes API Server 啟動成功 (port 8642)"
            break
        fi
        sleep 1
    done
    if ! ss -tlnp | grep -q ":8642 "; then
        echo "[錯誤] Hermes API Server 啟動失敗"
    fi
fi

# ── 4. WebSocket Chat Bridge (port 8767) ────────────────────────────
if ss -tlnp | grep -q ":8767 "; then
    echo "[OK] ws_chat_bridge 已在運行 (port 8767)"
else
    echo "[啟動] ws_chat_bridge (port 8767)..."
    cd "$SCRIPT_DIR"
    nohup python3 "$WS_BRIDGE" > "$LOG_DIR/ws_bridge.log" 2>&1 &
    sleep 2
    if ss -tlnp | grep -q ":8767 "; then
        echo "[OK] ws_chat_bridge 啟動成功 (port 8767)"
    else
        echo "[錯誤] ws_chat_bridge 啟動失敗"
    fi
fi

# ── 驗證狀態 ────────────────────────────────────────────────────────
echo ""
echo "=== 服務狀態 ==="
for port in 8000 5173 8642 8767; do
    if ss -tlnp | grep -q ":$port "; then
        echo "  port $port  ✅"
    else
        echo "  port $port  ❌"
    fi
done

echo ""
echo "啟動完成！"
echo "  前端: http://localhost:5173"
echo "  API Server: http://localhost:8642"
echo "  ws_chat_bridge: ws://localhost:8767"
echo "  日誌目錄: $LOG_DIR"