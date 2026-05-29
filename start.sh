#!/bin/bash
# hermes-web 一鍵啟動腳本

echo "=== Hermes Web 啟動腳本 ==="
echo ""

# 清理現有服務
echo "[1/3] 清理現有服務..."
pkill -f "uvicorn" 2>/dev/null
pkill -f "hermes" 2>/dev/null
sleep 1

# 啟動 Hermes API Server
echo "[2/3] 啟動 Hermes API Server (port 8642)..."
hermes run &
sleep 2

# 啟動 hermes-web Backend
echo "[3/3] 啟動 Backend (port 8000)..."
(cd /mnt/c/Users/user/Desktop/hermes-web/backend && python3 -m uvicorn main:app --reload --port 8000 --host 0.0.0.0) &
sleep 2

# 啟動 hermes-web Frontend
cd /mnt/c/Users/user/Desktop/hermes-web/frontend
nohup npm run dev > /tmp/hermes-web-frontend.log 2>&1 &
sleep 3

# 驗證
echo ""
echo "=== 驗證服務狀態 ==="
echo -n "Hermes API (8642): "
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8642/health

echo -n "Backend (8000):     "
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000

echo -n "Frontend (5173):    "
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173

echo ""
echo "=== 啟動完成 ==="
echo "Frontend: http://localhost:5173"
echo "Backend:  http://localhost:8000"
echo "Hermes:   http://127.0.0.1:8642"