#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
DOMAIN=""
TLS_EMAIL=""
while (($#)); do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --domain) DOMAIN="${2:-}"; shift 2 ;;
        --email) TLS_EMAIL="${2:-}"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! "$DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]]; then
    echo "Provide a DNS name with --domain (letters, digits, dots, and hyphens only)." >&2
    exit 2
fi
if [[ ! "$TLS_EMAIL" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]; then
    echo "Provide a valid contact address with --email for certificate renewal." >&2
    exit 2
fi

env_file="$ROOT_DIR/.env"
if [[ -f "$env_file" ]]; then
    echo "Existing .env found; preserving it."
else
    echo "No .env found; deployment will create it from .env.example."
    if [[ "$DRY_RUN" == false ]]; then
        cp "$ROOT_DIR/.env.example" "$env_file"
    fi
fi

env_source="$env_file"
if [[ ! -f "$env_source" ]]; then
    env_source="$ROOT_DIR/.env.example"
fi
read_env() {
    local name="$1"
    local value
    value="$(awk -F= -v key="$name" '$1 == key { sub(/^[^=]*=/, ""); print; exit }' "$env_source" | tr -d '\r')"
    if [[ -z "$value" && "$env_source" != "$ROOT_DIR/.env.example" ]]; then
        value="$(awk -F= -v key="$name" '$1 == key { sub(/^[^=]*=/, ""); print; exit }' "$ROOT_DIR/.env.example" | tr -d '\r')"
    fi
    printf '%s' "$value"
}

MODEL_PROVIDER="$(read_env MODEL_PROVIDER)"
MAX_UPLOAD_MB="$(read_env MAX_UPLOAD_MB)"
API_KEYS="$(read_env API_KEYS)"
BACKEND_API_KEY="$(read_env BACKEND_API_KEY)"
SESSION_SECRET="$(read_env SESSION_SECRET)"
GEMINI_API_KEY="$(read_env GEMINI_API_KEY)"

production_configured=true
if [[ ${#SESSION_SECRET} -lt 32 || "$SESSION_SECRET" == *replace-with* ]]; then
    production_configured=false
fi
if [[ -z "$BACKEND_API_KEY" || "$BACKEND_API_KEY" == *,* ]]; then
    production_configured=false
elif [[ ",$API_KEYS," != *",${BACKEND_API_KEY},"* ]]; then
    production_configured=false
fi
if [[ "$MODEL_PROVIDER" == "google_ai" && ( -z "$GEMINI_API_KEY" || "$GEMINI_API_KEY" == your_* ) ]]; then
    production_configured=false
fi
if [[ ! "$MAX_UPLOAD_MB" =~ ^[1-9][0-9]*$ ]]; then
    echo "MAX_UPLOAD_MB must be a positive integer in .env." >&2
    exit 2
fi

if [[ "$DRY_RUN" == true ]]; then
    echo "DRY RUN: configure Nginx for $DOMAIN, request HTTPS with Certbot, and proxy only to 127.0.0.1:3000."
    echo "DRY RUN: build and start the Compose services; backend stays on the private Compose network."
    echo "DRY RUN: configure UFW for SSH, HTTP, and HTTPS; retain the existing .env unchanged."
    if [[ "$production_configured" != true ]]; then
        echo "DRY RUN CHECK: production secrets/API_KEYS need attention before deployment."
    else
        echo "DRY RUN CHECK: required production secrets are present."
    fi
    echo "Check Oracle Cloud security lists too. Docker-published ports can bypass UFW; the frontend is bound to loopback only."
    exit 0
fi

if [[ "$production_configured" != true ]]; then
    echo "Refusing production deployment: set SESSION_SECRET, matching BACKEND_API_KEY/API_KEYS, and any selected provider key in .env." >&2
    exit 1
fi
if [[ ! -f "$env_file" ]]; then
    echo "Could not create .env from .env.example." >&2
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive
if ! command -v docker >/dev/null 2>&1; then
    echo "Docker Engine and the Compose plugin must be installed before deployment." >&2
    exit 1
fi
if docker info >/dev/null 2>&1; then
    DOCKER=(docker)
else
    DOCKER=(sudo docker)
fi
"${DOCKER[@]}" compose version >/dev/null
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx curl jq
"${DOCKER[@]}" compose config -q

sudo tee /etc/nginx/sites-available/docguru >/dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size ${MAX_UPLOAD_MB}M;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

sudo ln -sfn /etc/nginx/sites-available/docguru /etc/nginx/sites-enabled/docguru
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx || sudo systemctl start nginx
sudo ufw default deny incoming
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

"${DOCKER[@]}" compose up -d --build
sudo certbot --nginx --non-interactive --agree-tos --redirect -m "$TLS_EMAIL" -d "$DOMAIN"

ready=false
for attempt in {1..30}; do
    health="$(curl -fsS http://127.0.0.1:3000/api/health || true)"
    if [[ "$(jq -r '.ready // false' <<<"$health")" == true ]]; then
        ready=true
        mode="$(jq -r '.mode // "unknown"' <<<"$health")"
        break
    fi
    sleep 2
done
if [[ "$ready" != true ]]; then
    echo "The frontend/backend did not become ready. Check docker compose logs." >&2
    exit 1
fi

echo "DocGuru is ready in $mode mode at https://$DOMAIN."
echo "Check Oracle Cloud security lists too. Docker-published ports can bypass UFW; only loopback port 3000 is published."
