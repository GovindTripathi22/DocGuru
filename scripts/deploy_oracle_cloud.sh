#!/usr/bin/env bash
# ==============================================================================
# DocGuru — Automated Production Deployment Script
# Supports: Ampere A1 ARM64 (4 OCPUs, 24 GB RAM) & AMD/Intel x86 Instances
# Installs: Docker, Docker Compose, Nginx Reverse Proxy
# ==============================================================================

set -euo pipefail

DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
    esac
done

echo "================================================================="
echo "  DocGuru Deployment Script"
if [ "$DRY_RUN" = true ]; then
    echo "  MODE: DRY RUN (no modifications will be applied)"
fi
echo "================================================================="

# 1. Update System Packages
echo ">> Step 1/6: Ensuring system packages are installed..."
if [ "$DRY_RUN" = false ]; then
    export DEBIAN_FRONTEND=noninteractive
    sudo apt-get update -y
    sudo apt-get install -y curl wget git build-essential ufw nginx jq
fi

# 2. Install Docker & Docker Compose
echo ">> Step 2/6: Checking Docker and Docker Compose..."
if [ "$DRY_RUN" = false ]; then
    if ! command -v docker &> /dev/null; then
        curl -fsSL https://get.docker.com | sh
    fi
fi

# 3. Environment Configuration
echo ">> Step 3/6: Checking environment configuration (.env)..."
if [ -f .env ]; then
    echo "Existing .env found; preserving without modification."
else
    echo "No .env found; copying from .env.example..."
    if [ "$DRY_RUN" = false ]; then
        cp .env.example .env
        echo "Created .env from .env.example. Please review credentials before production use."
    fi
fi

# 4. Build and Start Production Containers
echo ">> Step 4/6: Deploying containers with Docker Compose..."
if [ "$DRY_RUN" = false ]; then
    docker compose down || true
    docker compose up -d --build
fi

# 5. Configure Nginx Reverse Proxy (Frontend only on Port 80)
echo ">> Step 5/6: Configuring Nginx Reverse Proxy (Port 80 -> Frontend)..."
if [ "$DRY_RUN" = false ]; then
    cat << 'EOF' | sudo tee /etc/nginx/sites-available/docguru
server {
    listen 80;
    server_name _;

    client_max_body_size 25M;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;

    # Only Next.js frontend is exposed to the public
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
}
EOF

    sudo ln -sf /etc/nginx/sites-available/docguru /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo nginx -t && sudo systemctl reload nginx
fi

# 6. Firewall Configuration
echo ">> Step 6/6: Verifying firewall rules..."
if [ "$DRY_RUN" = false ]; then
    if command -v ufw &> /dev/null; then
        sudo ufw default deny incoming || true
        sudo ufw allow 22/tcp || true
        sudo ufw allow 80/tcp || true
        sudo ufw allow 443/tcp || true
        sudo ufw --force enable || true
    fi
fi

echo "================================================================="
echo "  DEPLOYMENT COMPLETE!"
echo "================================================================="
