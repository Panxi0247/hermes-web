#!/bin/bash
# hermes-web 啟動腳本
# 啟動所有必要服務：FastAPI後端 + Vite前端 + Hermes API Server + WebSocket Bridge
#
# 部署約束：
#   - FastAPI/Vite/ws_bridge 綁定 0.0.0.0（對外暴露）
#   - Hermes API (8642) 僅供內部呼叫，依賴 UFW 防火牆阻擋外部訪問
#   - 所有 URL 不可寫死 localhost，需讀取環境變數動態取得伺服器 IP
#
# 環境變數（從 .env 讀取）：
#   SERVER_IP         伺服器 IP（Vite/FastAPI/ws_bridge 對外 URL 使用）
#   HERMES_HOST       Hermes API 主機（預設 127.0.0.1）
#   HERMES_PORT       Hermes API port（預設 8642）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_BRIDGE="$SCRIPT_DIR/ws_chat_bridge.py"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

# hermes CLI 完整路徑
HERMES_BIN="/home/fu/.local/bin/hermes"

# ── 載入 .env 環境變數 ────────────────────────────────────────────────
ENV_FILE="$SCRIPT_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
    set -a
    source "$ENV_FILE"
    set +a
    echo "[ENV] 載入 $ENV_FILE"
else
    echo "[WARN] $ENV_FILE 不存在，使用預設值"
fi

# 預設值
SERVER_IP="${SERVER_IP:-127.0.0.1}"
HERMES_HOST="${HERMES_HOST:-127.0.0.1}"
HERMES_PORT="${HERMES_PORT:-8642}"

echo "=== hermes-web 啟動腳本 ==="
echo "[CONFIG] SERVER_IP=$SERVER_IP  HERMES_HOST=$HERMES_HOST  HERMES_PORT=$HERMES_PORT"

# ── 1. FastAPI 後端 (port 8000) ──────────────────────────────────────
if ss -tlnp | grep -q ":8000 "; then
    echo "[OK] FastAPI 後端已在運行 (port 8000)"
else
    echo "[啟動] FastAPI 後端 (port 8000)..."
    cd "$SCRIPT_DIR/backend"
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
echo "  前端:    http://$SERVER_IP:5173"
echo "  API:     http://$SERVER_IP:8000"
echo "  ws_bridge: ws://$SERVER_IP:8767"
echo "  Hermes:  http://$HERMES_HOST:$HERMES_PORT (僅限內部)"
echo "  日誌目錄: $LOG_DIR"
echo ""
echo "【重要】請確認 UFW 防火牆已設定："
echo "  sudo ufw allow 5173/tcp  # Vite 前端"
echo "  sudo ufw allow 8000/tcp   # FastAPI 後端"
echo "  sudo ufw allow 8767/tcp   # WebSocket Bridge"
echo "  sudo ufw deny  8642/tcp   # Hermes API（必須禁止對外）"