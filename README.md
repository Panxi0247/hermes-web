# Hermes Web

## Docker

Copy `.env.example` to `.env` if you need to change the Hermes agent host, port, or API key.

```bash
docker compose up --build
```

Open:

```text
http://localhost:8080
```

The frontend container serves the React app and proxies `/api`, `/v1`, `/health`, and `/ws` to the backend container. By default the backend connects to Hermes on the host machine through `host.docker.internal:8642`.

本地端 Hermes 聊天介面，前後端分離架構。

## 架構

```
Browser (React)     →  localhost:5173
                           ↓ HTTP
FastAPI Backend  →  localhost:8000
                           ↓ HTTP
Hermes Agent   →  127.0.0.1:8642
```

## 啟動方式

### 前端
```bash
cd frontend
npm install
npm run dev      # 啟動在 http://localhost:5173
```

### 後端
```bash
cd backend
pip install -r requirements.txt
python main.py   # 啟動在 http://localhost:8000
```

## 功能

- **聊天** - 串流回應，支援對話歷史
- **終端機** - WebSocket 即時通訊，白名單指令：`echo`, `date`, `pwd`, `ls`, `whoami`
- **CLI 按鈕** - 快速執行白名單指令

## 開發

- 前端修改：`frontend/src/`（React + TypeScript）
- 後端修改：`backend/main.py`（FastAPI）
- VSCode 建議安裝：ESLint, Prettier, Python, Pylance

## API 端點

| 方法 | 路徑 | 說明 |
|------|------|------|
| POST | `/v1/chat/completions` | OpenAI-compatible 聊天 API |
| WS | `/ws/terminal` | 終端機 WebSocket |
| POST | `/api/cli` | 白名單 CLI 執行 |
| GET | `/health` | 健康檢查 |

## 安全

- Shell 指令僅支援白名單（無任意指令執行）
- CORS 僅允許前端開發伺服器
- WebSocket 自動重連
