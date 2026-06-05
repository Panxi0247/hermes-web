#!/bin/bash
# hermes-web 部署腳本
# 用途：將 hermes-web 部署到 Ubuntu 伺服器

set -e

# ── 設定 ──────────────────────────────────────────────────────────────
DOMAIN="${DOMAIN:-your-domain.com}"
HERMES_USER="${HERMES_USER:-$(whoami)}"
HERMES_HOME="/home/$HERMES_USER/hermes-web"
HERMES_BIN="/home/$HERMES_USER/.local/bin/hermes"

# 顏色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── 檢查 root ────────────────────────────────────────────────────────
if [[ $EUID -eq 0 ]]; then
    warn "不建議用 root 執行此腳本，以下範例假設 HERMES_USER 是非 root 用戶"
fi

# ── 1. 安裝系統依賴 ──────────────────────────────────────────────────
log "更新系統並安裝軟體..."
sudo apt update
sudo apt install -y \
    python3 python3-venv python3-pip git curl ufw \
    nginx certbot \
    build-essential libssl-dev libffi-dev

# ── 2. 安裝 Node.js（nvm） ───────────────────────────────────────────
if ! command -v node &> /dev/null; then
    log "安裝 nvm 和 Node.js..."
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm install 20
    nvm use 20
    nvm alias default 20
fi

# ── 3. Clone 或更新專案 ───────────────────────────────────────────────
if [[ -d "$HERMES_HOME/.git" ]]; then
    log "更新現有 hermes-web..."
    cd "$HERMES_HOME"
    git pull origin main
else
    log "Clone hermes-web..."
    git clone https://github.com/Panxi0247/hermes-web.git "$HERMES_HOME"
    cd "$HERMES_HOME"
fi

# ── 4. 安裝 Python 依賴 ──────────────────────────────────────────────
log "安裝 Python 依賴..."
cd "$HERMES_HOME/backend"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# ws_chat_bridge 額外依賴
pip install websockets httpx beautifulsoup4 requests

deactivate

# ── 5. 安裝 Node 依賴 ────────────────────────────────────────────────
log "安裝 Node 依賴..."
cd "$HERMES_HOME/frontend"
npm install

# ── 6. 複製並編輯 .env ────────────────────────────────────────────────
ENV_FILE="$HERMES_HOME/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    warn ".env 不存在，建立預設檔案（請編輯填入你的設定）..."
    cat > "$ENV_FILE" <<'EOF'
# Frontend 公開 URL（Vite 會用這個前綴 WebSocket URL）
VITE_WS_URL=/ws

# Server IP / Domain
SERVER_IP=127.0.0.1

# Hermes API（通常不需修改）
HERMES_HOST=127.0.0.1
HERMES_PORT=8642
EOF
    warn "請編輯 $ENV_FILE 填入正確的 DOMAIN 和 SERVER_IP"
fi

# ── 7. 建立 logs 目錄 ─────────────────────────────────────────────────
mkdir -p "$HERMES_HOME/logs"

# ── 8. 設定 Nginx ───────────────────────────────────────────────────
log "設定 Nginx 反向代理..."
NGINX_SITE="/etc/nginx/sites-available/hermes-web"
sudo tee "$NGINX_SITE" > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    root $HERMES_HOME/frontend/dist;
    index index.html;

    # 前端 static build（或 Vite dev proxy）
    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        # Vite HMR
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    location /v1/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
    }

    # WebSocket 代理
    location /ws/ {
        proxy_pass http://127.0.0.1:8767;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_read_timeout 86400;
    }
}
EOF

sudo ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/hermes-web
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
log "Nginx 設定完成"

# ── 9. SSL 憑證（選擇性，production 需要） ────────────────────────────
if [[ "${ENABLE_SSL:-false}" == "true" ]]; then
    log "申請 Let's Encrypt SSL 憑證..."
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN"
fi

# ── 10. 防火牆設定 ───────────────────────────────────────────────────
log "設定防火牆..."
sudo ufw --force enable
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw deny 8642/tcp  # Hermes API 僅供內部
sudo ufw reload
log "防火牆設定完成（只開放 22/80/443，8642 已阻擋）"

# ── 11. 建立 systemd 服務 ───────────────────────────────────────────
log "建立 systemd 服務..."
sudo tee /etc/systemd/system/hermes-web.service > /dev/null <<EOF
[Unit]
Description=hermes-web All Services
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=$HERMES_USER
WorkingDirectory=$HERMES_HOME
ExecStart=$HERMES_HOME/start.sh
ExecStop=/bin/bash -c 'pkill -f "uvicorn\|vite\|ws_chat_bridge\|hermes gateway"' || true
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# Hermes Gateway 单独服務（常駐）
sudo tee /etc/systemd/system/hermes-gateway.service > /dev/null <<EOF
[Unit]
Description=Hermes Gateway API
After=network.target

[Service]
Type=simple
User=$HERMES_USER
WorkingDirectory=$HERMES_HOME
ExecStart=$HERMES_BIN gateway run --quiet
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable hermes-web.service
sudo systemctl enable hermes-gateway.service

# ── 12. 啟動所有服務 ─────────────────────────────────────────────────
log "啟動所有服務..."
bash "$HERMES_HOME/start.sh"

# ── 完成 ─────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo -e "${GREEN}部署完成！${NC}"
echo "=========================================="
echo "  URL:        http://$DOMAIN"
echo "  目錄:       $HERMES_HOME"
echo "  日誌:       $HERMES_HOME/logs/"
echo "  Systemd:    sudo systemctl status hermes-web"
echo ""
echo "常用指令："
echo "  重啟所有服務:  sudo systemctl restart hermes-web"
echo "  查看日誌:      tail -f $HERMES_HOME/logs/*.log"
echo "  停止服務:      sudo systemctl stop hermes-web"
echo ""