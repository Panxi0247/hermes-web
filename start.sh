#!/bin/bash
# hermes-web 一鍵啟動腳本（供期中報告展示用）
# 終端機颜色
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_DIR="$ROOT_DIR/backend"

wait_for() {
  local host=$1; local port=$2; local name=$3
  printf "  等待 %s " "$name"
  while ! nc -z "$host" "$port" 2>/dev/null; do sleep 0.5; printf "."; done
  echo -e " ${GREEN}✓${NC}"
}

echo -e "\n${YELLOW}═══ hermes-web 啟動中 ═══${NC}\n"

# 1. 啟動 Hermes API（背景）
echo -e "${GREEN}[1/3]${NC} Hermes API (port 8642)"
cd "$ROOT_DIR"
# 若有 hermes 執行檔則啟動，否則略過
if command -v hermes &>/dev/null; then
  hermes gateway run -q &>/dev/null &
  wait_for 127.0.0.1 8642 "Hermes API"
else
  echo -e "  ${YELLOW}⚠ Hermes API 未安裝（需另外啟動）${NC}"
fi

# 2. 啟動 FastAPI 後端（背景）
echo -e "\n${GREEN}[2/3]${NC} FastAPI Backend (port 8000)"
cd "$BACKEND_DIR"
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 &>/dev/null &
wait_for 127.0.0.1 8000 "FastAPI"

# 3. 啟動 ws_chat_bridge（背景）
echo -e "\n${GREEN}[3/3]${NC} ws_chat_bridge (port 8767)"
cd "$ROOT_DIR"
python3 ws_chat_bridge.py 8767 &>/dev/null &
wait_for 127.0.0.1 8767 "ws_chat_bridge"

# 4. 啟動 Vite 前端（前景，會佔用終端）
echo -e "\n${GREEN}[4/4]${NC} Vite Frontend (port 5173)"
cd "$FRONTEND_DIR"
echo -e "\n${YELLOW}已啟動 http://localhost:5173${NC}\n"
npm run dev