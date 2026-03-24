#!/bin/bash
set -euo pipefail
exec > >(tee /var/log/finman-startup.log) 2>&1

echo "[finman] === Starting VM setup ==="

# ── Swap (e2-micro has 1 GB RAM — swap prevents OOM kills) ───────────────────
if [ ! -f /swapfile ]; then
  fallocate -l 1G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo "[finman] Swap created."
fi

# ── System packages ───────────────────────────────────────────────────────────
apt-get update -y
apt-get install -y git curl python3 python3-venv

# ── Install uv ────────────────────────────────────────────────────────────────
curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh
echo "[finman] uv installed: $(uv --version)"

# ── App user ──────────────────────────────────────────────────────────────────
useradd -r -s /bin/bash -m -d /home/finman finman 2>/dev/null || true

# ── Clone repository ──────────────────────────────────────────────────────────
APP_DIR=/opt/finman

if [ -n "${repo_url}" ]; then
  echo "[finman] Cloning ${repo_url} ..."
  git clone "${repo_url}" "$$APP_DIR"
  chown -R finman:finman "$$APP_DIR"
  echo "[finman] Clone complete."
else
  mkdir -p "$$APP_DIR"
  chown -R finman:finman "$$APP_DIR"
  echo "[finman] No repo_url set — deploy app files manually:"
  echo "         gcloud compute scp --recurse ./agent <instance-name>:/opt/finman/"
fi

# ── Write .env ────────────────────────────────────────────────────────────────
cat > /opt/finman/.env << 'ENVEOF'
OPENAI_API_KEY=${openai_api_key}
SUPABASE_URL=${supabase_url}
SUPABASE_PUBLISHABLE_KEY=${supabase_publishable_key}
SUPABASE_SECRET_KEY=${supabase_secret_key}
SUPABASE_DB_URL=${supabase_db_url}
ENVEOF

chmod 600 /opt/finman/.env
chown finman:finman /opt/finman/.env
echo "[finman] .env written."

# ── Install Python dependencies ───────────────────────────────────────────────
if [ -f "$$APP_DIR/agent/pyproject.toml" ]; then
  echo "[finman] Installing Python dependencies..."
  cd "$$APP_DIR/agent"
  sudo -u finman uv sync
  echo "[finman] Dependencies installed."
fi

# ── Systemd service ───────────────────────────────────────────────────────────
cat > /etc/systemd/system/finman.service << 'SVCEOF'
[Unit]
Description=FINMAN Data Agent (Streamlit)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=finman
WorkingDirectory=/opt/finman/agent
ExecStart=/opt/finman/agent/.venv/bin/streamlit run main.py --server.port=${app_port} --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false
Restart=on-failure
RestartSec=10
EnvironmentFile=/opt/finman/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable finman

if [ -f "/opt/finman/agent/main.py" ]; then
  systemctl start finman
  echo "[finman] Service started."
else
  echo "[finman] main.py not found — service enabled but not started."
  echo "[finman] After deploying app files run: sudo systemctl start finman"
fi

echo "[finman] === Setup complete ==="
