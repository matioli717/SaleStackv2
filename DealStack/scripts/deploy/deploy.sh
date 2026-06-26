#!/bin/bash
# Deploy Sales Prospecting Dashboard to VPS
# Usage: ./deploy.sh user@server [domain]

set -e

SERVER=$1
DOMAIN=$2

if [ -z "$SERVER" ]; then
    echo "Usage: ./deploy.sh user@server [domain]"
    exit 1
fi

echo "=== Building deployment package ==="
cd /workspaces/OpnCld
tar -czf /tmp/sales-dashboard.tar.gz \
    sales-prospecting/server.py \
    sales-prospecting/dashboard.html \
    sales-prospecting/.env \
    sales-prospecting/scripts/ \
    requirements.txt

echo "=== Copying to server ==="
scp /tmp/sales-dashboard.tar.gz $SERVER:/tmp/

echo "=== Deploying on server ==="
ssh $SERVER << 'REMOTE_EOF'
set -e

# Install dependencies
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip nginx certbot python3-certbot-nginx

# Create app directory
sudo mkdir -p /opt/sales-dashboard
cd /opt/sales-dashboard

# Extract
sudo tar -xzf /tmp/sales-dashboard.tar.gz

# Create venv
python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt

# Create .env if not exists
if [ ! -f sales-prospecting/.env ]; then
    cp sales-prospecting/.env.example sales-prospecting/.env 2>/dev/null || cat > sales-prospecting/.env << 'ENV_EOF'
API_KEYS="[{\"key\": \"sk_dev_$(openssl rand -base64 32 | tr -d '=+/'), \"name\": \"production\", \"scopes\": [\"read\", \"write\"]}]"
ALLOWED_ORIGINS="https://yourdomain.com,http://localhost:8765,http://127.0.0.1:8765"
RATE_LIMIT_PER_MIN=60
SHARED_DATA_DIR="/opt/sales-dashboard/shared_data"
TLS_CERT=""
TLS_KEY=""
MAX_PAYLOAD_SIZE=1048576
SUBPROCESS_TIMEOUT=60
ENV_EOF
fi

# Create shared data dir
mkdir -p shared_data

# Create systemd service
sudo tee /etc/systemd/system/sales-dashboard.service > /dev/null << 'SERVICE_EOF'
[Unit]
Description=Sales Prospecting Dashboard
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/sales-dashboard
Environment=PATH=/opt/sales-dashboard/venv/bin
ExecStart=/opt/sales-dashboard/venv/bin/python sales-prospecting/server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/sales-dashboard/shared_data

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Create nginx config
if [ -n "$DOMAIN" ]; then
    sudo tee /etc/nginx/sites-available/sales-dashboard > /dev/null << NGINX_EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }

    # WebSocket support if needed
    location /ws {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
    }
}
NGINX_EOF

    sudo ln -sf /etc/nginx/sites-available/sales-dashboard /etc/nginx/sites-enabled/
    sudo nginx -t && sudo systemctl reload nginx
fi

# Start service
sudo systemctl daemon-reload
sudo systemctl enable sales-dashboard
sudo systemctl restart sales-dashboard

echo "=== Deployment complete! ==="
echo "Service status: sudo systemctl status sales-dashboard"
echo "Logs: sudo journalctl -u sales-dashboard -f"
if [ -n "$DOMAIN" ]; then
    echo "Site: http://$DOMAIN"
    echo "To enable HTTPS: sudo certbot --nginx -d $DOMAIN"
fi
REMOTE_EOF
