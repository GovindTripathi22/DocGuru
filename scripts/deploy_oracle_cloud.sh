#!/usr/bin/env bash
# ==============================================================================
# Oracle Cloud Always Free Tier — Automated Production Deployment Script
# Supports: Ampere A1 ARM64 (4 OCPUs, 24 GB RAM) & AMD/Intel x86 Instances
# Installs: Docker, Docker Compose, Ollama, Gemma Model, Nginx Reverse Proxy
# ==============================================================================

set -e

echo "================================================================="
echo "  Deploying Exact Template Inheritance Engine on Oracle Cloud"
echo "================================================================="

# 1. Update System Packages
echo ">> Step 1/6: Updating operating system packages..."
sudo apt-get update -y && sudo apt-get upgrade -y
sudo apt-get install -y curl wget git build-essential ufw nginx jq

# 2. Install Docker & Docker Compose
echo ">> Step 2/6: Installing Docker and Docker Compose..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
fi

# 3. Install Ollama (Native ARM64 / x86_64)
echo ">> Step 3/6: Installing Ollama LLM Runtime..."
if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
fi

# Enable and start Ollama service
sudo systemctl enable ollama
sudo systemctl start ollama
sleep 3

# 4. Pull Gemma Model tailored for Oracle 24GB RAM
echo ">> Step 4/6: Downloading Gemma Model into Ollama..."
# Oracle Always Free Ampere gives 24 GB RAM — can run gemma:2b, gemma4:e4b, or gemma4:12b comfortably!
ollama pull gemma2:2b

# 5. Configure Environment
echo ">> Step 5/6: Configuring production environment..."
cat << 'EOF' > .env
MODEL_PROVIDER=ollama
MODEL_NAME=gemma2:2b
MODEL_ENDPOINT=http://127.0.0.1:11434
TEMPERATURE=0.2
MAX_TOKENS=8192
BACKEND_URL=http://127.0.0.1:8000
EOF

# 6. Build and Start Backend & Frontend
echo ">> Step 6/6: Starting Production Containers with Docker Compose..."
docker compose down || true
docker compose up -d --build

# 7. Configure Nginx Reverse Proxy
echo ">> Configuring Nginx Reverse Proxy (Port 80 -> Next.js Frontend)..."
cat << 'EOF' | sudo tee /etc/nginx/sites-available/exact-template-app
server {
    listen 80;
    server_name _;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /api/backend/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/exact-template-app /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# 8. Firewall Configuration (Open Port 80 & 443 in Oracle iptables)
echo ">> Opening Oracle Cloud Firewall Ports..."
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save || true

PUBLIC_IP=$(curl -s ifconfig.me || echo "your-server-ip")

echo "================================================================="
echo "  DEPLOYMENT COMPLETE!"
echo "  Access your live application at: http://$PUBLIC_IP"
echo "================================================================="
