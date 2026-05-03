#!/bin/bash
set -e

echo "=== FM Monitor Docker ==="

# Générer .env si absent
if [ ! -f /app/.env ]; then
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "SECRET_KEY=$SECRET_KEY" > /app/.env
    echo "FLASK_ENV=production" >> /app/.env
    echo "[i] .env généré"
fi

# Générer config.json si absent
if [ ! -f /app/config.json ]; then
    cp /app/config.example.json /app/config.json
    echo "[i] config.json créé depuis l'exemple"
fi

# Démarrer Icecast2
mkdir -p /run/icecast2
chown -R icecast2:icecast /run/icecast2 2>/dev/null || true
icecast2 -b -c /etc/icecast2/icecast.xml
echo "[i] Icecast2 démarré"
sleep 2

# Démarrer FM Monitor
echo "[i] Démarrage FM Monitor sur :5000..."
exec /app/venv/bin/python3 /app/app.py
